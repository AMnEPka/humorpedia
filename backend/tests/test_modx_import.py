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
        (1703, 19, 1629, "comedy-season-1", "comedy-battle/season1.html", "Comedy Баттл 1 сезон", ""),
        (1618, 25, 33, "improv-kom", "improv-teams/", "ИК", "Импровизация. Команды"),
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


# ─── Длинные страницы: разделы, спойлеры, таблицы (Убойная лига) ─────────────

from services.modx_content import clean_office_tables, extract_details, split_by_headings, table_rows  # noqa: E402
from services.modx_shows import _ubojnaya_liga  # noqa: E402


def test_split_headings_and_details():
    html = "<p>Вступление</p><h3>Правила</h3><ul><li>1</li></ul><details><summary>Статистика</summary><p>Л</p></details><h3>Жюри</h3><p>Ж</p>"
    body, details = extract_details(html)
    assert details == [("Статистика", "<p>Л</p>")]
    assert split_by_headings(body) == [("", "<p>Вступление</p>"), ("Правила", "<ul><li>1</li></ul>"), ("Жюри", "<p>Ж</p>")]


def test_table_rows_and_office_cleanup():
    headers, rows = table_rows("<table><thead><tr><th>ФИО</th><th>в банк&nbsp;₽</th></tr></thead>"
                               "<tbody><tr><td class='xl64'>Дуэт \"Компот\"</td><td>1056000</td></tr></tbody></table>")
    assert headers == ["ФИО", "в банк ₽"] and rows == [['Дуэт "Компот"', "1056000"]]
    excel = ('<div class="big-table"><br /><table border="0" width="624"><colgroup><col width="100" /></colgroup><tbody>'
             '<tr><td class="xl89" width="100" height="21"><strong>Выпуск</strong></td><td class="xl96" colspan="8">1</td></tr>'
             '<tr><td id="green_table" class="xl103" colspan="2" height="20">Денис Косяков</td>'
             '<td id="green_table" class="xl105">\u00a0</td><td rowspan="1">0</td></tr></tbody></table>\u00a0</div>')
    assert clean_office_tables(excel) == (
        '<table><tbody><tr><td><strong>Выпуск</strong></td><td colspan="8">1</td></tr>'
        '<tr><td colspan="2"><mark data-color="#bbf7d0" style="background-color: #bbf7d0; color: inherit">Денис Косяков</mark></td>'
        '<td>\u00a0</td><td>0</td></tr></tbody></table>')


def test_ubojnaya_liga_layout():
    def episode(n):
        return (f'<div class="big-table"><table><tbody><tr><td><strong>Выпуск</strong></td><td colspan="8"><strong>{n}</strong></td></tr>'
                f'<tr><td id="green_table">Победитель {n}</td></tr></tbody></table></div>')
    html = ("<p>«Убойная лига» — шоу.</p><h3>Правила</h3><ul><li>6 участников</li></ul>"
            "<h3>Личная статистика участников</h3><ul><li>48 участников</li></ul><p>\u00a0</p>"
            "<details><summary>Посмотреть подробную статистику участников</summary><p>Легенда: «В банк» — деньги.</p>"
            "<table class=\"table_sort\"><thead><tr><th>ФИО</th><th>Победы</th></tr></thead>"
            "<tbody><tr><td>Дуэт «Быдло»</td><td>20</td></tr></tbody></table></details>"
            "<details><summary>Полная статистика выпусков:</summary>" + episode(1) + episode(14) + episode(15) + episode(125) +
            "</details><p>\u00a0</p><p>* - признана в РФ иностранным агентом.</p>")
    warnings = []
    modules = _ubojnaya_liga([("text_block", "", {"title": "", "content": html})], warnings)
    assert warnings == []
    assert [(t, title) for t, title, _ in modules] == [
        ("text_block", ""), ("text_block", "Правила"), ("text_block", "Личная статистика участников"),
        ("table", "Подробная статистика участников"),
        ("text_block", "Статистика выпусков: 1-й сезон (выпуски 1–14)"),
        ("text_block", "Статистика выпусков: 2-й сезон (выпуски 15–86)"),
        ("text_block", "Статистика выпусков: 3-й сезон (выпуски 87–125)"),
        ("text_block", ""),
    ]
    assert modules[2][2]["content"] == "<ul><li>48 участников</li></ul>"
    table = modules[3][2]
    assert table["headers"] == ["ФИО", "Победы"] and table["rows"] == [["Дуэт «Быдло»", "20"]]
    assert table["sortable"] and table["collapsed"] and table["description"] == "Легенда: «В банк» — деньги."
    first_season = modules[4][2]
    assert first_season["collapsed"] and first_season["content"].count("<table>") == 2
    assert "<mark" in first_season["content"] and "big-table" not in first_season["content"]
    assert modules[-1][2]["content"] == "<p>* - признана в РФ иностранным агентом.</p>"


def test_show_text_blocks_generic():
    from services.modx_shows import text_blocks
    long_text = "<p>" + "Текст. " * 800 + "</p>"
    html = (f'<p>Вступление <span class="highlight">кино</span>театр</p><h3>Правила</h3>{long_text}<h3>Жюри</h3><p>Ж</p>'
            '<details><summary>Статистика участников:</summary><p>Легенда</p><table class="table_sort"><thead><tr><th>ФИО</th><th>Победы</th></tr></thead>'
            '<tbody><tr><td>А</td><td>2</td></tr></tbody></table></details>'
            '<p>Между спойлерами</p>'
            '<details><summary>Выпуски</summary><div class="big-table"><table width="600"><tr><td id="green_table" class="xl65">Победитель</td></tr></table></div></details>')
    blocks = text_blocks("", html)
    assert [(t, title, bool(d.get("collapsed"))) for t, title, d in blocks] == [
        ("text_block", "", False), ("text_block", "Правила", False), ("text_block", "Жюри", False),
        ("table", "Статистика участников", True), ("text_block", "", False), ("text_block", "Выпуски", True),
    ]
    assert blocks[0][2]["content"] == "<p>Вступление кинотеатр</p>"
    assert blocks[3][2]["rows"] == [["А", "2"]] and blocks[3][2]["description"] == "Легенда"
    assert blocks[5][2]["content"].startswith("<table><tr><td><mark") and "big-table" not in blocks[5][2]["content"]
    # короткий текст с заголовком не режется
    assert [t for t, _, _ in text_blocks("Схема", "<h3>А</h3><p>1</p><h3>Б</h3><p>2</p>")] == ["text_block"]


def test_team_like_wiki_pages_are_not_shows():
    site = shows_site()
    site.resources[1760] = {"id": 1760, "template": 19, "parent": 1629, "alias": "de-rishele", "uri": "ls/team/de-rishele.html",
                            "pagetitle": "Де Ришелье", "deleted": 0}
    site.tv_values[1760] = {"config": json.dumps([{"MIGX_formname": "info",
                                                   "table": "<table><tr><td>Город</td><td>Одесса</td></tr><tr><td>Капитан</td><td>В. Катан</td></tr></table>"}])}
    assert not is_show_page(site, site.resources[1760], 33)
    # студия: год основания есть, города и капитана нет — это шоу
    site.resources[1659] = {"id": 1659, "template": 25, "parent": 33, "alias": "kvartal-95", "uri": "kvartal-95/",
                            "pagetitle": "Студия Квартал-95", "deleted": 0}
    site.tv_values[1659] = {"config": json.dumps([{"MIGX_formname": "info",
                                                   "table": "<table><tr><td>Год основания</td><td>2003</td></tr></table>"}])}
    assert is_show_page(site, site.resources[1659], 33)


# ─── Команды шоу ─────────────────────────────────────────────────────────────

from models.content import TeamCreate  # noqa: E402
from services.modx_content import balance_html, fact_cell_html, first_heading  # noqa: E402
from services.modx_show_teams import (  # noqa: E402
    build_show_team, link_builders, misplaced_show_team_builder, show_team_pages, split_leading_roster, team_name,
)
from services.show_teams import split_team_path, team_url  # noqa: E402


def show_teams_site():
    site = shows_site()
    rows = [
        (1663, 25, 33, "zvezdy-ntv", "zvezdy-ntv/", "Звёзды на НТВ", ""),
        (1775, 19, 1663, "team", "zvezdy-ntv/team/", "Команды шоу «Звёзды»", ""),
        (2005, 21, 1775, "soyuz", "zvezdy-ntv/team/soyuz.html", "Союз (Звёзды)", ""),
        (1072, 21, 77, "soyuz", "kvn/team/soyuz.html", "Союз", ""),
        (2434, 19, 1771, "shablon", "liga-gorodov/team/shablon.html", "Шаблон команды Лиги Городов", ""),
    ]
    for rid, template, parent, alias, uri, title, longtitle in rows:
        site.resources[rid] = {"id": rid, "template": template, "parent": parent, "alias": alias, "uri": uri,
                               "pagetitle": title, "longtitle": longtitle, "published": 1, "deleted": 0,
                               "menuindex": 1, "description": "", "keywords": "", "rating": 0, "votes": 0,
                               "createdon": 1713441486, "publishedon": 0}
        site.by_uri[uri.strip("/")] = rid
    site.resources[1905]["published"] = 0
    return site


def test_team_urls_and_paths():
    assert team_url({"slug": "dals"}) == "/kvn/teams/dals"
    assert team_url({"slug": "soyuz", "show_id": "s1", "full_path": "zvezdy-ntv/teams/soyuz"}) == "/shows/zvezdy-ntv/teams/soyuz"
    assert team_url({"slug": "soyuz", "full_path": "soyuz"}) == "/kvn/teams/soyuz"   # старое поле у команд КВН
    assert split_team_path("liga-gorodov/teams/eto-oni") == ("liga-gorodov", "eto-oni")
    assert split_team_path("improv-teams/league/teams") is None
    assert direct_query("shows/zvezdy-ntv/teams/soyuz") == ("teams", "full_path", "zvezdy-ntv/teams/soyuz")
    assert direct_query("shows/zvezdy-ntv/teams") == ("shows", "full_path", "zvezdy-ntv/teams")


def test_show_team_pages_names_and_links():
    site = show_teams_site()
    assert set(show_team_pages(site)) == {1905, 2000, 2005}          # «Шаблон команды …» — не команда
    assert team_name(site, site.resources[2005]) == "Союз"            # пометка «(Звёзды)» из «Команды шоу «Звёзды»»
    assert team_name(site, site.resources[2000]) == "Это они"         # «(ЛГ)» из «Команды ЛГ»
    # страница-список «Команды …» — /teams внутри шоу
    assert show_path(site, site.resources[1775], 33) == "zvezdy-ntv/teams"
    mapper = LinkMapper(site, _try_pattern_redirect, {}, *link_builders(site))
    assert mapper.map("zvezdy-ntv/team/soyuz.html") == "/shows/zvezdy-ntv/teams/soyuz"
    assert mapper.map("kvn/team/soyuz.html") == "/kvn/teams/soyuz"                     # команда КВН — по шаблону
    assert mapper.map("improv-teams/baikalskiye.html") == "/shows/improv-teams/teams/baikalskiye"
    assert mapper.map("zvezdy-ntv/team/") == "/shows/zvezdy-ntv/teams"
    assert mapper.map("igra/team/soyuz.html") == "/igra/team/soyuz"         # раздела igra среди команд нет
    assert mapper.map("liga-gorodov/team/soyuz.html") == "/shows/zvezdy-ntv/teams/soyuz"   # переехавшая страница
    fixer = misplaced_show_team_builder(site, kvn_team_slugs={"soyuz"})
    assert fixer("kvn/teams/eto-oni-lg") == "/shows/improv-teams/teams/eto-oni-lg"
    assert fixer("kvn/teams/soyuz") is None                                 # есть команда КВН — ссылка верная


def test_html_helpers_for_teams():
    assert balance_html("<p>a</p></div><div><h4>x</h4>") == "<p>a</p><div><h4>x</h4></div>"
    assert first_heading('<div><h4 class="a">История</h4></div>') == ("h4", "История")
    assert first_heading("<p>Текст</p><h3>А</h3>") is None
    table = "<table><tr><td>Город</td><td>Москва</td></tr><tr><td>Состав</td><td><ul><li>А</li></ul></td></tr></table>"
    assert fact_cell_html(table, "Состав") == "<ul><li>А</li></ul>"
    facts = parse_facts_table("<table><tr><td>Сцена</td><td>Победа (2019в)<br />Победа (2019о)</td></tr>"
                              "<tr><td>Наставники</td><td><p>Светлаков (1)</p><p>Кравец (3)</p></td></tr>"
                              "<tr><td>Дата</td><td>19 апреля<br />1991 года</td></tr></table>")
    assert facts == [("Сцена", "Победа (2019в), Победа (2019о)"), ("Наставники", "Светлаков (1), Кравец (3)"),
                     ("Дата", "19 апреля 1991 года")]
    roster, rest = split_leading_roster('<div><a href="/people/a">Анна Аа</a></div><p>Борис Бб<br />Вера Вв</p>'
                                        "<h4>История команды</h4><p>Текст. 2021 год.</p>")
    assert roster == '<ul>\n<li><a href="/people/a">Анна Аа</a></li>\n<li>Борис Бб</li>\n<li>Вера Вв</li>\n</ul>'
    assert rest.startswith("<h4>История")
    assert split_leading_roster("<p>Анна Аа</p><p>Длинный текст о команде.</p>")[0] is None


def test_build_show_team_matches_admin_format():
    site = show_teams_site()
    info = {"MIGX_formname": "info", "subtitle": "<p>Команда «Союз» – участники шоу.</p>", "content": "",
            "list_social": json.dumps([{"link": "https://vk.com/soyuz", "name": "vk"}]),
            "table": "<table><tr><td>Звёзды</td><td>Джиган (1 сезон)<br>Костомаров (2 сезон)</td></tr></table>"}
    sections = [
        info,
        {"MIGX_formname": "timeline", "hide_section": "1", "list_triple": ""},
        {"MIGX_formname": "text", "title": "Состав",
         "content": '<ul><li><a href="people/natalya-andreevna.html">Наталья</a></li></ul>'},
        {"MIGX_formname": "text", "title": "История команды",
         "content": "<p>Начало.</p><h3>Шоу «Звёзды»</h3><p>Первый сезон.</p><p>[[$yandexAds_adder? &num=16]]</p>"},
        {"MIGX_formname": "table", "content": "<table><tr><td>Сезон</td></tr></table>"},
        {"MIGX_formname": "text", "title": "", "content": "<h3>Второй сезон</h3><p>Продолжение.</p>"},
        {"MIGX_formname": "text", "title": "Союз (Звёзды)", "content": "<h3>Эфиры</h3><p>Выпуски.</p>"},
    ]
    site.tv_values[2005] = {"config": json.dumps(sections), "img": "images/igra/soyuz1.jpg"}
    mapper = LinkMapper(site, _try_pattern_redirect, {}, *link_builders(site))
    payload, extra, warnings = build_show_team(site, 2005, mapper)
    TeamCreate(**payload, show_id="show-id")   # формат запроса админки
    assert payload["title"] == payload["name"] == "Союз" and payload["slug"] == "soyuz"
    assert payload["facts"] == {"Звёзды": "Джиган (1 сезон), Костомаров (2 сезон)"}
    assert payload["social_links"] == {"vk": "https://vk.com/soyuz"}
    assert payload["logo"]["url"] == "/media/imported/images/igra/soyuz1.jpg"
    assert payload["seo"]["meta_title"] == "Союз — команда шоу «Звёзды на НТВ»"
    content = [(m["type"], m["title"]) for m in payload["modules"][5:]]
    assert content == [("text_block", ""), ("text_block", "Состав команды"), ("text_block", "История команды")]
    history = payload["modules"][7]["data"]["content"]
    # продолжения раздела: таблица, «Второй сезон» (в разделе уже есть h3), секция с заголовком-названием команды
    assert "Второй сезон" in history and "<table>" in history and "Эфиры" in history and "yandexAds" not in history
    assert payload["modules"][6]["data"]["content"] == '<ul><li><a href="/people/natalya-andreevna">Наталья</a></li></ul>'
    assert extra["old_id"] == 2005 and extra["old_urls"] == ["/zvezdy-ntv/team/soyuz.html"]
    assert warnings == []


def test_build_show_team_roster_from_facts_and_leading_names():
    site = show_teams_site()
    site.tv_values[1905] = {"config": json.dumps([
        {"MIGX_formname": "info", "table": "<table><tr><td>Город</td><td>Иркутск</td></tr>"
                                           "<tr><td>Состав</td><td><ul><li>Анна Аа</li></ul></td></tr></table>"},
        {"MIGX_formname": "text", "title": "",
         "content": "<h3>История команды</h3><p>И.</p><h3>Официальные игры</h3><p>О.</p>"},
    ])}
    payload, _, warnings = build_show_team(site, 1905)
    assert payload["facts"] == {"Город": "Иркутск"} and payload["status"] == "draft"
    assert [m["title"] for m in payload["modules"][5:]] == ["Состав команды", "История команды", "Официальные игры"]
    assert "нет фото" in warnings
    site.tv_values[2000] = {"config": json.dumps([{"MIGX_formname": "text", "title": "Это они (ЛГ)", "content":
                                                   "<div>Анна Аа</div><div>Борис Бб</div><div>Вера Вв</div>"
                                                   "<h4>История команды</h4><p>Текст.</p>"}])}
    payload, _, _ = build_show_team(site, 2000)
    assert [m["title"] for m in payload["modules"][5:]] == ["Состав команды", "История команды"]


def test_same_name_team_matching():
    from scripts.link_same_name_teams import name_key, pair_evidence
    assert name_key("Два Капитана - 1955") == name_key("Два капитана-1955")
    assert name_key("Поживём-увидим!") == name_key("Поживем увидим")
    assert name_key("Сборная Москвы (МАМИ)") != name_key("Сборная Москвы")
    show = {"full_path": "liga-gorodov/teams/eto-oni", "facts": {"Город": "Тамбов"},
            "modules": [{"data": {"content": '<a href="/kvn/teams/eto-oni">КВН</a>'}}]}
    kvn = {"slug": "eto-oni", "facts": {"Город": "Москва"}, "modules": []}
    assert pair_evidence(show, kvn) == (["ссылка со страницы шоу"], True)
    assert pair_evidence({**show, "modules": []}, {**kvn, "facts": {"Город": "Москва, Тамбов"}}) == (["город"], False)
