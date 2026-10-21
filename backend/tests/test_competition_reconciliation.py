"""Поведенческие тесты read-only сверки канонических и legacy-сезонов."""
from __future__ import annotations

import copy

import pytest

from services.competition_reconciliation import reconcile_seasons
from services.competitions import TeamLookup, legacy_to_season


TOURNAMENT = {"_id": "t-vl", "slug": "vl-kvn", "show": "kvn", "participant_type": "team"}
TEAMS = [{"_id": "team-one", "slug": "one"}]


def page(page_id="page-1"):
    return {
        "_id": page_id,
        "slug": "vl-2026",
        "full_path": "kvn/vl-kvn/vl-2026",
        "title": "Сезон 2026",
        "status": "published",
        "season_data": {
            "league_slug": "vl-kvn",
            "year": 2026,
            "prev_season": "vl-2025",
            "next_season": None,
            "all_teams": [{"slug": "one", "name": "Команда один"}],
            "winners": [],
            "custom_field": {"source": "legacy"},
            "stages": [{
                "name": "Финал", "order": 1, "comment": "Комментарий",
                "games": [{
                    "id": "game-final", "name": "Финал", "order": 1,
                    "teams": [{"team_slug": "one", "team_name": "Команда один", "person_id": "person-1"}],
                }],
            }],
        },
    }


def canonical(source=None):
    source = source or page()
    season = legacy_to_season(source, TOURNAMENT, TeamLookup(TEAMS))
    season["created_at"] = "2026-01-01T00:00:00+00:00"
    season["updated_at"] = "2026-02-01T00:00:00+00:00"
    return season


def reconcile(pages, seasons, *, max_differences=50):
    return reconcile_seasons(pages, seasons, [TOURNAMENT], TEAMS, max_differences=max_differences)


def item_for(report, page_id):
    return next(item for item in report["items"] if item.get("page_id") == page_id)


def test_equal_projection_ignores_computed_links_and_timestamps():
    source = page()
    report = reconcile([source], [canonical(source)])
    item = item_for(report, "page-1")
    assert item["status"] == "equal_projection"
    assert item["projection_differences"] == []
    assert report["summary"]["equal_projection"] == 1


def test_reports_stage_person_and_unknown_extra_projection_conflicts():
    source = page()
    stored = canonical(source)
    source["season_data"]["custom_field"] = {"source": "changed"}
    source["season_data"]["stages"][0]["games"][0]["teams"][0]["person_id"] = "person-2"
    item = item_for(reconcile([source], [stored]), "page-1")
    paths = {difference["path"] for difference in item["projection_differences"]}
    assert item["status"] == "projection_conflict"
    assert any(path.endswith("/person_id") for path in paths)
    assert "/custom_field/source" in paths


def test_reports_page_metadata_separately_from_season_projection():
    source = page()
    source.update(title="Другое название", slug="renamed", status="draft")
    item = item_for(reconcile([source], [canonical()]), "page-1")
    assert item["status"] == "equal_projection"
    metadata = {diff["path"] for diff in item["metadata_differences"]}
    assert {"/title", "/slug", "/status"} <= metadata


def test_reports_missing_sides_and_duplicate_page_links():
    present = page("present")
    orphan = canonical()
    orphan.update(_id="orphan-season", page_id="missing-page")
    report = reconcile([present, copy.deepcopy(present)], [orphan])
    statuses = [item["status"] for item in report["items"]]
    assert statuses.count("ambiguous") == 2
    assert statuses.count("missing_legacy") == 1
    missing = item_for(reconcile([present], []), "present")
    assert missing["status"] == "missing_canonical"


def test_canonical_roundtrip_reports_unrepresentable_stable_id():
    stored = canonical()
    stored["stages"][0]["id"] = "canonical-only-stage-id"
    item = item_for(reconcile([page()], [stored]), "page-1")
    assert item["status"] == "equal_projection"
    assert any(diff["path"] == "/stages/0/id" for diff in item["canonical_roundtrip_differences"])


def test_malformed_row_is_reported_without_stopping_other_rows():
    good = page("good")
    bad = {"_id": "bad", "full_path": "kvn/vl-kvn/bad", "season_data": ["not", "an", "object"]}
    report = reconcile([bad, good], [canonical(good)])
    assert item_for(report, "bad")["status"] == "invalid"
    assert item_for(report, "good")["status"] == "equal_projection"


def test_malformed_page_path_is_isolated_from_other_rows():
    good = page("good")
    bad = page("bad-path")
    stored = [canonical(good), canonical(bad)]
    bad["full_path"] = 42

    report = reconcile([bad, good], stored)

    assert item_for(report, "bad-path")["status"] == "invalid"
    assert item_for(report, "good")["status"] == "equal_projection"


def test_difference_limit_and_input_immutability():
    source = page()
    source["season_data"].update({f"custom_{index}": f"legacy-{index}" for index in range(8)})
    stored = canonical(source)
    stored["extra"].update({f"custom_{index}": f"canonical-{index}" for index in range(8)})
    before = copy.deepcopy((source, stored))
    report = reconcile([source], [stored], max_differences=2)
    assert len(item_for(report, "page-1")["projection_differences"]) == 2
    assert report["summary"]["total_differences"] > 2
    assert report["summary"]["truncated"] is True
    assert (source, stored) == before


def test_diff_distinguishes_missing_from_null_and_bounds_large_values():
    source = page()
    source["season_data"].pop("custom_field")
    source["season_data"]["large"] = "x" * 500
    stored = canonical()
    stored["extra"]["custom_field"] = None
    stored["extra"]["large"] = "y" * 500
    differences = item_for(reconcile([source], [stored]), "page-1")["projection_differences"]
    missing = next(diff for diff in differences if diff["path"] == "/custom_field")
    large = next(diff for diff in differences if diff["path"] == "/large")
    assert missing["left"]["present"] is True
    assert missing["left"]["value"] is None
    assert missing["right"]["present"] is False
    assert len(large["left"]["value"]) <= 200
    assert large["left"]["digest"] != large["right"]["digest"]


def test_ignores_pages_without_season_data_but_reports_a_referenced_missing_page():
    ordinary_page = {"_id": "ordinary", "slug": "ordinary"}
    assert reconcile([ordinary_page], [])["items"] == []

    orphan = canonical()
    orphan["page_id"] = "ordinary"
    report = reconcile([ordinary_page], [orphan])
    assert item_for(report, "ordinary")["status"] == "missing_legacy"


def test_projection_diff_distinguishes_boolean_from_number():
    source = page()
    source["season_data"]["numeric_flag"] = 1
    stored = canonical(source)
    stored["extra"]["numeric_flag"] = True

    item = item_for(reconcile([source], [stored]), "page-1")

    assert any(diff["path"] == "/numeric_flag" for diff in item["projection_differences"])


def test_difference_counts_preserve_categories_after_global_cap():
    source = page()
    source["title"] = "Новое название"
    source["season_data"]["flag"] = "legacy"
    stored = canonical()
    stored["extra"]["flag"] = "canonical"
    stored["stages"][0]["id"] = "canonical-only-stage-id"

    report = reconcile([source], [stored], max_differences=1)
    item = item_for(report, "page-1")

    assert item["difference_counts"] == {
        "projection_differences": 1,
        "metadata_differences": 1,
        "canonical_roundtrip_differences": 1,
    }
    assert report["summary"]["difference_counts"] == item["difference_counts"]
    assert item["total_differences"] == 3


def test_cli_requires_explicit_mongo_connection_before_connecting(monkeypatch):
    from scripts import report_competition_reconciliation as cli

    for name in ("MONGO_URL", "MONGO_HOST", "HOST"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DB_NAME", "original-db")
    called = False

    async def forbidden_connect():
        nonlocal called
        called = True
        raise AssertionError("подключение не должно начинаться")

    monkeypatch.setattr(cli, "get_db", forbidden_connect)
    with pytest.raises(ValueError, match="MONGO_URL или MONGO_HOST"):
        __import__("asyncio").run(cli._run("audit-copy", 50))
    assert called is False
    assert __import__("os").environ["DB_NAME"] == "original-db"


def test_cli_rejects_database_name_mismatch(monkeypatch):
    from scripts import report_competition_reconciliation as cli

    class FakeDB:
        name = "unexpected"

    async def fake_connect():
        return FakeDB()

    async def fake_close():
        return None

    monkeypatch.setenv("MONGO_URL", "mongodb://readonly.invalid")
    monkeypatch.setenv("DB_NAME", "original-db")
    monkeypatch.setattr(cli, "get_db", fake_connect)
    monkeypatch.setattr(cli, "close_db", fake_close)

    with pytest.raises(ValueError, match="имя подключенной базы"):
        __import__("asyncio").run(cli._run("audit-copy", 50))
    assert __import__("os").environ["DB_NAME"] == "original-db"

def test_roundtrip_team_lookup_excludes_other_shows_with_the_same_slug():
    source=page();stored=canonical(source)
    teams=[*TEAMS,{'_id':'show-team','slug':'one','show_id':'other-show'}]
    report=reconcile_seasons([source],[stored],[TOURNAMENT],teams,max_differences=1000)
    assert report['items'][0]['canonical_roundtrip_differences']==[]
