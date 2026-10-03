"""Проверки сохранности страниц при импорте редакционных сезонов."""

from copy import deepcopy

import pytest

from scripts.import_show_seasons_2026 import TARGETS, prepare_modules, render_table, validate
from services.show_appearances import Tree, table_grid, text


def season(slug="standup"):
    show_id, number, layout = TARGETS[slug]
    return {"slug": slug, "id": show_id, "season": number, "layout": layout,
            "heading": f"Сезон {number} (2025–2026)", "after_module_id": "old-table",
            "source": {"url": "https://docs.google.com/spreadsheets/d/example/edit"},
            "episode_numbers": [1, 2], "rows": [
                {"name": "Комик <имя>", "performances": 1, "marks": ["+", ""]},
                {"name": "Ведущий", "performances": 1, "marks": ["В", "+В"]}]}


def show(s):
    return {"_id": s["id"], "slug": s["slug"], "modules": [
        {"id": "old-table", "type": "text_block", "title": "Выпуски", "order": 19,
         "data": {"content": "<table>Старый состав</table>", "collapsed": False}},
        {"id": "credits", "type": "text_block", "title": "", "order": 20,
         "data": {"content": "Производство и продюсеры"}}]}


def test_old_content_preserved_and_second_import_is_noop():
    s = season()
    before = show(s)
    modules, changed = prepare_modules(before, s)
    assert changed
    assert before == show(s)  # Чистая функция не меняет исходный документ.
    assert modules[0] == before["modules"][0]
    assert {k: v for k, v in modules[-1].items() if k != "order"} == {
        k: v for k, v in before["modules"][-1].items() if k != "order"}
    assert [m["order"] for m in modules] == [19, 20, 21, 22]
    again, changed = prepare_modules({**before, "modules": modules}, s)
    assert not changed and again == modules


def test_editor_changes_are_not_overwritten():
    s = season()
    before = show(s)
    modules, _ = prepare_modules(before, s)
    modules[2]["data"]["content"] += "<p>Редакторское дополнение</p>"
    with pytest.raises(ValueError, match="изменён редактором"):
        prepare_modules({**before, "modules": modules}, s)


def test_manual_duplicate_season_is_rejected():
    s = season()
    before = show(s)
    before["modules"].append({"id": "manual", "title": "", "data": {"content": "<h2>Сезон 13</h2>"}})
    with pytest.raises(ValueError, match="другими ID"):
        prepare_modules(before, s)


def test_validation_counts_performances_separately_from_hosting():
    payload = {"schema_version": 1, "seasons": [season(), season("standupwomen")]}
    validate(payload)
    bad = deepcopy(payload)
    bad["seasons"][0]["rows"][1]["performances"] = 2
    with pytest.raises(ValueError, match="не сходится"):
        validate(bad)
    bad = deepcopy(payload)
    bad["seasons"][0]["rows"][1]["marks"] = ["?", "+В"]
    with pytest.raises(ValueError, match="Неверные отметки"):
        validate(bad)
    bad = deepcopy(payload)
    bad["seasons"][0]["rows"].append(deepcopy(bad["seasons"][0]["rows"][0]))
    with pytest.raises(ValueError, match="дубль"):
        validate(bad)


@pytest.mark.parametrize("slug", ["standup", "standupwomen"])
def test_html_table_layout_and_host_markers(slug):
    s = season(slug)
    html = render_table(s)
    assert "Комик &lt;имя&gt;" in html
    table = next(Tree(html).root.find("table"))
    grid = [[text(c) for c in row] for row in table_grid(table)]
    assert all(len(row) == 4 for row in grid)
    assert grid[-1] == (["Ведущий", "1", "В", "+В"] if slug == "standup" else ["Ведущий", "В", "+В", "1"])
    assert "данные на июнь 2026 года" in html
