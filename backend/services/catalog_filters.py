"""Structured filters and option lists for public people and team catalogs."""

import re


def combine_query(base: dict, *conditions: dict | None) -> dict:
    parts = [part for part in (base, *conditions) if part]
    if not parts:
        return {}
    return parts[0] if len(parts) == 1 else {"$and": parts}


def exact(value: str) -> dict:
    return {"$regex": f"^{re.escape(value.strip())}$", "$options": "i"}


def options(values) -> list[dict]:
    unique = {}
    for value in values:
        if isinstance(value, dict):
            key, label = value.get("value"), value.get("label")
        else:
            key = label = value
        if isinstance(key, str) and key.strip() and isinstance(label, str) and label.strip():
            unique.setdefault(key.casefold(), {"value": key, "label": label})
    return sorted(unique.values(), key=lambda item: item["label"].casefold())


async def named_ids(collection, value: str, fields: tuple[str, ...]) -> list[str]:
    matched = await collection.find({"$or": [
        {"_id": value},
        *[{field: exact(value)} for field in fields],
    ]}, {"_id": 1}).limit(100).to_list(100)
    return [item["_id"] for item in matched]


async def city_condition(db, value: str, entity: str) -> dict:
    cities = await db.cities.find({"$or": [
        {"_id": value},
        *[{field: exact(value)} for field in ("slug", "title", "name", "aliases")],
    ]}, {"title": 1, "name": 1, f"related_{entity}_ids": 1}).limit(100).to_list(100)
    names = [value, *(city.get("name") or city.get("title") or "" for city in cities)]
    related_ids = [item_id for city in cities for item_id in city.get(f"related_{entity}_ids") or []]
    name_conditions = [{field: exact(name)} for name in names if name for field in (
        ("bio.current_city", "bio.birth_place") if entity == "person" else
        ("city", "facts.Город", "facts.city")
    )]
    return {"$or": [{"_id": {"$in": related_ids}}, *name_conditions]}


async def person_conditions(db, *, city=None, role=None, team=None, show=None) -> list[dict]:
    conditions = []
    if city:
        conditions.append(await city_condition(db, city, "person"))
    if role:
        membership_ids = await db.memberships.distinct("person_id", {"roles": exact(role)})
        conditions.append({"$or": [
            {"bio.occupation": exact(role)},
            {"_id": {"$in": [item for item in membership_ids if item]}},
        ]})
    if team:
        team_ids = await named_ids(db.teams, team, ("slug", "title", "name", "aliases"))
        membership_ids = await db.memberships.distinct("person_id", {"team_id": {"$in": team_ids}})
        conditions.append({"$or": [
            {"team_ids": {"$in": team_ids}},
            {"_id": {"$in": [item for item in membership_ids if item]}},
        ]})
    if show:
        show_ids = await named_ids(db.shows, show, ("slug", "full_path", "title", "name", "aliases"))
        appearance_ids = await db.show_appearances.distinct("person_id", {"show_id": {"$in": show_ids}})
        conditions.append({"$or": [
            {"show_ids": {"$in": show_ids}},
            {"_id": {"$in": [item for item in appearance_ids if item]}},
        ]})
    return conditions


async def team_conditions(db, *, city=None, league=None, year=None, show=None) -> list[dict]:
    conditions = []
    if city:
        conditions.append(await city_condition(db, city, "team"))
    if show:
        show_ids = await named_ids(db.shows, show, ("slug", "full_path", "title", "name", "aliases"))
        conditions.append({"show_id": {"$in": show_ids}})
    if league or year:
        participation_query = {"season_status": {"$ne": "archived"}}
        if league:
            participation_query["tournament_slug"] = league
        if year:
            participation_query["season_year"] = {"$in": [year, str(year)]}
        team_ids = await db.participations.distinct("team_id", participation_query)
        conditions.append({"_id": {"$in": [item for item in team_ids if item]}})
    return conditions


async def people_filter_options(db, base_query: dict) -> dict:
    cities = await db.cities.find(
        {"related_person_ids.0": {"$exists": True}},
        {"slug": 1, "title": 1, "name": 1},
    ).to_list(None)
    occupations = await db.people.distinct("bio.occupation", base_query)
    roles = await db.memberships.distinct("roles", {"person_id": {"$ne": None}})
    shows = await db.shows.find(
        {"status": {"$ne": "archived"}, "parent_id": None},
        {"_id": 1, "title": 1, "name": 1},
    ).to_list(None)
    return {
        "cities": options([{"value": city.get("slug"), "label": city.get("name") or city.get("title")}
                           for city in cities] + await db.people.distinct("bio.current_city", base_query)),
        "roles": options([*occupations, *roles]),
        "shows": options([{"value": show["_id"], "label": show.get("title") or show.get("name")}
                          for show in shows]),
    }


async def teams_filter_options(db, *, kvn: bool) -> dict:
    result = {}
    if kvn:
        participation_query = {"season_status": {"$ne": "archived"}}
        slugs = await db.participations.distinct("tournament_slug", participation_query)
        tournaments = await db.tournaments.find(
            {"slug": {"$in": slugs}}, {"slug": 1, "title": 1, "short_title": 1}
        ).to_list(None)
        labels = {item["slug"]: item.get("short_title") or item.get("title") or item["slug"]
                  for item in tournaments if item.get("slug")}
        years = await db.participations.distinct("season_year", participation_query)
        result["leagues"] = options([{"value": slug, "label": labels.get(slug, slug)} for slug in slugs])
        result["years"] = [{"value": str(year), "label": str(year)} for year in
                           sorted({int(year) for year in years if str(year).isdigit()}, reverse=True)]
    return result
