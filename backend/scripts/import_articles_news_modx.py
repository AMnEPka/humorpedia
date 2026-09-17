#!/usr/bin/env python3
"""Import legacy MODX articles and news through the normal content CRUD path.

Run inside the backend container:
    python scripts/import_articles_news_modx.py --all --list
    python scripts/import_articles_news_modx.py --kind article --ids 2161 --show
    python scripts/import_articles_news_modx.py --all --apply
    python scripts/import_articles_news_modx.py --all --apply --update

Without ``--apply`` the command is a dry run. ``--all`` imports only published
resources unless ``--include-unpublished`` is explicitly supplied.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from models.content import Article, ArticleCreate, ArticleUpdate, News, NewsCreate, NewsUpdate  # noqa: E402
from routes.content_articles import create_article, update_article  # noqa: E402
from routes.content_news import create_news, update_news  # noqa: E402
from routes.redirects import _try_pattern_redirect  # noqa: E402
from services.cache import cache_service  # noqa: E402
from services.link_resolver import load_old_id_urls  # noqa: E402
from services.modx_articles_news import (  # noqa: E402
    CONTENT_CONFIG, build_content, content_resources, content_url_builder, person_slugs_in_modules,
)
from services.modx_content import IMPORTED_IMAGES_PREFIX, LinkMapper  # noqa: E402
from services.modx_dump import load_modx_site  # noqa: E402
from services.modx_show_teams import link_builders  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402


DEFAULT_DUMP = "/app/backups/idemsku8_modx2.sql"
MEDIA_ROOT = "/app/media/imported"
MODEL_FIELDS = {
    "article": {field.alias or name for name, field in Article.model_fields.items()} | {"old_urls"},
    "news": {field.alias or name for name, field in News.model_fields.items()} | {"old_urls"},
}
_IMPORTED_MEDIA_RE = re.compile(r'(?:src|href)=["\'](/media/imported/[^"\']+)', re.I)


def _photo_exists(url: str) -> bool:
    if not url or not url.startswith(IMPORTED_IMAGES_PREFIX):
        return True
    return os.path.exists(os.path.join(MEDIA_ROOT, url[len(IMPORTED_IMAGES_PREFIX):]))


def _missing_media(payload: dict) -> set[str]:
    urls = set()
    cover = payload.get("cover_image") or {}
    if cover.get("url", "").startswith(IMPORTED_IMAGES_PREFIX):
        urls.add(cover["url"])
    for module in payload.get("modules") or []:
        data = module.get("data") or {}
        if str(data.get("url") or "").startswith(IMPORTED_IMAGES_PREFIX):
            urls.add(data["url"])
        value = data.get("content") or ""
        urls.update(_IMPORTED_MEDIA_RE.findall(value))
    return {url for url in urls if not _photo_exists(url)}


async def main(args) -> None:
    try:
        await run(args)
    finally:
        await close_db()


async def run(args) -> None:
    kinds = ["article", "news"] if args.kind == "all" else [args.kind]
    parents = {CONTENT_CONFIG[kind]["parent_id"] for kind in kinds}
    print(f"Читаю дамп {args.dump} …")
    site = load_modx_site(args.dump, keep_content_for=lambda resource: resource.get("parent") in parents)
    all_resources = {
        kind: {resource["id"]: resource for resource in content_resources(site, kind, include_unpublished=True)}
        for kind in kinds
    }
    db = await get_db()
    existing = {
        kind: [doc async for doc in db[CONTENT_CONFIG[kind]["path"]].find(
            {}, {"slug": 1, "old_id": 1, "title": 1}
        )]
        for kind in kinds
    }

    if args.list:
        for kind in kinds:
            resources = all_resources[kind]
            imported_old_ids = {doc.get("old_id") for doc in existing[kind]}
            imported_slugs = {doc.get("slug") for doc in existing[kind]}
            published = sum(bool(resource.get("published")) for resource in resources.values())
            imported = sum(resource_id in imported_old_ids or resource.get("alias") in imported_slugs
                           for resource_id, resource in resources.items())
            print(f"{kind}: всего {len(resources)}, опубликовано {published}, уже в базе {imported}")
        if not (args.ids or args.slugs or args.all):
            return

    selected = select_resources(args, all_resources)
    if not selected:
        raise SystemExit("Нет ресурсов для импорта: укажите --ids, --slugs или --all")

    known_urls = await load_old_id_urls(db)
    legacy_url_builders, legacy_path_builders = link_builders(site)
    mapper = LinkMapper(
        site,
        _try_pattern_redirect,
        known_urls,
        [content_url_builder(site, "article"), content_url_builder(site, "news"), *legacy_url_builders],
        legacy_path_builders,
    )
    people = await _people_lookup(db)
    totals = defaultdict(int)
    missing_media: set[str] = set()
    verbose = not args.all or args.show

    for batch_no, start in enumerate(range(0, len(selected), args.batch), start=1):
        batch = selected[start:start + args.batch]
        batch_stats = defaultdict(int)
        for kind, resource_id in batch:
            result = await import_one(
                db, site, kind, resource_id, existing[kind], known_urls, mapper, people, missing_media, args, verbose,
            )
            batch_stats[result] += 1
            totals[result] += 1
        if args.apply:
            await cache_service.invalidate_everywhere(db)
        if args.all:
            print(f"Группа {batch_no}: {len(batch)} — создано {batch_stats['created']}, "
                  f"обновлено {batch_stats['updated']}, пропущено {batch_stats['skipped']}, "
                  f"ошибок {batch_stats['failed']}")

    if mapper.unresolved:
        unique = list(dict.fromkeys(mapper.unresolved))
        print(f"Неразрешённых старых ссылок: {len(unique)}" + (f"; примеры: {unique[:5]}" if unique else ""))
    if missing_media:
        samples = sorted(missing_media)[:10]
        print(f"Нет файлов в media-volume: {len(missing_media)}; примеры: {samples}")
    print(f"Итого: {dict(totals)}" if args.apply else "Пробный прогон: ничего не записано (добавьте --apply).")


def select_resources(args, resources_by_kind: Dict[str, Dict[int, dict]]) -> List[tuple[str, int]]:
    selected: List[tuple[str, int]] = []
    ids = set(args.ids or [])
    slugs = set(args.slugs or [])
    for kind, resources in resources_by_kind.items():
        for resource_id, resource in resources.items():
            if args.all:
                if args.include_unpublished or resource.get("published"):
                    selected.append((kind, resource_id))
            elif resource_id in ids or resource.get("alias") in slugs:
                selected.append((kind, resource_id))
    return sorted(selected, key=lambda item: item[1])


async def _people_lookup(db) -> dict:
    by_slug: Dict[str, str] = {}
    by_name: Dict[str, List[str]] = defaultdict(list)
    async for person in db.people.find({}, {"slug": 1, "primary_tag": 1, "title": 1, "full_name": 1}):
        person_id = person["_id"]
        if person.get("slug"):
            by_slug[person["slug"]] = person_id
        for value in (person.get("primary_tag"), person.get("title"), person.get("full_name")):
            key = str(value or "").strip().casefold()
            if key and person_id not in by_name[key]:
                by_name[key].append(person_id)
    return {"by_slug": by_slug, "by_name": by_name}


def _related_people(payload: dict, people: dict) -> List[str]:
    result: List[str] = []
    for slug in person_slugs_in_modules(payload["modules"]):
        person_id = people["by_slug"].get(slug)
        if person_id and person_id not in result:
            result.append(person_id)
    for tag in payload.get("tags") or []:
        matches = people["by_name"].get(str(tag).strip().casefold(), [])
        if len(matches) == 1 and matches[0] not in result:
            result.append(matches[0])
    return result


async def import_one(db, site, kind, resource_id, existing_docs, known_urls, mapper, people, missing_media,
                     args, verbose) -> str:
    payload, extra, warnings = build_content(site, resource_id, kind, mapper)
    payload["related_person_ids"] = _related_people(payload, people)
    missing = _missing_media(payload)
    missing_media.update(missing)
    if missing:
        warnings.append(f"нет файлов изображений в volume: {len(missing)}")

    existing = next((doc for doc in existing_docs if doc.get("old_id") == resource_id), None)
    if existing is None:
        existing = next((doc for doc in existing_docs if doc.get("slug") == payload["slug"]), None)

    if verbose:
        print(f"\n{resource_id} {payload['title']} → /{CONTENT_CONFIG[kind]['path']}/{payload['slug']} "
              f"[{'существует' if existing else 'новый'}]")
        print(f"  модулей: {len(payload['modules'])}; тегов: {len(payload['tags'])}; "
              f"связей с людьми: {len(payload['related_person_ids'])}")
        for warning in warnings:
            print(f"  ⚠ {warning}")
        if args.show:
            print(json.dumps({**payload, **extra}, ensure_ascii=False, indent=1))

    if not args.apply:
        return "dry"
    if existing and not args.update:
        return "skipped"

    try:
        if kind == "article":
            if existing:
                await update_article(existing["_id"], ArticleUpdate(**payload))
                document_id = existing["_id"]
            else:
                document_id = (await create_article(ArticleCreate(**payload)))["id"]
        else:
            if existing:
                await update_news(existing["_id"], NewsUpdate(**payload))
                document_id = existing["_id"]
            else:
                document_id = (await create_news(NewsCreate(**payload)))["id"]
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        print(f"  ✗ {resource_id} {payload['title']}: не сохранён: {detail}")
        return "failed"

    update = {"$set": extra}
    if existing:
        current = await db[CONTENT_CONFIG[kind]["path"]].find_one({"_id": document_id})
        legacy = [key for key in current if key not in MODEL_FIELDS[kind]]
        if legacy:
            update["$unset"] = {key: "" for key in legacy}
    await db[CONTENT_CONFIG[kind]["path"]].update_one({"_id": document_id}, update)
    existing_docs.append({"_id": document_id, "slug": payload["slug"], "old_id": resource_id})
    known_urls[resource_id] = f"/{CONTENT_CONFIG[kind]['path']}/{payload['slug']}"
    return "updated" if existing else "created"


def parse_args():
    parser = argparse.ArgumentParser(description="Импорт статей и новостей из MODX")
    parser.add_argument("--kind", choices=("article", "news", "all"), default="all")
    parser.add_argument("--ids", nargs="*", type=int)
    parser.add_argument("--slugs", nargs="*")
    parser.add_argument("--all", action="store_true", help="все опубликованные ресурсы выбранного типа")
    parser.add_argument("--include-unpublished", action="store_true", help="с --all также импортировать черновики")
    parser.add_argument("--list", action="store_true", help="показать сводку дампа и состояние импорта")
    parser.add_argument("--apply", action="store_true", help="записать в MongoDB")
    parser.add_argument("--update", action="store_true", help="обновить уже импортированные документы")
    parser.add_argument("--show", action="store_true", help="показать собранный документ")
    parser.add_argument("--batch", type=int, default=75)
    parser.add_argument("--dump", default=DEFAULT_DUMP)
    args = parser.parse_args()
    if args.include_unpublished and not args.all:
        parser.error("--include-unpublished используется только вместе с --all")
    if args.update and not args.apply:
        parser.error("--update используется только вместе с --apply")
    return args


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
