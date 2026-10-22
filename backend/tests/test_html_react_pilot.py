import asyncio
from unittest.mock import AsyncMock,MagicMock
import pytest
import httpx
from test_html_react_shell import TEMPLATE,page

@pytest.fixture
def react_env(monkeypatch,tmp_path):
    values={"HTML_PILOT_ENABLED":"1","HTML_REACT_PILOT_ENABLED":"1","HTML_PILOT_RUN_ID":"b"*32,
            "DB_NAME":"humorpedia_html_pilot_"+"b"*32,"MONGO_URL":"mongodb://unused.invalid:27017","HTML_REACT_BUILD_DIR":str(tmp_path)}
    for k,v in values.items():monkeypatch.setenv(k,v)
    (tmp_path/"index.html").write_text(TEMPLATE)
    (tmp_path/"assets").mkdir();(tmp_path/"assets/main.js").write_text("console.log('asset')")
    return tmp_path

@pytest.mark.parametrize("key,value",[("HTML_REACT_PILOT_ENABLED","0"),("DB_NAME","humorpedia"),("HTML_REACT_BUILD_DIR","/does-not-exist")])
def test_factory_rejects_unowned_database(monkeypatch,react_env,key,value):
    from html_react_pilot import create_app
    monkeypatch.setenv(key,value)
    with pytest.raises(ValueError):create_app()

def test_api_assets_precede_legacy_catchall(monkeypatch,react_env):
    async def check():
        from html_react_pilot import create_app
        from routes import html_pilot,content_people
        monkeypatch.setattr(html_pilot,"load_html_page",AsyncMock(return_value=page()))
        db=MagicMock();db.__getitem__.return_value.find_one=AsyncMock(return_value=None)
        monkeypatch.setattr(html_pilot,"get_db",AsyncMock(return_value=db))
        monkeypatch.setattr(content_people,"get_by_id_or_slug",AsyncMock(return_value={"_id":"alpha","slug":"alpha","title":"Альфа","status":"published"}))
        monkeypatch.setattr(content_people,"get_current_user",AsyncMock(return_value=None))
        monkeypatch.setattr(content_people.LinkResolver,"resolve_document",AsyncMock())
        monkeypatch.setattr(content_people,"decorate_document",AsyncMock())
        app=create_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://owned") as client:
            assert (await client.get("/assets/main.js")).text=="console.log('asset')"
            assert "window.__HTML_PILOT__ = true" in (await client.get("/config.js")).text
            html=await client.get("/people/alpha")
            assert html.status_code==200 and 'id="html-pilot-fallback"' in html.text
            api=await client.get("/api/content/people/alpha?include_page_metadata=1")
            assert api.status_code==200 and api.json()["page_metadata"]["canonical_url"]=="https://humorpedia.ru/people/alpha"
            assert (await client.get("/people")).status_code==200
            assert (await client.get("/api/content/people")).status_code==404
            assert (await client.post("/api/content/people",json={})).status_code in {404,405}
            assert (await client.get("/unknown")).status_code==404
        forbidden=("/source-import","/page-packages","/seasons/import","/admin","/auth/register","/auth/vk")
        assert not any(any(part in getattr(route,"path","") for part in forbidden) for route in app.routes)
    asyncio.run(check())

def test_lifespan_stops_views_before_native_close(monkeypatch,react_env):
    async def check():
        import html_pilot,html_react_pilot
        events=[]
        fake=type("DB",(),{"command":AsyncMock(),"name":"humorpedia_html_pilot_"+"b"*32})()
        monkeypatch.setattr(html_pilot,"get_db",AsyncMock(return_value=fake))
        monkeypatch.setattr(html_react_pilot,"get_db",AsyncMock(return_value=fake))
        monkeypatch.setattr(html_pilot,"close_db",AsyncMock(side_effect=lambda:events.append("close")))
        monkeypatch.setattr(html_react_pilot.views_counter,"start",AsyncMock(side_effect=lambda db:events.append("start")))
        monkeypatch.setattr(html_react_pilot.views_counter,"stop",AsyncMock(side_effect=lambda:events.append("stop")))
        app=html_react_pilot.create_app()
        async with app.router.lifespan_context(app):events.append("inside")
        assert events==["start","inside","stop","close"]
    asyncio.run(check())

@pytest.mark.skipif(__import__("os").environ.get("HTML_REACT_PILOT_INTEGRATION")!="1",reason="Needs owned Mongo")
def test_native_html_zero_views_json_one_and_cleanup(monkeypatch,react_env):
    async def check():
        import importlib.util,sys,uuid
        from pathlib import Path
        from utils import database
        from services import views_counter as counters
        import html_react_pilot
        run_id=uuid.uuid4().hex
        monkeypatch.setenv("HTML_PILOT_RUN_ID",run_id)
        monkeypatch.setenv("DB_NAME","humorpedia_html_pilot_"+run_id)
        monkeypatch.setenv("MONGO_URL",__import__("os").environ["HTML_REACT_TEST_MONGO_URL"])
        counter=counters.ViewsCounter()
        monkeypatch.setattr(counters,"views_counter",counter)
        monkeypatch.setattr(html_react_pilot,"views_counter",counter)
        folder=Path(__file__).resolve().parents[2]/"scripts/seo"
        monkeypatch.syspath_prepend(str(folder))
        spec=importlib.util.spec_from_file_location("react_harness",folder/"react_pilot_server.py")
        harness=importlib.util.module_from_spec(spec);spec.loader.exec_module(harness)
        app=harness.create_fixture_app()
        async with app.router.lifespan_context(app):
            db=await database.get_db()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://owned") as client:
                assert (await client.get("/people/alpha")).status_code==200
                assert counter.pending_count()==0
                assert (await db.people.find_one({"_id":"person-alpha"})).get("views",0)==0
                api=await client.get("/api/content/people/alpha?include_page_metadata=1")
                assert api.status_code==200 and api.json()["page_metadata"]["title"]=="Альфа — карточка | humorpedia.ru"
                assert counter.pending_count()==1
                await counter.flush()
                assert (await db.people.find_one({"_id":"person-alpha"}))["views"]==1
                assert (await client.get("/api/competitions/people/alpha/career")).json()["teams"]
                shows=await client.get("/api/show-appearances/people/person-alpha")
                assert shows.status_code==200 and shows.json()["items"],shows.text
                login=await client.post("/api/auth/login",json={"email":"pilot@example.invalid","password":"Pilot-only-2026"})
                assert login.status_code==200,login.text
                vote=await client.post("/api/polls/poll-demo/vote",json={"option_id":"yes"},headers={"Authorization":"Bearer "+login.json()["access_token"]})
                assert vote.status_code==200,vote.text
        db=await database.get_db()
        assert db.name not in await db.client.list_database_names()
        await database.close_db()
    asyncio.run(check())
