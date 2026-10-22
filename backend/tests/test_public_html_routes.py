import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest
from fastapi import FastAPI, HTTPException
from services.public_html_config import load_public_html_settings
from tests.test_public_html_release import make_release

def config(tmp_path):
    make_release(tmp_path)
    return load_public_html_settings({"PUBLIC_HTML_ENABLED":"true", "PUBLIC_HTML_BUILD_DIR":str(tmp_path),
                                     "PUBLIC_HTML_DEFAULT_IMAGE_URL":"/media/share.png"})

def test_disabled_registers_nothing_and_keeps_metadata_absent():
    from routes.public_html import register_public_html
    app=FastAPI()
    paths=[r.path for r in app.routes]
    register_public_html(app, load_public_html_settings({}))
    assert [r.path for r in app.routes] == paths
    assert not hasattr(app.state, "html_page_metadata")

def test_detail_statuses_and_zero_html_views(monkeypatch, tmp_path):
    from routes import public_html as routes
    from services import public_html_dispatch as dispatch
    from services.page_metadata import build_page_metadata
    from services.public_html import HtmlPage, TextBlock
    cfg=config(tmp_path)
    async def load(kind, slug, **options):
        if slug in {"archived", "private", "unknown"}: raise HTTPException(404)
        if slug == "failure": raise RuntimeError("DB unavailable")
        document={"title":"Альфа", "slug":"alpha" if slug=="id" else slug, "status":"published"}
        meta=build_page_metadata(kind, document, **options)
        return HtmlPage(meta, "Альфа", (TextBlock("", "Основной текст"),), (), (), "/"+kind+"/"+document["slug"], ())
    monkeypatch.setattr(routes, "load_html_page", load)
    monkeypatch.setattr(dispatch, "load_html_page", load)
    db=MagicMock()
    async def find(query, projection):
        old=query["old_urls"]
        return {"_id":"private"} if old=="/private-old" else {"_id":"id"} if old in {"/legacy", "/old&name"} else None
    db.__getitem__.return_value.find_one=AsyncMock(side_effect=find)
    monkeypatch.setattr(dispatch, "get_db", AsyncMock(return_value=db))
    app=FastAPI()
    routes.register_public_html(app,cfg)
    assert set(app.state.html_page_metadata)=={"site_origin","indexing_enabled","default_image_url"}
    assert not any("__html_pilot__" in r.path for r in app.routes)
    release=app.state.public_html_release.release_id
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://evil.example",
                                     headers={"X-Humorpedia-Release":release, "Authorization":"Bearer staff"}) as client:
            for slug,code in [("alpha",200),("id",301),("archived",404),("private",404),("unknown",404),("failure",503)]:
                r=await client.get("/people/"+slug)
                assert r.status_code==code, (slug,r.text)
                assert r.headers["cache-control"]=="no-store"
                assert "noindex" in r.headers["x-robots-tag"]
                head=await client.head("/people/"+slug)
                assert head.status_code==code and not head.content
            assert (await client.get("/people/alpha",headers={"X-Humorpedia-Release":"wrong"})).status_code==503
            assert (await client.get("/people/id")).headers["location"]=="https://humorpedia.ru/people/alpha"
            assert (await client.get("/_internal/public-html/state")).headers["X-Humorpedia-Release"]==release
            for uri, code in [("/legacy?utm=x",301),("/old%26name?q=1",301),("/private-old",404),("/missing-old",418),
                              ("/%61pi/people",418),("/%61dmin/x",418)]:
                r=await client.get("/_internal/public-html/dispatch",headers={"X-Humorpedia-Original-URI":uri})
                assert r.status_code==code,(uri,r.text)
                if code==418: assert not r.content
                h=await client.head("/_internal/public-html/dispatch",headers={"X-Humorpedia-Original-URI":uri})
                assert h.status_code==code and not h.content
            db.__getitem__.return_value.find_one.side_effect=RuntimeError("DB down")
            assert (await client.get("/_internal/public-html/dispatch",headers={"X-Humorpedia-Original-URI":"/legacy"})).status_code==503
    asyncio.run(check())

def test_invalid_release_keeps_api_alive(tmp_path):
    from routes.public_html import register_public_html
    cfg=config(tmp_path)
    (tmp_path/"assets/chunk.js").unlink()
    app=FastAPI()
    @app.get("/api/health")
    def health(): return {"status":"ok"}
    register_public_html(app,cfg)
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            assert (await client.get("/api/health")).status_code==200
            for url in ["/people/a","/_internal/public-html/state"]:
                r=await client.get(url)
                assert r.status_code==503 and "noindex" in r.headers["x-robots-tag"]
    asyncio.run(check())

def test_optional_html_readiness_is_conditional(monkeypatch, tmp_path):
    from routes import health
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock
    monkeypatch.setattr(health, "get_db", AsyncMock(return_value=object()))
    monkeypatch.setattr(health, "check_readiness", AsyncMock(side_effect=lambda *a, **k: {"status":"ready","checks":{"mongodb":"ok","indexes":"ok","package_storage":"ok"}}))
    app=FastAPI()
    app.include_router(health.router,prefix="/api")
    with TestClient(app) as client:
        assert "public_html" not in client.get("/api/ready").json()["checks"]
        app.state.public_html_settings=object()
        app.state.public_html_release=None
        r=client.get("/api/ready")
        assert r.status_code==503 and r.json()["checks"]["public_html"]=="error"
        app.state.public_html_release=object()
        assert client.get("/api/ready").status_code==200
