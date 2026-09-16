"""
Создание первого администратора.

Пароль по умолчанию больше не используется: админ создаётся при старте только если
в БД нет ни одного пользователя с ролью admin И заданы переменные окружения
ADMIN_EMAIL и ADMIN_PASSWORD (ADMIN_USERNAME — необязательно, по умолчанию "admin").
Вручную: python init_admin.py (см. справку скрипта).
"""
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

import bcrypt

logger = logging.getLogger(__name__)

MIN_ADMIN_PASSWORD_LENGTH = 12


def build_admin_doc(username: str, email: str, password: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "_id": str(uuid4()),
        "username": username,
        "email": email,
        "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "profile": {"full_name": "Administrator", "avatar": None, "bio": None, "birth_date": None, "location": None},
        "role": "admin",
        "permissions": ["comment", "vote", "edit", "delete", "moderate", "admin"],
        "oauth": {"vk_id": None, "yandex_id": None, "vk_data": None, "yandex_data": None},
        "auth_provider": "email",
        "stats": {"articles_count": 0, "comments_count": 0, "votes_count": 0, "quiz_attempts": 0},
        "active": True,
        "verified": True,
        "banned": False,
        "old_id": None,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
    }


async def ensure_admin_from_env(db) -> None:
    """Создать администратора из ADMIN_EMAIL/ADMIN_PASSWORD, если админов ещё нет."""
    try:
        if await db.users.find_one({"role": "admin"}, {"_id": 1}):
            return

        email = os.environ.get("ADMIN_EMAIL", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        username = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"

        if not email or not password:
            logger.warning(
                "В БД нет администратора. Задайте ADMIN_EMAIL и ADMIN_PASSWORD "
                "или выполните: python init_admin.py"
            )
            return
        if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
            logger.error(f"ADMIN_PASSWORD короче {MIN_ADMIN_PASSWORD_LENGTH} символов — администратор не создан")
            return
        if await db.users.find_one({"$or": [{"email": email}, {"username": username}]}, {"_id": 1}):
            logger.error(f"Пользователь {username} / {email} уже существует, но не admin — назначьте роль вручную")
            return

        await db.users.insert_one(build_admin_doc(username, email, password))
        logger.info(f"Администратор создан: {username} ({email})")
    except Exception as e:
        logger.error(f"Не удалось создать администратора: {e}")
