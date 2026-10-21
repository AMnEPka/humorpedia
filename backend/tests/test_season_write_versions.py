"""Optimistic concurrency contracts for legacy and canonical season writes."""
import asyncio
import copy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from models.competition import SeasonUpdate
from models.content import KVNUpdate
from routes import content_kvn, competitions
from services import competitions as competition_service
from services.memberships import PersonLookup


class UpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


from test_season_projection import Collection as ProjectionCollection


class FakeCollection(ProjectionCollection):
    def __init__(self, docs=(), before_update=None, before_replace=None):
        super().__init__(docs)
        self.before_update = before_update
        self.before_replace = before_replace
        self.updates = self.replacements = self.deletions = 0

    _matches = staticmethod(ProjectionCollection.matches)

    async def update_one(self, query, update, upsert=False):
        if self.before_update:
            self.before_update(self)
            self.before_update = None
        self.updates += 1
        return await super().update_one(query, update, upsert)

    async def replace_one(self, query, replacement, upsert=False):
        if self.before_replace:
            self.before_replace(self)
            self.before_replace = None
        self.replacements += 1
        return await super().replace_one(query, replacement, upsert)

    async def delete_many(self, query):
        self.deletions += 1
        return await super().delete_many(query)

    def find(self, *args):
        documents = self.docs
        class Cursor:
            async def to_list(self, limit): return copy.deepcopy(documents)
        return Cursor()


def _run(coro):
    return asyncio.run(coro)


def _kvn_db(page, *, before_update=None):
    page = {'title': 'Season', 'slug': 'vl-2000', 'full_path': 'kvn/vl-kvn/vl-2000', **page}
    return SimpleNamespace(kvn=FakeCollection([page], before_update=before_update),
                           seasons=FakeCollection(), participations=FakeCollection(), teams=FakeCollection(),
                           people=FakeCollection(), tournaments=FakeCollection([{'_id':'t','slug':'vl-kvn','show':'kvn'}]))


def test_version_field_presence_is_distinct_from_explicit_null():
    assert "expected_updated_at" not in KVNUpdate(season_data={}).model_fields_set
    assert KVNUpdate(season_data={}, expected_updated_at=None).model_fields_set >= {"expected_updated_at"}
    assert "expected_updated_at" not in SeasonUpdate().model_fields_set
    assert SeasonUpdate(expected_updated_at=None).model_fields_set >= {"expected_updated_at"}
    null_cas = {"updated_at": {"$eq": None, "$exists": True}}
    assert FakeCollection._matches({"updated_at": None}, null_cas)
    assert not FakeCollection._matches({}, null_cas)
    assert not FakeCollection._matches({"updated_at": "newer"}, null_cas)


def test_next_version_advances_past_expected_even_if_clock_is_behind():
    expected = datetime(2099, 1, 1, tzinfo=timezone.utc)
    refreshed = datetime.fromisoformat(competition_service.next_version(expected.isoformat()))
    assert refreshed > expected


def test_legacy_put_requires_version_before_tag_side_effects(monkeypatch):
    page = {"_id": "page-1", "id": "page-1", "updated_at": "2025-01-01T00:00:00+00:00", "season_data": {}}
    db = _kvn_db(page)
    tag_calls = []
    monkeypatch.setattr(content_kvn, "get_db", lambda: _run_value(db))
    monkeypatch.setattr(content_kvn.tag_service, "sync_tags", lambda tags: _async_record(tag_calls, tags))
    monkeypatch.setattr(content_kvn, "sync_from_kvn_page", lambda *_args: _async_none())
    monkeypatch.setattr(content_kvn.cache_service, "invalidate_kvn", lambda: None)
    monkeypatch.setattr(content_kvn.cache_service, "invalidate_kvn_children", lambda: None)

    with pytest.raises(HTTPException) as error:
        _run(content_kvn.update_kvn("page-1", KVNUpdate(season_data={}, tags=["new"])))

    assert error.value.status_code == 409
    assert db.kvn.updates == 0
    assert tag_calls == []


def test_legacy_put_accepts_null_version_for_missing_or_null_field_then_rejects_replay(monkeypatch):
    page = {"_id": "page-1", "id": "page-1", "season_data": {}}
    db = _kvn_db(page)
    monkeypatch.setattr(content_kvn, "get_db", lambda: _run_value(db))
    monkeypatch.setattr(content_kvn, "sync_from_kvn_page", lambda *_args: _async_none())
    monkeypatch.setattr(content_kvn.cache_service, "invalidate_kvn", lambda: None)
    monkeypatch.setattr(content_kvn.cache_service, "invalidate_kvn_children", lambda: None)

    result = _run(content_kvn.update_kvn(
        "page-1", KVNUpdate(season_data={"year": 2000}, expected_updated_at=None, expected_season_updated_at=None)
    ))

    assert result["season_data"]["year"] == 2000
    assert result["updated_at"]

    explicit_null_db = _kvn_db({"_id": "page-null", "id": "page-null", "updated_at": None,
                                "season_data": {"year": 2000}})
    monkeypatch.setattr(content_kvn, "get_db", lambda: _run_value(explicit_null_db))
    result = _run(content_kvn.update_kvn(
        "page-null", KVNUpdate(season_data={"year": 2000}, expected_updated_at=None, expected_season_updated_at=None)
    ))
    assert result["season_data"]["year"] == 2000
    assert explicit_null_db.kvn.docs[0]["updated_at"]
    assert explicit_null_db.kvn.docs[0]["updated_at"]
    assert "expected_updated_at" not in explicit_null_db.kvn.docs[0]

    with pytest.raises(HTTPException) as conflict:
        _run(content_kvn.update_kvn(
            "page-null", KVNUpdate(season_data={"year": 2002}, expected_updated_at=None, expected_season_updated_at=None)
        ))
    assert conflict.value.status_code == 409
    assert explicit_null_db.kvn.docs[0]["updated_at"]


def test_legacy_put_rejects_stale_and_compare_and_swap_race_without_side_effects(monkeypatch):
    stale_page = {"_id": "page-1", "id": "page-1", "updated_at": "2025-01-02T00:00:00+00:00", "season_data": {}}
    stale_db = _kvn_db(stale_page)
    tag_calls = []
    monkeypatch.setattr(content_kvn, "get_db", lambda: _run_value(stale_db))
    monkeypatch.setattr(content_kvn.tag_service, "sync_tags", lambda tags: _async_record(tag_calls, tags))
    monkeypatch.setattr(content_kvn, "sync_from_kvn_page", lambda *_args: _async_none())
    monkeypatch.setattr(content_kvn.cache_service, "invalidate_kvn", lambda: None)
    monkeypatch.setattr(content_kvn.cache_service, "invalidate_kvn_children", lambda: None)

    with pytest.raises(HTTPException) as error:
        _run(content_kvn.update_kvn("page-1", KVNUpdate(
            season_data={}, tags=["new"], expected_updated_at="2025-01-01T00:00:00+00:00"
        )))
    assert error.value.status_code == 409
    assert stale_db.kvn.updates == 0 and tag_calls == []

    racing_page = {"_id": "page-2", "id": "page-2", "updated_at": "2025-01-02T00:00:00+00:00", "season_data": {}}
    racing_db = _kvn_db(racing_page, before_update=lambda collection: collection.docs[0].update(
        updated_at="2025-01-03T00:00:00+00:00"
    ))
    monkeypatch.setattr(content_kvn, "get_db", lambda: _run_value(racing_db))
    sync_calls = []
    monkeypatch.setattr(content_kvn, "sync_from_kvn_page", lambda *_args: _async_record(sync_calls, True))
    monkeypatch.setattr(content_kvn.cache_service, "invalidate_kvn", lambda: None)
    monkeypatch.setattr(content_kvn.cache_service, "invalidate_kvn_children", lambda: None)

    with pytest.raises(HTTPException) as race_error:
        _run(content_kvn.update_kvn("page-2", KVNUpdate(
            season_data={}, expected_updated_at="2025-01-02T00:00:00+00:00", expected_season_updated_at=None
        )))
    assert race_error.value.status_code == 409
    assert racing_db.kvn.docs[0]["updated_at"] == "2025-01-03T00:00:00+00:00"
    assert sync_calls == []


def test_canonical_put_requires_version(monkeypatch):
    db = SimpleNamespace(seasons=FakeCollection([{"_id": "season-1", "updated_at": "v1"}]))
    monkeypatch.setattr(competitions, "get_db", lambda: _run_value(db))
    monkeypatch.setattr(competitions, "load_team_lookup", lambda _db: _async_value(competition_service.TeamLookup([])))
    save_calls = []

    async def fake_save(*_args, **_kwargs):
        save_calls.append(True)
        return {"_id": "season-1", "updated_at": "v2", "stages": [], "teams": [], "winners": []}

    monkeypatch.setattr(competitions, "save_season", fake_save)

    with pytest.raises(HTTPException) as error:
        _run(competitions.update_season("season-1", SeasonUpdate()))

    assert error.value.status_code == 409
    assert db.seasons.replacements == 0
    assert save_calls == []


def test_canonical_conflict_and_replace_race_do_not_touch_derived_data(monkeypatch):
    page = {"_id": "page-1", "season_data": {"year": 2000}}
    season = {"_id": "season-1", "tournament_id": "t-1", "tournament_slug": "vl-kvn",
              "show": "kvn", "year": 2000, "title": "Season", "status": "published",
              "page_path": "kvn/vl-kvn/2000", "page_collection": "kvn", "page_id": "page-1",
              "updated_at": "2025-01-02T00:00:00+00:00", "stages": [], "teams": [], "winners": []}
    db = SimpleNamespace(seasons=FakeCollection([season]), kvn=FakeCollection([page]),
                         participations=FakeCollection(), people=FakeCollection())
    monkeypatch.setattr(competitions, "get_db", lambda: _run_value(db))
    monkeypatch.setattr(competitions, "load_team_lookup", lambda _db: _async_value(competition_service.TeamLookup([])))
    monkeypatch.setattr(competition_service, "load_person_lookup", lambda _db: _async_value(PersonLookup()))

    with pytest.raises(HTTPException) as stale:
        _run(competitions.update_season("season-1", SeasonUpdate(
            expected_updated_at="2025-01-01T00:00:00+00:00", description="stale"
        )))
    assert stale.value.status_code == 409
    assert db.seasons.docs[0].get("description") is None
    assert db.participations.deletions == 0
    assert db.kvn.updates == 0

    db.seasons.before_replace = lambda collection: collection.docs[0].update(
        updated_at="2025-01-03T00:00:00+00:00"
    )
    with pytest.raises(HTTPException) as raced:
        _run(competitions.update_season("season-1", SeasonUpdate(
            expected_updated_at="2025-01-02T00:00:00+00:00", description="raced"
        )))
    assert raced.value.status_code == 409
    assert db.seasons.docs[0].get("description") is None
    assert db.participations.deletions == 0
    assert db.kvn.docs[0] == page


def test_canonical_fresh_write_round_trips_to_legacy_page_and_handles_bson_datetime(monkeypatch):
    stored_version = datetime(2025, 1, 2, tzinfo=timezone.utc).replace(tzinfo=None)
    page = {"_id": "page-1", "season_data": {"year": 2000}}
    season = {"_id": "season-1", "tournament_id": "t-1", "tournament_slug": "vl-kvn",
              "show": "kvn", "year": 2000, "title": "Season", "status": "published",
              "page_path": "kvn/vl-kvn/2000", "page_collection": "kvn", "page_id": "page-1",
              "updated_at": stored_version, "stages": [], "teams": [], "winners": []}
    db = SimpleNamespace(seasons=FakeCollection([season]), kvn=FakeCollection([page]),
                         participations=FakeCollection(), people=FakeCollection())
    monkeypatch.setattr(competitions, "get_db", lambda: _run_value(db))
    monkeypatch.setattr(competitions, "load_team_lookup", lambda _db: _async_value(competition_service.TeamLookup([])))
    monkeypatch.setattr(competition_service, "load_person_lookup", lambda _db: _async_value(PersonLookup()))

    result = _run(competitions.update_season("season-1", SeasonUpdate(
        expected_updated_at="2025-01-02T00:00:00+00:00", description="fresh edit"
    )))

    saved = db.seasons.docs[0]
    assert result["description"] == "fresh edit"
    assert saved["updated_at"] != stored_version
    assert "expected_updated_at" not in saved
    assert db.kvn.docs[0]["season_data"]["description"] == "fresh edit"
    assert "expected_updated_at" not in db.kvn.docs[0]


def _run_value(value):
    async def get():
        return value
    return get()


async def _async_none():
    return None


async def _async_record(target, value):
    target.append(value)


async def _async_value(value):
    return value
