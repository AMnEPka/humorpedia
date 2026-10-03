"""Дополнить третий сезон «Звёзд» из проверенного редакционного пакета.

По умолчанию dry-run; для записи нужны --apply --backup-dir.
Новые люди не создаются. Команды создаются через обычный CRUD.
"""

import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import sys
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.content import TeamCreate  # noqa: E402
from routes.content_teams import create_team  # noqa: E402
from services.cache import cache_service  # noqa: E402
from services.crud import check_primary_tag_duplicate  # noqa: E402
from services.memberships import import_team_rosters, name_key  # noqa: E402
from services.show_appearances import extract  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402


ROOT = "a778bf34-cb28-4526-a065-dac7cb120708"
SEASON = "8b8d4b2f-5cfb-46fd-b372-e629d4386d7c"
DIRECTORY = "a7e33084-33db-45a7-818f-421c458cab44"
REPLACEMENTS = {
    "b7de6daf-90c4-4243-8dd8-9b866192db18": "intro",
    "c0d6daef-9322-4b1f-b9b7-6303a8c27252": "roster",
    "19d95dfd-83b7-4ed3-a307-e6b0be22d0d2": "format",
    "4e52fad9-a31a-41d6-b590-6a61171ff61a": "festival1",
    "d0cf47be-ba17-4d4c-b4fe-7d8b8c2b30a1": "results1",
}


def fingerprint(payload):
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def validate(payload):
    if (payload.get("schema_version"), payload.get("show_id"), payload.get("season_id"), payload.get("teams_page_id")) != (1, ROOT, SEASON, DIRECTORY):
        raise ValueError("Пакет не соответствует третьему сезону «Звёзд»")
    teams = payload["teams"]
    refs = {t["slug"]: t for t in teams}
    if len(teams) != 12 or len(refs) != 12 or sum(t["guest"] for t in teams) != 1:
        raise ValueError("Нужны 11 конкурсных команд и один специальный гость")
    if not refs["kamyzyaki"]["guest"] or refs["kamyzyaki"]["stars"] != ["Лёша Янгер"]:
        raise ValueError("Не подтверждена роль «Камызяков» или их звезды")
    seen, passed = set(), set()
    festivals = payload["festivals"]
    if [f["number"] for f in festivals] != [1, 2, 3]:
        raise ValueError("Нужны три фестивальных выпуска")
    for festival in festivals:
        if festival["date"] > payload["as_of"]:
            raise ValueError("Дата фестиваля позже даты среза")
        n = len(festival["results"])
        if n != (3 if festival["number"] == 3 else 4):
            raise ValueError("Неверное число конкурсных результатов")
        for result in festival["results"]:
            slug = result["slug"]
            if slug not in refs or refs[slug]["guest"] or slug in seen or refs[slug]["festival"] != festival["number"]:
                raise ValueError("Команда или специальный гость неверно включены в результаты")
            seen.add(slug)
            scores = result["scores"]
            if len(scores) != len(payload["judges"]) or any(type(v) is not int or not 1 <= v <= n for v in scores) or sum(scores) != result["total"]:
                raise ValueError("Не сходятся оценки жюри и сумма")
            if result["passed"]:
                passed.add(slug)
        for i in range(len(payload["judges"])):
            if sorted(r["scores"][i] for r in festival["results"]) != list(range(1, n + 1)):
                raise ValueError("Повторное место в оценках одного судьи")
    if seen != {s for s, t in refs.items() if not t["guest"]} or len(passed) != 8:
        raise ValueError("Список конкурсных команд или проход в дуэли неполон")
    duels = [slug for pair in payload["duels"] for slug in pair]
    if len(duels) != 8 or len(set(duels)) != 8 or set(duels) != passed:
        raise ValueError("Жеребьёвка не соответствует восьми прошедшим командам")
    for team in teams:
        if not team["stars"] or (team.get("new") and (not team.get("description") or not team.get("members"))):
            raise ValueError("Новая карточка не содержит описания, звезды или известных участников")
    return refs


def module(key, title, content):
    return {"id": str(uuid5(NAMESPACE_URL, "humorpedia:zvezdy3:" + key)), "type": "text_block",
            "title": title, "visible": True, "data": {"title": title, "content": content}}


def linked_name(name, people):
    matches = [p for p in people if p.get("status") != "archived" and name_key(name) in
               (name_key(p.get("title", "")), name_key(p.get("full_name", "")))]
    return (f'<a href="/people/{escape(matches[0]["slug"], quote=True)}">{escape(name)}</a>'
            if len(matches) == 1 else escape(name))


def team_link(team):
    return f'<a href="/shows/zvezdy-ntv/teams/{escape(team["slug"], quote=True)}">{escape(team["name"])}</a>'


def source_note(url):
    return f'<p>Источник: <a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">публикация о выпуске и составе</a>.</p>'


def roster_table(payload, people):
    rows = []
    for team in payload["teams"]:
        stars = " и ".join(linked_name(n, people) for n in team["stars"])
        status = "Специальный гость фестиваля" if team["guest"] else "Конкурсная команда"
        rows.append(f'<tr><td>{stars}</td><td>{team_link(team)}</td><td>{status}</td></tr>')
    return ('<table><tbody><tr><th>Звезда</th><th>Команда</th><th>Участие</th></tr>' + "".join(rows)
            + '</tbody></table><p>В номере «Камызяков» также появилась Екатерина Мизулина как гость.</p>'
            + source_note(payload["sources"]["announcement"]))


def festival_html(festival, refs, people):
    date = datetime.fromisoformat(festival["date"]).strftime("%d.%m.%Y")
    teams = [refs[r["slug"]] for r in festival["results"]] + [refs[s] for s in festival.get("guests", [])]
    lineup = "; ".join(team_link(t) + " — " + " и ".join(linked_name(n, people) for n in t["stars"]) for t in teams)
    return f'<p>Эфир игры: {date}.</p><p>Участники: {lineup}.</p><p>Результаты фестиваля:</p>'


def results_table(festival, refs, people, judges):
    header = '<tr><th>Команда</th><th>Звезда</th>' + "".join(f"<th>{escape(j)}</th>" for j in judges) + '<th>Сумма</th><th>Итог</th></tr>'
    rows = []
    for result in festival["results"]:
        team = refs[result["slug"]]
        stars = " и ".join(linked_name(n, people) for n in team["stars"])
        cells = [team_link(team), stars, *map(str, result["scores"]), str(result["total"]),
                 "Проход в дуэли" if result["passed"] else "Выбыли после фестиваля"]
        rows.append("<tr>" + "".join(f"<td>{v}</td>" for v in cells) + "</tr>")
    guest = '<p>«Камызяки» выступили специальным гостем: оценки не выставлялись, в дуэлях команда не участвовала.</p>' if festival.get("guests") else ""
    return "<table><tbody>" + header + "".join(rows) + "</tbody></table>" + guest + source_note(festival["source"])


def put_module(modules, addition):
    existing = next((m for m in modules if m["id"] == addition["id"]), None)
    if existing:
        if existing.get("data", {}).get("content") != addition["data"]["content"]:
            raise ValueError("Добавленный блок изменён редактором; автоматическая перезапись запрещена")
        return
    addition = deepcopy(addition)
    addition["order"] = max((m.get("order", 0) for m in modules), default=0) + 1
    modules.append(addition)


def season_modules(page, payload, people):
    refs = {t["slug"]: t for t in payload["teams"]}
    first = payload["festivals"][0]
    contents = {"intro": '<p>Участники третьего сезона: 11 конкурсных команд и специальный гость фестиваля «Камызяки».</p>',
                "roster": roster_table(payload, people),
                "format": '<p>Премьера третьего сезона состоялась 5 сентября 2026 года. Фестиваль показан в трёх выпусках — 5, 12 и 19 сентября. По его итогам в дуэли прошли восемь команд: по три из первых двух выпусков и две из третьего. «Камызяки» ограничились гостевым выступлением.</p>',
                "festival1": festival_html(first, refs, people),
                "results1": results_table(first, refs, people, payload["judges"])}
    modules = deepcopy(page["modules"])
    for ident, kind in REPLACEMENTS.items():
        target = next((m for m in modules if m["id"] == ident), None)
        if not target:
            raise ValueError(f"Не найден исходный блок сезона {ident}")
        old = target["data"]["content"]
        if old != contents[kind] and sha256(old.encode()).hexdigest() != payload["expected_content_hashes"][ident]:
            raise ValueError("Исходный блок сезона изменился после исследования")
        target["data"]["content"] = contents[kind]
    for festival in payload["festivals"][1:]:
        n = festival["number"]
        put_module(modules, module(f"festival{n}", f"{n} игра фестиваля", festival_html(festival, refs, people)))
        put_module(modules, module(f"results{n}", "", results_table(festival, refs, people, payload["judges"])))
    duels = '<p>По итогам фестиваля определены пары следующего этапа:</p><ul>' + "".join(
        f'<li>{team_link(refs[a])} — {team_link(refs[b])}</li>' for a, b in payload["duels"]) + '</ul>'
    put_module(modules, module("duels", "Жеребьёвка дуэлей", duels + source_note(payload["sources"]["festival3"])))
    return modules


def roster_module(team, people):
    stars = [f'<li>{linked_name(n, people)} — звезда (3 сезон, 2026)</li>' for n in team["stars"]]
    members = [f'<li>{linked_name(n, people)} (3 сезон, 2026)</li>' for n in team.get("members", [])]
    html = '<h3>Известные участники третьего сезона:</h3><ul>' + "".join(stars + members) + '</ul>'
    return module(team["slug"] + ":roster", "Состав команды", html)


def team_payload(team, payload, people):
    festival = next(f for f in payload["festivals"] if f["number"] == team["festival"])
    result = next((r for r in festival["results"] if r["slug"] == team["slug"]), None)
    facts = {"Шоу": "Звёзды на НТВ", "Сезон": "3 (2026)", "Звёзды (3 сезон)": " и ".join(team["stars"]),
             "Первое выступление": festival["date"], "Участие": "Специальный гость фестиваля" if team["guest"] else "Конкурсная команда"}
    outcome = "Гостевой номер; без оценок и без участия в дуэлях" if team["guest"] else f'{result["total"]} баллов; ' + ("проход в дуэли" if result["passed"] else "выбыли после фестиваля")
    facts["Результат фестиваля"] = outcome
    cast_sources = source_note(team["cast_source"])
    if team.get("additional_cast_source"):
        cast_sources += source_note(team["additional_cast_source"])
    modules = [module(team["slug"] + ":about", "", '<p>' + escape(team["description"]) + '</p>'), roster_module(team, people),
               module(team["slug"] + ":season", "Третий сезон", f'<p>Команда выступила {festival["date"]} в {festival["number"]}-м фестивальном выпуске. {escape(outcome)}.</p>' + cast_sources + source_note(festival["source"]))]
    if team.get("appearance_guests"):
        facts["Гость номера"] = " и ".join(team["appearance_guests"])
        modules.append(module(team["slug"] + ":guests", "Гости номера", '<p>В выступлении участвовала Екатерина Мизулина.</p>' + source_note(team["guest_source"]) + source_note(team["star_source"])))
    for i, m in enumerate(modules, 1):
        m["order"] = i
    return TeamCreate(title=team["name"], name=team["name"], slug=team["slug"], show_id=ROOT,
                      primary_tag=team["name"] + " (Звёзды на НТВ)",
                      status="published", facts=facts, facts_order=list(facts), aliases=team.get("aliases", []),
                      modules=modules, tags=["Звёзды на НТВ"], related_team_ids=team.get("related_team_ids", []))


async def sync_target_appearances(db):
    """Пересчитать только «Звёзды», сохраняя редакторские настройки вариантов."""
    from pymongo import UpdateOne
    shows = await db.shows.find({"$or": [{"_id": ROOT}, {"full_path": {"$regex": "^zvezdy-ntv/"}}]}).to_list(None)
    people = await db.people.find({}).to_list(None)
    teams = await db.teams.find({}).to_list(None)
    memberships = await db.memberships.find({}).to_list(None)
    rows, _ = extract(shows, people, teams, memberships)
    rows = [r for r in rows if r["show_id"] == ROOT]
    if not rows:
        raise ValueError("Не удалось извлечь участие в шоу; связи не изменены")
    existing = {r["_id"]: r async for r in db.show_appearances.find({"show_id": ROOT})}
    for row in rows:
        old = existing.get(row["_id"], {})
        for key in ("preferred", "excluded", "manual_person_id", "manual_achievement", "manual_group_name", "manual_group_kind"):
            if key in old:
                row[key] = old[key]
        if "manual_person_id" in old:
            row["person_id"] = old["manual_person_id"]
    await db.show_appearances.bulk_write([UpdateOne({"_id": r["_id"]}, {"$set": r}, upsert=True) for r in rows])
    await db.show_appearances.delete_many({"show_id": ROOT, "source": "local_content", "_id": {"$nin": [r["_id"] for r in rows]}})
    return len(rows)


async def run(args):
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    refs = validate(payload)
    db = await get_db()
    pages = {p["_id"]: p async for p in db.shows.find({"_id": {"$in": [ROOT, SEASON, DIRECTORY]}})}
    if len(pages) != 3:
        raise ValueError("Не найдены три исходные страницы шоу")
    stamp = fingerprint(payload)
    ledger = pages[SEASON].get("season_research_import")
    if ledger:
        if ledger["fingerprint"] != stamp:
            raise ValueError("Применён другой пакет: дальнейшие правки требуют отдельной проверки")
        return {"action": "без изменений", "fingerprint": stamp}
    people = await db.people.find({}, {"title": 1, "full_name": 1, "slug": 1, "status": 1}).to_list(None)
    existing = {t["slug"]: t async for t in db.teams.find({"show_id": ROOT})}
    plans = []
    for team in payload["teams"]:
        old = existing.get(team["slug"])
        if not old and not team.get("new"):
            raise ValueError(f'Не найдена старая команда {team["name"]}')
        if old and old.get("status") == "archived":
            raise ValueError("Найдена архивная карточка; автоматическая замена запрещена")
        if old and old.get("facts", {}).get("Звёзды (3 сезон)") not in (None, " и ".join(team["stars"])):
            raise ValueError("Звёзды третьего сезона уже отредактированы в карточке команды")
        if old and team.get("new"):
            expected = team_payload(team, payload, people).model_dump(mode="json")
            for expected_module in expected["modules"]:
                actual = next((m for m in old["modules"] if m["id"] == expected_module["id"]), None)
                if not actual or actual["data"]["content"] != expected_module["data"]["content"]:
                    raise ValueError("По адресу новой команды уже есть другая редакционная карточка")
        if old and not team.get("new"):
            # Проверка редакторских конфликтов для всех составов до первой записи.
            checked_modules = deepcopy(old["modules"])
            put_module(checked_modules, roster_module(team, people))
        new = team_payload(team, payload, people) if not old else None
        if new:
            await check_primary_tag_duplicate("teams", new.primary_tag)
        plans.append((team, old, new))
    season_new = season_modules(pages[SEASON], payload, people)
    directory_new = deepcopy(pages[DIRECTORY]["modules"])
    put_module(directory_new, module("directory", "Команды третьего сезона", roster_table(payload, people)))
    report = {"action": "дополнить" if not args.apply else "дополнено", "festivals": 3,
              "new_teams": [t["name"] for t, old, _ in plans if not old], "updated_teams": [t["name"] for t, old, _ in plans if old], "duel_teams": 8}
    if not args.apply:
        return report
    backup = Path(args.backup_dir) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup.mkdir(parents=True, exist_ok=False)
    snapshot = {"shows": list(pages.values()), "teams": list(existing.values()),
                "memberships": await db.memberships.find({"team_id": {"$in": [t["_id"] for t in existing.values()]}}).to_list(None),
                "show_appearances": await db.show_appearances.find({"show_id": ROOT}).to_list(None)}
    related_ids = [ident for team in payload["teams"] for ident in team.get("related_team_ids", [])]
    snapshot["related_teams"] = await db.teams.find({"_id": {"$in": related_ids}}).to_list(None)
    (backup / "before.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    written = False
    try:
        target_ids = []
        for team, old, new in plans:
            if not old:
                result = await create_team(new)
                target_ids.append(result["id"])
                written = True
                if team.get("aliases"):
                    # Обычный create_team пока не переносит aliases из TeamCreate в Team.
                    await db.teams.update_one({"_id": result["id"]}, {"$set": {"aliases": team["aliases"]}})
                continue
            modules = deepcopy(old["modules"])
            if not team.get("new"):
                put_module(modules, roster_module(team, people))
            facts = deepcopy(old.get("facts", {}))
            order = list(old.get("facts_order") or facts)
            if "Звёзды" in facts:
                facts["Звёзды (1–2 сезоны)"] = facts.pop("Звёзды")
                order = ["Звёзды (1–2 сезоны)" if k == "Звёзды" else k for k in order]
            facts["Звёзды (3 сезон)"] = " и ".join(team["stars"])
            if "Звёзды (3 сезон)" not in order:
                order.append("Звёзды (3 сезон)")
            query = {"_id": old["_id"], "modules": old["modules"], "facts": old.get("facts", {}), "updated_at": old.get("updated_at", {"$exists": False})}
            result = await db.teams.update_one(query, {"$set": {"modules": modules, "facts": facts, "facts_order": order, "updated_at": datetime.now(timezone.utc).isoformat()}})
            if result.matched_count != 1:
                raise ValueError("Карточка команды изменилась параллельно")
            written = True
            await import_team_rosters(db, await db.teams.find_one({"_id": old["_id"]}))
            target_ids.append(old["_id"])
        for ident, modules in ((SEASON, season_new), (DIRECTORY, directory_new)):
            old = pages[ident]
            changes = {"modules": modules, "updated_at": datetime.now(timezone.utc).isoformat()}
            if ident == SEASON:
                facts = deepcopy(old["facts"])
                facts["Количество команд"] = "11 конкурсных команд и специальный гость «Камызяки»"
                facts["Количество эфиров"] = "3 фестивальных выпуска (на 01.10.2026)"
                changes["facts"] = facts
            result = await db.shows.update_one({"_id": ident, "modules": old["modules"], "updated_at": old.get("updated_at", {"$exists": False})}, {"$set": changes})
            if result.matched_count != 1:
                raise ValueError("Страница шоу изменилась параллельно")
        await db.shows.update_one({"_id": ROOT}, {"$addToSet": {"team_ids": {"$each": target_ids}},
                                                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
        report["appearance_variants"] = await sync_target_appearances(db)
        await db.shows.update_one({"_id": SEASON}, {"$set": {"season_research_import": {"fingerprint": stamp, "as_of": payload["as_of"]}}})
        report["backup"] = str(backup)
    finally:
        if written:
            await cache_service.invalidate_everywhere(db)
    return report


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir")
    args = parser.parse_args()
    if args.apply and not args.backup_dir:
        parser.error("Для записи требуется --backup-dir")
    try:
        print(json.dumps(await run(args), ensure_ascii=False, indent=2))
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
