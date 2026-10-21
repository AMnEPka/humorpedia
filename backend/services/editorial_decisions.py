"""Атомарное владение редакционным решением и сохранение через CAS."""

from datetime import datetime, timezone
import uuid

from fastapi import HTTPException


def proposal_revision(proposal: dict) -> int:
    """Старые предложения без версии считаются версией ноль."""
    value = proposal.get("revision")
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def ensure_expected_revision(proposal: dict, expected_revision: int | None) -> int:
    current = proposal_revision(proposal)
    if expected_revision is not None and expected_revision != current:
        raise HTTPException(409, "Предложение изменилось. Обновите список и повторите решение.")
    return current


async def claim_decision(db, proposal: dict, actor: str, revision: int) -> dict:
    """Атомарно занять предложение до побочных записей."""
    token = str(uuid.uuid4())
    claim = {
        "token": token,
        "actor": actor,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    # Сравнение с None охватывает отсутствующее старое поле и BSON null;
    # при захвате версия нормализуется в целочисленный ноль.
    result = await db.editorial_proposals.update_one(
        {
            "_id": proposal["_id"],
            "revision": proposal.get("revision"),
            "decision_claim": None,
        },
        {"$set": {"revision": revision, "decision_claim": claim}},
    )
    if not result.matched_count:
        raise HTTPException(409, "Предложение уже обрабатывается или изменилось. Обновите список.")
    return claim


async def ensure_claim_owned(db, proposal: dict) -> None:
    """Проверить, что снимок всё ещё принадлежит исходному запросу до побочных записей."""
    token = (proposal.get("decision_claim") or {}).get("token")
    if not token:
        raise HTTPException(409, "Обработка предложения больше не принадлежит этому запросу.")
    current = await db.editorial_proposals.find_one(
        {
            "_id": proposal["_id"],
            "decision_claim.token": token,
            "revision": proposal_revision(proposal),
        },
        {"_id": 1},
    )
    if not current:
        raise HTTPException(409, "Обработка предложения больше не принадлежит этому запросу.")


async def persist_progress(db, proposal: dict) -> int:
    """Сохранить снимок решения только при совпадении владельца и версии."""
    claim = proposal.get("decision_claim") or {}
    token = claim.get("token")
    revision = proposal_revision(proposal)
    if not token:
        raise HTTPException(409, "Обработка предложения больше не принадлежит этому запросу.")

    fields = {key: value for key, value in proposal.items() if key not in {"_id", "revision"}}
    result = await db.editorial_proposals.update_one(
        {"_id": proposal["_id"], "decision_claim.token": token, "revision": revision},
        {"$set": fields, "$inc": {"revision": 1}},
    )
    if not result.matched_count:
        raise HTTPException(409, "Предложение изменилось или claim потерян; решение не сохранено.")
    proposal["revision"] = revision + 1
    return proposal["revision"]


async def release_decision(db, proposal_id: str, token: str) -> None:
    """Освободить только собственный claim; автоматического перехвата нет."""
    await db.editorial_proposals.update_one(
        {"_id": proposal_id, "decision_claim.token": token},
        {"$unset": {"decision_claim": ""}},
    )
