"""Отвязать однофамилицу Анну Бородину от состава команды «25-ая».

По умолчанию выполняет только проверку. Для изменения данных передайте --apply.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.memberships import name_key, now_iso
from utils.database import get_db


TEAM_SLUG = "25"
PERSON_NAME = "Анна Бородина"
WRONG_PERSON_ID = "489c36da-b54e-4161-bcc1-f1d5412b3551"


async def main(apply: bool) -> None:
    db = await get_db()
    team = await db.teams.find_one({"slug": TEAM_SLUG}, {"_id": 1, "title": 1})
    if not team:
        raise RuntimeError("Команда «25-ая» не найдена")

    membership = await db.memberships.find_one({
        "team_id": team["_id"],
        "name_key": name_key(PERSON_NAME),
    })
    if not membership:
        raise RuntimeError("Анна Бородина не найдена в составе команды «25-ая»")

    if membership.get("person_link_disabled") and membership.get("person_id") is None:
        print("Связь уже отключена; изменение не требуется.")
        return

    if membership.get("person_id") != WRONG_PERSON_ID:
        raise RuntimeError("Запись связана с другим человеком; автоматическая правка остановлена")

    if not apply:
        print(f"Будет отвязана запись {membership['_id']} от people/{WRONG_PERSON_ID}. Запустите с --apply.")
        return

    result = await db.memberships.update_one(
        {"_id": membership["_id"], "person_id": WRONG_PERSON_ID},
        {"$set": {
            "person_id": None,
            "person_link_disabled": True,
            "matched_by": "manual",
            "source": "manual",
            "updated_at": now_iso(),
        }},
    )
    if result.modified_count != 1:
        raise RuntimeError("Запись не была изменена")
    print("Ошибочная связь Анны Бородиной в составе команды «25-ая» отключена.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
