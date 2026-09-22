"""Составы команд и «карьера» человека: команды, сезоны, роли жюри/ведущего. Логика — services/memberships.py."""
import uuid
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from services.memberships import (
    LINK_CANDIDATE, LINK_CONFIRMED, LINK_REJECTED, SOURCE_MANUAL, STATUS_CURRENT, STATUS_FORMER,
    import_all_rosters, import_team_rosters, load_person_lookup, membership_link_reason,
    membership_review_status, name_key, now_iso,
)
from services.show_teams import attach_show_info, team_id_or_kvn_slug_query, team_url
from utils.auth import require_admin, require_editor, require_editor_on_write
from utils.database import get_db

router = APIRouter(prefix="/competitions", tags=["memberships"], dependencies=[Depends(require_editor_on_write)])

_TEAM_FIELDS = {"_id": 1, "slug": 1, "name": 1, "title": 1, "team_type": 1, "logo": 1, "status": 1,
                "show_id": 1, "full_path": 1}
_PERSON_FIELDS = {"_id": 1, "slug": 1, "title": 1, "full_name": 1, "photo": 1, "status": 1}


class MembershipIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    team_id: str
    person_id: Optional[str] = None
    person_link_disabled: bool = False
    person_name: str = ""
    person_slug: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    from_year: Optional[int] = None
    to_year: Optional[int] = None
    status: str = STATUS_CURRENT
    season_ids: List[str] = Field(default_factory=list)
    note: str = ""
    order: int = 0


async def _find_team(db, id_or_slug: str) -> dict:
    team = await db.teams.find_one(team_id_or_kvn_slug_query(id_or_slug), {**_TEAM_FIELDS, "roster_import": 1})
    if not team:
        raise HTTPException(status_code=404, detail="Команда не найдена")
    return team


async def _find_person(db, id_or_slug: str) -> dict:
    person = await db.people.find_one(
        {"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}, {**_PERSON_FIELDS, "aliases": 1, "old_urls": 1}
    )
    if not person:
        raise HTTPException(status_code=404, detail="Человек не найден")
    return person


def _team_card(team: dict) -> dict:
    return {
        "id": team["_id"], "slug": team.get("slug"), "name": team.get("name") or team.get("title"),
        "team_type": team.get("team_type"), "logo": team.get("logo"), "status": team.get("status"),
        "show_id": team.get("show_id"), "url": team_url(team), "show": team.get("show"),
    }


def _person_card(person: dict) -> dict:
    return {
        "id": person["_id"], "slug": person.get("slug"), "name": person.get("full_name") or person.get("title"),
        "photo": person.get("photo"), "status": person.get("status"),
    }


def _years_overlap(membership: dict, year: Optional[int]) -> bool:
    if year is None:
        return True
    start, end = membership.get("from_year"), membership.get("to_year")
    return (start is None or year >= start) and (end is None or year <= end)


# ─── Состав команды ────────────────────────────────────────────────────────────

@router.get("/teams/{id_or_slug}/members")
async def team_members(id_or_slug: str):
    """Состав команды: текущие и бывшие участники; roster_blocks — какие текстовые блоки разобраны полностью."""
    db = await get_db()
    team = await _find_team(db, id_or_slug)
    members = await db.memberships.find({"team_id": team["_id"]}).sort([("status", 1), ("order", 1)]).to_list(None)

    person_ids = [m["person_id"] for m in members if m.get("person_id")]
    people = {p["_id"]: p for p in await db.people.find({"_id": {"$in": person_ids}}, _PERSON_FIELDS).to_list(None)}
    for member in members:
        person = people.get(member.get("person_id"))
        member["person"] = _person_card(person) if person and person.get("status") != "archived" else None

    return {
        "team": _team_card(team),
        "current": [m for m in members if m.get("status") != STATUS_FORMER],
        "former": [m for m in members if m.get("status") == STATUS_FORMER],
        "total": len(members),
        "roster_blocks": team.get("roster_import") or [],
    }


@router.post("/memberships")
async def create_membership(data: MembershipIn):
    db = await get_db()
    doc = await _prepare_membership(db, data)
    now = now_iso()
    doc.update({"_id": str(uuid.uuid4()), "source": SOURCE_MANUAL, "created_at": now, "updated_at": now})
    await db.memberships.insert_one(doc)
    return doc


@router.put("/memberships/{membership_id}")
async def update_membership(membership_id: str, data: MembershipIn):
    """Правка записи. Запись, импортированная из текста, становится ручной и больше не перезаписывается импортом."""
    db = await get_db()
    existing = await db.memberships.find_one({"_id": membership_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Запись состава не найдена")
    doc = await _prepare_membership(db, data)
    if data.person_id:
        doc.update({
            "candidate_person_id": None,
            "rejected_person_id": None,
            "link_review_status": LINK_CONFIRMED,
        })
    elif data.person_link_disabled:
        doc.update({
            "candidate_person_id": None,
            "rejected_person_id": (
                existing.get("candidate_person_id") or existing.get("person_id") or existing.get("rejected_person_id")
            ),
            "link_review_status": LINK_REJECTED,
        })
    else:
        doc.update({"candidate_person_id": None, "rejected_person_id": None, "link_review_status": None})
    doc.update({"source": SOURCE_MANUAL, "updated_at": now_iso()})
    await db.memberships.update_one({"_id": membership_id}, {"$set": doc})
    return {**existing, **doc}


@router.delete("/memberships/{membership_id}")
async def delete_membership(membership_id: str):
    db = await get_db()
    result = await db.memberships.delete_one({"_id": membership_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Запись состава не найдена")
    return {"success": True}


async def _prepare_membership(db, data: MembershipIn) -> dict:
    if data.status not in (STATUS_CURRENT, STATUS_FORMER):
        raise HTTPException(status_code=422, detail="status: current или former")
    if data.from_year and data.to_year and data.from_year > data.to_year:
        raise HTTPException(status_code=422, detail="Год начала позже года окончания")
    await _find_team(db, data.team_id)
    doc = data.model_dump()
    if data.person_id:
        person = await _find_person(db, data.person_id)
        doc["person_name"] = doc["person_name"] or person.get("full_name") or person.get("title") or ""
        doc["matched_by"] = "manual"
        doc["person_link_disabled"] = False
        doc["link_review_status"] = LINK_CONFIRMED
    elif not doc["person_name"].strip():
        raise HTTPException(status_code=422, detail="Укажите человека или имя")
    elif data.person_link_disabled:
        doc["matched_by"] = "manual"
        doc["link_review_status"] = LINK_REJECTED
    doc["person_name"] = doc["person_name"].strip()
    doc["name_key"] = name_key(doc["person_name"])
    doc["roles"] = [r.strip() for r in doc["roles"] if r.strip()]
    return doc


@router.post("/memberships/import-rosters", dependencies=[Depends(require_admin)])
async def import_rosters(team: Optional[str] = Query(None, description="id или slug одной команды")):
    """Разобрать текстовые блоки «Состав команды» (всех команд или одной) в записи составов."""
    db = await get_db()
    if team:
        found = await db.teams.find_one(team_id_or_kvn_slug_query(team))
        if not found:
            raise HTTPException(status_code=404, detail="Команда не найдена")
        return await import_team_rosters(db, found)
    return await import_all_rosters(db)


# ─── Редакторская проверка связей ─────────────────────────────────────────────

class MembershipLinkReviewIn(BaseModel):
    action: Literal["confirm", "reject", "link"]
    person_id: Optional[str] = None


@router.get("/membership-links/review", dependencies=[Depends(require_editor)])
async def membership_links_review(
    q: str = "",
    status: Literal["pending", "confirmed", "rejected", "all"] = "pending",
    reason: Optional[Literal["name_only", "slug_conflict", "slug_unresolved", "name_mismatch"]] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    db = await get_db()
    lookup = await load_person_lookup(db)
    memberships = await db.memberships.find({}).to_list(None)

    team_ids = list({m.get("team_id") for m in memberships if m.get("team_id")})
    teams = {t["_id"]: t for t in await db.teams.find({"_id": {"$in": team_ids}}, _TEAM_FIELDS).to_list(None)}
    await attach_show_info(db, teams.values())
    person_ids = {
        pid for m in memberships
        for pid in (m.get("candidate_person_id"), m.get("person_id"), m.get("rejected_person_id"))
        if pid
    }
    person_ids.update(
        lookup.by_slug.get((m.get("person_slug") or "").lower())
        for m in memberships if m.get("person_slug")
    )
    person_ids.discard(None)
    people = {
        p["_id"]: p
        for p in await db.people.find({"_id": {"$in": list(person_ids)}}, _PERSON_FIELDS).to_list(None)
    }

    counts = {LINK_CANDIDATE: 0, LINK_CONFIRMED: 0, LINK_REJECTED: 0}
    rows = []
    query_text = q.strip().casefold()
    for membership in memberships:
        review_status = membership_review_status(membership, lookup)
        if review_status not in counts:
            continue
        counts[review_status] += 1
        if status != "all" and review_status != (LINK_CANDIDATE if status == "pending" else status):
            continue
        link_reason = membership_link_reason(membership, lookup)
        if reason and link_reason != reason:
            continue
        team = teams.get(membership.get("team_id"))
        target_id = membership.get("candidate_person_id") or membership.get("person_id") or membership.get("rejected_person_id")
        person = people.get(target_id)
        source_person_id = lookup.by_slug.get((membership.get("person_slug") or "").lower())
        source_person = people.get(source_person_id)
        haystack = " ".join(filter(None, [
            membership.get("person_name"),
            (team or {}).get("name") or (team or {}).get("title"),
            (person or {}).get("full_name") or (person or {}).get("title"),
            (source_person or {}).get("full_name") or (source_person or {}).get("title"),
        ])).casefold()
        if query_text and query_text not in haystack:
            continue
        rows.append({
            "membership": membership,
            "team": _team_card(team) if team else None,
            "person": _person_card(person) if person else None,
            "source_person": _person_card(source_person) if source_person and source_person_id != target_id else None,
            "reason": link_reason,
            "review_status": "pending" if review_status == LINK_CANDIDATE else review_status,
            "public_active": bool(membership.get("person_id")),
        })

    rows.sort(key=lambda row: (
        0 if row["reason"] == "name_only" else 1,
        (row["membership"].get("person_name") or "").casefold(),
        ((row.get("team") or {}).get("name") or "").casefold(),
    ))
    return {
        "items": rows[skip:skip + limit],
        "total": len(rows),
        "skip": skip,
        "limit": limit,
        "counts": {
            "pending": counts[LINK_CANDIDATE],
            "confirmed": counts[LINK_CONFIRMED],
            "rejected": counts[LINK_REJECTED],
        },
    }


@router.patch("/membership-links/review/{membership_id}")
async def review_membership_link(
    membership_id: str,
    data: MembershipLinkReviewIn,
    user: dict = Depends(require_editor),
):
    db = await get_db()
    membership = await db.memberships.find_one({"_id": membership_id})
    if not membership:
        raise HTTPException(status_code=404, detail="Запись состава не найдена")

    target_id = data.person_id if data.action == "link" else (
        membership.get("candidate_person_id") or membership.get("person_id") or membership.get("rejected_person_id")
    )
    if data.action in ("confirm", "link"):
        if not target_id:
            raise HTTPException(status_code=422, detail="Не выбрана страница человека")
        person = await _find_person(db, target_id)
        changes = {
            "person_id": person["_id"],
            "candidate_person_id": None,
            "rejected_person_id": None,
            "person_link_disabled": False,
            "matched_by": "manual",
            "link_review_status": LINK_CONFIRMED,
        }
    else:
        changes = {
            "person_id": None,
            "candidate_person_id": None,
            "rejected_person_id": target_id,
            "person_link_disabled": True,
            "matched_by": "manual",
            "link_review_status": LINK_REJECTED,
        }
    changes.update({
        "source": SOURCE_MANUAL,
        "reviewed_by": user["_id"],
        "reviewed_at": now_iso(),
        "updated_at": now_iso(),
    })
    await db.memberships.update_one({"_id": membership_id}, {"$set": changes})
    return {"ok": True, "review_status": changes["link_review_status"]}


# ─── Карьера человека ──────────────────────────────────────────────────────────

@router.get("/people/{id_or_slug}/career")
async def person_career(id_or_slug: str):
    """
    Команды человека (из составов), сезоны этих команд в годы его участия и роли в турнирах (жюри, ведущий, редактор).
    Публично используются только сохранённые person_id; кандидаты проверяются отдельно в админке.
    """
    db = await get_db()
    person = await _find_person(db, id_or_slug)
    person_id = person["_id"]
    memberships = await db.memberships.find({"person_id": person_id}).sort([("from_year", 1)]).to_list(None)

    teams = {t["_id"]: t for t in await db.teams.find(
        {"_id": {"$in": list({m["team_id"] for m in memberships})}}, _TEAM_FIELDS
    ).to_list(None)}
    await attach_show_info(db, teams.values())
    team_seasons = await db.participations.find(
        {"team_id": {"$in": list(teams)}, "kind": "season", "season_status": {"$ne": "draft"}}
    ).sort([("season_year", -1)]).to_list(None)

    tournaments = await _tournament_cards(db, {r["tournament_id"] for r in team_seasons})
    team_items = []
    for membership in memberships:
        team = teams.get(membership["team_id"])
        if not team or team.get("status") == "archived":
            continue
        seasons = [
            {**row, "tournament": tournaments.get(row["tournament_id"])}
            for row in team_seasons
            if row["team_id"] == team["_id"] and _years_overlap(membership, row.get("season_year"))
        ]
        team_items.append({"membership": membership, "team": _team_card(team), "seasons": seasons})

    roles = await db.participations.find({
        "kind": "role", "season_status": {"$ne": "draft"}, "person_id": person_id,
    }).sort([("season_year", -1)]).to_list(None)
    role_tournaments = await _tournament_cards(db, {r["tournament_id"] for r in roles})
    for row in roles:
        row["tournament"] = role_tournaments.get(row["tournament_id"])

    return {"person": _person_card(person), "teams": team_items, "roles": roles}


async def _tournament_cards(db, ids: set) -> dict:
    return {t["_id"]: t for t in await db.tournaments.find(
        {"_id": {"$in": list(ids)}}, {"slug": 1, "show": 1, "title": 1, "short_title": 1, "page_path": 1, "order": 1},
    ).to_list(None)}
