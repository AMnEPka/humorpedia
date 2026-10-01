"""Границы конкурсных результатов и сохранность редакционного контента."""

from copy import deepcopy
from hashlib import sha256

import pytest

from scripts.update_zvezdy_season3 import (
    DIRECTORY, REPLACEMENTS, ROOT, SEASON, module, put_module, results_table,
    roster_module, roster_table, season_modules, team_payload, validate,
)
from services.memberships import parse_roster_html
from services.show_appearances import Tree, table_grid, text


def package():
    groups = [["astana", "mechty", "moved", "friends"], ["actors", "regions", "fighters", "red"], ["boys", "spiders", "napoleon"]]
    scores = [[[4, 4, 4, 4, 3], [3, 3, 3, 3, 4], [2] * 5, [1] * 5],
              [[4] * 5, [3, 3, 3, 2, 3], [2, 1, 2, 3, 2], [1, 2, 1, 1, 1]],
              [[3, 2, 3, 2, 3], [2, 3, 2, 3, 2], [1] * 5]]
    teams, festivals = [], []
    for number, slugs in enumerate(groups, 1):
        results = []
        for i, slug in enumerate(slugs):
            teams.append({"slug": slug, "name": slug, "stars": ["Иван Абрамов"], "festival": number, "guest": False})
            results.append({"slug": slug, "scores": scores[number-1][i], "total": sum(scores[number-1][i]), "passed": i < len(slugs)-1})
        festivals.append({"number": number, "date": f"2026-09-{number*7-2:02d}", "results": results, "source": "https://example.org/report"})
    teams.append({"slug": "kamyzyaki", "name": "Камызяки", "stars": ["Лёша Янгер"], "festival": 3, "guest": True})
    festivals[-1]["guests"] = ["kamyzyaki"]
    return {"schema_version": 1, "show_id": ROOT, "season_id": SEASON, "teams_page_id": DIRECTORY,
            "as_of": "2026-10-01", "teams": teams, "festivals": festivals, "judges": ["К", "Х", "С", "И", "Л"],
            "duels": [["astana", "actors"], ["mechty", "regions"], ["moved", "boys"], ["fighters", "spiders"]],
            "sources": {"announcement": "https://example.org/announcement", "festival3": "https://example.org/f3"}}


def test_complete_festivals_and_eight_duel_teams():
    data = package()
    assert len(validate(data)) == 12
    bad = deepcopy(data)
    bad["festivals"][0]["results"][0]["total"] += 1
    with pytest.raises(ValueError, match="сумма"):
        validate(bad)
    bad = deepcopy(data)
    bad["duels"][0][0] = "kamyzyaki"
    with pytest.raises(ValueError, match="восьми прошедшим"):
        validate(bad)


def test_guest_has_no_score_and_mizulina_is_not_second_star():
    data = package()
    refs = validate(data)
    html = results_table(data["festivals"][2], refs, [], data["judges"])
    grid = [[text(c) for c in row] for row in table_grid(next(Tree(html).root.find("table")))]
    assert len(grid) == 4  # Заголовок + три конкурсных результата, без строки с нулём.
    assert not any("Камызяки" in row[0] for row in grid)
    assert "без" not in grid[-1][-1]  # Обычное выбывание Наполеонов, не гостевой статус.
    roster = roster_table(data, [])
    assert "Лёша Янгер" in roster and "Екатерина Мизулина как гость" in roster
    bad = deepcopy(data)
    bad["teams"][-1]["stars"].append("Екатерина Мизулина")
    with pytest.raises(ValueError, match="роль"):
        validate(bad)


def test_roster_heading_does_not_create_fake_member_and_known_person_is_linked():
    team = {"slug": "boys", "stars": ["Илья Соболев"], "members": ["Кирилл Мазур"]}
    people = [{"title": "Илья Соболев", "full_name": "Илья Соболев", "slug": "ilya-sobolev", "status": "published"}]
    html = roster_module(team, people)["data"]["content"]
    parsed = parse_roster_html(html)
    assert [r["person_name"] for r in parsed["entries"]] == ["Илья Соболев", "Кирилл Мазур"]
    assert parsed["entries"][0]["roles"] == ["звезда"]
    assert parsed["entries"][0]["person_slug"] == "ilya-sobolev"
    assert parsed["entries"][0]["from_year"] == 2026


def test_module_addition_is_idempotent_and_preserves_editor_changes():
    modules = [{"id": "old", "order": 9, "data": {"content": "Старый текст"}}]
    addition = module("new", "Фестиваль", "Новый текст")
    put_module(modules, addition)
    assert modules[0]["data"]["content"] == "Старый текст"
    assert modules[1]["order"] == 10
    put_module(modules, addition)
    assert len(modules) == 2
    modules[1]["data"]["content"] += " Правка редактора"
    with pytest.raises(ValueError, match="изменён редактором"):
        put_module(modules, addition)


def test_changed_original_season_is_rejected_before_writing():
    data = package()
    page = {"modules": [{"id": ident, "order": i, "data": {"content": "Исходный текст"}} for i, ident in enumerate(REPLACEMENTS)]}
    data["expected_content_hashes"] = {ident: sha256("Исходный текст".encode()).hexdigest() for ident in REPLACEMENTS}
    result = season_modules(page, data, [])
    assert len(result) == len(page["modules"]) + 5
    assert page["modules"][0]["data"]["content"] == "Исходный текст"
    page["modules"][0]["data"]["content"] = "Новая ручная правка"
    with pytest.raises(ValueError, match="изменился после исследования"):
        season_modules(page, data, [])


def test_new_team_has_description_roster_and_festival_result():
    data = package()
    team = data["teams"][0] | {"description": "Описание команды", "members": ["Участник"], "cast_source": "https://example.org/cast"}
    card = team_payload(team, data, [])
    assert card.show_id == ROOT and card.status.value == "published"
    assert card.primary_tag == team["name"] + " (Звёзды на НТВ)"
    assert card.facts["Результат фестиваля"] == "19 баллов; проход в дуэли"
    assert len(card.modules) == 3
