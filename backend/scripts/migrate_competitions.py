#!/usr/bin/env python3
"""
Миграция season_data страниц КВН в модель соревнований (tournaments / seasons / participations).

Идемпотентна: идентификаторы детерминированные, повторный запуск перезаписывает те же документы.
При старте сервер выполняет её сам, если коллекция seasons пуста.

Использование (внутри контейнера backend):
    python scripts/migrate_competitions.py            # пробный прогон: отчёт без записи
    python scripts/migrate_competitions.py --apply    # записать
"""
import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from utils.database import get_db, close_db  # noqa: E402
from services.competitions import (  # noqa: E402
    SHOW_KVN, TeamLookup, _league_slug_from_path, build_participations, legacy_to_season,
    load_team_lookup, stable_id, sync_kvn_pages, unresolved_participants,
)


async def report(db, lookup: TeamLookup) -> None:
    seasons_by_league = Counter()
    rows = Counter()
    unresolved = Counter()
    skipped = []
    async for page in db.kvn.find({"season_data": {"$exists": True}}):
        league = _league_slug_from_path(page.get("full_path", ""))
        if not league:
            skipped.append(page.get("full_path"))
            continue
        tournament = {"_id": stable_id("tournament", SHOW_KVN, league), "slug": league, "show": SHOW_KVN}
        season = legacy_to_season(page, tournament, lookup)
        seasons_by_league[league] += 1
        rows.update(r["kind"] for r in build_participations(season))
        for entry in unresolved_participants(season):
            unresolved[f"{entry['slug'] or '(без slug)'} / {entry['name']}  [{page.get('full_path')}]"] += 1

    print("Сезоны по лигам:", dict(seasons_by_league))
    print("Строк participations:", dict(rows))
    if skipped:
        print("Пропущены (страница не внутри лиги kvn/<лига>/<сезон>):", skipped)
    print(f"Участники без привязки к команде: {sum(unresolved.values())}")
    for key, count in unresolved.most_common():
        print(f"  {count:3} × {key}")


async def main(apply: bool) -> None:
    db = await get_db()
    try:
        lookup = await load_team_lookup(db)
        await report(db, lookup)
        if apply:
            stats = await sync_kvn_pages(db)
            print("\nЗаписано:", stats)
            print("Турниров:", await db.tournaments.count_documents({}),
                  "сезонов:", await db.seasons.count_documents({}),
                  "participations:", await db.participations.count_documents({}))
        else:
            print("\nПробный прогон. Для записи: --apply")
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="записать в БД")
    asyncio.run(main(parser.parse_args().apply))
