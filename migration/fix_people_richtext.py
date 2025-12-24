#!/usr/bin/env python3
"""Пост-фикс для уже импортированных people.

Нужен в редких случаях, когда первые записи были импортированы до того,
как мы укрепили нормализацию HTML/строк.

Использование:
  python3 fix_people_richtext.py --slugs sergey-drobotenko anton-shastun
  python3 fix_people_richtext.py --all-imported

По умолчанию работает как dry-run.
"""

import argparse
import os

import pymongo

from utils import MONGO_URL, DB_NAME, normalize_rich_text


def fix_person(doc, *, verbose=False):
    """Возвращает (changed: bool, new_modules: list)."""
    modules = doc.get("modules") or []
    new_modules = []
    changed = False

    for m in modules:
        nm = dict(m)
        data = dict(m.get("data") or {})

        if isinstance(data.get("content"), str):
            new = normalize_rich_text(data["content"])
            if new != data["content"]:
                data["content"] = new
                changed = True

        if m.get("type") == "timeline":
            events = []
            for ev in data.get("events") or []:
                if not isinstance(ev, dict):
                    continue
                nev = dict(ev)
                if isinstance(nev.get("title"), str):
                    nt = normalize_rich_text(nev["title"])
                    if nt != nev["title"]:
                        nev["title"] = nt
                        changed = True
                if isinstance(nev.get("description"), str):
                    nd = normalize_rich_text(nev["description"])
                    if nd != nev["description"]:
                        nev["description"] = nd
                        changed = True
                events.append(nev)
            data["events"] = events

        nm["data"] = data
        new_modules.append(nm)

    if verbose and changed:
        print(f"  - changed: {doc.get('slug')}")

    return changed, new_modules


def main():
    parser = argparse.ArgumentParser(description="Fix rich text escape artifacts in people modules")
    parser.add_argument("--slugs", nargs="*", help="Список slug для фикса")
    parser.add_argument("--all-imported", action="store_true", help="Починить всех, у кого migration_status=imported")
    parser.add_argument("--apply", action="store_true", help="Записать изменения в БД (по умолчанию dry-run)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]

    if args.all_imported:
        cursor = db.people.find({"migration_status": "imported"})
    else:
        if not args.slugs:
            raise SystemExit("Нужно указать --slugs ... или --all-imported")
        cursor = db.people.find({"slug": {"$in": args.slugs}})

    total = 0
    changed = 0

    for doc in cursor:
        total += 1
        is_changed, new_modules = fix_person(doc, verbose=args.verbose)
        if not is_changed:
            continue

        changed += 1
        if args.apply:
            db.people.update_one({"_id": doc["_id"]}, {"$set": {"modules": new_modules}})

    print(f"Checked: {total}; would change: {changed}; mode: {'apply' if args.apply else 'dry-run'}")
    client.close()


if __name__ == "__main__":
    main()
