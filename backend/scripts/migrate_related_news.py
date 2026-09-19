"""Remove legacy inline News sections and humor_chronicles markers.

The migration also backfills news relations from links before removing the old HTML.
Dry-run by default; pass --apply to write changes.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.related_news_migration import migrate_legacy_related_news  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402


async def main(apply: bool) -> None:
    try:
        report = await migrate_legacy_related_news(await get_db(), apply=apply)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not apply:
            print("Пробный прогон: ничего не записано (добавьте --apply).")
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="записать изменения в MongoDB")
    asyncio.run(main(parser.parse_args().apply))
