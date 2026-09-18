#!/usr/bin/env python3
"""Dry-run and import legacy poll definitions with anonymous aggregate counts.

Run inside the backend container:
    python scripts/import_polls_modx.py
    python scripts/import_polls_modx.py --show
    python scripts/import_polls_modx.py --apply

Without ``--apply`` MongoDB is not opened or changed. Legacy user ids are used
only to count distinct users in the report and are never stored.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.modx_dump import load_modx_site  # noqa: E402
from services.modx_polls import audit_polls, read_legacy_votes  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402

DEFAULT_DUMP = "/app/backups/idemsku8_modx2.sql"


async def run(args) -> None:
    site = load_modx_site(args.dump)
    report = audit_polls(site, read_legacy_votes(args.dump))
    print(
        f"Определений: {len(report['definitions'])}; размещений: {len(report['placements'])}; "
        f"голосов: {report['votes_count']}; старых пользователей: {report['legacy_users_count']}"
    )
    print(f"Отсутствующие определения: {report['missing_definitions'] or 'нет'}")
    print(f"Осиротевшие голоса по опросам: {report['orphan_vote_polls'] or 'нет'}")
    print(f"Голоса с неизвестным ответом: {report['invalid_answers'] or 'нет'}")
    print(f"Определения без видимого блока: {report['unplaced_definitions'] or 'нет'}")
    print(f"Расхождения агрегатов и строк голосов: {len(report['aggregate_mismatches'])}")
    for warning in report["warnings"]:
        print(f"  ⚠ {warning}")
    if args.show:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.apply:
        print("Пробный прогон: ничего не записано (добавьте --apply).")
        return

    db = await get_db()
    totals = {"created": 0, "updated": 0, "skipped": 0}
    now = datetime.now(timezone.utc).isoformat()
    for definition in report["definitions"]:
        poll = {key: value for key, value in definition.items() if key != "options"}
        poll["options"] = [
            {key: value for key, value in option.items() if key != "old_answer_id"}
            for option in definition["options"]
        ]
        existing = await db.polls.find_one({"_id": poll["_id"]})
        if existing and not args.update:
            totals["skipped"] += 1
            continue
        poll["updated_at"] = now
        if existing:
            await db.polls.update_one({"_id": poll["_id"]}, {"$set": poll})
            totals["updated"] += 1
        else:
            poll["created_at"] = now
            await db.polls.insert_one(poll)
            totals["created"] += 1
    print(f"Итого: {totals}. Модули poll добавляются при повторном импорте статей/новостей.")


def parse_args():
    parser = argparse.ArgumentParser(description="Импорт опросов из MODX")
    parser.add_argument("--dump", default=DEFAULT_DUMP)
    parser.add_argument("--apply", action="store_true", help="записать определения в MongoDB")
    parser.add_argument("--update", action="store_true", help="обновить ранее импортированные определения")
    parser.add_argument("--show", action="store_true", help="показать полный JSON-отчёт")
    args = parser.parse_args()
    if args.update and not args.apply:
        parser.error("--update используется только вместе с --apply")
    return args


async def main():
    try:
        await run(parse_args())
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
