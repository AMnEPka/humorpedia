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
    python scripts/import_people_modx.py --all --apply                   # всех опубликованных, кого ещё нет, группами по 75 (--batch N)
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

from models.content import Person, PersonCreate, PersonUpdate  # noqa: E402
from routes.content_people import create_person, update_person  # noqa: E402
from routes.redirects import _try_pattern_redirect  # noqa: E402
from services.cache import cache_service  # noqa: E402
from services.crud import check_primary_tag_duplicate  # noqa: E402
from services.link_resolver import load_old_id_urls  # noqa: E402
from services.modx_content import IMPORTED_IMAGES_PREFIX, LinkMapper  # noqa: E402
from services.modx_dump import load_modx_site  # noqa: E402
from services.modx_people import TEMPLATE_PERSON, build_person, person_resources  # noqa: E402
from services.modx_show_teams import link_builders  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402

DEFAULT_DUMP = "/app/backups/idemsku8_modx2.sql"
MEDIA_ROOT = "/app/media/imported"
# Поля документа, который сохраняет админка (+ old_urls); остальное у старых записей удаляется при --update
PERSON_FIELDS = {field.alias or name for name, field in Person.model_fields.items()} | {"old_urls"}


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
    if args.all:
        skipped = [r for r in people.values() if not r.get("published")]
        ids = sorted(rid for rid, r in people.items() if r.get("published") and r.get("alias") not in existing)
        print(f"К импорту: {len(ids)} (неопубликованных на старом сайте пропущено: {len(skipped)})")
    if not ids:
        raise SystemExit("Укажите --ids, --slugs или --all (или --list)")

    known_urls = await load_old_id_urls(db)
    verbose = not args.all
    totals = {"created": 0, "updated": 0, "failed": 0, "warnings": 0}
    for batch_no, start in enumerate(range(0, len(ids), args.batch), start=1):
        batch = ids[start:start + args.batch]
        stats = {"created": 0, "updated": 0, "failed": 0}
        for rid in batch:
            if rid not in people:
                print(f"[!] {rid}: не страница человека (или удалена)")
                continue
            result = await import_one(db, site, people, rid, existing, known_urls, args, verbose)
            if result in stats:
                stats[result] += 1
        for key, value in stats.items():
            totals[key] += value
        if args.apply:
            await cache_service.invalidate_everywhere(db)
        if args.all:
            print(f"Группа {batch_no}: {len(batch)} чел. — создано {stats['created']}, обновлено {stats['updated']}, "
                  f"ошибок {stats['failed']} (всего создано {totals['created']})")
    print(f"\nИтого: {totals}" if args.apply else "\nПробный прогон: ничего не записано (добавьте --apply).")


async def import_one(db, site, people, rid, existing, known_urls, args, verbose) -> str:
    mapper = LinkMapper(site, _try_pattern_redirect, known_urls, *link_builders(site))
    payload, extra, warnings = build_person(site, rid, mapper)
    slug = payload["slug"]
    photo = payload.get("photo") or {}
    if photo and not _photo_exists(photo["url"]):
        warnings.append(f"файла фото нет в volume: {photo['url']}")
    exists = slug in existing
    if verbose:
        modules = [m["type"] + (f"({len(m['data']['events'])})" if m["type"] == "timeline" else "")
                   for m in payload["modules"]]
        print(f"\n{rid} {payload['title']} → /people/{slug} [{'существует' if exists else 'новый'}]")
        print(f"  факты: {payload['facts_order']}; соцсети: {sorted(payload['social_links'])}; теги: {payload['tags']}")
        print(f"  модули: {', '.join(modules)}; рейтинг: {extra['rating']}")
        for w in warnings:
            print(f"  ⚠ {w}")
        if args.show:
            print(json.dumps({**payload, **extra}, ensure_ascii=False, indent=1))
    if not args.apply:
        return "dry"
    if exists and not args.update:
        if verbose:
            print("  пропущен: уже есть (для перезаписи --update)")
        return "skipped"
    person_id = existing[slug]["_id"] if exists else None
    try:
        payload["primary_tag"] = await free_primary_tag(payload, person_id)
        if exists:
            await update_person(person_id, PersonUpdate(**payload))
        else:
            person_id = (await create_person(PersonCreate(**payload)))["id"]
    except Exception as e:  # одна проблемная страница не должна останавливать импорт
        detail = getattr(e, "detail", None) or str(e)
        print(f"  ✗ {rid} {payload['title']}: не сохранён: {detail}")
        return "failed"
    update = {"$set": extra}
    if exists:
        current = await db.people.find_one({"_id": person_id})
        legacy = [k for k in current if k not in PERSON_FIELDS]
        if legacy:
            update["$unset"] = {k: "" for k in legacy}
        # поля, которые админка заполняет значениями по умолчанию при создании (bio, team_ids, …)
        defaults = Person(title=payload["title"], slug=slug, full_name=payload["full_name"]).model_dump(by_alias=True)
        for key, value in defaults.items():
            if key not in current and key not in extra:
                extra[key] = value.isoformat() if hasattr(value, "isoformat") else value
    await db.people.update_one({"_id": person_id}, update)
    existing[slug] = {"_id": person_id, "slug": slug}
    known_urls[rid] = f"/people/{slug}"
    if verbose:
        print(f"  ✓ сохранён, id {person_id}")
    return "updated" if exists else "created"


async def free_primary_tag(payload: dict, person_id) -> str:
    """Базовый тег «Имя Фамилия»; если он занят (тёзка или команда) — полное имя, затем «Имя Фамилия (slug)»."""
    candidates = [payload["primary_tag"], payload["full_name"], f"{payload['primary_tag']} ({payload['slug']})"]
    for tag in dict.fromkeys(c for c in candidates if c):
        try:
            await check_primary_tag_duplicate("people", tag, person_id)
            await check_primary_tag_duplicate("teams", tag)
            return tag
        except HTTPException:
            continue
    return candidates[-1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Импорт людей из SQL-дампа MODX")
    parser.add_argument("--dump", default=DEFAULT_DUMP)
    parser.add_argument("--ids", nargs="*", type=int, help="id ресурсов MODX")
    parser.add_argument("--slugs", nargs="*", help="alias страниц старого сайта")
    parser.add_argument("--list", action="store_true", help="список людей дампа")
    parser.add_argument("--show", action="store_true", help="напечатать документ целиком")
    parser.add_argument("--apply", action="store_true", help="записать в базу")
    parser.add_argument("--update", action="store_true", help="перезаписать существующих (по slug)")
    parser.add_argument("--all", action="store_true", help="всех опубликованных, кого ещё нет в базе")
    parser.add_argument("--batch", type=int, default=75, help="размер группы (по умолчанию 75)")
    asyncio.run(main(parser.parse_args()))
