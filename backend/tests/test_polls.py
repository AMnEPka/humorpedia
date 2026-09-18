import asyncio
import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from models.poll import PollCreate
from models.modules import PageModule
from services.polls import record_vote, serialize_poll


POLL = {
    "_id": "p1",
    "question": "Кто победит?",
    "status": "published",
    "options": [
        {"id": "a", "text": "Первый", "historical_votes": 3},
        {"id": "b", "text": "Второй", "historical_votes": 1},
    ],
}


def test_poll_model_strips_and_rejects_duplicate_options():
    poll = PollCreate(question="  Кто победит?  ", options=[{"id": "a", "text": "  Первый  "}, {"id": "b", "text": "Второй"}])
    assert poll.question == "Кто победит?"
    assert poll.options[0].text == "Первый"
    with pytest.raises(ValueError):
        PollCreate(question="Вопрос", options=[{"id": "a", "text": "Да"}, {"id": "b", "text": " да "}])


def test_poll_module_requires_poll_id():
    with pytest.raises(ValueError):
        PageModule(type="poll", data={})
    assert PageModule(type="poll", data={"poll_id": "p1"}).data["poll_id"] == "p1"


def test_results_combine_historical_and_live_votes():
    result = serialize_poll(POLL, {"a": 1, "b": 3}, selected_option_id="b", reveal_results=True)
    assert result["total_votes"] == 8
    assert result["options"] == [
        {"id": "a", "text": "Первый", "votes": 4, "percent": 50.0},
        {"id": "b", "text": "Второй", "votes": 4, "percent": 50.0},
    ]


def test_results_are_hidden_before_vote():
    result = serialize_poll(POLL, {}, reveal_results=False)
    assert result["total_votes"] is None
    assert "votes" not in result["options"][0]
    assert "percent" not in result["options"][0]


class _Aggregate:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return self.rows


class _PollVotes:
    def __init__(self):
        self.docs = {}

    async def insert_one(self, doc):
        if doc["_id"] in self.docs:
            raise DuplicateKeyError("duplicate")
        self.docs[doc["_id"]] = doc

    def aggregate(self, _pipeline):
        counts = {}
        for doc in self.docs.values():
            counts[doc["option_id"]] = counts.get(doc["option_id"], 0) + 1
        return _Aggregate([{"_id": key, "count": value} for key, value in counts.items()])


class _Polls:
    def __init__(self, poll):
        self.poll = poll

    async def find_one(self, query):
        return self.poll if query.get("_id") == self.poll.get("_id") else None


class _Db:
    def __init__(self, poll=POLL):
        self.polls = _Polls(poll)
        self.poll_votes = _PollVotes()


def test_vote_is_inserted_once_and_repeat_is_rejected():
    db = _Db()
    result = asyncio.run(record_vote(db, "p1", "u1", "a"))
    assert result["selected_option_id"] == "a"
    assert result["total_votes"] == 5
    with pytest.raises(HTTPException) as error:
        asyncio.run(record_vote(db, "p1", "u1", "b"))
    assert error.value.status_code == 409


def test_draft_poll_does_not_accept_vote():
    db = _Db({**POLL, "status": "draft"})
    with pytest.raises(HTTPException) as error:
        asyncio.run(record_vote(db, "p1", "u1", "a"))
    assert error.value.status_code == 404
