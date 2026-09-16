"""Импорт со старого сайта: чтение SQL-дампа MODX и сборка страницы человека в формате админки. Без БД."""
import json

import pytest

from models.content import Person, PersonCreate
from routes.redirects import _try_pattern_redirect
from services.modx_content import (
    LinkMapper, clean_html, decode_entities, image_url, parse_facts_table, plain_text,
)
from services.modx_dump import ModxSite, iter_table_rows, parse_values, unescape_mysql
from services.modx_people import build_person, swap_name_order


# ─── SQL-дамп ────────────────────────────────────────────────────────────────

def test_unescape_mysql():
    assert unescape_mysql(r"it\'s \"ok\"\r\nline\\slash") == "it's \"ok\"\r\nline\\slash"
    assert unescape_mysql("a''b") == "a'b"
    assert unescape_mysql(r"100\% \_x") == r"100\% \_x"


def test_parse_values_types_and_partial_tail():
    rows, consumed, finished = parse_values("(1, 'a,b', NULL, 2.50, -3), (2, 'c')")
    assert rows == [[1, "a,b", None, 2.5, -3], [2, "c"]] and not finished
    rows, consumed, finished = parse_values("(1, 'оборванная строка")
    assert rows == [] and consumed == 0 and not finished
    rows, _, finished = parse_values("(3, 'x');")
    assert rows == [[3, "x"]] and finished


def test_iter_table_rows_skips_other_tables_and_joins_lines():
    dump = [
        "INSERT INTO `other` (`id`) VALUES\n",
        "(1);\n",
        "INSERT INTO `wanted` (`id`, `text`) VALUES\n",
        "(1, 'first'),\n",
        "(2, 'multi\n",           # литеральный перевод строки внутри значения
        "line; still text'),\n",
        "(3, 'it\\'s');\n",
        "INSERT INTO `wanted` (`id`, `text`) VALUES (4, 'one-line');\n",
    ]
    rows = list(iter_table_rows(dump, ["wanted"]))
    assert [r["id"] for _, r in rows] == [1, 2, 3, 4]
    assert rows[1][1]["text"] == "multi\nline; still text"
    assert rows[2][1]["text"] == "it's"


# ─── HTML, ссылки, факты ─────────────────────────────────────────────────────

def site_with_resources():
    site = ModxSite()
    for rid, template, alias, uri in [
        (116, 20, "anton-shastun", "people/anton-shastun.html"),
        (500, 21, "dals", "kvn/team/dals.html"),
        (30, 5, "people", "people/"),
        (77, 5, "vysshaya-liga", "kvn/vysshaya-liga/"),
    ]:
        site.resources[rid] = {"id": rid, "template": template, "alias": alias, "uri": uri}
        site.by_uri[uri.strip("/")] = rid
    return site


def test_decode_entities_keeps_markup_escapes():
    assert decode_entities("&laquo;КВН&raquo;&nbsp;&ndash; 1 &lt; 2 &amp; &quot;x&quot;") == \
        "«КВН» – 1 &lt; 2 &amp; &quot;x&quot;"


def test_link_mapper():
    site = site_with_resources()
    mapper = LinkMapper(site, _try_pattern_redirect)
    assert mapper.map("people/anton-shastun.html") == "/people/anton-shastun"
    assert mapper.map("https://humorpedia.ru/kvn/team/dals.html#games") == "/kvn/teams/dals#games"
    assert mapper.map("[[~116]]") == "/people/anton-shastun"
    assert mapper.map("kvn/vysshaya-liga") == "/kvn/vl-kvn"             # раздел → известный паттерн
    assert mapper.map("images/people/x.jpg") == "/media/imported/images/people/x.jpg"
    assert mapper.map("https://vk.com/shastoon") == "https://vk.com/shastoon"
    assert mapper.map("#note") == "#note"
    assert mapper.map("kvn/lampa/") == "/kvn/lampa/"                      # нет в дампе — старый путь
    assert mapper.unresolved == ["kvn/lampa/"]


def test_clean_html():
    mapper = LinkMapper(site_with_resources(), _try_pattern_redirect)
    html = ('<p>Шастун&nbsp;&ndash; <a href="people/anton-shastun.html">актёр</a> '
            '<img src="images/p.jpg" /></p>\r\n<p>&nbsp;</p>')
    assert clean_html(html, mapper) == \
        '<p>Шастун – <a href="/people/anton-shastun">актёр</a> <img src="/media/imported/images/p.jpg" /></p>'


def test_parse_facts_table_with_styles():
    table = ('<table style="width: 99%" border="1"><tbody>'
             '<tr style="height: 18px;"><td style="width: 49%;">Полное имя</td><td>Антон&nbsp;Шастун</td></tr>'
             '<tr><td>Дата рождения</td><td>19 апреля<br />1991 года</td></tr>'
             '<tr><td>Пусто</td><td> </td></tr></tbody></table>')
    assert parse_facts_table(table) == [("Полное имя", "Антон Шастун"), ("Дата рождения", "19 апреля 1991 года")]


def test_image_url_and_helpers():
    assert image_url("images/people/a.jpg") == "/media/imported/images/people/a.jpg"
    assert image_url("https://humorpedia.ru/images/a.jpg") == "/media/imported/images/a.jpg"
    assert image_url("") is None
    assert plain_text("<b>2010</b>&nbsp;-&nbsp;2013") == "2010 - 2013"
    assert swap_name_order("Шастун Антон") == "Антон Шастун"
    assert swap_name_order("Дуэт «Шастун и Макар»") == "Дуэт «Шастун и Макар»"


# ─── Человек ─────────────────────────────────────────────────────────────────

def shastun_site():
    site = site_with_resources()
    site.resources[116].update({
        "pagetitle": "Шастун Антон", "longtitle": "Антон Шастун", "published": 1, "deleted": 0,
        "description": "Антон Шастун – актёр.", "keywords": "Антон Шастун, Импровизация",
        "rating": 8.94, "votes": 17, "createdon": 1713441486, "publishedon": 1713441480,
    })
    info = {
        "MIGX_formname": "info",
        "subtitle": '<p>Антон Шастун&nbsp;&ndash; актёр <a href="kvn/team/dals.html">«ДАЛС»</a></p>',
        "content": "<p>Рост&nbsp;&ndash; 197 см</p>\n<p>&nbsp;</p>",
        "list_social": json.dumps([
            {"MIGX_id": 1, "link": "https://vk.com/shastoon", "name": "vk"},
            {"MIGX_id": 2, "link": "https://example.ru/", "name": "global"},
            {"MIGX_id": 3, "link": "https://x.com/a", "name": "twitter"},
        ]),
        "table": "<table><tbody><tr><td>Полное имя</td><td>Антон Андреевич Шастун</td></tr>"
                 "<tr><td>Дата рождения</td><td>19 апреля 1991 года</td></tr></tbody></table>",
    }
    timeline = {
        "MIGX_formname": "timeline",
        # list_triple встречается и строкой JSON, и уже разобранным списком
        "list_triple": [
            {"MIGX_id": "1", "title": "КВН в Воронеже", "subtitle": "2010-2013", "content": "<p>Играл в «БВ».</p>"},
            {"MIGX_id": "2", "title": "", "subtitle": "", "content": "<p>&nbsp;</p>"},
        ],
    }
    footnote = {"MIGX_formname": "text", "content": "<p>* - признан иноагентом.</p>"}
    ads = {"MIGX_formname": "ad_250"}
    site.tv_values[116] = {
        "config": json.dumps([info, ads, timeline, footnote, {"MIGX_formname": "tags"}]),
        "img": "images/people/improv-teams/anton-shastun1.jpg",
        "img_alt": "Антон Шастун",
        "tags": "13||15",
    }
    site.tags = {13: "Антон Шастун", 15: "Воронеж", 16: "Не спать"}
    site.tag_resources = {116: [15, 13, 16]}
    return site


def test_build_person_matches_admin_format():
    site = shastun_site()
    payload, extra, warnings = build_person(site, 116, LinkMapper(site, _try_pattern_redirect))

    assert payload["title"] == "Шастун Антон" and payload["full_name"] == "Антон Шастун"
    assert payload["slug"] == "anton-shastun" and payload["status"] == "published"
    assert payload["primary_tag"] == "Антон Шастун"
    assert payload["photo"] == {
        "url": "/media/imported/images/people/improv-teams/anton-shastun1.jpg", "alt": "Антон Шастун",
        "caption": "", "thumbnail": "/media/imported/images/people/improv-teams/anton-shastun1.jpg",
    }
    assert payload["facts"] == {"Полное имя": "Антон Андреевич Шастун", "Дата рождения": "19 апреля 1991 года"}
    assert payload["facts_order"] == ["Полное имя", "Дата рождения"]
    assert payload["social_links"] == {"vk": "https://vk.com/shastoon", "website": "https://example.ru/"}
    assert payload["tags"] == ["Антон Шастун", "Воронеж", "Не спать"]
    assert payload["seo"] == {"meta_title": "Шастун Антон", "meta_description": "Антон Шастун – актёр.",
                              "keywords": ["Антон Шастун", "Импровизация"]}

    types = [(m["type"], m["title"], m["order"]) for m in payload["modules"]]
    assert types == [
        ("poster_photo", "", 1), ("facts_table", "Информация", 2), ("rating_widget", "Оценка", 3),
        ("tags_cloud", "", 4), ("social_links", "Ссылки", 5),
        ("text_block", "Биография", 6), ("text_block", "Личная жизнь", 7),
        ("timeline", "Хронология", 8), ("text_block", "", 9),
    ]
    # системные модули — только настройки вида, данные в полях документа
    assert payload["modules"][0]["data"] == {"size": "medium", "shape": "rounded"}
    bio = payload["modules"][5]["data"]["content"]
    assert bio == '<p>Антон Шастун – актёр <a href="/kvn/teams/dals">«ДАЛС»</a></p>'
    assert payload["modules"][6]["data"]["content"] == "<p>Рост – 197 см</p>"
    assert payload["modules"][7]["data"]["events"] == [
        {"year": "2010-2013", "date": "", "title": "КВН в Воронеже", "description": "<p>Играл в «БВ».</p>"},
    ]

    assert extra["old_id"] == 116 and extra["old_urls"] == ["/people/anton-shastun.html"]
    assert extra["rating"] == {"average": 8.94, "count": 17} and extra["votes_count"] == 17
    assert extra["created_at"].startswith("2024-04-18") and extra["published_at"].startswith("2024-04-18")
    assert warnings == ["соцсеть «twitter» не поддерживается: https://x.com/a"]

    # тело проходит валидацию админского API и модели документа
    create = PersonCreate(**payload)
    person = Person(**{**create.model_dump(), "bio": create.bio or {}, "seo": create.seo or {}})  # как create_person
    assert person.photo.url == payload["photo"]["url"]
    assert [m.type for m in person.modules][-1] == "text_block"


@pytest.mark.parametrize("published,deleted,status", [(1, 0, "published"), (0, 0, "draft")])
def test_build_person_status_and_missing_photo(published, deleted, status):
    site = shastun_site()
    site.resources[116].update({"published": published, "deleted": deleted, "publishedon": 0,
                                "longtitle": "Антон Андреевич Шастун"})
    site.tv_values[116]["img"] = ""
    payload, extra, warnings = build_person(site, 116)
    assert payload["status"] == status and payload["photo"] is None
    assert "нет фото" in warnings
    # базовый тег — «Имя Фамилия», как по умолчанию в админке, даже если полное имя с отчеством
    assert payload["full_name"] == "Антон Андреевич Шастун" and payload["primary_tag"] == "Антон Шастун"
    # дата публикации не заполнена в MODX → дата создания
    assert extra.get("published_at") == (extra["created_at"] if status == "published" else None)
