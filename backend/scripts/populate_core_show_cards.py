"""Add editorial core-cast cards to four imported show pages.

Dry-run by default. The local episode tables are the source of counts; existing
person pages supply portraits. No new person page or external image is created.

Sources for roster boundaries (checked 2026-09-25):
  Comedy Club: https://comedyclub.ru/projects/comedy-club/
  Женский стендап: https://comedyclub.ru/projects/zhenskiy-stendap/
                   https://tnt-online.ru/projects/jenskiy-standup
  Stand Up: https://tnt-online.ru/projects/standup
  Убойная лига: imported local statistics, plus format description at
                 https://premier.one/show/ubojnaja-liga/season/2
"""

import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.cache import cache_service  # noqa: E402
from services.memberships import name_key  # noqa: E402
from services.show_appearances import Tree, table_grid, text  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402


# The producer's roster is used as a historical selection, not a claim that
# everyone remains a resident today. Martirosyan is included as a former host.
COMEDY_CLUB = [
    ("Павел Воля", "2005", "резидент и ведущий"),
    ("Гарик Харламов", "2005", "резидент"),
    ("Тимур Батрутдинов", "2005", "резидент"),
    ("Дмитрий Сорокин", "2005", "резидент"),
    ("Андрей Аверин", "2007", "резидент"),
    ("Зураб Матуа", "2007", "резидент"),
    ("Марина Кравец", "2008", "резидент"),
    ("Дмитрий Грачёв", "2010", "резидент"),
    ("Демис Карибидис", "2013", "резидент"),
    ("Антон Иванов", "2013", "резидент"),
    ("Андрей Бебуришвили", "2013", "резидент"),
    ("Женя Синяков", "2015", "резидент"),
    ("Иван Половинкин", "2018", "резидент"),
    ("Константин Бутусов", "2021", "резидент"),
    ("Гарик Мартиросян", "2005–2019", "бывший резидент и ведущий"),
]

# Thresholds refer only to the imported tables, not an assertion about all
# broadcast episodes. They keep guest performers out of the core-cast cards.
WOMEN_MIN_APPEARANCES = 12
STANDUP_MIN_APPEARANCES = 20
WOMEN_ALIASES = {"Саша Муратова": "Александра Муратова", "Белла": "Белла Малу"}
UBOY_ALIASES = {"Андрей Родных": "Андрей Родной", "Вячеслав Комиссаренко": "Слава Комиссаренко"}

# Acts with 10+ appearances in the show's own summary table. For a duo, the
# count and victories belong to the duo, not separately to each member.
UBOY_ACTS = [
    ("Денис Косяков", ["Денис Косяков"]),
    ("Красивые", ["Илья Соболев", "Роман Клячкин"]),
    ("Лангепас", ["Евгений Кожевин"]),
    ("Костя Пушкин", ["Константин Пушкин"]),
    ("Братья Карамазовы", ["Вячеслав Назаров", "Дмитрий Скачков"]),
    ("Медведь", ["Евгений Отставнов"]),
    ("Феминисты", ["Артём Пушкин", "Роман Постовалов"]),
    ("Искандер Македонский", ["Искандер Гумеров"]),
    ("Компот", ["Леонид Моложанов", "Рустам Мухамеджанов"]),
    ("Соседи", ["Дмитрий Черных", "Рустам Хабибуллин"]),
    ("Бабанов и Мишланов", ["Кирилл Бабанов", "Дмитрий Мишланов"]),
    ("Белый", ["Руслан Белый"]),
    ("Родной и Федяй", ["Андрей Родной", "Андрей Федяй"]),
    ("Ирина Мягкова", ["Ирина Мягкова"]),
    ("Быдло", ["Алексей Смирнов", "Антон Иванов"]),
    ("Антон Борисов", ["Антон Борисов"]),
    ("Сделано руками", ["Дмитрий Романов", "Евгений Воронецкий"]),
    ("Партизаны", ["Игорь Чехов", "Михаил Кукота"]),
    ("Холодильник", ["Николай Камка", "Евгений Булка"]),
    ("Совесть", ["Слава Комиссаренко", "Дмитрий Невзоров"]),
]


def fact(title, value):
    return {"title": title, "value": str(value)}


def person_index(people):
    index = defaultdict(list)
    for person in people:
        if person.get("status") == "archived":
            continue
        for value in (person.get("full_name"), person.get("title")):
            if value and person not in index[name_key(value)]:
                index[name_key(value)].append(person)
    return index


def make_card(name, facts, people):
    matches = people.get(name_key(name), [])
    person = matches[0] if len(matches) == 1 else None
    photo = ((person or {}).get("photo") or {}).get("url")
    return {"name": name, "person_slug": person.get("slug") if person else None,
            "photo": photo, "facts": facts}


def seasonal_totals(show, women=False):
    totals, seasons = defaultdict(int), defaultdict(set)
    season = 0
    for module in show.get("modules") or []:
        if module.get("title") != "Выпуски":
            continue
        season += 1
        for table in Tree((module.get("data") or {}).get("content", "")).root.find("table"):
            for row in table_grid(table)[1:]:
                if len(row) < 2:
                    continue
                name = re.sub(r"\*+", "", text(row[0])).strip()
                name = (WOMEN_ALIASES if women else {}).get(name, name)
                count = text(row[-1] if women else row[1])
                if name == "Комик":
                    continue
                if not women and not count.isdigit() and len(name.split()) >= 2:
                    # The imported season 12 lists performers but has no
                    # numeric count; retain the season without inventing one.
                    seasons[name].add(season)
                if not count.isdigit():
                    continue
                totals[name] += int(count)
                seasons[name].add(season)
    return totals, seasons


def season_label(numbers):
    values = sorted(numbers)
    if values == list(range(values[0], values[-1] + 1)) and len(values) > 2:
        return f"{values[0]}–{values[-1]}"
    return ", ".join(map(str, values))


def comedy_cards(people):
    cards = []
    for name, period, role in COMEDY_CLUB:
        label = "Годы в шоу" if "–" in period else "В шоу с"
        cards.append(make_card(name, [fact("Участие", role), fact(label, period)], people))
    return cards


def standup_cards(show, people, women=False):
    totals, seasons = seasonal_totals(show, women)
    minimum = WOMEN_MIN_APPEARANCES if women else STANDUP_MIN_APPEARANCES
    names = sorted((name for name, count in totals.items() if count >= minimum),
                   key=lambda name: (-totals[name], name))
    cards = []
    for name in names:
        role = "ведущая и комик" if women and name == "Ирина Мягкова" else (
            "ведущий и комик" if not women and name in ("Руслан Белый", "Евгений Чебатков", "Алексей Щербаков") else "стендап-комик")
        cards.append(make_card(name, [
            fact("Участие", role),
            fact("Сезоны по таблицам", season_label(seasons[name])),
            fact("Выходов по таблицам" if women else "Выходов (сезоны 1–11)", totals[name]),
        ], people))
    return cards


def uboj_cards(show, people):
    table = next((m for m in show.get("modules") or []
                  if m.get("title") == "Подробная статистика участников"), None)
    if not table:
        raise RuntimeError("Не найдена таблица статистики «Убойной лиги»")
    rows = (table.get("data") or {}).get("rows") or []
    cards = []
    seen = set()
    for act, members in UBOY_ACTS:
        matches = [row for row in rows if act.casefold() in text(row[0]).casefold()]
        if len(matches) != 1 or len(matches[0]) < 3:
            raise RuntimeError(f"Неоднозначная статистика для {act}: {len(matches)} строк")
        row = matches[0]
        if not row[1].isdigit() or not row[2].isdigit() or int(row[1]) < 10:
            raise RuntimeError(f"Некорректная статистика для {act}")
        for raw_name in members:
            name = UBOY_ALIASES.get(raw_name, raw_name)
            if name in seen:
                raise RuntimeError(f"Повторная карточка: {name}")
            seen.add(name)
            if len(members) > 1:
                facts = [fact("Состав", f"дуэт «{act}»"),
                         fact("Выступлений дуэта", row[1]), fact("Побед дуэта", row[2])]
            else:
                facts = [fact("В шоу", act if act != name else "сольный участник"),
                         fact("Выступлений", row[1]), fact("Побед", row[2])]
            cards.append(make_card(name, facts, people))
    return cards


async def main(apply):
    db = await get_db()
    try:
        slugs = ("comedy-club", "standupwomen", "standup", "ubojnaya-liga")
        shows = {}
        for slug in slugs:
            show = await db.shows.find_one({"full_path": slug})
            if not show:
                raise RuntimeError(f"Шоу не найдено: {slug}")
            shows[slug] = show
        people = person_index(await db.people.find({}, {"full_name": 1, "title": 1, "slug": 1,
                                                          "photo": 1, "status": 1}).to_list(None))
        rosters = {
            "comedy-club": comedy_cards(people),
            "standupwomen": standup_cards(shows["standupwomen"], people, women=True),
            "standup": standup_cards(shows["standup"], people),
            "ubojnaya-liga": uboj_cards(shows["ubojnaya-liga"], people),
        }
        report = []
        updates = []
        for slug, cards in rosters.items():
            show = shows[slug]
            modules = show.get("modules") or []
            module_id = f"core-cast-{slug}"
            existing = [m for m in modules if m.get("type") == "participants"]
            if any(m.get("id") != module_id for m in existing):
                raise RuntimeError(f"{slug}: уже есть другой модуль участников; нужна ручная сверка")
            insert_at = next((i + 1 for i, m in enumerate(modules) if m.get("type") == "text_block"
                              and not m.get("title")), 5)
            new_module = {"id": module_id, "type": "participants", "order": 0, "title": "",
                          "visible": True, "data": {"title": "Основной состав шоу", "items": cards}}
            if existing:
                index = modules.index(existing[0])
                new_module["order"] = modules[index].get("order", index + 1)
                modules[index] = new_module
            else:
                modules.insert(insert_at, new_module)
                for index, module in enumerate(modules, start=1):
                    module["order"] = index
            updates.append((show["_id"], modules))
            report.append({"show": slug, "cards": len(cards),
                           "with_profile": sum(bool(c["person_slug"]) for c in cards),
                           "with_photo": sum(bool(c["photo"]) for c in cards),
                           "missing_profiles": [c["name"] for c in cards if not c["person_slug"]]})
        if apply:
            for show_id, modules in updates:
                await db.shows.update_one({"_id": show_id}, {"$set": {"modules": modules}})
            await cache_service.invalidate_everywhere(db)
        print(json.dumps({"applied": apply, "shows": report}, ensure_ascii=False, indent=2))
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="записать четыре модуля в локальную MongoDB")
    asyncio.run(main(parser.parse_args().apply))
