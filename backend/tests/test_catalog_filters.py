import asyncio
from types import SimpleNamespace

from services.catalog_filters import city_condition, person_conditions, team_conditions


class Cursor:
    def __init__(self, items):
        self.items = items

    def limit(self, _count):
        return self

    async def to_list(self, _count):
        return self.items


class Collection:
    def __init__(self, items=(), distinct_values=()):
        self.items = list(items)
        self.distinct_values = list(distinct_values)
        self.query = None

    def find(self, query, _projection):
        self.query = query
        return Cursor(self.items)

    async def distinct(self, _field, query):
        self.query = query
        return self.distinct_values


def test_person_team_filter_uses_structured_memberships_and_escapes_name():
    db = SimpleNamespace(
        teams=Collection([{"_id": "team-1"}]),
        memberships=Collection(distinct_values=["person-1"]),
    )

    conditions = asyncio.run(person_conditions(db, team="Прима (КВН)"))

    assert db.teams.query["$or"][2]["title"]["$regex"] == r"^Прима\ \(КВН\)$"
    assert db.memberships.query == {"team_id": {"$in": ["team-1"]}}
    assert conditions == [{"$or": [
        {"team_ids": {"$in": ["team-1"]}},
        {"_id": {"$in": ["person-1"]}},
    ]}]


def test_team_league_and_year_must_match_one_non_archived_participation():
    db = SimpleNamespace(participations=Collection(distinct_values=["team-1"]))

    conditions = asyncio.run(team_conditions(db, league="premier-liga", year=2024))

    assert db.participations.query == {
        "season_status": {"$ne": "archived"},
        "tournament_slug": "premier-liga",
        "season_year": {"$in": [2024, "2024"]},
    }
    assert conditions == [{"_id": {"$in": ["team-1"]}}]


def test_city_filter_uses_city_relationship_and_exact_fallback():
    db = SimpleNamespace(cities=Collection([{
        "_id": "city-1", "name": "Томск", "related_person_ids": ["person-1"],
    }]))

    condition = asyncio.run(city_condition(db, "Томск", "person"))

    assert {"_id": {"$in": ["person-1"]}} in condition["$or"]
    assert {"bio.current_city": {"$regex": "^Томск$", "$options": "i"}} in condition["$or"]
