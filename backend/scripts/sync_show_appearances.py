"""Связи участников из локальной БД. По умолчанию отчёт; запись только с --apply."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.show_appearances import sync
from utils.database import get_db, close_db


async def main(apply):
    try:
        print(json.dumps(await sync(await get_db(), apply=apply), ensure_ascii=False, indent=2))
    finally:
        await close_db()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    asyncio.run(main(parser.parse_args().apply))
