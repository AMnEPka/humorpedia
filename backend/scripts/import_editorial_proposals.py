#!/usr/bin/env python3
"""Import editor-reviewed research proposal cards from JSON (dry-run by default).

Usage in the backend environment:
    python scripts/import_editorial_proposals.py proposals.json
    python scripts/import_editorial_proposals.py proposals.json --apply

The JSON root may be an array or an object with a ``proposals`` array.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from routes.editorial_proposals import create_proposal, prepare_proposal  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402


async def run(file_path: Path, apply: bool) -> None:
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    proposals = raw.get("proposals") if isinstance(raw, dict) else raw
    if not isinstance(proposals, list):
        raise ValueError("JSON должен содержать массив proposals")
    db = await get_db()
    created = duplicates = 0
    try:
        for index, payload in enumerate(proposals, 1):
            prepared = await prepare_proposal(db, payload)
            if apply:
                card, inserted = await create_proposal(db, prepared, actor="json_import")
                created += int(inserted)
                duplicates += int(not inserted)
                print(f"{index}. {'создано' if inserted else 'уже есть'}: {card['id']} ({card['kind']})")
            else:
                print(f"{index}. проверено: {prepared['kind']} / {len(prepared['changes'])} изменений")
        if apply:
            print(f"Готово. Создано: {created}; уже существовало: {duplicates}.")
        else:
            print(f"Пробный прогон: проверено {len(proposals)} карточек, записей нет. Для импорта добавьте --apply.")
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("json_file", type=Path)
    parser.add_argument("--apply", action="store_true", help="сохранить предложения в MongoDB")
    args = parser.parse_args()
    asyncio.run(run(args.json_file, args.apply))
