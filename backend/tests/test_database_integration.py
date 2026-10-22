"""R12b native driver/API contracts on a new UUID database, one event loop per client."""
import asyncio
import json
import os
import uuid

import httpx
import pytest
from pymongo import AsyncMongoClient
from pymongo.errors import InvalidOperation

from utils import database

pytestmark = pytest.mark.skipif(os.environ.get("DATABASE_INTEGRATION") != "1", reason="Needs isolated MongoDB with DATABASE_INTEGRATION=1")


def test_native_aggregations_and_reopen_preserve_data(monkeypatch, tmp_path):
    name = "humorpedia_driver_test_" + uuid.uuid4().hex
    monkeypatch.setenv("DB_NAME", name)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))

    async def check():
        assert database._client is None, "Previous test must close its client on its own loop"
        db = await database.get_db()
        assert isinstance(db.client, AsyncMongoClient)
        assert db.name == name and not await db.list_collection_names()
        old_client = db.client
        try:
            await db.people.insert_many([
                {"_id": "alpha", "title": "Альфа", "slug": "alpha", "status": "published", "full_path": "people/alpha"},
                {"_id": "beta", "title": "Бета", "slug": "beta", "status": "published"},
                {"_id": "hidden", "title": "Архив", "slug": "hidden", "status": "archived"},
            ])
            await db.articles.insert_many([
                {"_id": "article", "title": "Статья", "slug": "article", "status": "published"},
                {"_id": "archived", "title": "Архивная статья", "slug": "archived", "status": "archived"},
            ])
            await db.poll_votes.insert_many([
                {"poll_id": "poll", "option_id": "a"}, {"poll_id": "poll", "option_id": "a"},
                {"poll_id": "other", "option_id": "a"},
            ])
            await db.rating_votes.insert_many([
                {"entity_type": "person", "entity_id": "alpha", "score": 6},
                {"entity_type": "person", "entity_id": "alpha", "score": 8},
                {"entity_type": "person", "entity_id": "beta", "score": 2},
            ])
            from services.crud import list_alphabetical_content
            from services.polls import live_vote_counts
            from services.ratings import _new_votes_total
            query = {"status": "published"}
            result = await list_alphabetical_content("people", 0, 1, query, ["title"], availability_query=query)
            assert [item["_id"] for item in result["items"]] == ["alpha"]
            assert result["total"] == 2 and result["available_letters"] == ["А", "Б"]
            assert await live_vote_counts(db, "poll") == {"a": 2}
            assert await _new_votes_total(db, "person", "alpha") == (14.0, 2)
            from server import app
            from utils.auth import create_token
            await db.users.insert_one({"_id": "driver-admin", "role": "admin"})
            token, _ = create_token("driver-admin", "admin")
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                article = await client.get("/api/content/articles/random")
                assert article.status_code == 200 and article.json()["_id"] == "article"
                person = await client.get("/api/random/person?exclude_slug=beta")
                assert person.status_code == 200 and person.json()["_id"] == "alpha"
                assert person.json()["full_path"] == "people/alpha"
                response = await client.post("/api/mongo/aggregate", headers={"Authorization": "Bearer " + token},
                    json={"collection": "people", "pipeline": json.dumps([{"$match": {"status": "published"}}, {"$sort": {"_id": 1}}])})
                assert response.status_code == 200, response.text
                assert response.json()["count"] == 2
                assert [item["_id"] for item in json.loads(response.json()["data"])] == ["alpha", "beta"]
                invalid = await client.get("/api/tags?sort_by=invalid")
                assert invalid.status_code == 422
                valid = await client.get("/api/tags?sort_by=name")
                assert valid.status_code == 200
            await database.close_db()
            with pytest.raises(InvalidOperation):
                await old_client.admin.command("ping")
            reopened = await database.get_db()
            assert reopened.client is not old_client
            assert (await reopened.people.find_one({"_id": "alpha"}))["title"] == "Альфа"
        finally:
            cleanup = await database.get_db()
            assert cleanup.name == name and name.startswith("humorpedia_driver_test_")
            await cleanup.client.drop_database(name)
            await database.close_db()
    asyncio.run(check())
