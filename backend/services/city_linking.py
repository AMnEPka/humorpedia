"""Safe relations between city pages, people, and teams.

People are an editorial shortlist. They are imported from legacy city articles or selected manually
and are never inferred from everybody's birthplace. Team relations may be rebuilt from
`facts["Город"]`, using exact city components rather than substring matching.
"""
from __future__ import annotations

import html
import re
from typing import Any, Dict, Iterable, List


_TAG_RE = re.compile(r"<[^>]+>")
_PREFIX_RE = re.compile(r"^(?:г\.?|город|ст\.?|станица|пгт\.?|п\.?|пос\.?|пос[её]лок)\s*", re.I)
_PAREN_SUFFIX_RE = re.compile(r"\s*\((?:с\s*)?\d{4}[^)]*\)\s*$", re.I)
_REGION_WORDS = re.compile(r"\b(?:область|край|республика|округ|район)\b", re.I)


def normalize_city_name(name: str) -> str:
    value = html.unescape(_TAG_RE.sub(" ", name or "")).replace("ё", "е").lower().strip()
    value = _PREFIX_RE.sub("", value)
    value = _PAREN_SUFFIX_RE.sub("", value)
    value = re.sub(r"\s*[-–—]\s*", "-", value)
    return re.sub(r"\s+", " ", value).strip(" .")


def split_city_names(value: str) -> List[str]:
    """Split compound fields such as `Челябинск / Тюмень` into exact place names."""
    cleaned = html.unescape(value or "")
    cleaned = re.sub(r"<br\s*/?>", ",", cleaned, flags=re.I)
    cleaned = _TAG_RE.sub(" ", cleaned)
    parts = re.split(r"\s*(?:,|;|/|\n|\s+и\s+)\s*", cleaned, flags=re.I)
    result = []
    for part in parts:
        normalized = normalize_city_name(part)
        if normalized and normalized != "-" and not _REGION_WORDS.search(normalized):
            result.append(normalized)
    return list(dict.fromkeys(result))


def city_matches(city_name: str, field_value: str, aliases: Iterable[str] = ()) -> bool:
    names = {normalize_city_name(city_name), *(normalize_city_name(alias) for alias in aliases)}
    names.discard("")
    return bool(names.intersection(split_city_names(field_value)))


async def find_people_by_city(db, city_name: str, aliases: Iterable[str] = ()) -> List[str]:
    """Return birthplace matches for an editor preview; do not publish them automatically."""
    people_ids = []
    cursor = db.people.find({"status": {"$ne": "archived"}}, {"_id": 1, "facts": 1})
    async for person in cursor:
        birthplace = (person.get("facts") or {}).get("Место рождения", "")
        if city_matches(city_name, birthplace, aliases):
            people_ids.append(person["_id"])
    return people_ids


async def find_teams_by_city(db, city_name: str, aliases: Iterable[str] = ()) -> List[str]:
    team_ids = []
    # Draft team records are real team pages assembled from KVN/show data. Keep them available from
    # city pages even when their editorial article has not been filled in yet.
    cursor = db.teams.find({"status": {"$ne": "archived"}}, {"_id": 1, "facts": 1})
    async for team in cursor:
        team_city = (team.get("facts") or {}).get("Город", "")
        if city_matches(city_name, team_city, aliases):
            team_ids.append(team["_id"])
    return team_ids


async def link_city(db, city_id: str) -> Dict[str, Any]:
    city = await db.cities.find_one({"_id": city_id})
    if not city:
        return {"error": "City not found", "city_id": city_id}

    city_name = city.get("name") or city.get("title")
    aliases = city.get("aliases") or []
    people_ids = city.get("related_person_ids") or []
    team_ids = await find_teams_by_city(db, city_name, aliases)
    await db.cities.update_one({"_id": city_id}, {"$set": {"related_team_ids": team_ids}})
    return {
        "city_id": city_id,
        "city_name": city_name,
        "people_count": len(people_ids),
        "people_source": "editorial",
        "teams_count": len(team_ids),
        "people_ids": people_ids,
        "team_ids": team_ids,
    }


async def link_all_cities(db) -> Dict[str, Any]:
    results = []
    editorial_people = 0
    total_teams = 0
    async for city in db.cities.find({}, {"_id": 1}):
        result = await link_city(db, city["_id"])
        results.append(result)
        editorial_people += result.get("people_count", 0)
        total_teams += result.get("teams_count", 0)
    return {
        "cities_processed": len(results),
        "editorial_people_preserved": editorial_people,
        "total_teams_linked": total_teams,
        "details": results,
    }


async def link_person_to_cities(db, person_id: str) -> Dict[str, Any]:
    """Deliberately do nothing: an editor decides whether the person belongs in a city shortlist."""
    exists = await db.people.find_one({"_id": person_id}, {"_id": 1})
    return {"person_id": person_id, "cities_updated": 0, "editorial_selection_required": bool(exists)}


async def link_team_to_cities(db, team_id: str) -> Dict[str, Any]:
    team = await db.teams.find_one({"_id": team_id})
    if not team:
        return {"error": "Team not found"}
    team_city = (team.get("facts") or {}).get("Город", "")
    if not team_city:
        return {"team_id": team_id, "cities_updated": 0}

    updated = 0
    async for city in db.cities.find({}, {"_id": 1, "name": 1, "title": 1, "aliases": 1}):
        if city_matches(city.get("name") or city.get("title"), team_city, city.get("aliases") or []):
            result = await db.cities.update_one({"_id": city["_id"]}, {"$addToSet": {"related_team_ids": team_id}})
            updated += result.modified_count
    return {"team_id": team_id, "cities_updated": updated}
