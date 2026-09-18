import asyncio
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from models.rating import RatingVoteRequest
from server import app
from services.ratings import (
    create_voter_cookie,
    normalize_legacy_rating,
    set_rating,
    verify_voter_cookie,
    visitor_hash,
    votes_label,
)


class _Result:
    matched_count = 1
    deleted_count = 1


class _AggregateCursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return deepcopy(self.rows)


class _Collection:
    def __init__(self, documents=None):
        self.documents = {doc["_id"]: deepcopy(doc) for doc in (documents or [])}
        self._lock = asyncio.Lock()

    async def find_one(self, query, projection=None):
        document = self.documents.get(query.get("_id"))
        if not document:
            return None
        if any(document.get(key) != value for key, value in query.items() if key != "_id"):
            return None
        if projection:
            return {key: document[key] for key in projection if key in document}
        return deepcopy(document)

    async def update_one(self, query, update, upsert=False):
        async with self._lock:
            document = deepcopy(self.documents.get(query["_id"]))
            if document is None:
                if not upsert:
                    result = _Result()
                    result.matched_count = 0
                    return result
                document = {"_id": query["_id"]}
                document.update(deepcopy(update.get("$setOnInsert", {})))
            document.update(deepcopy(update.get("$set", {})))
            self.documents[query["_id"]] = document
        return _Result()

    def aggregate(self, pipeline):
        match = pipeline[0]["$match"]
        scores = [
            doc["score"] for doc in self.documents.values()
            if doc.get("entity_type") == match["entity_type"] and doc.get("entity_id") == match["entity_id"]
        ]
        rows = [{"_id": None, "sum": sum(scores), "count": len(scores)}] if scores else []
        return _AggregateCursor(rows)


class _Db:
    def __init__(self, entity=None, collection_name="articles"):
        self.articles = _Collection([entity] if entity and collection_name == "articles" else [])
        self.people = _Collection([entity] if entity and collection_name == "people" else [])
        self.teams = _Collection([entity] if entity and collection_name == "teams" else [])
        self.shows = _Collection([entity] if entity and collection_name == "shows" else [])
        self.rating_baselines = _Collection()
        self.rating_votes = _Collection()


@pytest.mark.parametrize(
    "count,label",
    [
        (0, None),
        (1, "менее 50 голосов"),
        (49, "менее 50 голосов"),
        (50, "50+ голосов"),
        (99, "50+ голосов"),
        (100, "100+ голосов"),
        (249, "100+ голосов"),
        (250, "250+ голосов"),
        (499, "250+ голосов"),
        (500, "500+ голосов"),
        (999, "500+ голосов"),
        (1000, "1000+ голосов"),
    ],
)
def test_votes_label_boundaries(count, label):
    assert votes_label(count) == label


def test_legacy_shapes_and_team_object_count_priority():
    assert normalize_legacy_rating({"rating": 8.5, "votes_count": 4}) == (34.0, 4, 8.5)
    assert normalize_legacy_rating({"rating": {"average": 9.0, "count": 3}, "votes_count": 0}) == (27.0, 3, 9.0)
    assert normalize_legacy_rating({"rating": None, "votes_count": 12}) == (0.0, 0, None)


def test_cookie_is_signed_and_tampering_is_rejected():
    cookie = create_voter_cookie()
    token = verify_voter_cookie(cookie)
    assert token
    assert visitor_hash(token) == visitor_hash(token)
    assert verify_voter_cookie(cookie + "x") is None


@pytest.mark.parametrize("score", [0, 11, 1.5, "5", True, False])
def test_score_is_strict_integer_from_one_to_ten(score):
    with pytest.raises(Exception):
        RatingVoteRequest(score=score)


def test_replacing_vote_keeps_one_document_and_recalculates_average():
    db = _Db({"_id": "article-1", "status": "published", "rating": 8.0, "votes_count": 2})

    async def scenario():
        first = await set_rating(db, "article", "article-1", "visitor-a", 10)
        assert first == {"average": 8.7, "votes_label": "менее 50 голосов", "my_score": 10}

        replaced = await set_rating(db, "article", "article-1", "visitor-a", 2)
        assert replaced == {"average": 6.0, "votes_label": "менее 50 голосов", "my_score": 2}
        assert len(db.rating_votes.documents) == 1

        another = await set_rating(db, "article", "article-1", "visitor-b", 10)
        assert another == {"average": 7.0, "votes_label": "менее 50 голосов", "my_score": 10}
        assert len(db.rating_votes.documents) == 2

    asyncio.run(scenario())


def test_public_api_sets_cookie_and_never_returns_exact_count(monkeypatch):
    db = _Db({"_id": "person-1", "status": "draft", "rating": {"average": 9.0, "count": 2}} , "people")

    async def fake_get_db():
        return db

    async def no_cache_sync(_db):
        return None

    monkeypatch.setattr("routes.ratings.get_db", fake_get_db)
    monkeypatch.setattr("server.get_db", fake_get_db)
    monkeypatch.setattr("server._cache.sync_with_peers", no_cache_sync)
    client = TestClient(app, raise_server_exceptions=False)

    first = client.get("/api/ratings/person/person-1")
    assert first.status_code == 200
    assert first.json() == {"average": 9.0, "votes_label": "менее 50 голосов", "my_score": None}
    assert "hp_rating_voter=" in first.headers["set-cookie"]
    assert first.headers["cache-control"] == "private, no-store"
    assert first.headers["vary"] == "Cookie"
    assert "count" not in first.text

    voted = client.put("/api/ratings/person/person-1", json={"score": 7})
    assert voted.status_code == 200
    assert voted.json()["my_score"] == 7
    assert "count" not in voted.text

    refreshed = client.get("/api/ratings/person/person-1")
    assert refreshed.status_code == 200
    assert refreshed.json()["my_score"] == 7
