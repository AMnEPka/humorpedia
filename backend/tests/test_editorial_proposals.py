"""Editorial proposal API tests using an in-memory Mongo-shaped fake."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import editorial_proposals as route


class _Result:
    def __init__(self, matched=0, modified=0):
        self.matched_count = matched
        self.modified_count = modified


def _get_path(document, path):
    value = document
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _set_path(document, path, value):
    parts = path.split(".")
    target = document
    for key in parts[:-1]:
        target = target.setdefault(key, {})
    target[parts[-1]] = deepcopy(value)


class _Cursor:
    def __init__(self, rows):
        self.rows = deepcopy(rows)

    def sort(self, *_args):
        return self

    def skip(self, count):
        self.rows = self.rows[count:]
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    async def to_list(self, _limit):
        return deepcopy(self.rows)


class _Collection:
    def __init__(self, docs=()):
        self.docs = {doc["_id"]: deepcopy(doc) for doc in docs}

    @staticmethod
    def _matches(doc, query):
        return all(_get_path(doc, key) == value for key, value in query.items())

    async def find_one(self, query, projection=None):
        doc = next((d for d in self.docs.values() if self._matches(d, query)), None)
        if doc is None:
            return None
        if projection:
            return {key: deepcopy(doc[key]) for key in projection if key in doc}
        return deepcopy(doc)

    def find(self, query=None, projection=None):
        query = query or {}
        rows = [doc for doc in self.docs.values() if self._matches(doc, query)]
        if projection:
            rows = [{key: deepcopy(doc[key]) for key in projection if key in doc} for doc in rows]
        return _Cursor(rows)

    async def insert_one(self, document):
        self.docs[document["_id"]] = deepcopy(document)
        return SimpleNamespace(inserted_id=document["_id"])

    async def count_documents(self, query):
        return sum(self._matches(doc, query) for doc in self.docs.values())

    async def update_one(self, query, update, upsert=False):
        doc = next((d for d in self.docs.values() if self._matches(d, query)), None)
        if doc is None:
            if not upsert:
                return _Result()
            doc = {"_id": query["_id"]}
            doc.update(deepcopy(update.get("$setOnInsert", {})))
            self.docs[doc["_id"]] = doc
            return _Result(1, 1)
        before = deepcopy(doc)
        for path, value in update.get("$set", {}).items():
            _set_path(doc, path, value)
        for path, value in update.get("$addToSet", {}).items():
            items = _get_path(doc, path)
            if items is None:
                _set_path(doc, path, [])
                items = _get_path(doc, path)
            if value not in items:
                items.append(deepcopy(value))
        for path, value in update.get("$push", {}).items():
            items = _get_path(doc, path)
            if items is None:
                _set_path(doc, path, [])
                items = _get_path(doc, path)
            items.append(deepcopy(value))
        return _Result(1, int(doc != before))


class _Db:
    def __init__(self):
        self.people = _Collection([{
            "_id": "p1", "title": "Иван", "full_name": "Иван Иванов", "slug": "ivan-ivanov",
            "bio": {}, "facts": {"show": "старое"}, "modules": [], "status": "published",
        }])
        self.editorial_proposals = _Collection()
        self.shows = _Collection()
        self.show_appearances = _Collection()


@pytest.fixture
def editorial_client(monkeypatch):
    db = _Db()

    async def fake_db():
        return db

    async def editor():
        return {"_id": "editor-1", "role": "editor"}

    monkeypatch.setattr(route, "get_db", fake_db)
    app = FastAPI()
    app.include_router(route.router, prefix="/api")
    app.dependency_overrides[route.require_editor] = editor
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, db


def _proposal(**overrides):
    data = {
        "kind": "update_person", "person_id": "p1", "reason": "Проверено",
        "changes": [{
            "id": "change-1", "field": "facts.show", "old_value": "старое", "proposed_value": "новое",
            "sources": [{"url": "https://example.org/source", "title": "Источник"}],
        }],
    }
    data.update(overrides)
    return data


def test_editorial_routes_require_editor_for_reads_and_writes():
    app = FastAPI()
    app.include_router(route.router, prefix="/api")
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/api/editorial-proposals").status_code == 401
        assert client.post("/api/editorial-proposals", json={}).status_code == 401


def test_editor_can_create_and_idempotently_import_same_proposal(editorial_client):
    client, db = editorial_client
    created = client.post("/api/editorial-proposals", json=_proposal())
    repeated = client.post("/api/editorial-proposals", json=_proposal())

    assert created.status_code == 200
    assert repeated.status_code == 200
    assert created.json()["id"] == repeated.json()["id"]
    assert len(db.editorial_proposals.docs) == 1
    listed = client.get("/api/editorial-proposals?kind=update_person&status=new")
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["changes"][0]["status"] == "pending"


def test_import_fingerprint_ignores_generated_ids_and_checked_at_but_tracks_old_value(editorial_client):
    client, db = editorial_client
    payload = _proposal()
    payload["changes"][0].pop("id")
    first = client.post("/api/editorial-proposals", json=payload)
    repeated = client.post("/api/editorial-proposals", json=payload)
    changed_baseline = deepcopy(payload)
    changed_baseline["changes"][0]["old_value"] = "другой старый текст"
    revised = client.post("/api/editorial-proposals", json=changed_baseline)

    assert first.status_code == repeated.status_code == revised.status_code == 200
    assert first.json()["id"] == repeated.json()["id"]
    assert first.json()["changes"][0]["id"] == repeated.json()["changes"][0]["id"]
    assert revised.json()["id"] != first.json()["id"]
    assert len(db.editorial_proposals.docs) == 2


def test_accept_applies_only_after_editor_decision_and_audits(editorial_client):
    client, db = editorial_client
    card = client.post("/api/editorial-proposals", json=_proposal()).json()
    before = db.people.docs["p1"]["facts"]["show"]
    assert before == "старое"

    result = client.post(f"/api/editorial-proposals/{card['id']}/decide", json={
        "decisions": [{"change_id": "change-1", "decision": "accept", "edited_value": "утверждено"}],
    })

    assert result.status_code == 200
    assert db.people.docs["p1"]["facts"]["show"] == "утверждено"
    assert db.people.docs["p1"]["_editorial_change_ids"] == [f"{card['id']}:change-1"]
    assert db.people.docs["p1"]["editorial_audit"][0]["old_value"] == "старое"
    assert result.json()["changes"][0]["status"] == "accepted"
    assert result.json()["status"] == "accepted"


def test_old_value_conflict_does_not_overwrite_person(editorial_client):
    client, db = editorial_client
    card = client.post("/api/editorial-proposals", json=_proposal()).json()
    db.people.docs["p1"]["facts"]["show"] = "обновили вручную"

    result = client.post(f"/api/editorial-proposals/{card['id']}/decide", json={
        "decisions": [{"change_id": "change-1", "decision": "accept"}],
    })

    assert result.status_code == 200
    assert db.people.docs["p1"]["facts"]["show"] == "обновили вручную"
    assert result.json()["changes"][0]["status"] == "conflict"
    assert result.json()["status"] == "conflict"


def test_update_packet_preflights_all_values_before_first_write(editorial_client):
    client, db = editorial_client
    card = client.post("/api/editorial-proposals", json=_proposal(changes=[
        {"id": "first", "field": "facts.show", "old_value": "старое", "proposed_value": "новое",
         "sources": [{"url": "https://example.org/first", "title": "Первый источник"}]},
        {"id": "invalid-later", "field": "bio.occupation", "old_value": None, "proposed_value": "не список",
         "sources": [{"url": "https://example.org/second", "title": "Второй источник"}]},
    ])).json()

    result = client.post(f"/api/editorial-proposals/{card['id']}/decide", json={
        "decisions": [
            {"change_id": "first", "decision": "accept"},
            {"change_id": "invalid-later", "decision": "accept"},
        ],
    })

    assert result.status_code == 422
    assert db.people.docs["p1"]["facts"]["show"] == "старое"
    assert db.editorial_proposals.docs[card["id"]]["changes"][0]["status"] == "pending"


def test_update_packet_persists_each_decision_and_retry_is_idempotent(monkeypatch, editorial_client):
    client, db = editorial_client
    card = client.post("/api/editorial-proposals", json=_proposal(changes=[
        {"id": "first", "field": "facts.show", "old_value": "старое", "proposed_value": "новое",
         "sources": [{"url": "https://example.org/first", "title": "Первый источник"}]},
        {"id": "second", "field": "bio.birth_place", "old_value": None, "proposed_value": "Москва",
         "sources": [{"url": "https://example.org/second", "title": "Второй источник"}]},
    ])).json()
    apply_value = route._apply_person_value

    async def fail_on_second(db_arg, proposal, change, value, actor):
        if change["id"] == "second":
            raise RuntimeError("injected second item failure")
        return await apply_value(db_arg, proposal, change, value, actor)

    monkeypatch.setattr(route, "_apply_person_value", fail_on_second)
    decisions = {"decisions": [
        {"change_id": "first", "decision": "accept"},
        {"change_id": "second", "decision": "accept"},
    ]}
    failed = client.post(f"/api/editorial-proposals/{card['id']}/decide", json=decisions)
    assert failed.status_code == 500
    saved = db.editorial_proposals.docs[card["id"]]
    assert [change["status"] for change in saved["changes"]] == ["accepted", "pending"]
    assert db.people.docs["p1"]["facts"]["show"] == "новое"

    monkeypatch.setattr(route, "_apply_person_value", apply_value)
    retried = client.post(f"/api/editorial-proposals/{card['id']}/decide", json=decisions)
    assert retried.status_code == 200
    assert [change["status"] for change in retried.json()["changes"]] == ["accepted", "accepted"]
    assert db.people.docs["p1"]["_editorial_change_ids"] == [f"{card['id']}:first", f"{card['id']}:second"]


def test_same_change_id_in_different_proposals_has_distinct_idempotency_keys(editorial_client):
    client, db = editorial_client
    first = client.post("/api/editorial-proposals", json=_proposal(changes=[{
        "id": "same-id", "field": "facts.show", "old_value": "старое", "proposed_value": "новый факт",
        "sources": [{"url": "https://example.org/first", "title": "Первый источник"}],
    }])).json()
    second = client.post("/api/editorial-proposals", json=_proposal(changes=[{
        "id": "same-id", "field": "bio.birth_place", "old_value": None, "proposed_value": "Москва",
        "sources": [{"url": "https://example.org/second", "title": "Второй источник"}],
    }])).json()

    first_result = client.post(f"/api/editorial-proposals/{first['id']}/decide", json={
        "decisions": [{"change_id": "same-id", "decision": "accept"}],
    })
    second_result = client.post(f"/api/editorial-proposals/{second['id']}/decide", json={
        "decisions": [{"change_id": "same-id", "decision": "accept"}],
    })

    assert first_result.status_code == second_result.status_code == 200
    assert db.people.docs["p1"]["facts"]["show"] == "новый факт"
    assert db.people.docs["p1"]["bio"]["birth_place"] == "Москва"
    assert db.people.docs["p1"]["_editorial_change_ids"] == [
        f"{first['id']}:same-id", f"{second['id']}:same-id",
    ]


def test_module_validation_preserves_legacy_module_fields(editorial_client):
    client, db = editorial_client
    db.people.docs["p1"]["modules"] = [{
        "id": "module-1", "type": "text_block", "order": 0, "visible": True,
        "title": "Биография", "unknown_top_level": "keep",
        "data": {"content": "старый текст", "legacy_payload": {"keep": True}},
    }]
    card = client.post("/api/editorial-proposals", json=_proposal(changes=[{
        "id": "module-change", "field": "module.module-1.content", "label": "Биография",
        "old_value": "старый текст", "proposed_value": "новый текст",
        "sources": [{"url": "https://example.org/module", "title": "Источник"}],
    }])).json()

    result = client.post(f"/api/editorial-proposals/{card['id']}/decide", json={
        "decisions": [{"change_id": "module-change", "decision": "accept"}],
    })

    assert result.status_code == 200
    module = db.people.docs["p1"]["modules"][0]
    assert module["data"]["content"] == "новый текст"
    assert module["data"]["legacy_payload"] == {"keep": True}
    assert module["unknown_top_level"] == "keep"


def test_new_person_is_created_only_after_final_batch(monkeypatch, editorial_client):
    client, db = editorial_client
    created_people = []

    async def fake_create_content(_collection, person, _tags):
        created_people.append(person)
        return {"id": "new-person", "slug": person.slug}

    async def no_link(_person_id):
        return None

    from routes import content_people
    monkeypatch.setattr(route, "create_content", fake_create_content)
    monkeypatch.setattr(content_people, "_link_person_everywhere", no_link)
    proposal = _proposal(
        kind="new_person", person_id=None, candidate_name="Новый комик", candidate_slug="novyi-komik",
        changes=[
            {"id": "name-fact", "field": "facts.role", "proposed_value": "комик",
             "sources": [{"url": "https://example.org/role", "title": "Роль"}]},
            {"id": "bio-fact", "field": "bio.birth_place", "proposed_value": "Москва",
             "sources": [{"url": "https://example.org/bio", "title": "Биография"}]},
        ],
    )
    card = client.post("/api/editorial-proposals", json=proposal).json()

    partial = client.post(f"/api/editorial-proposals/{card['id']}/decide", json={
        "person": {"name": "Новый комик", "slug": "novyi-komik"},
        "decisions": [{"change_id": "name-fact", "decision": "accept"}],
    })
    assert partial.status_code == 200
    assert not created_people
    assert not db.people.docs.get("new-person")

    final = client.post(f"/api/editorial-proposals/{card['id']}/decide", json={
        "decisions": [{"change_id": "bio-fact", "decision": "accept"}],
    })

    assert final.status_code == 200
    assert len(created_people) == 1
    assert created_people[0].status.value == "draft"
    assert final.json()["created_person"]["id"] == "new-person"


def test_new_person_appearance_failure_keeps_created_id_and_retry_recovers(monkeypatch, editorial_client):
    client, db = editorial_client
    db.shows.docs["show-1"] = {"_id": "show-1", "slug": "show", "title": "Шоу"}
    created = []

    async def fake_create_content(_collection, person, _tags):
        created.append(person)
        return {"id": person.id, "slug": person.slug}

    async def no_link(_person_id):
        return None

    from routes import content_people
    monkeypatch.setattr(route, "create_content", fake_create_content)
    monkeypatch.setattr(content_people, "_link_person_everywhere", no_link)
    apply_appearance = route._apply_appearance
    attempts = {"count": 0}

    async def fail_once(*_args, **_kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("injected appearance failure")
        return await apply_appearance(*_args, **_kwargs)

    monkeypatch.setattr(route, "_apply_appearance", fail_once)
    card = client.post("/api/editorial-proposals", json=_proposal(
        kind="new_person", person_id=None, candidate_name="Новый комик", slug="novyi-komik",
        changes=[{
            "id": "show-change", "field": "appearance.show-1", "proposed_value": {"achievement": "participant"},
            "sources": [{"url": "https://example.org/show", "title": "Состав шоу"}],
        }],
    )).json()
    decisions = {
        "person": {"title": "Новый комик", "full_name": "Новый комик", "slug": "novyi-komik"},
        "decisions": [{"change_id": "show-change", "decision": "accept"}],
    }

    failed = client.post(f"/api/editorial-proposals/{card['id']}/decide", json=decisions)
    assert failed.status_code == 500
    saved = db.editorial_proposals.docs[card["id"]]
    assert saved["created_person_id"] == created[0].id
    assert saved["changes"][0]["status"] == "accepted"

    monkeypatch.setattr(route, "_apply_appearance", apply_appearance)
    recovered = client.post(f"/api/editorial-proposals/{card['id']}/decide", json=decisions)
    assert recovered.status_code == 200
    assert len(created) == 1
    row = next(iter(db.show_appearances.docs.values()))
    assert row["source"] == "editorial"
    assert recovered.json()["created_person_id"] == created[0].id
