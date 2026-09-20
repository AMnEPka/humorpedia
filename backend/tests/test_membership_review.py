import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import routes.memberships as membership_routes


class _EmptyCursor:
    def __init__(self):
        self.sort_args = None

    def sort(self, *args):
        self.sort_args = args
        return self

    async def to_list(self, _limit):
        return []


class _RecordingCollection:
    def __init__(self, one=None):
        self.one = one
        self.find_calls = []
        self.update_one = AsyncMock()

    async def find_one(self, *_args, **_kwargs):
        return self.one

    def find(self, query, *_args, **_kwargs):
        self.find_calls.append(query)
        return _EmptyCursor()


def test_review_reject_unlinks_but_keeps_membership(monkeypatch):
    memberships = _RecordingCollection({
        "_id": "membership-1",
        "person_id": "wrong-person",
        "person_name": "Анна Бородина",
    })
    db = SimpleNamespace(memberships=memberships)
    monkeypatch.setattr(membership_routes, "get_db", AsyncMock(return_value=db))

    result = asyncio.run(membership_routes.review_membership_link(
        "membership-1",
        membership_routes.MembershipLinkReviewIn(action="reject"),
        user={"_id": "editor-1"},
    ))

    assert result == {"ok": True, "review_status": "rejected"}
    update = memberships.update_one.await_args.args[1]["$set"]
    assert update["person_id"] is None
    assert update["rejected_person_id"] == "wrong-person"
    assert update["person_link_disabled"] is True
    assert update["source"] == "manual"
    assert update["reviewed_by"] == "editor-1"


def test_review_link_confirms_selected_person(monkeypatch):
    memberships = _RecordingCollection({"_id": "membership-1", "candidate_person_id": "suggested"})
    people = _RecordingCollection({"_id": "chosen", "slug": "chosen", "title": "Выбранный человек"})
    db = SimpleNamespace(memberships=memberships, people=people, teams=_RecordingCollection())
    monkeypatch.setattr(membership_routes, "get_db", AsyncMock(return_value=db))

    result = asyncio.run(membership_routes.review_membership_link(
        "membership-1",
        membership_routes.MembershipLinkReviewIn(action="link", person_id="chosen"),
        user={"_id": "editor-1"},
    ))

    assert result == {"ok": True, "review_status": "confirmed"}
    update = memberships.update_one.await_args.args[1]["$set"]
    assert update["person_id"] == "chosen"
    assert update["candidate_person_id"] is None
    assert update["person_link_disabled"] is False


def test_review_confirm_can_restore_rejected_link(monkeypatch):
    memberships = _RecordingCollection({"_id": "membership-1", "rejected_person_id": "person-1"})
    people = _RecordingCollection({"_id": "person-1", "slug": "person", "title": "Человек"})
    db = SimpleNamespace(memberships=memberships, people=people, teams=_RecordingCollection())
    monkeypatch.setattr(membership_routes, "get_db", AsyncMock(return_value=db))

    result = asyncio.run(membership_routes.review_membership_link(
        "membership-1",
        membership_routes.MembershipLinkReviewIn(action="confirm"),
        user={"_id": "editor-1"},
    ))

    assert result == {"ok": True, "review_status": "confirmed"}
    update = memberships.update_one.await_args.args[1]["$set"]
    assert update["person_id"] == "person-1"
    assert update["rejected_person_id"] is None


def test_person_career_uses_only_saved_person_ids(monkeypatch):
    people = _RecordingCollection({"_id": "person-1", "slug": "person", "title": "Человек"})
    memberships = _RecordingCollection()
    participations = _RecordingCollection()
    db = SimpleNamespace(
        people=people,
        memberships=memberships,
        teams=_RecordingCollection(),
        participations=participations,
        tournaments=_RecordingCollection(),
    )
    monkeypatch.setattr(membership_routes, "get_db", AsyncMock(return_value=db))

    result = asyncio.run(membership_routes.person_career("person-1"))

    assert result["teams"] == [] and result["roles"] == []
    assert memberships.find_calls == [{"person_id": "person-1"}]
    assert participations.find_calls[-1] == {
        "kind": "role",
        "season_status": {"$ne": "draft"},
        "person_id": "person-1",
    }
