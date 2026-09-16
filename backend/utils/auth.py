"""
Авторизация: JWT и FastAPI-зависимости для проверки ролей.

Использование в роутерах:
    from utils.auth import require_admin, require_editor, require_editor_on_write

    router = APIRouter(prefix="/content", dependencies=[Depends(require_editor_on_write)])

    @router.get("/me")
    async def me(user: dict = Depends(require_user)): ...
"""
import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request

from utils.database import get_db

logger = logging.getLogger(__name__)

# ─── Роли ──────────────────────────────────────────────────────────────────────
ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
ROLE_MODERATOR = "moderator"
ROLE_USER = "user"

EDITOR_ROLES = {ROLE_ADMIN, ROLE_EDITOR}                      # правка контента
MODERATOR_ROLES = {ROLE_ADMIN, ROLE_MODERATOR}                # модерация комментариев
STAFF_ROLES = {ROLE_ADMIN, ROLE_EDITOR, ROLE_MODERATOR}       # доступ в админку, медиа

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# ─── JWT ───────────────────────────────────────────────────────────────────────
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7          # 7 дней
REFRESH_GRACE_HOURS = 24 * 30          # refresh принимает токены, просроченные не более 30 дней
MIN_SECRET_LENGTH = 32


def _load_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret) >= MIN_SECRET_LENGTH:
        return secret
    if os.environ.get("ENVIRONMENT") == "production":
        raise RuntimeError(
            f"JWT_SECRET не задан или короче {MIN_SECRET_LENGTH} символов. "
            "Сгенерируйте: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    logger.warning(
        "JWT_SECRET не задан — используется временный секрет. "
        "Токены станут невалидны после рестарта и не будут работать при нескольких воркерах."
    )
    return secrets.token_hex(32)


JWT_SECRET = _load_jwt_secret()


def create_token(user_id: str, role: str) -> tuple[str, int]:
    """Выпустить JWT. Возвращает (token, expires_in_seconds)."""
    expires = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {"sub": user_id, "role": role, "exp": expires}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, int(JWT_EXPIRATION_HOURS * 3600)


def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return None


def verify_token_with_grace(token: str) -> Optional[dict]:
    """Проверить токен, допуская недавно истёкшие (для /auth/refresh)."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        try:
            payload = jwt.decode(
                token, JWT_SECRET, algorithms=[JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            if datetime.now(timezone.utc) - exp < timedelta(hours=REFRESH_GRACE_HOURS):
                return payload
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            pass
        return None
    except jwt.InvalidTokenError:
        return None


def extract_bearer_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header[len("Bearer "):].strip() or None


# ─── Зависимости ───────────────────────────────────────────────────────────────

async def get_current_user(request: Request) -> Optional[dict]:
    """Текущий пользователь по Bearer-токену или None. Заблокированные считаются неавторизованными."""
    token = extract_bearer_token(request)
    if not token:
        return None
    payload = verify_token(token)
    if not payload or not payload.get("sub"):
        return None
    db = await get_db()
    user = await db.users.find_one({"_id": payload["sub"]})
    if not user or user.get("banned") or user.get("active") is False:
        return None
    return user


async def require_user(request: Request) -> dict:
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    return user


def require_roles(*roles: str):
    """Фабрика зависимостей: пользователь должен иметь одну из ролей."""
    allowed = set(roles)

    async def dependency(user: dict = Depends(require_user)) -> dict:
        if user.get("role") not in allowed:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        return user

    return dependency


require_admin = require_roles(ROLE_ADMIN)
require_editor = require_roles(*EDITOR_ROLES)
require_moderator = require_roles(*MODERATOR_ROLES)
require_staff = require_roles(*STAFF_ROLES)


async def require_editor_on_write(request: Request) -> None:
    """
    Зависимость уровня роутера: чтение открыто всем, любые изменяющие запросы — только admin/editor.
    Новые POST/PUT/PATCH/DELETE в таком роутере защищены автоматически.
    """
    if request.method in SAFE_METHODS:
        return
    user = await require_user(request)
    if user.get("role") not in EDITOR_ROLES:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
