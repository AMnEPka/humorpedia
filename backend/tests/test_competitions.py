"""Модель соревнований: конвертация season_data ⇄ сезон, перекрёстные ссылки, правка сезона. Без БД."""
import copy

import pytest

from services.competitions import (
    TeamLookup, apply_season_update, build_participations, legacy_to_season, season_to_legacy,
    stable_id, stage_code, unresolved_participants,
)

TEAMS = [
    {"_id": "team-odessa", "slug": "odesskie-gentlmeni"},
    {"_id": "team-visi", "slug": "visi"},
    {"_id": "team-ermi", "slug": "ermi"},
]
TOURNAMENT = {"_id": "t-vl", "slug": "vl-kvn", "show": "kvn", "participant_type": "team"}


def legacy_page():
    """Страница сезона в формате реальных данных (включая старые/нестандартные варианты)."""
    return {
        "_id": "page-1987",
        "slug": "vl-1987",
        "title": "Сезон 1986-87 Высшей лиги",
        "full_path": "kvn/vl-kvn/vl-1987",
        "status": "published",
        "season_data": {
            "league_slug": "vl-kvn",
            "league_name": "Высшая лига",
            "year": 1987,
            "season_number": 1,
            "intro_html": "<p>Первый сезон</p>",
            "metadata": {"сезон": "1", "ведущий": "Александр Масляков"},
            "jury": ["Юлий Гусман"],
            "hosts": [], "editors": [], "host": "", "extra_sections": [],
            "late_joined_teams": [{"name": "ЕрМИ", "stage": "Финал", "note": "финалисты прошлого сезона"}],
            "prev_season": "", "next_season": "vl-1988",
            "all_teams": [
                {"slug": "odesskie-gentlmeni", "name": "Одесские джентльмены (Одесса)", "city": "Одесса"},
                {"slug": "visi", "name": "ВИСИ (Воронеж)"},
                {"slug": "ermi", "name": "ЕрМИ", "city": ""},
            ],
            "winners": [{"name": "Одесские джентльмены (Одесса)", "slug": "odesskie-gentlmeni"}],
            "custom_flag": True,
            "stages": [
                {
                    "name": "1/4 финала", "order": 1, "notes": "", "additional_teams": [], "additional_notes": "",
                    "games": [{
                        "name": "Первая 1/4 финала", "order": 1, "date": "1986-12-01", "contests": ["Приветствие"],
                        "jury": ["Юлий Гусман"], "host": "", "notes": "",
                        "teams": [
                            {"team_slug": "odesskie-gentlmeni", "team_name": "ОГУ", "place": 1, "total": 5,
                             "scores": {"Приветствие": 5}, "passed": True, "is_winner": False,
                             "is_additional": False, "city": "Одесса", "team_id": "team-odessa"},
                            {"team_slug": "visi", "team_name": "ВИСИ", "place": 2, "total": 4.5,
                             "scores": {"Приветствие": 4.5}, "passed": False, "is_winner": False,
                             "is_additional": False, "city": "Воронеж"},
                            {"team_slug": "", "team_name": "ДПИ", "place": 3, "total": 1,
                             "scores": {"Прив": 1}, "passed": False, "is_winner": False,
                             "is_additional": False, "city": ""},
                        ],
                    }],
                },
                {
                    "name": "Утешительный полуфинал", "order": 2.5, "notes": "", "additional_teams": ["ВИСИ"],
                    "additional_notes": "", "games": [],
                },
                {
                    "name": "Финал", "order": 3, "notes": "", "additional_teams": [], "additional_notes": "",
                    "games": [{
                        "id": "game-final", "date_raw": "декабрь 1987", "is_cancelled": False,
                        "name": "Финал", "order": 1, "date": "1987-12-20", "contests": [], "jury": [], "host": "",
                        "notes": "",
                        "teams": [
                            {"team_slug": "odesskie-gentlmeni", "team_name": "ОГУ", "place": 1, "total": 20,
                             "scores": {}, "passed": False, "is_winner": True, "is_additional": False,
                             "city": "Одесса", "team_link": "kvn/team/odesskie-gentlmeni.html"},
                            {"team_slug": "ermi", "team_name": "ЕрМИ", "place": 2, "total": 18,
                             "scores": {}, "passed": False, "is_winner": False, "is_additional": True, "city": ""},
                        ],
                    }],
                },
            ],
        },
    }


@pytest.fixture
def lookup():
    return TeamLookup(TEAMS)


def without_computed(sd):
    return {k: v for k, v in sd.items() if k not in ("prev_season", "next_season")}


def test_roundtrip_is_lossless(lookup):
    page = legacy_page()
    season = legacy_to_season(page, TOURNAMENT, lookup)
    assert season_to_legacy(season) == without_computed(page["season_data"])


def test_roundtrip_is_stable(lookup):
    page = legacy_page()
    first = legacy_to_season(page, TOURNAMENT, lookup)
    page2 = copy.deepcopy(page)
    page2["season_data"] = season_to_legacy(first)
    second = legacy_to_season(page2, TOURNAMENT, lookup)
    for key in ("created_at", "updated_at"):
        first.pop(key, None), second.pop(key, None)
    assert first == second


def test_season_ids_are_deterministic(lookup):
    a = legacy_to_season(legacy_page(), TOURNAMENT, lookup)
    b = legacy_to_season(legacy_page(), TOURNAMENT, lookup)
    assert a["_id"] == b["_id"] == stable_id("kvn-page", "page-1987")
    assert [g["id"] for s in a["stages"] for g in s["games"]] == [g["id"] for s in b["stages"] for g in s["games"]]


def test_duplicate_game_ids_get_unique_internal_ids(lookup):
    page = legacy_page()
    stages = page["season_data"]["stages"]
    stages[0]["games"][0]["id"] = "1-4-финала-1"
    stages[2]["games"][0]["id"] = "1-4-финала-1"  # скопирован между этапами, как в реальных данных
    season = legacy_to_season(page, TOURNAMENT, lookup)
    ids = [g["id"] for s in season["stages"] for g in s["games"]]
    assert len(set(ids)) == len(ids)
    rows = build_participations(season)
    assert len({r["_id"] for r in rows}) == len(rows)
    assert season_to_legacy(season) == without_computed(page["season_data"])


def test_team_references_resolved(lookup):
    season = legacy_to_season(legacy_page(), TOURNAMENT, lookup)
    assert [t["team_id"] for t in season["teams"]] == ["team-odessa", "team-visi", "team-ermi"]
    assert season["winners"][0]["team_id"] == "team-odessa"
    results = season["stages"][0]["games"][0]["results"]
    assert [r["team_id"] for r in results] == ["team-odessa", "team-visi", None]
    assert results[1]["total"] == 4.5
    assert season["stages"][1]["order"] == 2.5
    assert season["stages"][1]["code"] == "consolation"


def test_missing_year_taken_from_slug(lookup):
    page = legacy_page()
    del page["season_data"]["year"]
    season = legacy_to_season(page, TOURNAMENT, lookup)
    assert season["year"] == 1987


def test_old_string_winners_format(lookup):
    page = legacy_page()
    page["season_data"]["winners"] = ["odesskie-gentlmeni"]
    season = legacy_to_season(page, TOURNAMENT, lookup)
    assert season["winners"][0]["team_id"] == "team-odessa"


@pytest.mark.parametrize("name,code", [
    ("1/8 финала", "1/8"), ("1/4 финала", "1/4"), ("1/2 финала", "1/2"), ("Полуфинал", "1/2"),
    ("Финал", "final"), ("Утешительная игра", "consolation"), ("1/8 + 1/4 финала", ""), ("Кубок мэра", ""),
])
def test_stage_code(name, code):
    assert stage_code(name) == code


def test_participations(lookup):
    season = legacy_to_season(legacy_page(), TOURNAMENT, lookup)
    rows = build_participations(season)
    games = [r for r in rows if r["kind"] == "game"]
    summaries = {r["participant_key"]: r for r in rows if r["kind"] == "season"}

    assert len(games) == 5
    assert len({r["_id"] for r in rows}) == len(rows)

    odessa = summaries["team:team-odessa"]
    assert odessa["is_champion"] and odessa["in_season_list"]
    assert odessa["games_played"] == 2 and odessa["wins"] == 2
    assert odessa["best_stage_code"] == "final"
    assert odessa["season_year"] == 1987 and odessa["season_path"] == "kvn/vl-kvn/vl-1987"

    visi = summaries["team:team-visi"]
    assert visi["best_stage_code"] == "1/4" and not visi["last_stage_passed"] and not visi["is_champion"]

    ermi = summaries["team:team-ermi"]
    assert ermi["best_stage_code"] == "final" and ermi["games_played"] == 1

    # участник без slug и без команды тоже попадает (для ручной привязки)
    assert summaries["name:дпи"]["team_id"] is None


def test_unresolved(lookup):
    season = legacy_to_season(legacy_page(), TOURNAMENT, lookup)
    unresolved = unresolved_participants(season)
    assert unresolved == [{"where": "results", "stage": "1/4 финала", "game": "Первая 1/4 финала", "slug": "", "name": "ДПИ"}]


def test_apply_update_resolves_teams_and_assigns_ids(lookup):
    season = legacy_to_season(legacy_page(), TOURNAMENT, lookup)
    update = {
        "year": 1988,
        "jury": ["Юлий Гусман", "Леонид Якубович"],
        "teams": [{"slug": "visi", "name": "ВИСИ"}, {"team_id": "team-ermi", "name": "ЕрМИ"}, {"team_id": "ghost", "name": "Призрак"}],
        "stages": [{
            "name": "Финал",
            "games": [{"name": "Финал", "results": [
                {"slug": "ermi", "name": "ЕрМИ", "place": 1, "total": 10},
                {"team_id": "team-visi", "name": "ВИСИ", "place": 2},
            ]}],
        }],
    }
    updated = apply_season_update(season, update, lookup)

    assert updated["year"] == 1988
    assert season["year"] == 1987, "исходный документ не меняется"
    assert [t["team_id"] for t in updated["teams"]] == ["team-visi", "team-ermi", None]
    assert updated["teams"][1]["slug"] == "ermi"

    stage = updated["stages"][0]
    assert stage["id"] and stage["code"] == "final" and stage["order"] == 1
    game = stage["games"][0]
    assert game["id"] and game["order"] == 1
    assert [r["team_id"] for r in game["results"]] == ["team-ermi", "team-visi"]

    legacy = season_to_legacy(updated)
    assert legacy["year"] == 1988
    assert legacy["stages"][0]["games"][0]["id"] == game["id"]
    assert legacy["stages"][0]["games"][0]["teams"][1]["team_slug"] == "visi"
