"""Публичный readiness: недоступные зависимости дают 503 без внутренних подробностей."""
import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from routes import health
from services.readiness import check_readiness


INDEX = {"collection": "entities", "keys": [("slug", 1)], "options": {"unique": True}}


class FakeDB:
    def __init__(self, *, mongo_error=False, mongo_hangs=False, indexes=None):
        self.mongo_error = mongo_error
        self.mongo_hangs = mongo_hangs
        self.indexes = {"slug_1": {"key": [("slug", 1)], "unique": True}} if indexes is None else indexes

    async def command(self, _command):
        if self.mongo_hangs:
            await asyncio.Event().wait()
        if self.mongo_error:
            raise RuntimeError("mongodb://private-user:private-password@internal-host")
        return {"ok": 1}

    def __getitem__(self, _collection):
        return self

    async def index_information(self):
        return self.indexes


def run(db, path, **kwargs):
    return asyncio.run(check_readiness(db, indexes_initialized=True, required_indexes=[INDEX],
                                      package_dir=path, public_dirs=[], **kwargs))


def test_ready_checks_live_indexes_and_storage_without_leaving_probe_files(tmp_path):
    result = run(FakeDB(), tmp_path)
    assert result == {"status": "ready", "checks": {"mongodb": "ok", "indexes": "ok", "package_storage": "ok"}}
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("failure", ["unreachable", "timeout"])
def test_mongo_failure_and_bounded_timeout_hide_connection_details(tmp_path, failure):
    result = run(FakeDB(mongo_error=failure == "unreachable", mongo_hangs=failure == "timeout"),
                 tmp_path, timeout=0.02)
    assert result["status"] == "not_ready"
    assert result["checks"]["mongodb"] == "error"
    assert "private-password" not in str(result) and "internal-host" not in str(result)


@pytest.mark.parametrize("indexes", [{}, {"slug_1": {"key": [("slug", 1)]}},
                                    {"slug_1": {"key": [("slug", 1)], "unique": True, "sparse": True}}])
def test_missing_or_weaker_unique_index_is_not_ready(tmp_path, indexes):
    assert run(FakeDB(indexes=indexes), tmp_path)["checks"]["indexes"] == "error"


def test_index_initialization_must_complete(tmp_path):
    result = asyncio.run(check_readiness(FakeDB(), indexes_initialized=False, required_indexes=[INDEX],
                                        package_dir=tmp_path, public_dirs=[]))
    assert result["checks"]["indexes"] == "error"


def test_required_sparse_and_partial_index_options_are_preserved(tmp_path):
    partial = {"slug": {"$type": "string"}}
    index = {"collection": "entities", "keys": [("slug", 1)],
             "options": {"unique": True, "partialFilterExpression": partial}}
    db = FakeDB(indexes={"custom": {"key": [("slug", 1)], "unique": True, "partialFilterExpression": partial}})
    result = asyncio.run(check_readiness(db, indexes_initialized=True, required_indexes=[index],
                                        package_dir=tmp_path, public_dirs=[]))
    assert result["checks"]["indexes"] == "ok"


def test_missing_or_public_package_directory_is_not_ready(tmp_path):
    absent = tmp_path / "absent"
    assert run(FakeDB(), absent)["checks"]["package_storage"] == "error"
    assert not absent.exists()
    result = asyncio.run(check_readiness(FakeDB(), indexes_initialized=True, required_indexes=[INDEX],
                                        package_dir=tmp_path, public_dirs=[tmp_path.parent]))
    assert result["checks"]["package_storage"] == "error"


def test_storage_write_failure_is_not_ready(tmp_path, monkeypatch):
    import services.readiness as service
    def fail(*_args, **_kwargs):
        raise PermissionError("private path")
    monkeypatch.setattr(service.tempfile, "TemporaryFile", fail)
    assert run(FakeDB(), tmp_path)["checks"]["package_storage"] == "error"


def test_http_readiness_is_public_and_reports_failure_with_503(tmp_path, monkeypatch):
    db = FakeDB(mongo_error=True)
    async def get_db():
        return db
    monkeypatch.setattr(health, "get_db", get_db)
    monkeypatch.setenv("PAGE_PACKAGE_DIR", str(tmp_path))
    app = FastAPI()
    app.state.indexes_initialized = True
    app.state.required_indexes = [INDEX]
    app.include_router(health.router, prefix="/api")
    with TestClient(app) as client:
        response = client.get("/api/ready")
        assert response.status_code == 503
        assert response.json()["checks"]["mongodb"] == "error"
        assert "private-password" not in response.text
        db.mongo_error = False
        assert client.get("/api/ready").status_code == 200

def test_server_health_probes_bypass_content_cache(tmp_path, monkeypatch):
    import server
    async def unavailable():
        raise RuntimeError("content cache must not gate health probes")
    async def healthy_db():
        return FakeDB()
    monkeypatch.setattr(server, "get_db", unavailable)
    monkeypatch.setattr(health, "get_db", healthy_db)
    monkeypatch.setenv("PAGE_PACKAGE_DIR", str(tmp_path))
    monkeypatch.setattr(server.app.state, "indexes_initialized", True)
    monkeypatch.setattr(server.app.state, "required_indexes", [INDEX])
    client = TestClient(server.app, raise_server_exceptions=False)
    assert client.get("/api/health").json() == {"status": "healthy"}
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
