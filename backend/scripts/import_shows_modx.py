#!/usr/bin/env python3
"""
Импорт шоу со старого сайта (раздел «Шоу» SQL-дампа MODX) — партиями, на проверку.

Страница сохраняется тем же кодом, что кнопка «Сохранить» в админке (POST/PUT /api/content/shows),
затем дописываются поля старого сайта: old_id, old_urls, рейтинг, даты. Сезоны и подпроекты — дочерние шоу
(/shows/<шоу>/<сезон>); родитель должен быть перенесён раньше (с --tree порядок соблюдается сам).
Существующее шоу находится по old_id, затем по адресу; при --update пересоздаётся с тем же _id.

Использование (внутри контейнера backend):
    python scripts/import_shows_modx.py --list                        # дерево раздела и что уже в базе
    python scripts/import_shows_modx.py --ids 1617 1646               # пробный прогон
    python scripts/import_shows_modx.py --ids 1622 --show             # документ целиком
    python scripts/import_shows_modx.py --ids 1617 1646 --apply --update
    python scripts/import_shows_modx.py --ids 1625 --tree --apply     # шоу вместе со всеми подстраницами
    python scripts/import_shows_modx.py --all --apply --update        # весь раздел (родители раньше детей)
    python scripts/import_shows_modx.py --ids 1649 --publish 1649 --apply   # неопубликованное на старом сайте — опубликовать
"""
import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from models.content import Show, ShowCreate, ShowUpdate  # noqa: E402
from routes.content_shows import ROOT_QUERY, create_show, update_show  # noqa: E402
from routes.redirects import _try_pattern_redirect  # noqa: E402
from services.cache import cache_service  # noqa: E402
from services.link_resolver import load_old_id_urls  # noqa: E402
from services.modx_content import LinkMapper  # noqa: E402
from services.modx_dump import load_modx_site  # noqa: E402
from services.modx_show_teams import link_builders  # noqa: E402
from services.modx_shows import build_show, is_show_page, section_id, show_chain, show_path  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402

DEFAULT_DUMP = "/app/backups/idemsku8_modx2.sql"
SHOW_FIELDS = {field.alias or name for name, field in Show.model_fields.items()} | {"old_urls"}


async def main(args) -> None:
    try:
        await run(args)
    finally:
        await close_db()


async def find_existing(db, resource: dict, full_path: str, slug: str, is_root: bool):
    """Уже перенесённое шоу: по old_id, по адресу; у корневых — по slug или alias старого сайта (старый импорт)."""
    doc = await db.shows.find_one({"old_id": resource["id"]})
    if doc:
        return doc
    doc = await db.shows.find_one({"full_path": full_path, "old_id": None})
    if doc or not is_root:
        return doc
    slugs = list({slug, (resource.get("alias") or "").strip("/")})
    return await db.shows.find_one({"slug": {"$in": slugs}, "old_id": None, **ROOT_QUERY})


async def run(args) -> None:
    print(f"Читаю дамп {args.dump} …")
    site = load_modx_site(args.dump)
    root_id = section_id(site)
    pages = {rid: r for rid, r in site.resources.items() if is_show_page(site, r, root_id)}
    children = defaultdict(list)
    for rid, r in pages.items():
        children[r["parent"]].append(rid)
    depth = {rid: len(show_chain(site, r, root_id)) for rid, r in pages.items()}
    db = await get_db()

    if args.list:
        in_db = {d.get("old_id") async for d in db.shows.find({"old_id": {"$ne": None}}, {"old_id": 1})}

        def walk(parent, level):
            for rid in sorted(children.get(parent, []), key=lambda i: (pages[i]["menuindex"], pages[i]["pagetitle"])):
                r = pages[rid]
                flag = "" if r["published"] else " (не опубликовано)"
                mark = "✓" if rid in in_db else " "
                print(f"{mark} {rid:5} {'   ' * level}{r['pagetitle'][:50]}{flag}  /shows/{show_path(site, r, root_id)}")
                walk(rid, level + 1)
        walk(root_id, 0)
        print(f"Страниц шоу: {len(pages)}, перенесено: {len(in_db & set(pages))}")
        return

    ids = [i for i in (args.ids or []) if i in pages]
    if args.all:
        ids = [rid for rid, r in pages.items() if r["parent"] == root_id]
        args.tree = True
    for i in set(args.ids or []) - set(ids):
        print(f"[!] {i}: не страница раздела «Шоу» (или команда шоу)")
    if args.tree:
        stack = list(ids)
        while stack:
            for child in children.get(stack.pop(), []):
                if child not in ids:
                    ids.append(child)
                    stack.append(child)
    ids.sort(key=lambda i: (depth[i], pages[i]["menuindex"], i))
    if not ids:
        raise SystemExit("Укажите --ids или --all (или --list)")

    known_urls = await load_old_id_urls(db)
    builders = link_builders(site)
    publish = set(args.publish or [])
    totals = defaultdict(int)
    for rid in ids:
        result = await import_one(db, site, pages[rid], root_id, known_urls, builders, rid in publish, args)
        totals[result] += 1
    if args.apply:
        await cache_service.invalidate_everywhere(db)
    print(f"\nИтого: {dict(totals)}" if args.apply else "\nПробный прогон: ничего не записано (добавьте --apply).")


async def import_one(db, site, resource, root_id, known_urls, builders, publish, args) -> str:
    rid = resource["id"]
    mapper = LinkMapper(site, _try_pattern_redirect, known_urls, *builders)
    payload, extra, warnings = build_show(site, rid, mapper)
    if publish and payload["status"] != "published":
        payload["status"] = "published"
        if extra.get("created_at"):
            extra["published_at"] = extra["created_at"]

    parent_doc = None
    if resource["parent"] != root_id:
        parent_doc = await db.shows.find_one({"old_id": resource["parent"]})
        if not parent_doc:
            print(f"\n✗ {rid} {payload['title']}: родитель (old_id {resource['parent']}) ещё не перенесён")
            return "failed"
    payload["parent_id"] = parent_doc["_id"] if parent_doc else None
    full_path = f"{parent_doc['full_path']}/{payload['slug']}" if parent_doc else payload["slug"]
    existing = await find_existing(db, resource, full_path, payload["slug"], parent_doc is None)

    modules = [m["type"] + (f"«{m['title']}»" if m["type"] == "text_block" and m["title"] else "")
               for m in payload["modules"][5:]]
    print(f"\n{rid} {payload['title']} → /shows/{full_path} [{'существует' if existing else 'новое'}, {payload['status']}]")
    print(f"  факты: {payload['facts_order']}; соцсети: {sorted(k for k, v in payload['social_links'].items() if v)}; "
          f"постер: {'есть' if payload['poster'] else 'нет'}; тегов: {len(payload['tags'])}")
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
            show_id = existing["_id"]
            await update_show(show_id, ShowUpdate(**payload))
        else:
            show_id = (await create_show(ShowCreate(**payload)))["id"]
    except Exception as e:  # одна проблемная страница не останавливает партию
        print(f"  ✗ не сохранено: {getattr(e, 'detail', None) or e}")
        return "failed"

    update = {"$set": dict(extra)}
    if existing:
        current = await db.shows.find_one({"_id": show_id})
        legacy = [k for k in current if k not in SHOW_FIELDS]
        if legacy:
            update["$unset"] = {k: "" for k in legacy}
        defaults = Show(title=payload["title"], slug=payload["slug"], name=payload["name"]).model_dump(by_alias=True)
        for key, value in defaults.items():
            if key not in current and key not in extra:
                update["$set"][key] = value.isoformat() if hasattr(value, "isoformat") else value
    await db.shows.update_one({"_id": show_id}, update)
    known_urls[rid] = f"/shows/{full_path}"
    print(f"  ✓ сохранено, id {show_id}")
    return "updated" if existing else "created"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dump", default=DEFAULT_DUMP)
    parser.add_argument("--ids", nargs="*", type=int, help="id ресурсов MODX")
    parser.add_argument("--tree", action="store_true", help="вместе со всеми подстраницами")
    parser.add_argument("--all", action="store_true", help="весь раздел «Шоу» (все верхние шоу с подстраницами)")
    parser.add_argument("--publish", nargs="*", type=int, help="id неопубликованных на старом сайте, которые опубликовать")
    parser.add_argument("--list", action="store_true", help="дерево раздела «Шоу»")
    parser.add_argument("--show", action="store_true", help="напечатать документ целиком")
    parser.add_argument("--apply", action="store_true", help="записать в базу")
    parser.add_argument("--update", action="store_true", help="перезаписать существующие")
    asyncio.run(main(parser.parse_args()))
