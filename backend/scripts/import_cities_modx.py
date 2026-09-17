#!/usr/bin/env python3
"""Import Geography cities from the legacy MODX SQL dump.

Dry-run is the default. Examples inside the backend container:

    python scripts/import_cities_modx.py --list
    python scripts/import_cities_modx.py --slugs moscow voronezh --show
    python scripts/import_cities_modx.py --all --apply
    python scripts/import_cities_modx.py --all --apply --update

Related people are not inferred from birthplace. The import uses the editorial shortlist of people
linked in the old city's "Известные комики" block and keeps every non-archived person page.
Teams are rebuilt from every non-archived team whose exact city field matches the city page.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from models.city import City, CityCreate, CityUpdate
from routes.cities import create_city, update_city
from routes.redirects import _try_pattern_redirect
from scripts.migrate_foreign_agent_notices import link_known_mentions, remove_obsolete_notes
from services.cache import cache_service
from services.link_resolver import load_old_id_urls
from services.modx_cities import build_city, city_resources
from services.city_linking import city_matches, find_teams_by_city
from services.modx_content import IMPORTED_IMAGES_PREFIX, LinkMapper
from services.modx_dump import load_modx_site
from services.modx_show_teams import link_builders
from utils.database import close_db, get_db


DEFAULT_DUMP = "/app/backups/idemsku8_modx2.sql"
MEDIA_ROOT = "/app/media/imported"
CITY_FIELDS = {field.alias or name for name, field in City.model_fields.items()} | {"old_urls"}
LEGACY_TEAM_NAME_ALIASES = {
    "сборная камызякского края по квну": "камызяки",
    "сборная краснодарского края бак соучастники": "сборная краснодарского края",
    "сборная квн кыргызстана": "сборная кыргызстана",
    "сборная тпу": "тпу",
    "иркутск ру": "иркутск ru",
    "50 х 50": "50х50",
    "2х2": "2x2",
    "сборная грузия": "сборная грузии",
    "женская сборная хабаровская края": "женская сборная хабаровского края",
    "сборная хабаровская края": "сборная хабаровского края",
    "девичья сборная уюргу": "девичья сборная юургу",
    "19 30": "19 30 дгту",
}


def _image_exists(url: str) -> bool:
    if not url or not url.startswith(IMPORTED_IMAGES_PREFIX):
        return True
    return os.path.exists(os.path.join(MEDIA_ROOT, url[len(IMPORTED_IMAGES_PREFIX):]))


def _normalize_foreign_agent_content(payload: dict) -> None:
    for module in payload.get("modules") or []:
        data = module.get("data") or {}
        if isinstance(data.get("content"), str):
            data["content"], _ = link_known_mentions(data["content"])
    remove_obsolete_notes(payload)


def _team_reference_keys(value: str) -> set[str]:
    """Normalize a displayed name, with and without a trailing city/explanation in brackets."""
    variants = {value or "", re.sub(r"\s*\([^)]*\)\s*$", "", value or "").strip()}
    keys = set()
    for variant in variants:
        normalized = variant.replace("ё", "е").casefold()
        normalized = re.sub(r"[«»„“\"'№#]", " ", normalized)
        normalized = re.sub(r"[^0-9a-zа-я]+", " ", normalized)
        key = re.sub(r"\s+", " ", normalized).strip()
        if key:
            keys.add(key)
            if canonical := LEGACY_TEAM_NAME_ALIASES.get(key):
                keys.add(canonical)
    return keys


async def _resolve_relations(db, candidates: dict) -> tuple[list[str], list[str], list[str]]:
    warnings = []

    async def resolve(collection_name: str, items: list[dict]) -> list[str]:
        if not items:
            return []
        old_ids = [item["old_id"] for item in items]
        slugs = [item["slug"] for item in items if item.get("slug")]
        docs = await db[collection_name].find(
            {
                "status": {"$ne": "archived"},
                "$or": [{"old_id": {"$in": old_ids}}, {"slug": {"$in": slugs}}],
            },
            {"_id": 1, "old_id": 1, "slug": 1},
        ).to_list(None)
        by_old_id = {doc.get("old_id"): doc for doc in docs if doc.get("old_id") is not None}
        by_slug = {doc.get("slug"): doc for doc in docs if doc.get("slug")}
        resolved = []
        missing = []
        for item in items:
            doc = by_old_id.get(item["old_id"]) or by_slug.get(item.get("slug"))
            if doc and doc["_id"] not in resolved:
                resolved.append(doc["_id"])
            elif not doc:
                missing.append(item.get("url") or item.get("slug") or str(item["old_id"]))
        if missing:
            warnings.append(
                f"{collection_name}: {len(missing)} редакционных ссылок без неархивной страницы "
                f"({', '.join(missing[:5])}{'…' if len(missing) > 5 else ''})"
            )
        return resolved

    people = await resolve("people", candidates.get("people") or [])
    teams = await resolve("teams", candidates.get("teams") or [])
    return people, teams, warnings


async def run(args) -> None:
    print(f"Читаю дамп {args.dump} …")
    site = load_modx_site(args.dump)
    resources = {r["id"]: r for r in city_resources(site, include_unpublished=True)}
    by_slug = {r.get("alias"): rid for rid, r in resources.items()}
    db = await get_db()
    existing_docs = await db.cities.find({}, {"_id": 1, "slug": 1, "old_id": 1, "title": 1,
                                               "related_person_ids": 1, "related_team_ids": 1}).to_list(None)
    existing_by_old = {d.get("old_id"): d for d in existing_docs if d.get("old_id") is not None}
    existing_by_slug = {d.get("slug"): d for d in existing_docs if d.get("slug")}
    all_teams = await db.teams.find(
        {"status": {"$ne": "archived"}},
        {"_id": 1, "name": 1, "title": 1, "aliases": 1, "facts": 1},
    ).to_list(None)
    teams_by_id = {team["_id"]: team for team in all_teams}
    teams_by_name: dict[str, list[dict]] = {}
    for team in all_teams:
        for name in [team.get("name"), team.get("title"), *(team.get("aliases") or [])]:
            for key in _team_reference_keys(name or ""):
                if team not in teams_by_name.setdefault(key, []):
                    teams_by_name[key].append(team)

    if args.list:
        for rid, resource in sorted(resources.items(), key=lambda item: item[1].get("pagetitle") or ""):
            existing = existing_by_old.get(rid) or existing_by_slug.get(resource.get("alias"))
            flags = []
            if not resource.get("published"):
                flags.append("не опубликован")
            if resource.get("hidemenu"):
                flags.append("hidemenu")
            state = "в базе" if existing else ""
            suffix = f" ({', '.join(flags)})" if flags else ""
            print(f"{rid:5}  {resource.get('alias', ''):24} {resource.get('pagetitle', '')}{suffix}  {state}")
        print(f"Всего: {len(resources)}, уже в базе: {sum(bool(existing_by_old.get(rid) or existing_by_slug.get(r.get('alias'))) for rid, r in resources.items())}")
        return

    ids = list(args.ids or [])
    for slug in args.slugs or []:
        if slug not in by_slug:
            print(f"[!] slug {slug} не найден среди городов дампа")
            continue
        ids.append(by_slug[slug])
    if args.all:
        ids = sorted(rid for rid, r in resources.items() if r.get("published"))
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise SystemExit("Укажите --ids, --slugs или --all (или --list)")

    known_urls = await load_old_id_urls(db)
    builders = link_builders(site)
    totals = {"created": 0, "updated": 0, "skipped": 0, "failed": 0, "dry": 0}
    for rid in ids:
        if rid not in resources:
            print(f"[!] {rid}: не страница города")
            continue
        resource = resources[rid]
        mapper = LinkMapper(site, _try_pattern_redirect, known_urls, *builders)
        payload, extra, candidates, warnings = build_city(site, rid, mapper)
        _normalize_foreign_agent_content(payload)
        people_ids, linked_team_ids, relation_warnings = await _resolve_relations(db, candidates)
        warnings.extend(relation_warnings)
        payload["related_person_ids"] = people_ids
        city_team_ids = await find_teams_by_city(
            db, payload["name"], payload.get("aliases") or []
        )
        payload["related_team_ids"] = list(dict.fromkeys(city_team_ids + linked_team_ids))
        for mention in payload.get("related_team_mentions") or []:
            matches = list({
                team["_id"]: team
                for key in _team_reference_keys(mention.get("name") or "")
                for team in teams_by_name.get(key, [])
            }.values())
            if len(matches) > 1:
                matches = [
                    team for team in matches
                    if city_matches(
                        payload["name"], (team.get("facts") or {}).get("Город", ""), payload.get("aliases") or []
                    )
                ]
            if len(matches) == 1 and matches[0]["_id"] not in payload["related_team_ids"]:
                payload["related_team_ids"].append(matches[0]["_id"])
        team_docs = [teams_by_id[team_id] for team_id in payload["related_team_ids"] if team_id in teams_by_id]
        known_team_names = set().union(*[
            _team_reference_keys(team.get("name") or team.get("title") or "") for team in team_docs
        ]) if team_docs else set()
        payload["related_team_mentions"] = [
            mention for mention in payload.get("related_team_mentions") or []
            if _team_reference_keys(mention.get("name") or "").isdisjoint(known_team_names)
        ]

        poster = payload.get("poster") or {}
        if poster and not _image_exists(poster.get("url", "")):
            warnings.append(f"файла изображения нет в volume: {poster['url']}")

        existing = existing_by_old.get(rid) or existing_by_slug.get(payload["slug"])
        if existing and args.update and not args.update_relations:
            payload["related_person_ids"] = existing.get("related_person_ids") or []

        print(f"\n{rid} {payload['title']} → /city/{payload['slug']} "
              f"[{'существует' if existing else 'новый'}, {payload['status']}]")
        print(f"  фактов: {len(payload['facts'])}; модулей: {len(payload['modules'])}; тегов: {len(payload['tags'])}; "
              f"избранных людей: {len(payload['related_person_ids'])}; команд: {len(payload['related_team_ids'])}"
              f" + {len(payload['related_team_mentions'])} без страницы")
        for warning in warnings:
            print(f"  ⚠ {warning}")
        if args.show:
            print(json.dumps({**payload, **extra}, ensure_ascii=False, indent=1))
        if not args.apply:
            totals["dry"] += 1
            continue
        if existing and not args.update:
            print("  пропущен: уже есть (для перезаписи --update)")
            totals["skipped"] += 1
            continue

        try:
            if existing:
                city_id = existing["_id"]
                await update_city(city_id, CityUpdate(**payload), None)
            else:
                city_id = (await create_city(CityCreate(**payload), None))["id"]
        except Exception as error:
            print(f"  ✗ не сохранён: {getattr(error, 'detail', None) or error}")
            totals["failed"] += 1
            continue

        update = {"$set": extra}
        if existing:
            current = await db.cities.find_one({"_id": city_id})
            legacy = [key for key in current if key not in CITY_FIELDS]
            if legacy:
                update["$unset"] = {key: "" for key in legacy}
            defaults = City(title=payload["title"], slug=payload["slug"], name=payload["name"]).model_dump(by_alias=True)
            for key, value in defaults.items():
                if key not in current and key not in extra:
                    update["$set"][key] = value.isoformat() if hasattr(value, "isoformat") else value
        await db.cities.update_one({"_id": city_id}, update)
        saved = {"_id": city_id, "old_id": rid, "slug": payload["slug"],
                 "related_person_ids": payload["related_person_ids"], "related_team_ids": payload["related_team_ids"]}
        existing_by_old[rid] = saved
        existing_by_slug[payload["slug"]] = saved
        known_urls[rid] = f"/city/{payload['slug']}"
        totals["updated" if existing else "created"] += 1
        print(f"  ✓ сохранён, id {city_id}")

    if args.apply:
        await cache_service.invalidate_everywhere(db)
        print(f"\nИтого: {totals}")
    else:
        print("\nПробный прогон: ничего не записано (добавьте --apply).")


async def main(args) -> None:
    try:
        await run(args)
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dump", default=DEFAULT_DUMP)
    parser.add_argument("--ids", nargs="*", type=int, help="id ресурсов MODX")
    parser.add_argument("--slugs", nargs="*", help="alias страниц старого сайта")
    parser.add_argument("--list", action="store_true", help="список городов дампа")
    parser.add_argument("--show", action="store_true", help="напечатать документ целиком")
    parser.add_argument("--all", action="store_true", help="все опубликованные города")
    parser.add_argument("--apply", action="store_true", help="записать в базу")
    parser.add_argument("--update", action="store_true", help="перезаписать существующие города")
    parser.add_argument("--update-relations", action="store_true",
                        help="при --update также заменить ручную подборку людей редакционным списком дампа")
    asyncio.run(main(parser.parse_args()))
