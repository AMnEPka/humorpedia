"""Editor controlled intake and application of researched person changes."""
from copy import deepcopy
import hashlib
import json
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from models.content import Person, PersonBio, PersonCreate, PersonUpdate
from models.editorial_proposal import (
    EditorialDecisionRequest, EditorialProposalCreate, utc_iso,
)
from services.crud import create_content
from services.memberships import PersonLookup, name_key
from utils.auth import require_editor
from utils.database import get_db

router = APIRouter(
    prefix="/editorial-proposals", tags=["editorial-proposals"], dependencies=[Depends(require_editor)],
)

BIO_FIELDS = {"birth_date", "death_date", "birth_place", "current_city", "occupation", "achievements"}
FACTS_KEY = re.compile(r"^[^.$][^.$]*$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MISSING = object()


def _wire(document: dict) -> dict:
    result = deepcopy(document)
    result["id"] = str(result.get("_id") or result.get("id") or "")
    return result


def _validate_with_http(model, value):
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        raise HTTPException(422, detail=jsonable_encoder(exc.errors())) from exc


def _validate_change_field(field: str, kind: str) -> None:
    if field.startswith("bio.") and field[4:] in BIO_FIELDS:
        return
    if field.startswith("facts.") and FACTS_KEY.fullmatch(field[6:]):
        return
    if re.fullmatch(r"module\.[^.$]+\.content", field):
        return
    if re.fullmatch(r"appearance\.[^.$]+", field):
        return
    raise HTTPException(422, f"Недопустимое поле предложения: {field}")


def _person_update_plan(person: dict, change: dict, value):
    """Validate one accepted person change and return its atomic Mongo update."""
    field = change["field"]
    compare = {"_id": person["_id"]}
    update = {}
    old_value = change.get("old_value")
    if field.startswith("bio."):
        key = field[4:]
        bio = deepcopy(person.get("bio") or {})
        bio[key] = value
        _validate_with_http(PersonBio, bio)
        _validate_with_http(PersonUpdate, {"bio": bio})
        compare[f"bio.{key}"] = old_value
        update[f"bio.{key}"] = value
    elif field.startswith("facts."):
        facts = deepcopy(person.get("facts") or {})
        key = field[6:]
        if not isinstance(value, str):
            raise HTTPException(422, "Значение facts должно быть строкой")
        facts[key] = value
        _validate_with_http(PersonUpdate, {"facts": facts})
        compare[f"facts.{key}"] = old_value
        update[f"facts.{key}"] = value
    elif field.startswith("module."):
        _, module_id, _ = field.split(".")
        modules = deepcopy(person.get("modules") or [])
        module = next((entry for entry in modules if str(entry.get("id")) == module_id), None)
        if module is None:
            return None, "Модуль из предложения больше не существует"
        data = module.setdefault("data", {})
        if data.get("content", MISSING) != old_value:
            return None, "Содержимое модуля изменилось после исследования"
        if not isinstance(value, str):
            raise HTTPException(422, "Содержимое модуля должно быть строкой")
        data["content"] = value
        _validate_with_http(PersonUpdate, {"modules": modules})
        # Pydantic checks the existing module contract; persist the original copy so legacy fields survive.
        compare["modules"] = person.get("modules") or []
        update["modules"] = modules
    else:
        raise HTTPException(422, "Неподдерживаемый тип изменения")

    return {"compare": compare, "update": update}, None


def _fingerprint(data: dict) -> str:
    canonical = {
        "kind": data["kind"],
        "person_id": data.get("person_id"),
        "candidate_name": (data.get("candidate_name") or "").strip().casefold(),
        "slug": data.get("slug") or data.get("candidate_slug"),
        "changes": sorted(
            ((change["field"], change.get("old_value"), change.get("proposed_value"),
              sorted(src["url"] for src in change["sources"]))
             for change in data["changes"]),
            key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, default=str),
        ),
    }
    return hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


async def prepare_proposal(db, payload: EditorialProposalCreate | dict) -> dict:
    """Shared validation used by the API and the JSON importer."""
    model = payload if isinstance(payload, EditorialProposalCreate) else EditorialProposalCreate.model_validate(payload)
    data = model.model_dump(mode="json")
    data["slug"] = data.get("slug") or data.pop("candidate_slug", None)
    data.pop("candidate_slug", None)
    if data["kind"] == "update_person":
        if data.get("candidate_name") or data.get("slug"):
            raise HTTPException(422, "Для update_person не передают поля кандидата")
        if not data.get("person_id"):
            raise HTTPException(422, "Для update_person нужен person_id")
        person = await db.people.find_one({"_id": data["person_id"]}, {"_id": 1, "title": 1})
        if not person:
            raise HTTPException(404, "Человек не найден")
        data["person_title"] = person.get("title")
    else:
        if data.get("person_id"):
            raise HTTPException(422, "Для new_person нельзя задавать person_id")
        if not data.get("candidate_name"):
            raise HTTPException(422, "Для new_person нужно candidate_name")

    seen_ids = set()
    for change in data["changes"]:
        _validate_change_field(change["field"], data["kind"])
        if not change.get("id"):
            change["id"] = str(uuid.uuid4())
        if change["id"] in seen_ids:
            raise HTTPException(422, "ID изменений должны быть уникальны")
        seen_ids.add(change["id"])
        for source in change["sources"]:
            source["checked_at"] = source.get("checked_at") or utc_iso()
    return data


async def create_proposal(db, payload: EditorialProposalCreate | dict, actor: str = "import") -> tuple[dict, bool]:
    """Validate and save a proposal; exact repeated imports return the existing card."""
    data = await prepare_proposal(db, payload)

    fingerprint = _fingerprint(data)
    existing = await db.editorial_proposals.find_one({"fingerprint": fingerprint})
    if existing:
        return _wire(existing), False

    now = utc_iso()
    doc = {
        "_id": str(uuid.uuid4()),
        **data,
        "changes": [{**change, "status": "pending"} for change in data["changes"]],
        "status": "new",
        "fingerprint": fingerprint,
        "created_by": actor,
        "created_at": now,
        "updated_at": now,
        "audit": [{"action": "created", "actor": actor, "at": now}],
    }
    try:
        await db.editorial_proposals.insert_one(doc)
        return _wire(doc), True
    except DuplicateKeyError:
        # A concurrent importer may win between find_one and insert_one.
        existing = await db.editorial_proposals.find_one({"fingerprint": fingerprint})
        if existing:
            return _wire(existing), False
        raise


@router.get("")
async def list_editorial_proposals(
    kind: Optional[str] = Query(None, pattern="^(update_person|new_person)$"),
    status: Optional[str] = Query(None, pattern="^(new|in_review|accepted|rejected|conflict)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    db = await get_db()
    query = {}
    if kind:
        query["kind"] = kind
    if status:
        query["status"] = status
    items = await db.editorial_proposals.find(query).sort([("updated_at", -1)]).skip(skip).limit(limit).to_list(limit)
    return {"items": [_wire(item) for item in items], "total": await db.editorial_proposals.count_documents(query)}


@router.post("")
async def create_editorial_proposal(data: EditorialProposalCreate, user: dict = Depends(require_editor)):
    db = await get_db()
    card, _created = await create_proposal(db, data, str(user.get("_id") or user.get("id") or "editor"))
    return card


def _proposal_status(changes: list[dict]) -> str:
    statuses = [change["status"] for change in changes]
    if "conflict" in statuses:
        return "conflict"
    if "pending" in statuses:
        return "in_review" if any(status != "pending" for status in statuses) else "new"
    if any(status == "accepted" for status in statuses):
        return "accepted"
    return "rejected"


async def _persist_proposal_progress(db, proposal: dict) -> None:
    if not proposal.get("conflict_reason"):
        proposal["status"] = _proposal_status(proposal["changes"])
    else:
        proposal["status"] = "conflict"
    proposal["updated_at"] = utc_iso()
    await db.editorial_proposals.update_one(
        {"_id": proposal["_id"]},
        {"$set": {key: value for key, value in proposal.items() if key != "_id"}},
    )


def _proposed_value(change: dict, decision: dict):
    return decision.get("edited_value") if "edited_value" in decision else change.get("proposed_value")


async def _apply_person_value(db, proposal: dict, change: dict, value, actor: str) -> bool:
    person_id = proposal["person_id"]
    people = db.people
    person = await people.find_one({"_id": person_id})
    if not person:
        raise HTTPException(404, "Человек не найден")
    idempotency_key = f"{proposal['_id']}:{change['id']}"
    applied_ids = person.get("_editorial_change_ids", [])
    if idempotency_key in applied_ids:
        return True

    plan, conflict_reason = _person_update_plan(person, change, value)
    if conflict_reason:
        raise HTTPException(409, conflict_reason)
    old_value = change.get("old_value")
    now = utc_iso()
    audit = {
        "proposal_id": proposal["_id"], "change_id": change["id"], "actor": actor,
        "at": now, "field": change["field"], "old_value": old_value, "value": value,
        "sources": change.get("sources", []),
    }
    result = await people.update_one(
        plan["compare"],
        {"$set": {**plan["update"], "updated_at": now},
         "$addToSet": {"_editorial_change_ids": idempotency_key},
         "$push": {"editorial_audit": audit}},
    )
    return result.modified_count > 0


def _appearance_row_id(proposal: dict, change: dict) -> str:
    return "editorial-" + hashlib.sha256(f"{proposal['_id']}:{change['id']}".encode()).hexdigest()


async def _validate_appearance(db, proposal: dict, change: dict, value):
    if not isinstance(value, dict):
        raise HTTPException(422, "Участие должно быть объектом")
    show_id = change["field"].split(".", 1)[1]
    show = await db.shows.find_one({"_id": show_id}, {"_id": 1, "slug": 1, "full_path": 1, "title": 1})
    if not show:
        raise HTTPException(404, "Шоу не найдено")
    achievement = value.get("achievement", "participant")
    if achievement not in {"participant", "finalist", "winner"}:
        raise HTTPException(422, "Недопустимый статус участия")
    appearances = value.get("appearances", 0)
    if not isinstance(appearances, int) or isinstance(appearances, bool) or appearances < 0:
        raise HTTPException(422, "Число появлений должно быть неотрицательным целым")
    if len(str(value.get("person_name") or "")) > 200:
        raise HTTPException(422, "Имя в записи участия слишком длинное")
    row_id = _appearance_row_id(proposal, change)
    if await db.show_appearances.find_one({"_id": row_id}):
        return {"show": show, "row_id": row_id, "already_applied": True}, None
    person_id = proposal.get("person_id")
    if person_id and await db.show_appearances.find_one({"show_id": show_id, "person_id": person_id}):
        return None, "Участие этого человека в шоу уже есть; сначала сравните существующую запись"
    return {"show": show, "row_id": row_id, "already_applied": False}, None


async def _apply_appearance(db, proposal: dict, change: dict, value, actor: str) -> None:
    prepared, conflict_reason = await _validate_appearance(db, proposal, change, value)
    if conflict_reason:
        raise HTTPException(409, conflict_reason)
    if prepared["already_applied"]:
        return
    show = prepared["show"]
    row_id = prepared["row_id"]
    achievement = value.get("achievement", "participant")
    appearances = value.get("appearances", 0)
    source = change["sources"][0]
    row = {
        "_id": prepared["row_id"], "show_id": show["_id"], "show_path": show.get("full_path") or show.get("slug"),
        "person_id": proposal["person_id"], "person_name": value.get("person_name") or "",
        "person_slug": None, "achievement": achievement, "group_kind": "", "group_name": "",
        "team_id": None, "appearances": appearances, "first_episode": value.get("first_episode"),
        "source_page_id": show["_id"], "source_path": show.get("full_path") or show.get("slug"),
        "source_title": value.get("source_title") or source["title"], "source": "editorial",
        "source_url": str(source["url"]), "source_checked_at": source.get("checked_at") or utc_iso(),
        "created_by": actor, "created_at": utc_iso(),
    }
    if not row["person_name"]:
        person = await db.people.find_one({"_id": proposal["person_id"]}, {"title": 1, "full_name": 1})
        row["person_name"] = (person or {}).get("full_name") or (person or {}).get("title") or proposal.get("candidate_name") or ""
    await db.show_appearances.update_one({"_id": row_id}, {"$setOnInsert": row}, upsert=True)


async def _create_new_person(db, proposal: dict, identity, accepted_changes: list[dict], actor: str) -> tuple[dict, list[tuple[dict, object]]]:
    if not identity:
        raise HTTPException(422, "Для создания страницы передайте person.name/title/full_name/slug")
    title = identity.title or identity.name or proposal.get("candidate_name")
    full_name = identity.full_name or identity.name or proposal.get("candidate_name")
    slug = identity.slug or proposal.get("slug")
    if not title or not full_name or not slug or not SLUG.fullmatch(slug):
        raise HTTPException(422, "Для создания страницы нужны title, full_name и slug")
    person_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"humorpedia:editorial-proposal:{proposal['_id']}"))
    existing_created = await db.people.find_one({"_id": person_id})
    people = await db.people.find({}, {"_id": 1, "slug": 1, "title": 1, "full_name": 1, "aliases": 1}).to_list(None)
    lookup = PersonLookup(people)
    if existing_created:
        if existing_created.get("slug") != slug or (existing_created.get("full_name") or "") != full_name:
            raise HTTPException(409, "Найден профиль с ID предложения, но его данные отличаются")
    elif slug.lower() in lookup.by_slug or name_key(full_name) in lookup.by_key:
        raise HTTPException(409, "Страница человека с таким slug или именем уже существует")

    bio = {}
    facts = {}
    modules = []
    appearance_changes = []
    for change, value in accepted_changes:
        field = change["field"]
        if field.startswith("bio."):
            bio[field[4:]] = value
        elif field.startswith("facts."):
            if not isinstance(value, str):
                raise HTTPException(422, "Значение facts должно быть строкой")
            facts[field[6:]] = value
        elif field.startswith("module."):
            _, module_id, _ = field.split(".")
            module_data = value if isinstance(value, dict) else {"content": value}
            content = module_data.get("content")
            if not isinstance(content, str):
                raise HTTPException(422, "Для нового человека модуль должен содержать content")
            modules.append({"id": module_id, "type": module_data.get("type", "text_block"),
                            "title": module_data.get("title"), "order": len(modules),
                            "visible": True, "data": {"content": content}})
        elif field.startswith("appearance."):
            appearance_changes.append((change, value))
        else:
            raise HTTPException(422, f"Недопустимое поле новой страницы: {field}")
    payload = _validate_with_http(PersonCreate, {
        "title": title, "full_name": full_name, "slug": slug,
        "bio": bio, "facts": facts, "modules": modules, "status": "draft",
    })
    linked_proposal = {**proposal, "person_id": person_id}
    for change, value in appearance_changes:
        _prepared, conflict_reason = await _validate_appearance(db, linked_proposal, change, value)
        if conflict_reason:
            raise HTTPException(409, conflict_reason)

    if existing_created:
        result = {"id": person_id, "slug": existing_created["slug"]}
    else:
        result = await create_content("people", Person(
            id=person_id, title=payload.title, full_name=payload.full_name, slug=payload.slug, aliases=payload.aliases,
            bio=payload.bio or {}, facts=payload.facts or {}, facts_order=payload.facts_order or [],
            modules=payload.modules, tags=payload.tags, seo=payload.seo or {}, status=payload.status,
        ), payload.tags)
    # Keep the existing people links in sync using the same helper as the CRUD route.
    from routes.content_people import _link_person_everywhere
    await _link_person_everywhere(result["id"])
    return {"id": result["id"], "slug": result["slug"]}, appearance_changes


@router.post("/{proposal_id}/decide")
async def decide_editorial_proposal(
    proposal_id: str,
    data: EditorialDecisionRequest,
    user: dict = Depends(require_editor),
):
    db = await get_db()
    proposal = await db.editorial_proposals.find_one({"_id": proposal_id})
    if not proposal:
        raise HTTPException(404, "Предложение не найдено")
    actor = str(user.get("_id") or user.get("id") or "editor")
    changes = {change["id"]: change for change in proposal["changes"]}
    decisions = {decision.change_id: decision.model_dump(exclude_unset=True) for decision in data.decisions}
    if len(decisions) != len(data.decisions):
        raise HTTPException(422, "Нельзя передавать одно решение дважды")
    if not set(decisions).issubset(changes):
        raise HTTPException(422, "Решение ссылается на неизвестное изменение")
    if data.person is not None and proposal["kind"] != "new_person":
        raise HTTPException(422, "Данные person допустимы только для new_person")
    for change_id, decision in decisions.items():
        change = changes[change_id]
        requested_status = "accepted" if decision["decision"] == "accept" else "rejected"
        if change["status"] in {"accepted", "rejected"}:
            if change["status"] != requested_status:
                raise HTTPException(409, "Изменение уже решено иначе")
            if requested_status == "accepted" and "edited_value" in decision:
                saved = (change.get("decision") or {}).get("edited_value", change.get("proposed_value"))
                if decision["edited_value"] != saved:
                    raise HTTPException(409, "Изменение уже принято с другим значением")

    # Validate every update_person acceptance before the first content write. A
    # malformed later decision must not leave earlier facts applied invisibly.
    preflight_conflicts = {}
    if proposal["kind"] == "update_person":
        person = await db.people.find_one({"_id": proposal["person_id"]})
        if not person:
            raise HTTPException(404, "Человек не найден")
        applied_ids = person.get("_editorial_change_ids", [])
        for change_id, decision in decisions.items():
            change = changes[change_id]
            if decision["decision"] != "accept" or change["status"] in {"accepted", "rejected"}:
                continue
            if f"{proposal['_id']}:{change_id}" in applied_ids:
                continue
            value = _proposed_value(change, decision)
            if change["field"].startswith("appearance."):
                _prepared, conflict_reason = await _validate_appearance(db, proposal, change, value)
                if conflict_reason:
                    preflight_conflicts[change_id] = conflict_reason
            else:
                _plan, conflict_reason = _person_update_plan(person, change, value)
                if conflict_reason:
                    preflight_conflicts[change_id] = conflict_reason

    if data.person is not None:
        proposal["person_identity"] = data.person.model_dump(exclude_none=True)

    for change_id, decision in decisions.items():
        change = changes[change_id]
        requested_status = "accepted" if decision["decision"] == "accept" else "rejected"
        if change["status"] in {"accepted", "rejected"}:
            if change["status"] != requested_status:
                raise HTTPException(409, "Изменение уже решено иначе")
            if requested_status == "accepted" and "edited_value" in decision:
                saved = (change.get("decision") or {}).get("edited_value", change.get("proposed_value"))
                if decision["edited_value"] != saved:
                    raise HTTPException(409, "Изменение уже принято с другим значением")
            continue
        if proposal["kind"] == "update_person" and requested_status == "accepted":
            value = _proposed_value(change, decision)
            if change_id in preflight_conflicts:
                change["status"] = "conflict"
                change["decision"] = {"decision": "accept", "actor": actor, "at": utc_iso(), "reason": preflight_conflicts[change_id]}
                proposal.setdefault("audit", []).append({"action": "conflict", "change_id": change_id, "actor": actor, "at": utc_iso()})
                await _persist_proposal_progress(db, proposal)
                continue
            if change["field"].startswith("appearance."):
                try:
                    await _apply_appearance(db, proposal, change, value, actor)
                except HTTPException as exc:
                    if exc.status_code != 409:
                        raise
                    preflight_conflicts[change_id] = exc.detail
                    change["status"] = "conflict"
                    change["decision"] = {"decision": "accept", "actor": actor, "at": utc_iso(), "reason": exc.detail}
                    proposal.setdefault("audit", []).append({"action": "conflict", "change_id": change_id, "actor": actor, "at": utc_iso()})
                    await _persist_proposal_progress(db, proposal)
                    continue
            else:
                try:
                    matched = await _apply_person_value(db, proposal, change, value, actor)
                except HTTPException as exc:
                    if exc.status_code != 409:
                        raise
                    change["status"] = "conflict"
                    change["decision"] = {"decision": "accept", "actor": actor, "at": utc_iso(), "reason": exc.detail}
                    proposal.setdefault("audit", []).append({"action": "conflict", "change_id": change_id, "actor": actor, "at": utc_iso()})
                    await _persist_proposal_progress(db, proposal)
                    continue
                if not matched:
                    change["status"] = "conflict"
                    change["decision"] = {"decision": "accept", "actor": actor, "at": utc_iso(), "reason": "Поле изменилось после исследования"}
                    proposal.setdefault("audit", []).append({"action": "conflict", "change_id": change_id, "actor": actor, "at": utc_iso()})
                    await _persist_proposal_progress(db, proposal)
                    continue
        change["status"] = requested_status
        change["decision"] = {
            "decision": decision["decision"], "actor": actor, "at": utc_iso(),
            **({"edited_value": decision["edited_value"]} if "edited_value" in decision else {}),
        }
        proposal.setdefault("audit", []).append({"action": requested_status, "change_id": change_id, "actor": actor, "at": utc_iso()})
        # Persist each item immediately. If a later database operation fails,
        # retry sees a terminal change and the content-side idempotency key.
        await _persist_proposal_progress(db, proposal)

    if proposal["kind"] == "new_person" and not proposal.get("created_person_id"):
        if any(change["status"] == "pending" for change in proposal["changes"]):
            # The candidate stays outside people until the editor submits a final batch for every change.
            pass
        elif any(change["status"] == "conflict" for change in proposal["changes"]):
            pass
        elif any(change["status"] == "accepted" for change in proposal["changes"]):
            identity = data.person
            if identity is None and proposal.get("person_identity"):
                from models.editorial_proposal import EditorialPersonIdentity
                identity = EditorialPersonIdentity.model_validate(proposal["person_identity"])
            try:
                accepted_for_new = [
                    (change, (change.get("decision") or {}).get("edited_value", change.get("proposed_value")))
                    for change in proposal["changes"] if change["status"] == "accepted"
                ]
                created, _appearance_changes = await _create_new_person(db, proposal, identity, accepted_for_new, actor)
            except HTTPException as exc:
                if exc.status_code == 409:
                    proposal["status"] = "conflict"
                    proposal["conflict_reason"] = exc.detail
                    proposal.setdefault("audit", []).append({"action": "conflict", "actor": actor, "at": utc_iso(), "reason": exc.detail})
                    await _persist_proposal_progress(db, proposal)
                else:
                    raise
            else:
                proposal["person_identity"] = identity.model_dump(exclude_none=True)
                proposal["created_person"] = created
                proposal["created_person_id"] = created["id"]
                proposal["person_id"] = created["id"]
                proposal.pop("conflict_reason", None)
                proposal.setdefault("audit", []).append({"action": "person_created", "person_id": created["id"], "actor": actor, "at": utc_iso()})
                await _persist_proposal_progress(db, proposal)

    # A retry after profile creation resumes any accepted manual appearances.
    if proposal["kind"] == "new_person" and proposal.get("created_person_id"):
        linked_proposal = {**proposal, "person_id": proposal["created_person_id"]}
        for change in proposal["changes"]:
            if change["status"] != "accepted" or not change["field"].startswith("appearance."):
                continue
            value = (change.get("decision") or {}).get("edited_value", change.get("proposed_value"))
            await _apply_appearance(db, linked_proposal, change, value, actor)
            applied = proposal.setdefault("appearance_applied_change_ids", [])
            if change["id"] not in applied:
                applied.append(change["id"])
                await _persist_proposal_progress(db, proposal)

    await _persist_proposal_progress(db, proposal)
    return _wire(proposal)
