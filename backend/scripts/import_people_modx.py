#!/usr/bin/env python3
"""
Импорт людей со старого сайта (SQL-дамп MODX) — небольшими партиями, на проверку.

Страница создаётся тем же кодом, что и кнопка «Сохранить» в админке (POST /api/content/people),
поэтому документ получается таким же, как созданный вручную. Затем дописываются поля старого сайта:
old_id, old_urls (для редиректов), рейтинг и даты.

Использование (внутри контейнера backend):
    python scripts/import_people_modx.py --ids 117 130                  # пробный прогон: отчёт без записи
    python scripts/import_people_modx.py --slugs phil-voronin --show     # показать документ целиком
    python scripts/import_people_modx.py --ids 117 130 --apply           # создать
    python scripts/import_people_modx.py --ids 117 --apply --update      # пересоздать содержимое существующих
    python scripts/import_people_modx.py --list                          # все люди дампа и статус импорта
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from fastapi import HTTPException  # noqa: E402

from models.content import PersonCreate, PersonUpdate  # noqa: E402
from routes.content_people import create_person, update_person  # noqa: E402
from routes.redirects import _try_pattern_redirect  # noqa: E402
from services.cache import cache_service  # noqa: E402
from services.modx_content import IMPORTED_IMAGES_PREFIX, LinkMapper  # noqa: E402
from services.modx_dump import load_modx_site  # noqa: E402
from services.modx_people import TEMPLATE_PERSON, build_person, person_resources  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402

DEFAULT_DUMP = "/app/backups/idemsku8_modx2.sql"
MEDIA_ROOT = "/app/media/imported"


def _photo_exists(url: str) -> bool:
    if not url or not url.startswith(IMPORTED_IMAGES_PREFIX):
        return True
    return os.path.exists(os.path.join(MEDIA_ROOT, url[len(IMPORTED_IMAGES_PREFIX):]))


async def main(args) -> None:
    try:
        await run(args)
    finally:
        await close_db()


async def run(args) -> None:
    print(f"Читаю дамп {args.dump} …")
    site = load_modx_site(args.dump, keep_content_for=lambda r: r.get("template") == TEMPLATE_PERSON)
    people = {r["id"]: r for r in person_resources(site, include_unpublished=True)}
    by_slug = {r.get("alias"): rid for rid, r in people.items()}
    db = await get_db()
    existing = {p["slug"]: p async for p in db.people.find({}, {"slug": 1, "old_id": 1, "title": 1})}

    if args.list:
        for rid, r in sorted(people.items(), key=lambda x: x[1]["pagetitle"]):
            state = "в базе" if r.get("alias") in existing else ""
            flag = "" if r.get("published") else " (не опубликован)"
            print(f"{rid:6}  {r['alias']:40} {r['pagetitle']}{flag}  {state}")
        print(f"Всего: {len(people)}, уже в базе: {sum(1 for r in people.values() if r.get('alias') in existing)}")
        return

    ids = list(args.ids or [])
    for slug in args.slugs or []:
        if slug not in by_slug:
            print(f"[!] slug {slug} не найден среди людей дампа")
            continue
        ids.append(by_slug[slug])
    if not ids:
        raise SystemExit("Укажите --ids или --slugs (или --list)")

    written = 0
    for rid in ids:
        if rid not in people:
            print(f"[!] {rid}: не страница человека (или удалена)")
            continue
        mapper = LinkMapper(site, _try_pattern_redirect)
        payload, extra, warnings = build_person(site, rid, mapper)
        slug = payload["slug"]
        photo = payload.get("photo") or {}
        if photo and not _photo_exists(photo["url"]):
            warnings.append(f"файла фото нет в volume: {photo['url']}")
        if mapper.unresolved:
            warnings.append("ссылки на страницы, которых нет в дампе: " + ", ".join(sorted(set(mapper.unresolved))))
        modules = [m["type"] + (f"({len(m['data']['events'])})" if m["type"] == "timeline" else "") for m in payload["modules"]]
        state = "существует" if slug in existing else "новый"
        print(f"\n{rid} {payload['title']} → /people/{slug} [{state}]")
        print(f"  факты: {payload['facts_order']}; соцсети: {sorted(payload['social_links'])}; теги: {payload['tags']}")
        print(f"  модули: {', '.join(modules)}; рейтинг: {extra['rating']}")
        for w in warnings:
            print(f"  ⚠ {w}")
        if args.show:
            print(json.dumps({**payload, **extra}, ensure_ascii=False, indent=1))

        if not args.apply:
            continue
        try:
            if slug in existing:
                if not args.update:
                    print("  пропущен: уже есть (для перезаписи --update)")
                    continue
                person_id = existing[slug]["_id"]
                await update_person(person_id, PersonUpdate(**payload))
            else:
                person_id = (await create_person(PersonCreate(**payload)))["id"]
        except HTTPException as e:
            print(f"  ✗ не сохранён: {e.detail}")
            continue
        await db.people.update_one({"_id": person_id}, {"$set": extra})
        written += 1
        print(f"  ✓ сохранён, id {person_id}")

    if args.apply and written:
        await cache_service.invalidate_everywhere(db)
    print("\nГотово." if args.apply else "\nПробный прогон: ничего не записано (добавьте --apply).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Импорт людей из SQL-дампа MODX")
    parser.add_argument("--dump", default=DEFAULT_DUMP)
    parser.add_argument("--ids", nargs="*", type=int, help="id ресурсов MODX")
    parser.add_argument("--slugs", nargs="*", help="alias страниц старого сайта")
    parser.add_argument("--list", action="store_true", help="список людей дампа")
    parser.add_argument("--show", action="store_true", help="напечатать документ целиком")
    parser.add_argument("--apply", action="store_true", help="записать в базу")
    parser.add_argument("--update", action="store_true", help="перезаписать существующих (по slug)")
    asyncio.run(main(parser.parse_args()))
