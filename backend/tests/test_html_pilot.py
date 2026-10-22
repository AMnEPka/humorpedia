import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
import httpx
from fastapi import HTTPException

@pytest.fixture
def pilot_env(monkeypatch):
    for key, value in {"HTML_PILOT_ENABLED": "1", "HTML_PILOT_RUN_ID": "a"*32, "DB_NAME": "humorpedia_html_pilot_"+"a"*32, "MONGO_URL": "mongodb://pilot.invalid:27017"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("HTML_PILOT_INDEXING_ENABLED", raising=False)

@pytest.mark.parametrize("key,value", [("HTML_PILOT_ENABLED","0"), ("HTML_PILOT_RUN_ID","bad"), ("DB_NAME","humorpedia"), ("MONGO_URL","")])
def test_factory_rejects_unowned_database(monkeypatch, pilot_env, key, value):
    from html_pilot import create_app
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        create_app()

def test_http_visibility_robots_and_safe_redirects(monkeypatch, pilot_env):
    async def check():
        from html_pilot import create_app
        from routes import html_pilot as routes
        from services.page_metadata import build_page_metadata
        from services.public_html import HtmlPage, TextBlock
        async def load(kind, slug, **options):
            if slug == "archived": raise HTTPException(404)
            if slug == "unavailable": raise RuntimeError("test-only DB failure")
            doc = {"title": "Альфа", "slug": "alpha" if slug == "uuid" else slug, "status": "draft" if slug == "draft" else "published"}
            meta = build_page_metadata(kind, doc, **options)
            return HtmlPage(meta, doc["title"], (TextBlock("", "Основной текст"),), (), (), "/"+kind+"/"+doc["slug"], ())
        monkeypatch.setattr(routes, "load_html_page", load)
        db = MagicMock()
        db.__getitem__.return_value.find_one = AsyncMock(return_value=None)
        monkeypatch.setattr(routes, "get_db", AsyncMock(return_value=db))
        app = create_app()
        assert not any(set(getattr(r, "methods", ())) & {"POST","PUT","DELETE"} for r in app.routes)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://evil.invalid", cookies={"admin_token":"staff"}) as client:
            for slug, expected in [("alpha",200),("draft",200),("archived",404),("unavailable",503)]:
                r=await client.get("/people/"+slug, headers={"Authorization":"Bearer staff","Forwarded":"host=evil.invalid"})
                assert r.status_code == expected
                assert r.headers["cache-control"] == "no-store"
                assert "noindex" in r.headers["x-robots-tag"]
            r=await client.get("/people/uuid", follow_redirects=False)
            assert r.status_code == 301 and r.headers["location"] == "https://humorpedia.ru/people/alpha"
            assert (await client.post("/people/alpha")).status_code == 405
            assert (await client.get("/no-such-route")).status_code == 404
            assert (await client.get("/__html_pilot__/status")).json()["run_id"] == "a"*32
        monkeypatch.setenv("HTML_PILOT_INDEXING_ENABLED","1")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://test", cookies={"admin_token":"staff"}) as client:
            assert "index,follow" in (await client.get("/people/alpha")).headers["x-robots-tag"]
            assert "noindex" in (await client.get("/people/draft")).headers["x-robots-tag"]
    asyncio.run(check())

def test_lifespan_closes_native_client_on_its_loop(monkeypatch, pilot_env):
    async def check():
        import html_pilot
        fake = type("DB", (), {"command": AsyncMock(), "name": "humorpedia_html_pilot_"+"a"*32})()
        monkeypatch.setattr(html_pilot,"get_db",AsyncMock(return_value=fake))
        close=AsyncMock()
        monkeypatch.setattr(html_pilot,"close_db",close)
        app=html_pilot.create_app()
        async with app.router.lifespan_context(app):
            assert close.await_count == 0
        assert close.await_count == 1
    asyncio.run(check())

def test_production_app_does_not_register_pilot():
    from server import app
    assert not any(getattr(route, "endpoint", None).__module__ == "routes.html_pilot"
                   for route in app.routes if getattr(route, "endpoint", None))
    assert not any(getattr(route, "path", "").startswith("/__html_pilot__") for route in app.routes)
