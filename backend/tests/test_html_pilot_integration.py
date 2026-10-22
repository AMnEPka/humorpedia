"""Opt-in driver/app test; owns a fresh UUID DB and never uses production data."""
import asyncio
import importlib.util
import os
from pathlib import Path
import uuid
import httpx
import pytest
from bson import BSON

pytestmark = pytest.mark.skipif(os.environ.get("HTML_PILOT_INTEGRATION") != "1", reason="Needs owned Mongo with HTML_PILOT_INTEGRATION=1")

def test_real_mongo_gets_preserve_documents_and_restart(monkeypatch):
    async def check():
        from utils import database
        assert database._client is None, "Previous loop left a client"
        run_id=uuid.uuid4().hex
        monkeypatch.setenv("HTML_PILOT_ENABLED","1")
        monkeypatch.setenv("HTML_PILOT_RUN_ID",run_id)
        monkeypatch.setenv("HTML_PILOT_INDEXING_ENABLED","1")
        monkeypatch.setenv("DB_NAME","humorpedia_html_pilot_"+run_id)
        module_path=Path(__file__).resolve().parents[2]/"scripts/seo/pilot_server.py"
        spec=importlib.util.spec_from_file_location("pilot_harness",module_path)
        harness=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(harness)
        db=await database.get_db()
        async def snapshot():
            return {name:[BSON.encode(d) for d in await db[name].find({}).sort("_id",1).to_list(None)] for name in sorted(await db.list_collection_names())}
        owned=False
        try:
            await harness.seed_fixture_database(db,run_id)
            owned=True
            before=await snapshot()
            with pytest.raises(RuntimeError):
                await harness.seed_fixture_database(db,run_id)
            from html_pilot import create_app
            app=create_app()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test", cookies={"admin_token":"staff"}) as client:
                person=await client.get("/people/alpha")
                assert person.status_code==200
                assert "Основной текст Альфы" in person.text and "Бета*" in person.text
                assert "признан в РФ иностранным агентом" in person.text
                assert "HIDDEN_SECRET" not in person.text and "SIDEBAR_SECRET" not in person.text
                assert "index,follow" == person.headers["x-robots-tag"]
                article=await client.get("/articles/story")
                assert article.status_code==200 and "Бете*" in article.text and "SCRIPT_SECRET" not in article.text
                legacy=(await client.get("/articles/legacy")).text
                assert "Legacy text" in legacy and "Бета*" in legacy
                assert legacy.count("признан в РФ иностранным агентом") == 1
                notice=(await client.get("/articles/legacy-notice")).text
                assert "Бета*" in notice and notice.count("признан в РФ иностранным агентом") == 1
                assert "FALLBACK_SECRET" not in (await client.get("/articles/hidden-only")).text
                for slug in ("draft","missing"):
                    response=await client.get("/people/"+slug)
                    assert response.status_code==200 and "noindex" in response.headers["x-robots-tag"]
                for url in ("/people/archived","/people/unknown","/old/archived.html","/old/unknown.html","/people/private","/old/private.html","/people/private.html","/people/archived.html","/people/unknown.html"):
                    response=await client.get(url,headers={"Authorization":"Bearer staff"})
                    assert response.status_code==404
                for url in ("/old/alpha.html","/people/alpha-old.html","/people/person-alpha"):
                    response=await client.get(url,headers={"Host":"evil.invalid"},follow_redirects=False)
                    assert response.status_code==301 and response.headers["location"]=="https://humorpedia.ru/people/alpha"
                for url,target in [("/people/beta.html","/people/beta"),("/articles/story.html","/articles/story")]:
                    response=await client.get(url,follow_redirects=False)
                    assert response.status_code==301 and response.headers["location"]=="https://humorpedia.ru"+target
                assert await snapshot()==before
                await db.people.update_one({"_id":"person-alpha"},{"$set":{"status":"draft","modules.0.data.content":"<p>Обновлённый текст</p>"}})
                response=await client.get("/people/alpha")
                assert response.status_code==200 and "noindex" in response.headers["x-robots-tag"] and "Обновлённый текст" in response.text
                await db.people.update_one({"_id":"person-alpha"},{"$set":{"slug":"renamed","status":"archived"}})
                assert (await client.get("/people/renamed")).status_code==404
            await database.close_db()
            db=await database.get_db()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()),base_url="http://test") as client:
                assert (await client.get("/people/renamed")).status_code==404
                assert (await client.get("/people/alpha")).status_code==404
                assert (await client.get("/articles/story")).status_code==200
        finally:
            if owned:
                await harness.cleanup_fixture_database(await database.get_db(),run_id)
            await database.close_db()
    asyncio.run(check())
