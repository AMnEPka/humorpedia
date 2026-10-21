#!/usr/bin/env python3
"""Вывести JSON-отчёт сверки канонических сезонов и страниц КВН без записи."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.competition_reconciliation import reconcile_seasons  # noqa: E402
from services.show_teams import KVN_ONLY  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402


async def _rows(collection, query):
    return await collection.find(query).to_list(None)


async def _report(db, max_differences: int) -> dict:
    pages, seasons, tournaments, teams = await asyncio.gather(
        _rows(db.kvn, {"season_data": {"$exists": True}}),
        _rows(db.seasons, {"page_collection": "kvn"}),
        _rows(db.tournaments, {"show": "kvn"}),
        _rows(db.teams, KVN_ONLY),
    )
    return reconcile_seasons(pages, seasons, tournaments, teams, max_differences=max_differences)


async def _run(db_name: str, max_differences: int) -> dict:
    if not os.environ.get("MONGO_URL") and not os.environ.get("MONGO_HOST"):
        raise ValueError("Задайте MONGO_URL или MONGO_HOST")
    previous_db_name = os.environ.get("DB_NAME")
    os.environ["DB_NAME"] = db_name
    try:
        db = await get_db()
        try:
            if getattr(db, "name", None) != db_name:
                raise ValueError("имя подключенной базы не совпадает с --db-name")
            return await _report(db, max_differences)
        finally:
            await close_db()
    finally:
        if previous_db_name is None:
            os.environ.pop("DB_NAME", None)
        else:
            os.environ["DB_NAME"] = previous_db_name


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-name", required=True, help="Явное имя базы только для чтения")
    parser.add_argument("--max-differences", type=int, default=50, help="Лимит строковых различий (не меньше 1)")
    args = parser.parse_args(argv)
    if args.max_differences < 1:
        parser.error("--max-differences должен быть не меньше 1")
    try:
        report = asyncio.run(_run(args.db_name, args.max_differences))
    except Exception as exc:
        print(f"Ошибка read-only сверки: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
