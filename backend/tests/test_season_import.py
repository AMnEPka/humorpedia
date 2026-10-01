import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from models.season_import import SeasonImport
from services.competitions import TeamLookup, legacy_to_season, build_participations
from services.season_import import apply_import, build_season_data, digest, match_teams, preview_import


def payload():
    return {"league_slug": "vl-kvn", "slug": "vl-2026", "title": "Высшая лига 2026", "year": 2026,
            "source_url": "https://example.org/results", "as_of": "2026-10-01",
            "teams": [{"key": "a", "name": "НК", "city": "Астана", "aliases": ["Не кипишуй"]},
                      {"key": "b", "name": "Новая", "city": "Омск"}],
            "stages": [{"name": "1/2 финала", "order": 1, "games": [
                {"name": "Первый полуфинал", "order": 1, "date": "2026-09-12", "contests": ["Приветствие"],
                 "results": [{"team_key": "a", "place": 1, "total": 5, "scores": {"Приветствие": 5}, "passed": True},
                             {"team_key": "b", "place": 2, "total": 4.5}]}]}]}


TEAMS = [{"_id": "a-id", "slug": "ne-kipishuy", "title": "Не кипишуй", "facts": {"Город": "Астана"}}]
LEAGUE = {"_id": "league", "id": "league-uuid", "name": "Высшая лига", "full_path": "kvn/vl-kvn"}


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, *args, **kwargs):
        return self.rows


def database(page=None):
    async def find_page(query):
        return LEAGUE if "full_path" in query else page
    return SimpleNamespace(kvn=SimpleNamespace(find_one=AsyncMock(side_effect=find_page)),
                           teams=SimpleNamespace(find=lambda *args: Cursor(TEAMS)),
                           season_import_locks=SimpleNamespace(update_one=AsyncMock(), delete_one=AsyncMock()))


@pytest.mark.parametrize("problem", ["duplicate", "alias", "empty", "unknown", "total", "nan", "future", "contest", "extra"])
def test_rejects_bad_package(problem):
    data = payload()
    game = data["stages"][0]["games"][0]
    if problem == "duplicate":
        data["teams"].append(copy.deepcopy(data["teams"][0]))
    elif problem == "alias":
        data["teams"].append({"key": "duplicate-a", "name": "Не кипишуй", "city": "Другой город"})
    elif problem == "empty":
        game["results"] = []
    elif problem == "unknown":
        game["results"][0]["team_key"] = "unknown"
    elif problem == "total":
        game["results"][0]["total"] = 6
    elif problem == "nan":
        game["results"][0]["scores"]["Приветствие"] = float("nan")
    elif problem == "future":
        game["date"] = "2026-12-31"
    elif problem == "contest":
        game["results"][0]["scores"] = {"Разминка": 5}
    else:
        game["typo"] = True
    with pytest.raises(ValidationError):
        SeasonImport.model_validate(data)


def test_aliases_city_history_and_ambiguous_matches():
    package = SeasonImport.model_validate(payload())
    rows, errors = match_teams(package, TEAMS)
    assert not errors and rows[0]["team_id"] == "a-id" and rows[1]["action"] == "create"
    alternate = {**TEAMS[0], "_id": "second-id", "slug": "other", "facts": {"Город": "Другой город"}}
    assert not match_teams(package, [*TEAMS, alternate])[1]  # город снимает неоднозначность
    alternate["facts"] = TEAMS[0]["facts"]
    assert "несколько совпадений" in match_teams(package, [*TEAMS, alternate])[1][0]
    explicit = payload()
    explicit["teams"][0]["existing_slug"] = "ne-kipishuy"
    explicit["teams"][0]["city"] = "Новый город"
    rows, errors = match_teams(SeasonImport.model_validate(explicit), TEAMS)
    assert not errors and "Новый город" in rows[0]["warning"]
    assert "в архиве" in match_teams(package, [{**TEAMS[0], "status": "archived"}])[1][0]


def test_structured_results_roundtrip_and_crosslinks():
    package = SeasonImport.model_validate(payload())
    refs = {"a": {"team_id": "a-id", "slug": "ne-kipishuy", "name": "НК", "city": "Астана"},
            "b": {"team_id": "b-id", "slug": "new", "name": "Новая", "city": "Омск"}}
    sd = build_season_data(package, refs, "Высшая лига")
    season = legacy_to_season({"_id": "page", "slug": "vl-2026", "full_path": "kvn/vl-kvn/vl-2026",
                               "title": package.title, "status": "published", "season_data": sd},
                              {"_id": "t", "slug": "vl-kvn", "show": "kvn"},
                              TeamLookup([TEAMS[0], {"_id": "b-id", "slug": "new"}]))
    game = season["stages"][0]["games"][0]
    assert game["results"][0]["team_id"] == "a-id"
    assert game["results"][0]["name"] == "НК"
    assert game["results"][1]["scores"] == {}  # неизвестные оценки не становятся нулями
    assert season["winners"] == []
    assert len([row for row in build_participations(season) if row["kind"] == "game"]) == 2


@pytest.mark.anyio
async def test_preview_never_writes_and_existing_pages_protected():
    package = SeasonImport.model_validate(payload())
    preview = await preview_import(database(), package)
    assert not preview["errors"] and preview["teams_to_create"] == 1
    preview = await preview_import(database({"_id": "old", "season_data": {}}), package)
    assert preview["errors"] and not preview["unchanged"]


@pytest.mark.anyio
async def test_stale_preview_rejected_before_creating(monkeypatch):
    from routes import content_teams
    create = AsyncMock()
    monkeypatch.setattr(content_teams, "bulk_create_teams", create)
    with pytest.raises(HTTPException) as caught:
        await apply_import(database(), SeasonImport.model_validate(payload()), "stale")
    assert caught.value.status_code == 409
    create.assert_not_called()


@pytest.mark.anyio
async def test_creation_uses_bulk_import_and_complete_page(monkeypatch):
    from routes import content_kvn, content_teams
    package = SeasonImport.model_validate(payload())
    db = database()
    bulk = AsyncMock(return_value={"created": [{"index": 0, "id": "b-id", "slug": "new"}]})
    create_page = AsyncMock(return_value={"id": "page-id"})
    monkeypatch.setattr(content_teams, "bulk_create_teams", bulk)
    monkeypatch.setattr(content_kvn, "create_kvn", create_page)
    preview = await preview_import(db, package)
    result = await apply_import(db, package, preview["preview_token"])
    assert result["created"] and len(result["created_teams"]) == 1
    assert bulk.call_args.args[0].rows[0].name == "Новая"
    saved = create_page.call_args.args[0]
    assert saved.parent_id == "league-uuid" and saved.status == "published"
    assert len(saved.season_data["all_teams"]) == 2
    assert saved.season_data["stages"][0]["games"][0]["teams"][1]["total"] == 4.5


@pytest.mark.anyio
async def test_repeat_import_preserves_editor_changes(monkeypatch):
    from services import season_import
    package = SeasonImport.model_validate(payload())
    page = {"_id": "page", "season_data": {"import_source": {"fingerprint": digest(package.model_dump(mode="json"))},
                                          "intro_html": "Ручная правка"}}
    sync = AsyncMock()
    monkeypatch.setattr(season_import, "sync_from_kvn_page", sync)
    db = database(page)
    preview = await preview_import(db, package)
    result = await apply_import(db, package, preview["preview_token"])
    assert not result["created"] and not result["created_teams"]
    assert sync.call_args.args[1]["season_data"]["intro_html"] == "Ручная правка"


@pytest.mark.anyio
async def test_parallel_worker_import_rejected_before_creation(monkeypatch):
    from routes import content_teams
    db = database()
    db.season_import_locks.update_one.side_effect = DuplicateKeyError("lease already held")
    bulk = AsyncMock()
    monkeypatch.setattr(content_teams, "bulk_create_teams", bulk)
    with pytest.raises(HTTPException) as caught:
        await apply_import(db, SeasonImport.model_validate(payload()), "token")
    assert caught.value.status_code == 409
    bulk.assert_not_called()
    db.season_import_locks.delete_one.assert_not_called()
