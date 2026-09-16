"""Импорт со старого сайта: чтение SQL-дампа MODX и сборка страницы человека в формате админки. Без БД."""
import json

import pytest

from models.content import Person, PersonCreate
from routes.redirects import _try_pattern_redirect
from services.link_resolver import collect_keys, direct_query, link_key, replace_links
from services.modx_content import (
    LinkMapper, clean_html, decode_entities, image_url, parse_facts_table, plain_text, rewrite_links,
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


# ─── Ссылки: перевод сохранённого контента и выдача на сайт ──────────────────

def test_mapper_prefers_migrated_page_by_old_id():
    site = site_with_resources()
    mapper = LinkMapper(site, _try_pattern_redirect, known_urls={77: "/kvn/vl-kvn", 500: "/kvn/teams/dals-renamed"})
    assert mapper.map("kvn/vysshaya-liga/") == "/kvn/vl-kvn"
    assert mapper.map("[[~500]]") == "/kvn/teams/dals-renamed"
    assert mapper.map("/people/anton-shastun") == "/people/anton-shastun"   # новые адреса не трогаются


def test_rewrite_links_changes_only_attributes():
    mapper = LinkMapper(site_with_resources(), _try_pattern_redirect)
    html = ('<p style="x">&laquo;Текст&raquo; <a href="kvn/team/dals.html" target="_blank">ДАЛС</a> '
            '<a href="https://vk.com/a?b=1&amp;c=2">vk</a> <img src="images/t.jpg"></p>')
    assert rewrite_links(html, mapper) == (
        '<p style="x">&laquo;Текст&raquo; <a href="/kvn/teams/dals" target="_blank">ДАЛС</a> '
        '<a href="https://vk.com/a?b=1&amp;c=2">vk</a> <img src="/media/imported/images/t.jpg"></p>')


def test_link_key_and_direct_query():
    assert link_key("/people/anton-shastun") == "people/anton-shastun"
    assert link_key("people/x.html") == "people/x.html"
    assert link_key("https://humorpedia.ru/kvn/teams/dals#a") == "kvn/teams/dals"
    assert link_key("[[~116]]") == "~116"
    for skipped in ("https://vk.com/x", "#top", "/people", "/tags/КВН", "/media/imported/images/a.jpg", "mailto:a@b.c"):
        assert link_key(skipped) is None
    assert direct_query("people/anton-shastun") == ("people", "slug", "anton-shastun")
    assert direct_query("kvn/teams/dals") == ("teams", "slug", "dals")
    assert direct_query("kvn/vl-kvn/vl-2015") == ("kvn", "full_path", "kvn/vl-kvn/vl-2015")
    assert direct_query("shows/igra/season-1") == ("shows", "full_path", "igra/season-1")
    assert direct_query("city/voronezh") == ("cities", "slug", "voronezh")
    assert direct_query("proekty/standup.html") is None


def test_replace_links_missing_pages_become_text():
    html = ('<p><a href="/people/anton-shastun" class="x">Шастун</a>, <a href="people/old.html"><b>Старый</b></a>, '
            '<a href="/people/nobody">Никто</a>, <a href="https://vk.com/a">vk</a>, <a href="#n">сноска</a></p>')
    keys = collect_keys(html)
    assert keys == {"people/anton-shastun", "people/old.html", "people/nobody"}
    targets = {"people/anton-shastun": "/people/anton-shastun", "people/old.html": "/people/new-slug",
               "people/nobody": None}
    assert replace_links(html, targets) == (
        '<p><a href="/people/anton-shastun" class="x">Шастун</a>, <a href="/people/new-slug"><b>Старый</b></a>, '
        'Никто, <a href="https://vk.com/a">vk</a>, <a href="#n">сноска</a></p>')


# ─── Шоу ─────────────────────────────────────────────────────────────────────

from services.modx_shows import build_show, is_show_page, section_id, show_path, show_url_builder, strip_nav_paragraph  # noqa: E402


def shows_site():
    site = ModxSite()
    rows = [
        # id, template, parent, alias, uri, pagetitle, longtitle
        (33, 12, 0, "show", "show/", "Шоу", ""),
        (1629, 19, 33, "comedy-battle", "comedy-battle/", "Comedy Баттл", ""),
        (1703, 19, 1629, "season1", "comedy-battle/season1.html", "Comedy Баттл 1 сезон", ""),
        (1618, 25, 33, "improv-teams", "improv-teams/", "ИК", "Импровизация. Команды"),
        (1673, 19, 1618, "team", "improv-teams/team.html", "Команды ИК", ""),
        (1905, 19, 1673, "baikalskiye", "improv-teams/baikalskiye.html", "Байкальские", ""),
        (1771, 19, 1618, "team", "liga-gorodov/team/", "Команды ЛГ", ""),
        (2000, 21, 1771, "eto-oni-lg", "liga-gorodov/team/eto-oni-lg.html", "Это они (ЛГ)", ""),
        (682, 20, 30, "natalya-andreevna", "people/natalya-andreevna.html", "Еприкян Наталья", "Наталья Еприкян"),
    ]
    for rid, template, parent, alias, uri, title, longtitle in rows:
        site.resources[rid] = {"id": rid, "template": template, "parent": parent, "alias": alias, "uri": uri,
                               "pagetitle": title, "longtitle": longtitle, "published": 1, "deleted": 0,
                               "menuindex": 3, "description": "Описание шоу", "keywords": "", "rating": 9.5,
                               "votes": 4, "createdon": 1713441486, "publishedon": 0}
        site.by_uri[uri.strip("/")] = rid
    return site


def test_show_tree_paths_and_team_pages_excluded():
    site = shows_site()
    root = section_id(site)
    assert root == 33
    assert show_path(site, site.resources[1703], root) == "comedy-battle/season1"
    assert is_show_page(site, site.resources[1703], root)
    assert is_show_page(site, site.resources[1673], root)          # страница-список «Команды ИК» — раздел шоу
    assert not is_show_page(site, site.resources[1905], root)      # команда внутри «Команды …»
    assert not is_show_page(site, site.resources[2000], root)      # шаблон «Команда»
    assert not is_show_page(site, site.resources[682], root)       # вне раздела
    mapper = LinkMapper(site, _try_pattern_redirect, url_builders=[show_url_builder(site)])
    assert mapper.map("comedy-battle/season1.html") == "/shows/comedy-battle/season1"
    assert mapper.map("/comedy-battle/season1") == "/shows/comedy-battle/season1"   # путь без .html
    assert mapper.map("improv-teams/") == "/shows/improv-teams"


def test_strip_nav_paragraph():
    html = '<p><a href="/x">&lt; Смех без правил</a> &nbsp; <a href="/y">Турнир &gt;</a></p><p>Текст</p>'
    assert strip_nav_paragraph(html) == "<p>Текст</p>"
    assert strip_nav_paragraph("<p>Обычный <a href='/x'>текст</a></p>") == "<p>Обычный <a href='/x'>текст</a></p>"


def test_build_show_sections():
    site = shows_site()
    info = {"MIGX_formname": "info",
            "table": "<table><tr><td>Статус шоу</td><td>Завершено</td></tr><tr><td>Дата премьеры</td><td>28 августа 2010 года</td></tr></table>",
            "list_social": [{"link": "https://premier.one/show/x", "name": "global"}]}
    config = {  # объект с ключами-номерами, а не список
        "1": info,
        "2": {"MIGX_formname": "text", "title": "Comedy Баттл",
              "content": "<p>&lt; <a href=\"smeh-bez-pravil/\">СБП</a></p><p>Шоу на ТНТ.</p>"},
        "3": {"MIGX_formname": "text", "title": "Сезоны и победители", "content": "<p>...</p>"},
        "4": {"MIGX_formname": "table", "content": "<table><tr><td>Сезон</td></tr></table>"},
        "5": {"MIGX_formname": "people_cards", "title": "Основной состав", "list_people": json.dumps([
            {"photo": "images/cw/natalya.jpg", "link": "682", "list_double": json.dumps([
                {"title": "Сценическое имя", "content": "<p>Наталья Андреевна</p>"},
                {"title": "Выпуски", "content": "<p>237</p>"}])}])},
        "6": {"MIGX_formname": "post_footer"},
        "7": {"MIGX_formname": "tags"},
    }
    site.tv_values[1629] = {"config": json.dumps(config), "img": "images/shows/comedy-battle.jpg"}
    payload, extra, warnings = build_show(site, 1629, LinkMapper(site, _try_pattern_redirect))

    assert payload["title"] == payload["name"] == "Comedy Баттл" and payload["slug"] == "comedy-battle"
    assert payload["facts"] == {"Статус шоу": "Завершено", "Дата премьеры": "28 августа 2010 года"}
    assert payload["facts_order"] == ["Статус шоу", "Дата премьеры"]
    assert payload["social_links"] == {"website": "https://premier.one/show/x"}
    assert payload["poster"]["url"] == "/media/imported/images/shows/comedy-battle.jpg"
    assert payload["order"] == 3 and payload["description"] == "Описание шоу"
    content = [(m["type"], m["title"]) for m in payload["modules"][5:]]
    # заголовок = название страницы не повторяется; «Сезоны и победители» переходит к таблице
    assert content == [("text_block", ""), ("text_block", "Сезоны и победители"), ("participants", "Основной состав")]
    assert payload["modules"][5]["data"]["content"] == "<p>Шоу на ТНТ.</p>"
    assert payload["modules"][7]["data"]["items"] == [{
        "name": "Наталья Андреевна", "person_slug": "natalya-andreevna",
        "photo": "/media/imported/images/cw/natalya.jpg",
        "facts": [{"title": "Сценическое имя", "value": "Наталья Андреевна"}, {"title": "Выпуски", "value": "237"}],
    }]
    assert extra["old_urls"] == ["/comedy-battle"] and extra["rating"] == {"average": 9.5, "count": 4}
    assert extra["published_at"] == extra["created_at"]
    assert warnings == []

    from models.content import Show, ShowCreate
    create = ShowCreate(**payload)
    Show(**{**create.model_dump(), "seo": create.seo or {}, "related_person_ids": []})  # как create_show


def test_build_show_title_from_longtitle():
    site = shows_site()
    site.tv_values[1618] = {"config": "[]"}
    payload, _, warnings = build_show(site, 1618)
    assert payload["title"] == "Импровизация. Команды" and "на странице нет текста" in warnings
