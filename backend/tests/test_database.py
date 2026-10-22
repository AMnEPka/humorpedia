"""Async driver lifecycle: pool contract, awaited close and clean reinitialization."""
import asyncio
from types import SimpleNamespace

import pytest
from pymongo import AsyncMongoClient
from utils import database


def test_native_async_client_retains_pool_and_shared_database(monkeypatch):
    monkeypatch.setattr(database, "_client", None)
    monkeypatch.setattr(database, "_db", None)
    monkeypatch.setenv("MONGO_URL", "mongodb://127.0.0.1:1")
    monkeypatch.setenv("DB_NAME", "humorpedia_driver_unit")

    async def check():
        db = await database.get_db()
        try:
            assert isinstance(db.client, AsyncMongoClient)
            assert db.name == "humorpedia_driver_unit"
            assert await database.get_db() is db
            pool = db.client.options.pool_options
            assert (pool.max_pool_size, pool.min_pool_size, pool.max_idle_time_seconds) == (50, 10, 45)
            assert db.client.options.server_selection_timeout == 5
        finally:
            await database.close_db()
        assert database._client is None and database._db is None
        reopened = await database.get_db()
        try:
            assert reopened.client is not db.client
        finally:
            await database.close_db()
    asyncio.run(check())


def test_close_waits_for_client_and_detaches_it_before_await(monkeypatch):
    async def check():
        started, release = asyncio.Event(), asyncio.Event()
        async def close():
            started.set()
            await release.wait()
        old_client = SimpleNamespace(close=close)
        monkeypatch.setattr(database, "_client", old_client)
        monkeypatch.setattr(database, "_db", object())
        task = asyncio.create_task(database.close_db())
        try:
            await asyncio.sleep(0)
            assert started.is_set(), "Native asynchronous close was not awaited"
            assert not task.done(), "close_db returned before the client released its resources"
            assert database._client is None and database._db is None
            await database.close_db()  # Repeated shutdown must not close the old client twice.
        finally:
            release.set()
            await task
    asyncio.run(check())


def test_failed_close_does_not_leave_unusable_client_cached(monkeypatch):
    async def close():
        raise RuntimeError("close failed")
    monkeypatch.setattr(database, "_client", SimpleNamespace(close=close))
    monkeypatch.setattr(database, "_db", object())
    with pytest.raises(RuntimeError, match="close failed"):
        asyncio.run(database.close_db())
    assert database._client is None and database._db is None
