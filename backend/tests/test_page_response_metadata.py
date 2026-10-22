import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock
from types import SimpleNamespace
import httpx
import pytest
from fastapi import FastAPI
from starlette.requests import Request

CONFIG = dict(site_origin="https://humorpedia.ru", indexing_enabled=True, default_image_url="/media/pilot-share.png")
DOC = {"_id":"alpha-id","slug":"alpha","title":"Альфа","status":"published","seo":{"meta_title":"Альфа — карточка"},"modules":[]}

def request(config=True):
    app=FastAPI()
    if config:app.state.html_page_metadata=CONFIG
    return Request({"type":"http","app":app,"headers":[],"method":"GET","path":"/"})

def test_metadata_is_opt_in_and_uses_existing_document():
    from services.page_response_metadata import attach_page_metadata
    before=deepcopy(DOC)
    for req,enabled in [(None,True),(request(False),True),(request(),False)]:
        assert attach_page_metadata("people",DOC,req,enabled=enabled)==DOC
    result=attach_page_metadata("people",DOC,request(),enabled=True)
    assert DOC==before
    assert result["page_metadata"]["title"]=="Альфа — карточка | humorpedia.ru"
    assert result["page_metadata"]["canonical_url"]=="https://humorpedia.ru/people/alpha"
    assert result["page_metadata"]["robots"]=="index,follow"

def test_metadata_failure_does_not_break_json():
    from services.page_response_metadata import attach_page_metadata
    document=dict(DOC,slug="")
    result=attach_page_metadata("people",document,request(),enabled=True)
    assert result["page_metadata"] is None and result["slug"]==""
    assert "page_metadata" not in document

@pytest.mark.parametrize("kind",["people","articles"])
def test_metadata_does_not_add_views_or_reads(monkeypatch,kind):
    async def check():
        from routes import content_people,content_articles
        module=content_people if kind=="people" else content_articles
        read=AsyncMock(side_effect=lambda *a,**kw:deepcopy(DOC))
        monkeypatch.setattr(module,"get_by_id_or_slug",read)
        monkeypatch.setattr(module,"get_current_user",AsyncMock(return_value=None))
        monkeypatch.setattr(module.LinkResolver,"resolve_document",AsyncMock())
        monkeypatch.setattr(module,"decorate_document",AsyncMock())
        app=FastAPI();app.state.html_page_metadata=CONFIG
        app.include_router(module.router,prefix="/api")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://evil.invalid") as client:
            url="/api/content/"+kind+"/alpha"
            plain=await client.get(url)
            rich=await client.get(url+"?include_page_metadata=1",headers={"Host":"evil.invalid","Forwarded":"host=evil.invalid"})
            raw=await client.get(url+"?raw=true&include_page_metadata=1")
        assert plain.status_code==rich.status_code==raw.status_code==200
        assert plain.json()==raw.json()==DOC
        assert rich.json()["page_metadata"]["canonical_url"]=="https://humorpedia.ru/"+kind+"/alpha"
        assert read.await_count==3
        assert all(call.kwargs=={"editor":False} for call in read.call_args_list)
    asyncio.run(check())
