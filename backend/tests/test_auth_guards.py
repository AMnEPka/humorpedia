"""
Проверки авторизации, не требующие MongoDB.

Главный тест обходит ВСЕ маршруты приложения: любой изменяющий запрос к /api без токена
должен получать 401/403. Новый эндпоинт без защиты уронит этот тест.
"""
import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from server import app
from utils import auth
from utils.auth import create_token, SAFE_METHODS

# Изменяющие запросы, которые намеренно доступны без токена
PUBLIC_WRITE_ROUTES = {
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/refresh"),   # сам проверяет токен из заголовка
    ("POST", "/api/auth/logout"),
}

# Чтение, закрытое авторизацией
PROTECTED_READ_ROUTES = [
    "/api/mongo/collections",
    "/api/mongo/stats",
    "/api/users",
    "/api/users/some-id",
    "/api/media",
    "/api/media/browse",
    "/api/comments/pending",
    "/api/cache/stats",
    "/api/auth/me",
]


def _fill_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "x", path)


def _write_routes():
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api"):
            continue
        for method in sorted(route.methods - SAFE_METHODS):
            if (method, route.path) not in PUBLIC_WRITE_ROUTES:
                yield method, route.path


@pytest.fixture(scope="module")
def client():
    # Без контекстного менеджера lifespan не запускается — БД не нужна
    return TestClient(app, raise_server_exceptions=False)


def test_write_routes_exist():
    assert len(list(_write_routes())) > 50


@pytest.mark.parametrize("method,path", list(_write_routes()))
def test_write_route_requires_auth(client, method, path):
    response = client.request(method, _fill_path(path), json={})
    assert response.status_code in (401, 403), f"{method} {path} → {response.status_code}"


@pytest.mark.parametrize("path", PROTECTED_READ_ROUTES)
def test_protected_read_requires_auth(client, path):
    response = client.get(path)
    assert response.status_code in (401, 403), f"GET {path} → {response.status_code}"


def test_forged_token_rejected(client):
    import jwt
    forged = jwt.encode({"sub": "someone", "role": "admin"}, "wrong-secret", algorithm="HS256")
    response = client.post("/api/content/people", json={}, headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


# ─── Роли (БД подменяется) ─────────────────────────────────────────────────────

class _FakeUsers:
    def __init__(self, users):
        self._users = {u["_id"]: u for u in users}

    async def find_one(self, query, *args, **kwargs):
        return self._users.get(query.get("_id"))


class _FakeDb:
    def __init__(self, users):
        self.users = _FakeUsers(users)


@pytest.fixture
def fake_users(monkeypatch):
    users = [
        {"_id": "u-admin", "role": "admin"},
        {"_id": "u-editor", "role": "editor"},
        {"_id": "u-moderator", "role": "moderator"},
        {"_id": "u-user", "role": "user"},
        {"_id": "u-banned", "role": "admin", "banned": True},
    ]

    async def fake_get_db():
        return _FakeDb(users)

    monkeypatch.setattr(auth, "get_db", fake_get_db)


def _headers(user_id, role="user"):
    token, _ = create_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("user_id,expected", [
    ("u-user", 403),
    ("u-moderator", 403),
    ("u-banned", 401),
])
def test_content_write_denied_for_non_editors(client, fake_users, user_id, expected):
    response = client.post("/api/content/people", json={}, headers=_headers(user_id))
    assert response.status_code == expected


@pytest.mark.parametrize("user_id", ["u-admin", "u-editor"])
def test_content_write_allowed_for_editors(client, fake_users, user_id):
    # Пустое тело → 422: авторизация пройдена, дальше сработала валидация
    response = client.post("/api/content/people", json={}, headers=_headers(user_id))
    assert response.status_code == 422


@pytest.mark.parametrize("user_id,expected", [
    ("u-editor", 403),
    ("u-admin", 422),
])
def test_mongo_admin_only(client, fake_users, user_id, expected):
    response = client.post("/api/mongo/export", json={}, headers=_headers(user_id))
    assert response.status_code == expected


def test_validation_error_does_not_echo_body(client, fake_users):
    response = client.post(
        "/api/content/people",
        json={"password": "secret-value"},
        headers=_headers("u-admin"),
    )
    assert response.status_code == 422
    assert "secret-value" not in response.text
