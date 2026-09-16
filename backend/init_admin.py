#!/usr/bin/env python3
"""Создать администратора или сбросить пароль существующему пользователю и сделать его админом.

Использование (внутри контейнера backend):
    python init_admin.py --email me@example.com [--username admin]
    python init_admin.py --email me@example.com --reset

Пароль берётся из переменной ADMIN_PASSWORD, иначе запрашивается интерактивно.
Подключение к БД — как у сервера (MONGO_URL или MONGO_HOST/MONGO_USER/...).
"""

import argparse
import asyncio
import getpass
import os
import sys
from datetime import datetime, timezone

import bcrypt
from dotenv import load_dotenv

load_dotenv()

from utils.database import get_db, close_db  # noqa: E402
from services.admin_bootstrap import build_admin_doc, MIN_ADMIN_PASSWORD_LENGTH  # noqa: E402


async def main(args) -> int:
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Пароль администратора: ")
    if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
        print(f"Пароль должен быть не короче {MIN_ADMIN_PASSWORD_LENGTH} символов")
        return 1

    db = await get_db()
    try:
        existing = await db.users.find_one({"$or": [{"email": args.email}, {"username": args.username}]})
        if existing and not args.reset:
            print(f"Пользователь уже существует: {existing.get('username')} ({existing.get('email')}). "
                  "Используйте --reset, чтобы сбросить пароль и выдать роль admin.")
            return 1
        if existing:
            await db.users.update_one({"_id": existing["_id"]}, {"$set": {
                "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                "role": "admin",
                "banned": False,
                "active": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }})
            print(f"✅ Пароль сброшен, роль admin: {existing.get('username')} ({existing.get('email')})")
        else:
            await db.users.insert_one(build_admin_doc(args.username, args.email, password))
            print(f"✅ Администратор создан: {args.username} ({args.email})")
        return 0
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--reset", action="store_true", help="сбросить пароль существующему пользователю")
    sys.exit(asyncio.run(main(parser.parse_args())))
