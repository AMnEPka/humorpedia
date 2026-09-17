#!/usr/bin/env python3
"""
Связать одноимённые команды КВН и команды шоу (related_team_ids, связь двусторонняя).

Пара связывается, если название команды шоу совпадает с названием (или алиасом) ровно одной команды КВН и
это подтверждается: ссылкой между страницами, совпадением города или у команды шоу город не указан.
Если города указаны у обеих и не совпадают, а ссылок нет, — пара только печатается (разные коллективы
с одинаковым названием, например «Провинция» из Кирово-Чепецка и из Владикавказа).

Использование (внутри контейнера backend):
    python scripts/link_same_name_teams.py           # пробный прогон: пары и основание
    python scripts/link_same_name_teams.py --apply   # записать связи
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from services.cache import cache_service  # noqa: E402
from services.show_teams import KVN_ONLY, sync_related_teams  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402

FIELDS = {"name": 1, "title": 1, "slug": 1, "aliases": 1, "facts": 1, "modules": 1, "full_path": 1,
          "related_team_ids": 1, "show_id": 1}


def name_key(name: str) -> str:
    """Сравнение названий без регистра, ё/е и знаков («Два Капитана - 1955» = «Два капитана-1955»);
    уточнение в скобках остаётся частью названия («Сборная Москвы (МАМИ)» ≠ «Сборная Москвы»)."""
    text = re.sub(r"[«»\"'“”„]", "", (name or "").lower().replace("ё", "е"))
    return re.sub(r"[^0-9a-zа-я]+", " ", text).strip()


def cities(team: dict) -> set:
    value = (team.get("facts") or {}).get("Город") or ""
    return {c.strip().lower() for c in re.split(r"[,;/()]|\bи\b", value) if c.strip() and not re.search(r"\d", c)}


def pair_evidence(show_team: dict, kvn_team: dict) -> tuple:
    """(основания для связи, города противоречат)."""
    show_text = json.dumps(show_team.get("modules") or [], ensure_ascii=False)
    kvn_text = json.dumps(kvn_team.get("modules") or [], ensure_ascii=False)
    evidence = []
    if f'/kvn/teams/{kvn_team["slug"]}"' in show_text.replace('\\"', '"'):
        evidence.append("ссылка со страницы шоу")
    if f'/shows/{show_team["full_path"]}"' in kvn_text.replace('\\"', '"'):
        evidence.append("ссылка со страницы КВН")
    show_cities, kvn_cities = cities(show_team), cities(kvn_team)
    if show_cities & kvn_cities:
        evidence.append("город")
    elif not show_cities:
        evidence.append("у команды шоу город не указан")
    conflict = bool(show_cities and kvn_cities and not show_cities & kvn_cities)
    return evidence, conflict


async def main(args) -> None:
    db = await get_db()
    try:
        kvn_teams = await db.teams.find(KVN_ONLY, FIELDS).to_list(None)
        index = {}
        for team in kvn_teams:
            for name in {team.get("name") or team.get("title"), *(team.get("aliases") or [])}:
                if name:
                    index.setdefault(name_key(name), {})[team["_id"]] = team
        linked = skipped = 0
        async for show_team in db.teams.find({"show_id": {"$ne": None}}, FIELDS):
            candidates = list(index.get(name_key(show_team["name"]), {}).values())
            if not candidates:
                continue
            label = f"{show_team['name']} (/shows/{show_team['full_path']})"
            if len(candidates) > 1:
                print(f"? {label}: несколько команд КВН — {[c['slug'] for c in candidates]}")
                skipped += 1
                continue
            kvn_team = candidates[0]
            evidence, conflict = pair_evidence(show_team, kvn_team)
            links = [e for e in evidence if e.startswith("ссылка")]
            if conflict and not links:
                print(f"✗ {label} ↔ /kvn/teams/{kvn_team['slug']}: разные города "
                      f"({(show_team.get('facts') or {}).get('Город')} / {(kvn_team.get('facts') or {}).get('Город')}), ссылок нет — не связываю")
                skipped += 1
                continue
            already = kvn_team["_id"] in (show_team.get("related_team_ids") or [])
            print(f"{'=' if already else '+'} {label} ↔ /kvn/teams/{kvn_team['slug']}: {', '.join(evidence)}")
            if args.apply and not already:
                current = show_team.get("related_team_ids") or []
                related = await sync_related_teams(db, show_team["_id"], current + [kvn_team["_id"]], current)
                await db.teams.update_one({"_id": show_team["_id"]}, {"$set": {"related_team_ids": related}})
            linked += 1
        if args.apply:
            await cache_service.invalidate_everywhere(db)
        print(f"\nПар: {linked}, пропущено: {skipped}" + ("" if args.apply else " (пробный прогон, --apply — записать)"))
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="записать связи")
    asyncio.run(main(parser.parse_args()))
