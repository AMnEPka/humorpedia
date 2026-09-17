#!/usr/bin/env python3
"""
Импорт команд шоу со старого сайта (страницы команд внутри раздела «Шоу» SQL-дампа MODX).

Команда сохраняется тем же кодом, что кнопка «Сохранить» в админке (POST/PUT /api/content/teams, с show_id
корневого шоу), затем дописываются поля старого сайта: old_id, old_urls, рейтинг, даты. Шоу должно быть
перенесено раньше (scripts/import_shows_modx.py). Существующая команда находится по old_id, затем по адресу
в шоу; при --update пересоздаётся с тем же _id. Адрес — /shows/{шоу}/teams/{slug}.

Основной тег — название; если он занят другой командой или человеком — «Название (Шоу)».

Использование (внутри контейнера backend):
    python scripts/import_show_teams_modx.py --list                      # команды по шоу и что уже в базе
    python scripts/import_show_teams_modx.py --ids 1926 2005             # пробный прогон
    python scripts/import_show_teams_modx.py --ids 1858 --show           # документ целиком
    python scripts/import_show_teams_modx.py --shows 1658 --apply        # все команды шоу (id шоу MODX)
    python scripts/import_show_teams_modx.py --all --publish 1649 --apply --update   # все; 1649 — команды шоу опубликовать
"""
import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from models.content import Team, TeamCreate, TeamUpdate  # noqa: E402
from routes.content_teams import create_team, update_team  # noqa: E402
from routes.redirects import _try_pattern_redirect  # noqa: E402
from services.cache import cache_service  # noqa: E402
from services.link_resolver import load_old_id_urls  # noqa: E402
from services.modx_content import LinkMapper  # noqa: E402
from services.modx_dump import load_modx_site  # noqa: E402
from services.modx_show_teams import build_show_team, link_builders, show_team_pages, team_show_resource  # noqa: E402
from services.show_teams import team_url  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402

DEFAULT_DUMP = "/app/backups/idemsku8_modx2.sql"
TEAM_FIELDS = {field.alias or name for name, field in Team.model_fields.items()} | {"old_urls", "old_id", "roster_import"}


async def main(args) -> None:
    try:
        await run(args)
    finally:
        await close_db()


async def run(args) -> None:
    print(f"Читаю дамп {args.dump} …")
    site = load_modx_site(args.dump)
    pages = show_team_pages(site)
    show_of = {rid: team_show_resource(site, r) for rid, r in pages.items()}
    db = await get_db()

    if args.list:
        in_db = {d["old_id"] async for d in db.teams.find({"old_id": {"$in": list(pages)}}, {"old_id": 1})}
        by_show = defaultdict(list)
        for rid, r in pages.items():
            by_show[show_of[rid]["id"]].append(r)
        for show_rid, teams in by_show.items():
            show = site.resources[show_rid]
            print(f"\n{show_rid} {show['pagetitle']}: {len(teams)} команд, перенесено {len(in_db & {t['id'] for t in teams})}")
            for r in sorted(teams, key=lambda t: t["pagetitle"]):
                flag = "" if r["published"] else " (не опубликовано)"
                print(f"  {'✓' if r['id'] in in_db else ' '} {r['id']:5} {r['pagetitle']}{flag}  {r['uri']}")
        return

    ids = [i for i in (args.ids or []) if i in pages]
    for i in set(args.ids or []) - set(ids):
        print(f"[!] {i}: не страница команды шоу")
    if args.shows:
        ids += [rid for rid in pages if show_of[rid]["id"] in set(args.shows) and rid not in ids]
    if args.all:
        ids = list(pages)
    if not ids:
        raise SystemExit("Укажите --ids, --shows или --all (или --list)")
    ids.sort(key=lambda rid: (show_of[rid]["id"], pages[rid]["pagetitle"]))

    known_urls = await load_old_id_urls(db)
    publish = set(args.publish or [])
    totals = defaultdict(int)
    for rid in ids:
        do_publish = rid in publish or show_of[rid]["id"] in publish
        result = await import_one(db, site, pages[rid], show_of[rid], known_urls, do_publish, args)
        totals[result] += 1
    if args.apply:
        await cache_service.invalidate_everywhere(db)
    print(f"\nИтого: {dict(totals)}" if args.apply else "\nПробный прогон: ничего не записано (добавьте --apply).")


async def free_primary_tag(db, name: str, show_title: str, exclude_id) -> str:
    """Название, если такой основной тег свободен (команды и люди), иначе «Название (Шоу)»."""
    pattern = {"$regex": f"^{re.escape(name)}$", "$options": "i"}
    taken = await db.teams.find_one({"primary_tag": pattern, "_id": {"$ne": exclude_id}}, {"_id": 1}) \
        or await db.people.find_one({"primary_tag": pattern}, {"_id": 1})
    return f"{name} ({show_title})" if taken else name


async def import_one(db, site, resource, show_resource, known_urls, publish, args) -> str:
    rid = resource["id"]
    mapper = LinkMapper(site, _try_pattern_redirect, known_urls, *link_builders(site))
    payload, extra, warnings = build_show_team(site, rid, mapper)
    if publish and payload["status"] != "published":
        payload["status"] = "published"
        if extra.get("created_at"):
            extra["published_at"] = extra["created_at"]

    show = await db.shows.find_one({"old_id": show_resource["id"]})
    if not show:
        print(f"\n✗ {rid} {payload['title']}: шоу «{show_resource['pagetitle']}» (old_id {show_resource['id']}) ещё не перенесено")
        return "failed"
    existing = await db.teams.find_one({"old_id": rid}) \
        or await db.teams.find_one({"show_id": show["_id"], "slug": payload["slug"]})
    payload["primary_tag"] = await free_primary_tag(db, payload["name"], show.get("title") or "", existing and existing["_id"])
    url = team_url({"full_path": f"{show['full_path']}/teams/{payload['slug']}"})

    modules = [m["type"] + (f"«{m['title']}»" if m["title"] else "") for m in payload["modules"][5:]]
    print(f"\n{rid} {resource['pagetitle']} → «{payload['title']}» {url} [{'существует' if existing else 'новая'}, {payload['status']}]")
    print(f"  факты: {payload['facts_order']}; соцсети: {sorted(k for k, v in payload['social_links'].items() if v)}; "
          f"лого: {'есть' if payload['logo'] else 'нет'}; тег: {payload['primary_tag']}; тегов: {len(payload['tags'])}")
    print(f"  модули: {', '.join(modules)}")
    for w in warnings:
        print(f"  ⚠ {w}")
    if args.show:
        print(json.dumps({**payload, **extra}, ensure_ascii=False, indent=1))
    if not args.apply:
        return "dry"
    if existing and not args.update:
        print("  пропущено: уже есть (для перезаписи --update)")
        return "skipped"

    try:
        if existing:
            team_id = existing["_id"]
            await update_team(team_id, TeamUpdate(**payload, show_id=show["_id"]))
        else:
            team_id = (await create_team(TeamCreate(**payload, show_id=show["_id"])))["id"]
    except Exception as e:  # одна проблемная страница не останавливает партию
        print(f"  ✗ не сохранено: {getattr(e, 'detail', None) or e}")
        return "failed"

    update = {"$set": dict(extra)}
    if existing:
        current = await db.teams.find_one({"_id": team_id})
        legacy = [k for k in current if k not in TEAM_FIELDS]
        if legacy:
            update["$unset"] = {k: "" for k in legacy}
        defaults = Team(title=payload["title"], slug=payload["slug"], name=payload["name"]).model_dump(by_alias=True)
        for key, value in defaults.items():
            if key not in current and key not in extra:
                update["$set"][key] = value.isoformat() if hasattr(value, "isoformat") else value
    await db.teams.update_one({"_id": team_id}, update)
    known_urls[rid] = url
    print(f"  ✓ сохранено, id {team_id}")
    return "updated" if existing else "created"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dump", default=DEFAULT_DUMP)
    parser.add_argument("--ids", nargs="*", type=int, help="id страниц команд MODX")
    parser.add_argument("--shows", nargs="*", type=int, help="id корневых шоу MODX — все их команды")
    parser.add_argument("--all", action="store_true", help="все команды шоу")
    parser.add_argument("--publish", nargs="*", type=int,
                        help="id неопубликованных команд (или шоу — все его команды), которые опубликовать")
    parser.add_argument("--list", action="store_true", help="команды шоу и что уже в базе")
    parser.add_argument("--show", action="store_true", help="напечатать документ целиком")
    parser.add_argument("--apply", action="store_true", help="записать в базу")
    parser.add_argument("--update", action="store_true", help="перезаписать существующие")
    asyncio.run(main(parser.parse_args()))
