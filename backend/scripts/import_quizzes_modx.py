#!/usr/bin/env python3
"""Import legacy MODX quizzes through the normal content CRUD path.

Run inside the backend container:
    python scripts/import_quizzes_modx.py --list
    python scripts/import_quizzes_modx.py --all
    python scripts/import_quizzes_modx.py --all --apply

Without ``--apply`` the command is a dry run. ``--all`` imports only published
resources unless ``--include-unpublished`` is explicitly supplied.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from models.content import Quiz, QuizCreate, QuizUpdate  # noqa: E402
from routes.content_quizzes import create_quiz, update_quiz  # noqa: E402
from routes.redirects import _try_pattern_redirect  # noqa: E402
from services.cache import cache_service  # noqa: E402
from services.link_resolver import load_old_id_urls  # noqa: E402
from services.modx_articles_news import content_url_builder  # noqa: E402
from services.modx_content import IMPORTED_IMAGES_PREFIX, LinkMapper  # noqa: E402
from services.modx_dump import load_modx_site  # noqa: E402
from services.modx_quizzes import build_quiz, quiz_path_builder, quiz_resources, quiz_url_builder  # noqa: E402
from services.modx_show_teams import link_builders  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402


DEFAULT_DUMP = "/app/backups/idemsku8_modx2.sql"
MEDIA_ROOT = "/app/media/imported"
MODEL_FIELDS = {field.alias or name for name, field in Quiz.model_fields.items()} | {"old_urls"}


def _media_exists(url: str) -> bool:
    if not url or not url.startswith(IMPORTED_IMAGES_PREFIX):
        return True
    return os.path.exists(os.path.join(MEDIA_ROOT, url[len(IMPORTED_IMAGES_PREFIX):]))


def _missing_media(payload: dict) -> set[str]:
    urls: set[str] = set()
    cover = payload.get("cover_image") or {}
    if str(cover.get("url") or "").startswith(IMPORTED_IMAGES_PREFIX):
        urls.add(cover["url"])
    for module in payload.get("modules") or []:
        for item in (module.get("data") or {}).get("questions", []):
            if str(item.get("image") or "").startswith(IMPORTED_IMAGES_PREFIX):
                urls.add(item["image"])
        for item in (module.get("data") or {}).get("results", []):
            if str(item.get("image") or "").startswith(IMPORTED_IMAGES_PREFIX):
                urls.add(item["image"])
    return {url for url in urls if not _media_exists(url)}


async def main(args) -> None:
    try:
        await run(args)
    finally:
        await close_db()


async def run(args) -> None:
    print(f"Читаю дамп {args.dump} …")
    site = load_modx_site(
        args.dump,
        keep_content_for=lambda resource: resource.get("parent") == 31 or resource.get("id") == 31,
    )
    resources = {resource["id"]: resource for resource in quiz_resources(site, include_unpublished=True)}
    db = await get_db()
    existing = [doc async for doc in db.quizzes.find({}, {"slug": 1, "old_id": 1, "title": 1})]

    if args.list:
        imported_old_ids = {doc.get("old_id") for doc in existing}
        imported_slugs = {doc.get("slug") for doc in existing}
        published = sum(bool(resource.get("published")) for resource in resources.values())
        imported = sum(
            resource_id in imported_old_ids or resource.get("alias") in imported_slugs
            for resource_id, resource in resources.items()
        )
        print(f"quizzes: всего {len(resources)}, опубликовано {published}, уже в базе {imported}")
        if not (args.ids or args.slugs or args.all):
            return

    selected = select_resources(args, resources)
    if not selected:
        raise SystemExit("Нет ресурсов для импорта: укажите --ids, --slugs или --all")

    known_urls = await load_old_id_urls(db)
    legacy_url_builders, legacy_path_builders = link_builders(site)
    mapper = LinkMapper(
        site,
        _try_pattern_redirect,
        known_urls,
        [
            quiz_url_builder(site),
            content_url_builder(site, "article"),
            content_url_builder(site, "news"),
            *legacy_url_builders,
        ],
        [quiz_path_builder(site), *legacy_path_builders],
    )
    totals = defaultdict(int)
    missing_media: set[str] = set()
    verbose = not args.all or args.show

    for resource_id in selected:
        payload, extra, warnings = build_quiz(site, resource_id, mapper)
        missing = _missing_media(payload)
        missing_media.update(missing)
        if missing:
            warnings.append(f"нет файлов изображений в volume: {len(missing)}")
        existing_doc = next((doc for doc in existing if doc.get("old_id") == resource_id), None)
        if existing_doc is None:
            existing_doc = next((doc for doc in existing if doc.get("slug") == payload["slug"]), None)

        if verbose:
            print(f"\n{resource_id} {payload['title']} → /quizzes/{payload['slug']} "
                  f"[{'существует' if existing_doc else 'новый'}]")
            print(f"  вопросов: {payload['questions_count']}; результатов: "
                  f"{len(payload['modules'][1]['data']['results'])}; тегов: {len(payload['tags'])}")
            for warning in warnings:
                print(f"  ⚠ {warning}")
            if args.show:
                print(json.dumps({**payload, **extra}, ensure_ascii=False, indent=1))

        if not args.apply:
            totals["dry"] += 1
            continue
        if existing_doc and not args.update:
            totals["skipped"] += 1
            continue

        try:
            if existing_doc:
                await update_quiz(existing_doc["_id"], QuizUpdate(**payload))
                document_id = existing_doc["_id"]
                result = "updated"
            else:
                document_id = (await create_quiz(QuizCreate(**payload)))["id"]
                result = "created"
        except Exception as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            print(f"  ✗ {resource_id} {payload['title']}: не сохранён: {detail}")
            totals["failed"] += 1
            continue

        update = {"$set": extra}
        if existing_doc:
            current = await db.quizzes.find_one({"_id": document_id})
            legacy = [key for key in current if key not in MODEL_FIELDS]
            if legacy:
                update["$unset"] = {key: "" for key in legacy}
        await db.quizzes.update_one({"_id": document_id}, update)
        existing.append({"_id": document_id, "slug": payload["slug"], "old_id": resource_id})
        known_urls[resource_id] = f"/quizzes/{payload['slug']}"
        totals[result] += 1

    if args.apply:
        await cache_service.invalidate_everywhere(db)
    if mapper.unresolved:
        unique = list(dict.fromkeys(mapper.unresolved))
        print(f"Неразрешённых старых ссылок: {len(unique)}" + (f"; примеры: {unique[:5]}" if unique else ""))
    if missing_media:
        print(f"Нет файлов в media-volume: {len(missing_media)}; примеры: {sorted(missing_media)[:10]}")
    print(f"Итого: {dict(totals)}" if args.apply else "Пробный прогон: ничего не записано (добавьте --apply).")


def select_resources(args, resources: dict[int, dict]) -> list[int]:
    ids = set(args.ids or [])
    slugs = set(args.slugs or [])
    selected = []
    for resource_id, resource in resources.items():
        if args.all:
            if args.include_unpublished or resource.get("published"):
                selected.append(resource_id)
        elif resource_id in ids or resource.get("alias") in slugs:
            selected.append(resource_id)
    return sorted(selected)


def parse_args():
    parser = argparse.ArgumentParser(description="Импорт квизов из MODX")
    parser.add_argument("--ids", nargs="*", type=int)
    parser.add_argument("--slugs", nargs="*")
    parser.add_argument("--all", action="store_true", help="все опубликованные квизы")
    parser.add_argument("--include-unpublished", action="store_true", help="с --all также импортировать черновики")
    parser.add_argument("--list", action="store_true", help="показать сводку дампа и состояние импорта")
    parser.add_argument("--apply", action="store_true", help="записать в MongoDB")
    parser.add_argument("--update", action="store_true", help="обновить уже импортированные документы")
    parser.add_argument("--show", action="store_true", help="показать собранный документ")
    parser.add_argument("--dump", default=DEFAULT_DUMP)
    args = parser.parse_args()
    if args.include_unpublished and not args.all:
        parser.error("--include-unpublished используется только вместе с --all")
    if args.update and not args.apply:
        parser.error("--update используется только вместе с --apply")
    return args


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
