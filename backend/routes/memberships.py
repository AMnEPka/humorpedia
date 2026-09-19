"""Составы команд и «карьера» человека: команды, сезоны, роли жюри/ведущего. Логика — services/memberships.py."""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from services.memberships import (
    SOURCE_MANUAL, STATUS_CURRENT, STATUS_FORMER, import_all_rosters, import_team_rosters,
    load_person_lookup, name_key, now_iso, person_keys,
)
from services.show_teams import attach_show_info, team_id_or_kvn_slug_query, team_url
from utils.auth import require_admin, require_editor_on_write
from utils.database import get_db

router = APIRouter(prefix="/competitions", tags=["memberships"], dependencies=[Depends(require_editor_on_write)])

_TEAM_FIELDS = {"_id": 1, "slug": 1, "name": 1, "title": 1, "team_type": 1, "logo": 1, "status": 1,
                "show_id": 1, "full_path": 1}
_PERSON_FIELDS = {"_id": 1, "slug": 1, "title": 1, "full_name": 1, "photo": 1, "status": 1}


class MembershipIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    team_id: str
    person_id: Optional[str] = None
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
    elif not doc["person_name"].strip():
        raise HTTPException(status_code=422, detail="Укажите человека или имя")
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


# ─── Карьера человека ──────────────────────────────────────────────────────────

@router.get("/people/{id_or_slug}/career")
async def person_career(id_or_slug: str):
    """
    Команды человека (из составов), сезоны этих команд в годы его участия и роли в турнирах (жюри, ведущий, редактор).
    Записи без person_id подбираются по slug старого сайта или однозначному имени.
    """
    db = await get_db()
    person = await _find_person(db, id_or_slug)
    person_id = person["_id"]
    lookup = await load_person_lookup(db)
    slugs = [s for s, pid in lookup.by_slug.items() if pid == person_id]
    keys = [k for k in person_keys(person) if lookup.by_key.get(k) == person_id]

    memberships = await db.memberships.find({"$or": [
        {"person_id": person_id},
        {"person_id": None, "person_slug": {"$in": slugs}},
        {"person_id": None, "name_key": {"$in": keys}},
    ]}).sort([("from_year", 1)]).to_list(None)

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

    roles = await db.participations.find({"kind": "role", "season_status": {"$ne": "draft"}, "$or": [
        {"person_id": person_id},
        {"person_id": None, "name_key": {"$in": keys}},
    ]}).sort([("season_year", -1)]).to_list(None)
    role_tournaments = await _tournament_cards(db, {r["tournament_id"] for r in roles})
    for row in roles:
        row["tournament"] = role_tournaments.get(row["tournament_id"])

    return {"person": _person_card(person), "teams": team_items, "roles": roles}


async def _tournament_cards(db, ids: set) -> dict:
    return {t["_id"]: t for t in await db.tournaments.find(
        {"_id": {"$in": list(ids)}}, {"slug": 1, "show": 1, "title": 1, "short_title": 1, "page_path": 1, "order": 1},
    ).to_list(None)}
