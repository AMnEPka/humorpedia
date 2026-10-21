"""Team slug/delete writers must update canonical season refs through CAS."""
import asyncio
import copy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from models.content import TeamUpdate
from routes import content_teams


def run(coro):
    return asyncio.run(coro)


def _path_values(document, path):
    parts = path.split(".")

    def walk(value, index):
        if isinstance(value, list):
            for item in value:
                yield from walk(item, index)
        elif index == len(parts):
            yield value
        elif isinstance(value, dict) and parts[index] in value:
            yield from walk(value[parts[index]], index + 1)

    return list(walk(document, 0))


def _matches(document, query):
    if "$or" in query:
        return any(_matches(document, clause) for clause in query["$or"])
    return all(any(value == expected for value in _path_values(document, path))
               for path, expected in query.items())


class AsyncCursor:
    def __init__(self, documents):
        self.documents = iter(copy.deepcopy(documents))

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.documents)
        except StopIteration:
            raise StopAsyncIteration


class FakeSeasons:
    def __init__(self, documents):
        self.documents = list(copy.deepcopy(documents))
        self.find_queries = []

    def find(self, query):
        self.find_queries.append(copy.deepcopy(query))
        return AsyncCursor([doc for doc in self.documents if _matches(doc, query)])


class FakeCollection:
    def __init__(self, documents=()):
        self.documents = copy.deepcopy(list(documents))
        self.deleted = []
        self.updated_many = []

    async def find_one(self, query, *_args):
        return copy.deepcopy(next((doc for doc in self.documents if _matches(doc, query)), None))

    async def delete_many(self, query):
        self.deleted.append(copy.deepcopy(query))

    async def update_many(self, query, update):
        self.updated_many.append((copy.deepcopy(query), copy.deepcopy(update)))


def _season(season_id="season-1", *, active=False):
    season = {
        "_id": season_id,
        "updated_at": "v1",
        "teams": [
            {"team_id": "team-1", "slug": "old-slug", "name": "Старое название (Казань)",
             "city": "Казань", "extra": {"source": "archive"}},
            {"team_id": None, "slug": "old-slug", "name": "Уже отвязанная команда"},
            {"team_id": "other-team", "slug": "old-slug", "name": "Другая команда"},
        ],
        "winners": [
            {"team_id": "team-1", "slug": "old-slug", "name": "Чемпион того сезона", "place": 1},
        ],
        "stages": [{"name": "Финал", "games": [{
            "name": "Финал",
            "results": [
                {"team_id": "team-1", "slug": "old-slug", "name": "Сборная 2005 года",
                 "place": 1, "total": 20, "scores": {"СТЭМ": 5}},
                {"team_id": None, "slug": "old-slug", "name": "Отвязана после удаления"},
            ],
        }]}],
    }
    if active:
        season["_write_claim"] = {"token": "in-flight"}
    return season


def _db(*seasons, team=None):
    return SimpleNamespace(
        seasons=FakeSeasons(seasons),
        teams=FakeCollection([team] if team else []),
        memberships=FakeCollection(),
        kvn=FakeCollection(),
    )


def _install_fake_save(monkeypatch, db, *, fail_on=None):
    calls = []

    async def save_season(_db, proposed, **kwargs):
        assert _db is db
        season_id = proposed["_id"]
        calls.append((season_id, copy.deepcopy(proposed), kwargs))
        if fail_on and fail_on(season_id, len(calls)):
            raise HTTPException(status_code=409, detail="season CAS conflict")
        stored = next(doc for doc in db.seasons.documents if doc["_id"] == season_id)
        assert kwargs["expected_updated_at"] == stored.get("updated_at")
        updated = copy.deepcopy(proposed)
        updated["updated_at"] = f"v{int(stored['updated_at'][1:]) + 1}"
        db.seasons.documents[db.seasons.documents.index(stored)] = updated
        return updated

    monkeypatch.setattr(content_teams, "save_season", save_season, raising=False)
    return calls


def test_slug_rename_updates_canonical_refs_without_rewriting_historical_names(monkeypatch):
    season = _season()
    db = _db(season)
    calls = _install_fake_save(monkeypatch, db)

    run(content_teams.update_team_slug_in_seasons("old-slug", "new-slug", "team-1", db))

    saved = db.seasons.documents[0]
    assert [ref["slug"] for ref in saved["teams"]] == ["new-slug", "new-slug", "old-slug"]
    assert [ref["team_id"] for ref in saved["teams"]] == ["team-1", "team-1", "other-team"]
    assert saved["teams"][0]["name"] == "Старое название (Казань)"
    assert saved["teams"][0]["city"] == "Казань"
    assert saved["teams"][0]["extra"] == {"source": "archive"}
    assert saved["winners"][0] == {
        "team_id": "team-1", "slug": "new-slug", "name": "Чемпион того сезона", "place": 1,
    }
    result = saved["stages"][0]["games"][0]["results"][0]
    assert (result["slug"], result["name"], result["place"], result["total"], result["scores"]) == (
        "new-slug", "Сборная 2005 года", 1, 20, {"СТЭМ": 5},
    )
    assert saved["stages"][0]["games"][0]["results"][1]["slug"] == "new-slug"
    assert saved["stages"][0]["games"][0]["results"][1]["team_id"] == "team-1"
    assert len(calls) == 1
    assert calls[0][2]["write_page"] is True
    assert db.kvn.deleted == [] and db.kvn.updated_many == []


def test_slug_rename_retry_converges_by_team_id_after_partial_cas_failure(monkeypatch):
    linked_seasons = [_season("season-1"), _season("season-2")]
    for season in linked_seasons:
        season["teams"] = [season["teams"][0]]
        season["stages"][0]["games"][0]["results"] = [season["stages"][0]["games"][0]["results"][0]]
    db = _db(*linked_seasons)
    attempts = []

    async def save_season(_db, proposed, **kwargs):
        attempts.append(proposed["_id"])
        if proposed["_id"] == "season-2" and attempts.count("season-2") == 1:
            raise HTTPException(status_code=409, detail="season CAS conflict")
        stored = next(doc for doc in db.seasons.documents if doc["_id"] == proposed["_id"])
        assert kwargs == {"write_page": True, "expected_updated_at": stored["updated_at"]}
        updated = copy.deepcopy(proposed)
        updated["updated_at"] = "v2"
        db.seasons.documents[db.seasons.documents.index(stored)] = updated
        return updated

    monkeypatch.setattr(content_teams, "save_season", save_season, raising=False)

    with pytest.raises(HTTPException) as conflict:
        run(content_teams.update_team_slug_in_seasons("old-slug", "new-slug", "team-1", db))
    assert conflict.value.status_code == 409
    assert db.seasons.documents[0]["teams"][0]["slug"] == "new-slug"
    assert db.seasons.documents[1]["teams"][0]["slug"] == "old-slug"

    # The team document is already on new-slug when the caller retries.
    run(content_teams.update_team_slug_in_seasons("new-slug", "new-slug", "team-1", db))

    assert db.seasons.documents[0]["teams"][0]["slug"] == "new-slug"
    assert db.seasons.documents[1]["teams"][0]["slug"] == "new-slug"
    assert attempts == ["season-1", "season-2", "season-2"]


def test_delete_detaches_only_canonical_team_id_refs_and_keeps_historical_labels(monkeypatch):
    season = _season()
    team = {"_id": "team-1", "slug": "old-slug", "show_id": None}
    db = _db(season, team=team)
    save_calls = _install_fake_save(monkeypatch, db)
    events = []

    async def get_db():
        return db

    async def delete_content(_collection, team_id, _not_found):
        events.append("delete-team")
        db.teams.documents = [doc for doc in db.teams.documents if doc["_id"] != team_id]
        return {"id": team_id, "deleted": True}

    monkeypatch.setattr(content_teams, "get_db", get_db)
    monkeypatch.setattr(content_teams, "delete_content", delete_content)
    monkeypatch.setattr(content_teams, "sync_kvn_pages", lambda *_args, **_kwargs: pytest.fail("legacy reverse sync"), raising=False)
    original_save = content_teams.save_season

    async def record_save(*args, **kwargs):
        events.append("save-season")
        return await original_save(*args, **kwargs)

    monkeypatch.setattr(content_teams, "save_season", record_save, raising=False)

    result = run(content_teams.delete_team("team-1"))

    saved = db.seasons.documents[0]
    assert result["deleted"] is True
    assert events == ["delete-team", "save-season"]
    assert [ref["team_id"] for ref in saved["teams"]] == [None, None, "other-team"]
    assert [ref["slug"] for ref in saved["teams"]] == ["old-slug", "old-slug", "old-slug"]
    assert saved["teams"][0]["name"] == "Старое название (Казань)"
    assert saved["winners"][0]["team_id"] is None
    assert saved["winners"][0]["slug"] == "old-slug"
    assert saved["winners"][0]["name"] == "Чемпион того сезона"
    results = saved["stages"][0]["games"][0]["results"]
    assert (results[0]["team_id"], results[0]["slug"], results[0]["name"]) == (
        None, "old-slug", "Сборная 2005 года",
    )
    assert results[1]["team_id"] is None and results[1]["slug"] == "old-slug"
    assert save_calls[0][2]["expected_updated_at"] == "v1"
    assert db.kvn.deleted == [] and db.kvn.updated_many == []


def test_delete_rejects_related_active_season_claim_before_removing_team(monkeypatch):
    team = {"_id": "team-1", "slug": "old-slug", "show_id": None}
    db = _db(_season(active=True), team=team)
    deleted = []

    async def get_db():
        return db

    async def delete_content(*args):
        deleted.append(args)
        return {"id": "team-1", "deleted": True}

    monkeypatch.setattr(content_teams, "get_db", get_db)
    monkeypatch.setattr(content_teams, "delete_content", delete_content)

    with pytest.raises(HTTPException) as error:
        run(content_teams.delete_team("team-1"))

    assert error.value.status_code == 409
    assert deleted == []
    assert db.teams.documents == [team]


def test_delete_retry_after_cas_conflict_finishes_by_exact_team_id_only(monkeypatch):
    season = _season()
    # Keep a detached legacy record with the same slug as a sentinel: after the
    # team document is gone, cleanup must never rediscover refs by slug.
    unrelated = {"_id": "other-team", "slug": "old-slug", "show_id": None}
    db = _db(season, team={"_id": "team-1", "slug": "old-slug", "show_id": None})
    db.teams.documents.append(unrelated)
    delete_calls = []

    async def get_db():
        return db

    async def delete_content(_collection, team_id, _not_found):
        delete_calls.append(team_id)
        db.teams.documents = [doc for doc in db.teams.documents if doc["_id"] != team_id]
        return {"id": team_id, "deleted": True}

    monkeypatch.setattr(content_teams, "get_db", get_db)
    monkeypatch.setattr(content_teams, "delete_content", delete_content)
    save_calls = _install_fake_save(monkeypatch, db, fail_on=lambda _id, count: count == 1)

    with pytest.raises(HTTPException) as conflict:
        run(content_teams.delete_team("team-1"))
    assert conflict.value.status_code == 409
    assert db.teams.documents == [unrelated]
    assert db.seasons.documents[0]["teams"][0]["team_id"] == "team-1"

    # The team deletion has committed. The retry resumes only canonical ID
    # detach; it does not use the old slug and cannot touch unrelated refs.
    db.seasons.find_queries.clear()
    result = run(content_teams.delete_team("team-1"))

    assert result == {"id": "team-1", "deleted": True}
    assert delete_calls == ["team-1"]
    assert db.teams.documents == [unrelated]
    refs = db.seasons.documents[0]["teams"]
    assert refs[0]["team_id"] is None and refs[0]["slug"] == "old-slug"
    assert refs[1]["team_id"] is None and refs[1]["slug"] == "old-slug"
    assert refs[2]["team_id"] == "other-team" and refs[2]["slug"] == "old-slug"
    assert len(save_calls) == 2
    assert all("slug" not in repr(query) for query in db.seasons.find_queries)


def test_update_retries_slug_projection_when_team_already_has_requested_slug(monkeypatch):
    team = {"_id": "team-1", "slug": "new-slug", "show_id": None, "modules": []}
    db = _db(team=team)
    sync_calls = []

    async def get_db():
        return db

    async def update_content(_collection, _team_id, _data, _message):
        return {"id": "team-1", "updated": True}

    async def retry(old_slug, new_slug, team_id, _db):
        sync_calls.append((old_slug, new_slug, team_id))

    async def no_self_heal(*_args):
        return None

    monkeypatch.setattr(content_teams, "get_db", get_db)
    monkeypatch.setattr(content_teams, "update_content", update_content)
    monkeypatch.setattr(content_teams, "update_team_slug_in_seasons", retry)
    monkeypatch.setattr(content_teams, "_run_team_self_healing", no_self_heal)
    monkeypatch.setattr(content_teams.cache_service, "invalidate_team", lambda: None)
    monkeypatch.setattr(content_teams.cache_service, "invalidate_team_lists", lambda: None)

    run(content_teams.update_team("team-1", TeamUpdate(slug="new-slug")))

    assert sync_calls == [("new-slug", "new-slug", "team-1")]
