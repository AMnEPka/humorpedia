"""Durable, repeatable projections for canonical KVN seasons.

MongoDB standalone cannot atomically update a season, its page and participation
rows.  The canonical season therefore stores the projection intent and its
operation token in the same CAS write that commits the new canonical version.
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from services.competitions import (
    _LEGACY_COMPUTED_KEYS,
    _NO_EXPECTED_VERSION,
    build_participations,
    next_version,
    page_filter,
    season_to_legacy,
    version_filter,
    version_matches,
)


def public_season(season: dict) -> dict:
    """Return a season without workflow ownership or persisted projection data."""
    result = copy.deepcopy(season)
    result.pop("_write_claim", None)
    projection = result.pop("_projection", None)
    result["projection_status"] = projection.get("state") if projection else "ready"
    return result


def _free_claim(field: str) -> dict:
    return {"$or": [{field: {"$exists": False}}, {field: None}]}


def _cas_query(document: dict, *, claim_field: str | None = None) -> dict:
    query = {"_id": document["_id"], **version_filter(document)}
    if claim_field:
        query["$and"] = [_free_claim(claim_field)]
    return query


def _claim_token(document: dict) -> str | None:
    claim = document.get("_write_claim")
    return claim.get("token") if isinstance(claim, dict) else None


async def _release_season_claim(db, season_id: str, token: str) -> None:
    await db.seasons.update_one(
        {"_id": season_id, "_write_claim.token": token},
        {"$unset": {"_write_claim": ""}},
    )


async def _claim_season(db, season: dict, expected_updated_at: Any, now: str) -> tuple[dict, str, bool]:
    """Claim one canonical version; a missing season is insert-only."""
    existing = await db.seasons.find_one({"_id": season["_id"]})
    token = uuid.uuid4().hex
    new_document = existing is None
    if existing is None:
        if expected_updated_at not in (_NO_EXPECTED_VERSION, None):
            raise HTTPException(status_code=409, detail="Сезон уже изменён. Обновите страницу и повторите сохранение.")
        claimed = copy.deepcopy(season)
        claimed["created_at"] = season.get("created_at") or now
        claimed["updated_at"] = now
        claimed["_write_claim"] = {"token": token, "new_document": True}
        try:
            await db.seasons.insert_one(claimed)
        except Exception as exc:
            # A concurrent insert is a conflict. Do not mask unrelated database failures.
            if exc.__class__.__name__ not in {"DuplicateKeyError", "BulkWriteError"}:
                raise
            raise HTTPException(status_code=409, detail="Сезон уже создан. Обновите страницу и повторите сохранение.") from exc
        return claimed, token, True

    if expected_updated_at is _NO_EXPECTED_VERSION or not version_matches(existing, expected_updated_at):
        raise HTTPException(status_code=409, detail="Сезон уже изменён. Обновите страницу и повторите сохранение.")
    if (existing.get("_projection") or {}).get("state") not in (None, "ready"):
        raise HTTPException(status_code=409, detail="Проекция сезона ожидает восстановления; повторите позже.")
    result = await db.seasons.update_one(
        _cas_query(existing, claim_field="_write_claim"),
        {"$set": {"_write_claim": {"token": token, "new_document": False}}},
    )
    if result.matched_count != 1:
        raise HTTPException(status_code=409, detail="Сезон уже обрабатывается. Повторите позже.")
    claimed = copy.deepcopy(existing)
    claimed["_write_claim"] = {"token": token, "new_document": False}
    return claimed, token, False


async def _claim_page(db, page: dict, season: dict, expected_page_updated_at: Any,
                      operation_token: str) -> str:
    if (expected_page_updated_at is not _NO_EXPECTED_VERSION
            and not version_matches(page, expected_page_updated_at)):
        raise HTTPException(status_code=409, detail="Страница уже изменена. Обновите её и повторите сохранение.")
    version = next_version(page.get("updated_at"))
    result = await db.kvn.update_one(
        {"_id": page["_id"], **version_filter(page), "$and": [_free_claim("_season_write_claim")]},
        {"$set": {"_season_write_claim": {
            "season_id": season["_id"], "token": operation_token,
        }}},
    )
    if result.matched_count != 1:
        raise HTTPException(status_code=409, detail="Страница уже изменена или обрабатывается.")
    return version


def _page_projection(season: dict, projection: dict) -> dict:
    legacy = season_to_legacy(season)
    for key in _LEGACY_COMPUTED_KEYS:
        if key in projection.get("computed_page_fields", {}):
            legacy[key] = copy.deepcopy(projection["computed_page_fields"][key])
    return legacy


async def _rebuild_participations(db, season: dict, rows: list[dict]) -> None:
    ids = []
    for row in rows:
        ids.append(row["_id"])
        await db.participations.replace_one({"_id": row["_id"]}, row, upsert=True)
    await db.participations.delete_many({"season_id": season["_id"], "_id": {"$nin": ids}})


async def _project(db, season: dict, worker_token: str, people=None) -> dict:
    projection = season.get("_projection") or {}
    op_token = projection.get("operation_token")
    if not op_token:
        raise HTTPException(status_code=409, detail="Нет сохранённого задания проекции сезона.")
    await _rebuild_participations(db, season, projection.get("participation_rows") or [])

    page_id = projection.get("page_id")
    if page_id:
        page_query = {"_id": projection["page_db_id"], "_season_write_claim.season_id": season["_id"],
                      "_season_write_claim.token": op_token}
        page = await db.kvn.find_one(page_query)
        if page is None:
            raise HTTPException(status_code=409, detail="Захват страницы сезона потерян; требуется восстановление.")
        page_data = {"season_data": _page_projection(season, projection),
                     "updated_at": projection["page_updated_at"]}
        page_data.update(copy.deepcopy(projection.get("page_patch") or {}))
        page_data["updated_at"] = projection["page_updated_at"]
        result = await db.kvn.update_one(page_query, {"$set": page_data})
        if result.matched_count != 1:
            raise HTTPException(status_code=409, detail="Захват страницы сезона потерян; требуется восстановление.")

    ready = copy.deepcopy(season)
    ready_projection = copy.deepcopy(projection)
    ready_projection["state"] = "ready"
    ready["_projection"] = ready_projection
    result = await db.seasons.replace_one(
        {"_id": season["_id"], "updated_at": projection["target_version"], "_write_claim.token": worker_token},
        ready,
    )
    if result.matched_count != 1:
        raise HTTPException(status_code=409, detail="Захват сезона потерян; требуется восстановление.")
    if page_id:
        page_release = await db.kvn.update_one(
            {"_id": projection["page_db_id"], "_season_write_claim.season_id": season["_id"],
             "_season_write_claim.token": op_token},
            {"$unset": {"_season_write_claim": ""}},
        )
        if page_release.matched_count != 1:
            raise HTTPException(status_code=409, detail="Проекция готова, но claim страницы не освобождён.")
    await _release_season_claim(db, season["_id"], worker_token)
    return public_season(ready)


async def save_season_with_projection(
    db, season: dict, *, write_page: bool, people=None,
    expected_updated_at: Any = _NO_EXPECTED_VERSION,
    page_patch: dict | None = None,
    expected_page_updated_at: Any = _NO_EXPECTED_VERSION,
) -> dict:
    """CAS commit plus durable projection intent; all retries replay saved intent."""
    if people is None:
        from services.memberships import load_person_lookup

        people = await load_person_lookup(db)
    participation_rows = build_participations(season, people)
    now = next_version(expected_updated_at if expected_updated_at is not _NO_EXPECTED_VERSION else None)
    proposed = copy.deepcopy(season)
    proposed.pop("_write_claim", None)
    proposed.pop("_projection", None)
    claimed, worker_token, new_document = await _claim_season(db, proposed, expected_updated_at, now)
    page = None
    op_token = uuid.uuid4().hex
    page_version = None
    commit_attempted = False
    try:
        if write_page and proposed.get("page_collection") == "kvn" and proposed.get("page_id"):
            page = await db.kvn.find_one(page_filter(str(proposed["page_id"])))
            if page is None:
                raise HTTPException(status_code=409, detail="Страница сезона не найдена.")
            claim = {"token": worker_token, "new_document": new_document,
                     "page_db_id": page["_id"], "operation_token": op_token}
            claim_result = await db.seasons.update_one(
                {"_id": proposed["_id"], "_write_claim.token": worker_token},
                {"$set": {"_write_claim": claim}},
            )
            if claim_result.matched_count != 1:
                raise HTTPException(status_code=409, detail="Захват сезона потерян до записи страницы.")
            page_version = await _claim_page(
                db, page, proposed, expected_page_updated_at, op_token,
            )

        created_at = (claimed.get("created_at") or proposed.get("created_at") or now)
        target = copy.deepcopy(proposed)
        target["created_at"] = created_at
        target["updated_at"] = now
        target["_write_claim"] = {"token": worker_token, "new_document": new_document,
            "operation_token": op_token,
            **({"page_db_id": page["_id"]} if page else {})}
        target["_projection"] = {
            "operation_token": op_token,
            "target_version": now,
            "state": "applying",
            "page_id": str(proposed.get("page_id")) if page else None,
            "page_db_id": page["_id"] if page else None,
            "page_base_updated_at": page.get("updated_at") if page else None,
            "page_updated_at": page_version,
            "page_patch": copy.deepcopy(page_patch or {}) if page else {},
            "computed_page_fields": {
                key: copy.deepcopy((page.get("season_data") or {})[key])
                for key in _LEGACY_COMPUTED_KEYS
                if page and key in (page.get("season_data") or {})
            },
            "participation_rows": participation_rows,
        }
        query = {"_id": proposed["_id"], "_write_claim.token": worker_token,
                 **version_filter(claimed)}
        commit_attempted = True
        result = await db.seasons.replace_one(query, target)
        if result.matched_count != 1:
            commit_attempted = False  # A returned CAS miss proves no commit occurred.
            raise HTTPException(status_code=409, detail="Сезон изменён во время сохранения. Повторите.")
    except Exception:
        if not commit_attempted:
            if page is not None:
                await db.kvn.update_one(
                    {"_id": page["_id"], "_season_write_claim.season_id": proposed["_id"],
                     "_season_write_claim.token": op_token},
                    {"$unset": {"_season_write_claim": ""}},
                )
            if new_document:
                await db.seasons.delete_one({"_id": proposed["_id"], "_write_claim.token": worker_token})
            else:
                await _release_season_claim(db, proposed["_id"], worker_token)
        raise

    try:
        return await _project(db, target, worker_token, people)
    except Exception:
        failed = copy.deepcopy(target)
        failed["_projection"]["state"] = "error"
        marked = await db.seasons.replace_one(
            {"_id": proposed["_id"], "updated_at": now, "_write_claim.token": worker_token},
            failed,
        )
        if marked.matched_count != 1:
            raise HTTPException(status_code=409, detail="Не удалось сохранить ошибку проекции; claim оставлен для восстановления.")
        await _release_season_claim(db, proposed["_id"], worker_token)
        return public_season(failed)


async def retry_season_projection(db, season_id: str, expected_updated_at: Any, *, people=None) -> dict:
    """Resume the stored projection snapshot; this never increments content version."""
    season = await db.seasons.find_one({"_id": season_id})
    if (season is None or not version_matches(season, expected_updated_at)
            or not season.get("_projection")):
        raise HTTPException(status_code=409, detail="Версия или задание проекции сезона изменены.")
    if season["_projection"].get("state") == "ready" and not season.get("_write_claim"):
        return public_season(season)
    token = uuid.uuid4().hex
    result = await db.seasons.update_one(
        {"_id": season_id, **version_filter(season), "_projection.state": {"$in": ["error", "applying", "ready"]},
         "$and": [_free_claim("_write_claim")]},
        {"$set": {"_write_claim": {"token": token, "new_document": False,
                                      "operation_token": season["_projection"]["operation_token"]}}},
    )
    if result.matched_count != 1:
        raise HTTPException(status_code=409, detail="Сезон уже обрабатывается; takeover не выполняется.")
    prior_state = season["_projection"].get("state")
    season["_write_claim"] = {"token": token, "new_document": False,
                              "operation_token": season["_projection"]["operation_token"]}
    try:
        projection = copy.deepcopy(season["_projection"])
        if projection.get("page_id"):
            page = await db.kvn.find_one({"_id": projection["page_db_id"]})
            if page is None:
                raise HTTPException(status_code=409, detail="Страница сезона не найдена.")
            page_claim_value = page.get("_season_write_claim") or {}
            if page_claim_value.get("season_id") != season_id or page_claim_value.get("token") != projection["operation_token"]:
                if page_claim_value:
                    raise HTTPException(status_code=409, detail="Страница уже обрабатывается.")
                resumed_from = projection.pop("recovery_from_state", prior_state)
                if resumed_from == "ready":
                    # A completed operation's patch must not overwrite later manual page edits.
                    projection["page_patch"] = {}
                page_base = page.get("updated_at")
                if not version_matches({"updated_at": page_base}, projection.get("page_base_updated_at")):
                    projection["page_base_updated_at"] = page_base
                    projection["page_updated_at"] = next_version(page_base)
                    projection["computed_page_fields"] = {
                        key: copy.deepcopy((page.get("season_data") or {})[key])
                        for key in _LEGACY_COMPUTED_KEYS if key in (page.get("season_data") or {})
                    }
                season["_projection"] = projection
                # Persist the exact page projection before claiming the page. If the
                # worker dies after the following CAS, recovery can replay this snapshot.
                update_result = await db.seasons.update_one(
                    {"_id": season_id, "updated_at": season["updated_at"], "_write_claim.token": token},
                    {"$set": {"_projection": projection}},
                )
                if update_result.matched_count != 1:
                    raise HTTPException(status_code=409, detail="Захват сезона потерян; требуется восстановление.")
                page_result = await db.kvn.update_one(
                    {"_id": page["_id"], **version_filter(page), "$and": [_free_claim("_season_write_claim")]},
                    {"$set": {"_season_write_claim": {"season_id": season_id,
                                                         "token": projection["operation_token"]}}},
                )
                if page_result.matched_count != 1:
                    raise HTTPException(status_code=409, detail="Страница уже изменена или обрабатывается.")
        return await _project(db, season, token, people)
    except Exception:
        failed = copy.deepcopy(season)
        failed["_projection"]["state"] = "error"
        marked = await db.seasons.replace_one(
            {"_id": season_id, "updated_at": season["updated_at"], "_write_claim.token": token}, failed,
        )
        if marked.matched_count != 1:
            raise HTTPException(status_code=409, detail="Не удалось сохранить ошибку проекции; claim оставлен для восстановления.")
        await _release_season_claim(db, season_id, token)
        return public_season(failed)


async def rebuild_season_projection(db, season: dict, *, people=None) -> dict:
    """Rebuild derived rows/page from a canonical document without changing its version."""
    if (season.get("_projection") or {}).get("state") not in (None, "ready"):
        raise HTTPException(status_code=409, detail="Проекция сезона ожидает восстановления; сначала выполните retry.")
    if people is None:
        from services.memberships import load_person_lookup

        people = await load_person_lookup(db)
    participation_rows = build_participations(season, people)
    token = uuid.uuid4().hex
    op_token = uuid.uuid4().hex
    result = await db.seasons.update_one(
        {"_id": season["_id"], **version_filter(season), "$and": [_free_claim("_write_claim")]},
        {"$set": {"_write_claim": {"token": token, "new_document": False}}},
    )
    if result.matched_count != 1:
        raise HTTPException(status_code=409, detail="Сезон уже обрабатывается.")
    current = copy.deepcopy(season)
    current["_write_claim"] = {"token": token, "new_document": False}
    page = None
    page_version = None
    committed_snapshot = False
    try:
        if current.get("page_collection") == "kvn" and current.get("page_id"):
            page = await db.kvn.find_one(page_filter(str(current["page_id"])))
            if page is None:
                raise HTTPException(status_code=409, detail="Страница сезона не найдена.")
            claim_update = await db.seasons.update_one(
                {"_id": current["_id"], "_write_claim.token": token},
                {"$set": {"_write_claim": {"token": token, "new_document": False,
                                              "page_db_id": page["_id"], "operation_token": op_token}}},
            )
            if claim_update.matched_count != 1:
                raise HTTPException(status_code=409, detail="Захват сезона потерян до записи страницы.")
            current["_write_claim"] = {"token": token, "new_document": False,
                                       "page_db_id": page["_id"], "operation_token": op_token}
            op_page_claim = {"_id": page["_id"], **version_filter(page),
                             "$and": [_free_claim("_season_write_claim")]}
            page_version = next_version(page.get("updated_at"))
            page_result = await db.kvn.update_one(
                op_page_claim,
                {"$set": {"_season_write_claim": {"season_id": current["_id"], "token": op_token}}},
            )
            if page_result.matched_count != 1:
                raise HTTPException(status_code=409, detail="Страница уже изменена или обрабатывается.")
        projection = {
            "operation_token": op_token,
            "target_version": current.get("updated_at"),
            "state": "applying",
            "page_id": str(current.get("page_id")) if page else None,
            "page_db_id": page["_id"] if page else None,
            "page_updated_at": page_version,
            "page_patch": {},
            "computed_page_fields": {
                key: copy.deepcopy((page.get("season_data") or {})[key])
                for key in _LEGACY_COMPUTED_KEYS
                if page and key in (page.get("season_data") or {})
            },
            "participation_rows": participation_rows,
        }
        current["_projection"] = projection
        current["_write_claim"] = {"token": token, "new_document": False,
                                    **({"page_db_id": page["_id"], "operation_token": op_token} if page else {})}
        current["_write_claim"]["operation_token"] = op_token
        committed_snapshot = True
        committed = await db.seasons.replace_one(
            {"_id": current["_id"], **version_filter(season), "_write_claim.token": token},
            current,
        )
        if committed.matched_count != 1:
            committed_snapshot = False
            raise HTTPException(status_code=409, detail="Сезон изменён во время восстановления.")
    except Exception:
        if not committed_snapshot:
            if page:
                await db.kvn.update_one(
                    {"_id": page["_id"], "_season_write_claim.season_id": current["_id"],
                     "_season_write_claim.token": op_token},
                    {"$unset": {"_season_write_claim": ""}},
                )
            await _release_season_claim(db, current["_id"], token)
        raise
    try:
        return await _project(db, current, token, people)
    except Exception:
        failed = copy.deepcopy(current)
        failed["_projection"]["state"] = "error"
        marked = await db.seasons.replace_one(
            {"_id": current["_id"], "updated_at": current.get("updated_at"), "_write_claim.token": token},
            failed,
        )
        if marked.matched_count != 1:
            raise HTTPException(status_code=409, detail="Не удалось сохранить ошибку проекции; claim оставлен для восстановления.")
        await _release_season_claim(db, current["_id"], token)
        return public_season(failed)


async def recover_season_claim(
    db, season_id: str, exact_token: str, *, worker_stopped: bool, actor: str, reason: str,
) -> dict:
    """Operator-only release of an exact durable worker claim after worker shutdown."""
    if not worker_stopped or not actor.strip() or not reason.strip():
        raise HTTPException(status_code=409, detail="Требуются остановка worker, оператор и причина восстановления.")
    season = await db.seasons.find_one({"_id": season_id})
    if season is None or _claim_token(season) != exact_token:
        raise HTTPException(status_code=409, detail="Токен захвата изменён; освобождение отклонено.")
    claim = season.get("_write_claim") or {}
    projection = season.get("_projection")
    committed_operation = bool(
        projection and claim.get("operation_token")
        and projection.get("operation_token") == claim.get("operation_token")
    )
    if not committed_operation:
        audit = list(projection.get("recovery_audit") or []) if projection else []
        event = {"actor": actor, "reason": reason, "token": exact_token,
                 "phase": "precommit", "at": datetime.now(timezone.utc).isoformat()}
        audit.append(event)
        recovery_collection = getattr(db, "season_projection_recoveries", None)
        if recovery_collection is not None:
            recovery_id = uuid.uuid5(uuid.NAMESPACE_URL, f"season-projection-recovery:{season_id}:{exact_token}").hex
            await recovery_collection.replace_one(
                {"_id": recovery_id}, {"_id": recovery_id, "season_id": season_id, **event}, upsert=True,
            )
        if claim.get("page_db_id"):
            await db.kvn.update_one(
                {"_id": claim["page_db_id"], "_season_write_claim.season_id": season_id,
                 "_season_write_claim.token": claim.get("operation_token")},
                {"$unset": {"_season_write_claim": ""}},
            )
        if claim.get("new_document"):
            deleted = await db.seasons.delete_one({"_id": season_id, "_write_claim.token": exact_token})
            if deleted.deleted_count != 1:
                raise HTTPException(status_code=409, detail="Захват сезона изменён; восстановление отклонено.")
            return {"season_id": season_id, "released": True, "phase": "precommit"}
        fields = {"_write_claim": ""}
        if projection:
            projection = copy.deepcopy(projection)
            projection["recovery_audit"] = audit
            fields["_projection"] = projection
        result = await db.seasons.update_one(
            {"_id": season_id, "_write_claim.token": exact_token},
            {"$set": {key: value for key, value in fields.items() if key != "_write_claim"},
             "$unset": {"_write_claim": ""}},
        )
        if result.matched_count != 1:
            raise HTTPException(status_code=409, detail="Захват сезона изменён; восстановление отклонено.")
        return {"season_id": season_id, "released": True, "phase": "precommit"}
    audit = list(projection.get("recovery_audit") or [])
    if committed_operation:
        projection = copy.deepcopy(projection)
        recovery_from_state = projection.get("state")
        projection["state"] = "error"
        projection["recovery_from_state"] = recovery_from_state
        audit.append({"actor": actor, "reason": reason, "token": exact_token,
                      "phase": "postcommit", "at": datetime.now(timezone.utc).isoformat()})
        projection["recovery_audit"] = audit
        result = await db.seasons.update_one(
            {"_id": season_id, "_write_claim.token": exact_token},
            {"$set": {"_projection": projection}, "$unset": {"_write_claim": ""}},
        )
        if result.matched_count != 1:
            raise HTTPException(status_code=409, detail="Захват сезона изменён; восстановление отклонено.")
    return {"season_id": season_id, "released": True, "phase": "postcommit"}
