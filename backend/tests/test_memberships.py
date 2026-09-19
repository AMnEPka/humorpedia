"""Составы: разбор текстовых блоков, сопоставление людей, роли жюри/ведущих в participations. Без БД."""
import pytest

from services.competitions import TeamLookup, build_participations, legacy_to_season
from services.memberships import (
    LINK_CANDIDATE, LINK_CONFIRMED, PersonLookup, linkable_memberships_query, membership_link_reason,
    membership_review_status, memberships_from_team, name_key, normalize_role, parse_roster_html, parse_years,
    preserve_pending_public_link,
)


def by_name(entries):
    return {e["person_name"]: e for e in entries}


def test_list_with_links_and_roles():
    html = (
        '<ul> <li><a href="people/dmitry-shpenkov.html">Дмитрий Шпеньков</a> – капитан</li> '
        '<li><a href="people/mikhail-belyanin.html">Михаил Белянин</a></li> <li>Евгений Штылёв</li> '
        '<li><a href="people/evgeniy-trikoz.html">Евгений Трикоз</a>* </li> '
        '<li><a href="people/oleg-valentsov.html">Олег Валенцов</a> – основатель команды</li> </ul>'
    )
    parsed = parse_roster_html(html)
    assert parsed["complete"] and not parsed["unparsed"]
    entries = by_name(parsed["entries"])
    assert entries["Дмитрий Шпеньков"]["person_slug"] == "dmitry-shpenkov"
    assert entries["Дмитрий Шпеньков"]["roles"] == ["капитан"]
    assert entries["Евгений Штылёв"]["person_slug"] is None and entries["Евгений Штылёв"]["roles"] == []
    assert entries["Евгений Трикоз"]["note"].strip() == "*"
    assert entries["Олег Валенцов"]["roles"] == ["основатель"]


def test_sections_former_and_joined():
    html = (
        '<ul><li><a href="people/tatiana-suvorina.html">Татьяна Суворина</a> – капитан</li>'
        '<li>Полина Бабина – директор</li></ul>'
        '<p>Присоединившиеся к коллективу в сезоне 2025:</p><ul><li>Никита Аверичев</li></ul>'
        '<p>Бывшие участники:</p><ul><li>Марьям Оганисян</li></ul>'
    )
    parsed = parse_roster_html(html)
    assert parsed["complete"]
    entries = by_name(parsed["entries"])
    assert entries["Никита Аверичев"]["from_year"] == 2025 and entries["Никита Аверичев"]["status"] == "current"
    assert entries["Марьям Оганисян"]["status"] == "former"
    assert entries["Полина Бабина"]["status"] == "current"


@pytest.mark.parametrize("line,from_year,to_year,status,roles", [
    ("Алексей Хамин (с 2022)", 2022, None, "current", []),
    ("Денис Гвоздёв (2017-2019)", 2017, 2019, "former", []),
    ("Настя Капацина (до 2018)", None, 2018, "former", []),
    ("Ксения Корнева (2013 и 2017)", 2013, 2017, "former", []),
    ("Арсений Агапов (с 2021) – фрнтмен", 2021, None, "current", ["фронтмен"]),
    ("Вадим Самойлов – музыкант (1986-1987)", 1986, 1987, "former", ["музыкант"]),
    ("Иван Иванов – капитан с 1997", 1997, None, "current", ["капитан"]),
])
def test_years_in_parentheses_and_roles(line, from_year, to_year, status, roles):
    parsed = parse_roster_html(f"<ul><li>{line}</li></ul>")
    assert parsed["complete"], parsed["unparsed"]
    entry = parsed["entries"][0]
    assert (entry["from_year"], entry["to_year"], entry["status"], entry["roles"]) == (from_year, to_year, status, roles)


def test_nickname_in_parentheses_stays_in_name():
    entry = parse_roster_html('<ul><li><a href="people/olga-klimentieva.html">Ольга (Лёля) Климентьева</a></li></ul>')["entries"][0]
    assert entry["person_name"] == "Ольга (Лёля) Климентьева"
    assert entry["name_key"] == name_key("Климентьева Ольга")


def test_name_key_strips_aliases_without_regex_backtracking():
    assert name_key('Иван «Грозный» Петров (капитан) "Ваня"') == "иван петров"
    assert name_key("(" * 10_000 + "Иван") == "иван"


def test_divs_and_br_lines():
    parsed = parse_roster_html("<div>Александра Михайлова</div> <div>Регина Рудченко</div> <p>Иван Исаков<br>Пётр Петров – автор</p>")
    assert [e["person_name"] for e in parsed["entries"]] == ["Александра Михайлова", "Регина Рудченко", "Иван Исаков", "Пётр Петров"]
    assert parsed["entries"][-1]["roles"] == ["автор"]


def test_narrative_text_is_not_complete():
    parsed = parse_roster_html(
        "<ul><li>Иван Иванов</li></ul><p>Практически с первой телевизионной игры у каждого актёра команды была определённая роль.</p>"
    )
    assert not parsed["complete"]
    assert len(parsed["entries"]) == 1 and parsed["unparsed"]


def test_parse_years_and_roles_helpers():
    assert parse_years("покинул команду после сезона 2018 года") == {"from_year": 2018, "to_year": 2018, "former": True}
    assert normalize_role("Звукач") == "звукооператор"
    assert name_key("Шастун Антон") == name_key("Антон  Шастун") == name_key("антон шастун")
    assert name_key("Семён Ёлкин") == name_key("Семен Елкин")


def test_person_lookup_by_slug_old_url_and_unambiguous_name():
    lookup = PersonLookup([
        {"_id": "p1", "slug": "anton-shastun", "title": "Шастун Антон", "full_name": "Антон Шастун"},
        {"_id": "p2", "slug": "ivan-ivanov-1", "title": "Иванов Иван", "old_urls": ["/people/ivan-ivanov.html"]},
        {"_id": "p3", "slug": "ivan-ivanov-2", "title": "Иванов Иван"},
    ])
    assert lookup.resolve("anton-shastun") == ("p1", "slug")
    assert lookup.resolve(None, "Антон Шастун") == ("p1", "name")
    assert lookup.resolve("ivan-ivanov", "Иван Иванов") == ("p2", "slug")
    assert lookup.resolve(None, "Иван Иванов") == (None, None), "тёзки — по имени не связываем"


def test_manual_unlink_is_excluded_from_future_auto_linking():
    assert linkable_memberships_query(["anna-borodina"], ["анна бородина"]) == {
        "person_id": None,
        "person_link_disabled": {"$ne": True},
        "$or": [
            {"person_slug": {"$in": ["anna-borodina"]}},
            {"name_key": {"$in": ["анна бородина"]}},
        ],
    }


def test_legacy_name_link_and_slug_conflict_require_review():
    lookup = PersonLookup([{"_id": "p1", "slug": "anna-borodina", "full_name": "Анна Бородина"}])
    name_only = {"person_id": "p1", "person_name": "Анна Бородина", "person_slug": None}
    slug_conflict = {**name_only, "person_slug": "other-anna"}

    assert membership_link_reason(name_only, lookup) == "name_only"
    assert membership_link_reason(slug_conflict, lookup) == "slug_unresolved"
    lookup.by_slug["other-anna"] = "p2"
    assert membership_link_reason(slug_conflict, lookup) == "slug_conflict"
    assert membership_review_status(name_only, lookup) == LINK_CANDIDATE
    assert membership_link_reason({**name_only, "link_review_status": LINK_CONFIRMED}, lookup) is None


def test_reimport_keeps_legacy_candidate_public_until_review():
    lookup = PersonLookup([{"_id": "p1", "slug": "anna-borodina", "full_name": "Анна Бородина"}])
    generated = {
        "person_id": None,
        "candidate_person_id": "p1",
        "matched_by": "name",
        "link_review_status": LINK_CANDIDATE,
    }
    existing = {"person_id": "p1", "person_name": "Анна Бородина", "matched_by": "name"}

    result = preserve_pending_public_link(generated, existing, lookup)

    assert result["person_id"] == "p1"
    assert result["link_review_status"] == LINK_CANDIDATE


def test_memberships_from_team():
    team = {"_id": "team-1", "modules": [
        {"id": "m1", "type": "text_block", "data": {"title": "Состав команды", "content":
            '<ul><li><a href="people/anton-shastun.html">Антон Шастун</a> – капитан</li><li>Пётр Петров</li></ul>'}},
        {"id": "m2", "type": "text_block", "data": {"title": "История команды", "content": "<p>Текст</p>"}},
    ]}
    lookup = PersonLookup([
        {"_id": "p1", "slug": "anton-shastun", "title": "Шастун Антон"},
        {"_id": "p2", "slug": "petr-petrov", "title": "Пётр Петров"},
    ])
    docs, report = memberships_from_team(team, lookup)
    assert report == [{"module_id": "m1", "complete": True, "unparsed": [], "count": 2}]
    assert [(d["person_name"], d["person_id"], d["roles"]) for d in docs] == [
        ("Антон Шастун", "p1", ["капитан"]), ("Пётр Петров", None, []),
    ]
    assert docs[0]["link_review_status"] == LINK_CONFIRMED
    assert docs[1]["candidate_person_id"] == "p2"
    assert docs[1]["link_review_status"] == LINK_CANDIDATE
    assert docs[0]["_id"] != docs[1]["_id"] and all(d["source"] == "roster_text" for d in docs)


def test_role_participations():
    page = {
        "_id": "page-1", "slug": "vl-2015", "title": "Сезон 2015", "full_path": "kvn/vl-kvn/vl-2015", "status": "published",
        "season_data": {
            "year": 2015, "jury": ["Юлий Гусман"], "hosts": ["Александр Масляков"], "host": "Александр Масляков",
            "editors": ["Андрей Чивурин"], "all_teams": [], "winners": [],
            "stages": [{"name": "Финал", "order": 1, "games": [
                {"id": "g1", "name": "Финал", "jury": ["Юлий Гусман", "Константин Эрнст"], "host": "Александр Масляков", "teams": []},
                {"id": "g2", "name": "Финал 2", "jury": ["Юлий Гусман"], "host": "", "teams": []},
            ]}],
        },
    }
    season = legacy_to_season(page, {"_id": "t", "slug": "vl-kvn", "show": "kvn"}, TeamLookup())
    people = PersonLookup([{"_id": "gusman", "slug": "yuliy-gusman", "full_name": "Юлий Гусман"}])
    roles = {(r["role"], r["name"]): r for r in build_participations(season, people) if r["kind"] == "role"}

    assert set(roles) == {
        ("jury", "Юлий Гусман"), ("jury", "Константин Эрнст"), ("host", "Александр Масляков"), ("editor", "Андрей Чивурин"),
    }
    assert roles[("jury", "Юлий Гусман")]["person_id"] == "gusman"
    assert roles[("jury", "Юлий Гусман")]["games_count"] == 2
    assert roles[("jury", "Константин Эрнст")]["person_id"] is None
    assert roles[("host", "Александр Масляков")]["games_count"] == 1
