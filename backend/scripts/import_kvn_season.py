"""Импорт редакционного JSON-пакета сезона. Без --apply только проверяет, не записывая в БД."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.season_import import SeasonImport
from services.season_import import apply_import, preview_import
from utils.database import get_db


async def run(path, apply):
    package = SeasonImport.model_validate_json(Path(path).read_text(encoding="utf-8-sig"))
    db = await get_db()
    preview = await preview_import(db, package)
    print(json.dumps(preview, ensure_ascii=False, indent=2))
    if preview["errors"]:
        return 1
    if apply:
        result = await apply_import(db, package, preview["preview_token"])
        print(json.dumps({key: result[key] for key in ("page_id", "path", "created", "created_teams")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Путь к JSON внутри контейнера backend")
    parser.add_argument("--apply", action="store_true", help="Создать сезон и недостающие команды")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.path, args.apply)))
