"""Behavioral tests for explicit-db content creation commands (no live MongoDB)."""

import asyncio
import re
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from models.content import PersonCreate, ShowCreate, TeamCreate


def run(coro):
    return asyncio.run(coro)


class FakeCursor:
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        self._iterator = iter(self.items)
        return self

    async def __anext__(self):
        try:
            return deepcopy(next(self._iterator))
        except StopIteration:
            raise StopAsyncIteration

    def limit(self, _limit):
        return self

    async def to_list(self, length=None):
        items = self.items if length is None else self.items[:length]
        return deepcopy(items)


def _field(document, dotted):
    value = document
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _matches(document, query):
    for key, wanted in (query or {}).items():
        if key == "$and":
            if not all(_matches(document, item) for item in wanted):
                return False
            continue
        actual = _field(document, key)
        if isinstance(wanted, dict):
            for operator, expected in wanted.items():
                if operator == "$ne" and actual == expected:
                    return False
                if operator == "$in" and actual not in expected:
                    return False
                if operator == "$regex":
                    flags = re.IGNORECASE if wanted.get("$options") == "i" else 0
                    if actual is None or not re.search(expected, str(actual), flags):
                        return False
        elif actual != wanted:
            return False
    return True


class FakeCollection:
    def __init__(self, documents=()):
        self.documents = [deepcopy(item) for item in documents]

    async def find_one(self, query, projection=None):
        for document in self.documents:
            if _matches(document, query):
                if projection:
                    return {key: deepcopy(document[key]) for key, value in projection.items()
                            if value and key in document}
                return deepcopy(document)
        return None

    async def insert_one(self, document):
        self.documents.append(deepcopy(document))
        return SimpleNamespace(inserted_id=document.get("_id"))

    async def update_one(self, query, update, upsert=False):
        for document in self.documents:
            if _matches(document, query):
                self._apply(document, update)
                return SimpleNamespace(matched_count=1, modified_count=1)
        if upsert:
            document = {key: value for key, value in query.items() if not key.startswith("$")}
            self._apply(document, update)
            self.documents.append(document)
            return SimpleNamespace(matched_count=0, upserted_id=document.get("_id"))
        return SimpleNamespace(matched_count=0, modified_count=0)

    async def update_many(self, query, update):
        matched = 0
        for document in self.documents:
            if _matches(document, query):
                self._apply(document, update)
                matched += 1
        return SimpleNamespace(matched_count=matched, modified_count=matched)

    def find(self, query=None, projection=None):
        return FakeCursor([item for item in self.documents if _matches(item, query or {})])

    @staticmethod
    def _apply(document, update):
        for key, value in update.get("$set", {}).items():
            document[key] = deepcopy(value)
        for key, value in update.get("$setOnInsert", {}).items():
            document.setdefault(key, deepcopy(value))
        for key, value in update.get("$addToSet", {}).items():
            values = document.setdefault(key, [])
            if value not in values:
                values.append(deepcopy(value))
        for key, value in update.get("$inc", {}).items():
            document[key] = document.get(key, 0) + value


class FakeDB:
    def __init__(self, **collections):
        self.collections = collections

    def __getattr__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


def forbid_global_db(monkeypatch):
    async def fail():
        raise AssertionError("content command escaped the explicitly supplied database")

    from services import crud, tags
    monkeypatch.setattr(crud, "get_db", fail)
    monkeypatch.setattr(tags, "get_db", fail)


def test_person_command_persists_normalized_page_and_tags_in_supplied_db(monkeypatch):
    from services import content_commands, memberships, show_appearances

    forbid_global_db(monkeypatch)
    db = FakeDB()
    links = []

    async def record_link(*args):
        links.append(args)

    monkeypatch.setattr(memberships, "link_person", record_link)
    monkeypatch.setattr(show_appearances, "link_new_person", record_link)
    request = PersonCreate(
        title="Алексей Сергеев *", full_name="Алексей Сергеев *", slug="alexey-sergeev",
        foreign_agent=True, tags=["Юмор"],
    )

    result = run(content_commands.create_person_record(
        db, request, document_id="person-fixed", page_package_id="package-1"
    ))

    person = run(db.people.find_one({"_id": "person-fixed"}))
    assert result == {"id": "person-fixed", "slug": "alexey-sergeev"}
    assert person["title"] == person["full_name"] == "Алексей Сергеев"
    assert person["primary_tag"] == "Сергеев Алексей"
    assert person["page_package_id"] == "package-1"
    assert person["page_package_state"] == "preparing"
    assert person["page_package_initial_updated_at"] == person["updated_at"]
    assert {tag["name"] for tag in db.tags.documents} == {"Юмор", "Сергеев Алексей"}
    assert links == [(db, person), (db, person)]


def test_deferred_person_creation_skips_automatic_linking(monkeypatch):
    from services import content_commands, memberships, show_appearances

    calls = []

    async def record(*args):
        calls.append(args)

    monkeypatch.setattr(memberships, "link_person", record)
    monkeypatch.setattr(show_appearances, "link_new_person", record)
    run(content_commands.create_person_record(
        FakeDB(), PersonCreate(title="Имя", full_name="Имя", slug="name"), defer_links=True
    ))

    assert calls == []


def test_link_person_everywhere_is_noop_for_missing_person(monkeypatch):
    from services import content_commands, memberships, show_appearances

    async def unexpected(*_args):
        raise AssertionError("links must not be created for a missing person")

    monkeypatch.setattr(memberships, "link_person", unexpected)
    monkeypatch.setattr(show_appearances, "link_new_person", unexpected)
    run(content_commands.link_person_everywhere(FakeDB(), "missing-person"))


def test_team_creation_builds_kvn_scaffold_and_syncs_related_team(monkeypatch):
    from services import content_commands, memberships, crud, tags

    forbid_global_db(monkeypatch)
    imported = []
    invalidations = []

    async def import_roster(db, team):
        imported.append((db, team["_id"]))

    monkeypatch.setattr(memberships, "import_team_rosters", import_roster)
    monkeypatch.setattr(content_commands.cache_service, "invalidate_team", lambda slug: invalidations.append(slug))
    monkeypatch.setattr(content_commands.cache_service, "invalidate_team_lists", lambda: invalidations.append("lists"))
    db = FakeDB(
        teams=FakeCollection([{"_id": "related", "related_team_ids": []}]),
        templates=FakeCollection([{
            "content_type": "team", "is_default": True,
            "modules": [{"id": "template-module", "type": "text_block", "order": 4,
                         "visible": True, "data": {"title": "Заготовка", "content": "Текст"}}],
        }]),
    )

    result = run(content_commands.create_team_record(db, TeamCreate(
        title="Команда", name="Команда", slug="team", facts={"city": "Самара"},
        related_team_ids=["related"],
    ), document_id="team-fixed", page_package_id="package-2"))

    team = run(db.teams.find_one({"_id": "team-fixed"}))
    assert result["id"] == "team-fixed"
    assert team["primary_tag"] == "Команда"
    assert team["facts"]["Город"] == "Самара" and "city" not in team["facts"]
    assert team["facts"]["Год основания"] == team["facts"]["Капитан"] == "—"
    template_module = next(module for module in team["modules"]
                           if module.get("data", {}).get("title") == "Заготовка")
    assert template_module["id"] != "template-module"
    assert team["related_team_ids"] == ["related"]
    assert (run(db.teams.find_one({"_id": "related"}))["related_team_ids"] == ["team-fixed"])
    assert imported == [(db, "team-fixed")]
    assert invalidations == ["team", "lists"]
    assert {tag["name"] for tag in db.tags.documents} == {"Команда"}


def test_deferred_team_skips_roster_import_but_keeps_scaffold(monkeypatch):
    from services import content_commands, memberships

    imported = []

    async def import_roster(*args):
        imported.append(args)

    monkeypatch.setattr(memberships, "import_team_rosters", import_roster)
    db = FakeDB()
    run(content_commands.create_team_record(
        db, TeamCreate(title="Команда", name="Команда", slug="team"), defer_links=True
    ))

    team = db.teams.documents[0]
    assert team["facts"]["Год основания"] == team["facts"]["Капитан"] == "—"
    assert imported == []


def test_show_creation_keeps_parent_hierarchy_and_related_people(monkeypatch):
    from services import content_commands

    forbid_global_db(monkeypatch)
    db = FakeDB(shows=FakeCollection([{
        "_id": "parent", "slug": "project", "full_path": "project", "level": 0,
    }]))

    result = run(content_commands.create_show_record(db, ShowCreate(
        title="Первый сезон", name="Первый сезон", slug="season-1", parent_id="parent",
        order=2, related_person_ids=["person-1"],
    ), document_id="show-fixed"))

    show = run(db.shows.find_one({"_id": "show-fixed"}))
    assert result["id"] == "show-fixed"
    assert show["parent_id"] == "parent" and show["full_path"] == "project/season-1"
    assert show["level"] == 1 and show["order"] == 2
    assert show["related_person_ids"] == ["person-1"]


def test_show_creation_rejects_duplicate_full_path_without_inserting():
    from services import content_commands

    db = FakeDB(shows=FakeCollection([
        {"_id": "parent", "slug": "project", "full_path": "project", "level": 0},
        {"_id": "existing", "slug": "season-1", "full_path": "project/season-1"},
    ]))
    with pytest.raises(HTTPException) as error:
        run(content_commands.create_show_record(db, ShowCreate(
            title="Сезон", name="Сезон", slug="season-1", parent_id="parent",
        )))

    assert error.value.status_code == 400
    assert len(db.shows.documents) == 2
