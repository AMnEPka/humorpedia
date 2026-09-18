"""Audit and initialize immutable baselines for the public rating system.

Run inside the backend container:
    python scripts/migrate_ratings.py
    python scripts/migrate_ratings.py --apply
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.ratings import migrate_baselines  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402


async def main(apply: bool) -> None:
    try:
        report = await migrate_baselines(await get_db(), apply=apply)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not apply:
            print("Пробный прогон: ничего не записано (добавьте --apply).")
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="создать недостающие baseline-документы")
    asyncio.run(main(parser.parse_args().apply))
