"""Crash-safe canonical season writes and projection retries."""
import asyncio
import copy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.competitions import save_season
from services.memberships import PersonLookup
from services.season_projection import public_season, recover_season_claim, retry_season_projection


class Result:
    def __init__(self, matched_count=0):
        self.matched_count = matched_count
        self.modified_count = matched_count
        self.deleted_count = matched_count


class Collection:
    def __init__(self, docs=(), fail_update=None):
        self.docs = [copy.deepcopy(doc) for doc in docs]
        self.fail_update = fail_update

    @classmethod
    def matches(cls, doc, query):
        for key, expected in query.items():
            if key == "$and":
                if not all(cls.matches(doc, part) for part in expected):
                    return False
                continue
            if key == "$or":
                if not any(cls.matches(doc, part) for part in expected):
                    return False
                continue
            actual = doc
            present = True
            for part in key.split("."):
                if not isinstance(actual, dict) or part not in actual:
                    present = False
                    actual = None
                    break
                actual = actual[part]
            if isinstance(expected, dict):
                if "$exists" in expected and present != expected["$exists"]:
                    return False
                if "$eq" in expected and (not present or actual != expected["$eq"]):
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$nin" in expected and actual in expected["$nin"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
            elif actual != expected:
                return False
        return True

    async def find_one(self, query, _projection=None):
        return copy.deepcopy(next((d for d in self.docs if self.matches(d, query)), None))

    async def insert_one(self, doc):
        if any(d.get("_id") == doc.get("_id") for d in self.docs):
            raise RuntimeError("duplicate key")
        self.docs.append(copy.deepcopy(doc))
        return SimpleNamespace(inserted_id=doc["_id"])

    async def update_one(self, query, update, upsert=False):
        if self.fail_update:
            keys, error = self.fail_update
            if keys.intersection(update.get("$set", {})):
                self.fail_update = None
                raise error
        for doc in self.docs:
            if self.matches(doc, query):
                for key, value in update.get("$set", {}).items():
                    doc[key] = copy.deepcopy(value)
                for key in update.get("$unset", {}):
                    doc.pop(key, None)
                return Result(1)
        return Result()

    async def replace_one(self, query, replacement, upsert=False):
        for index, doc in enumerate(self.docs):
            if self.matches(doc, query):
                self.docs[index] = copy.deepcopy(replacement)
                return Result(1)
        if upsert:
            self.docs.append(copy.deepcopy(replacement))
            return Result(1)
        return Result()

    async def delete_many(self, query):
        old = len(self.docs)
        self.docs = [d for d in self.docs if not self.matches(d, query)]
        return Result(old - len(self.docs))

    async def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if self.matches(doc, query):
                del self.docs[index]
                return Result(1)
        return Result()


def db_for(season, page, *, fail_page_update=None):
    return SimpleNamespace(
        seasons=Collection([season] if season else []),
        kvn=Collection([page] if page else [], fail_update=fail_page_update),
        participations=Collection(),
    )


def season_doc():
    return {
        "_id": "season-1", "tournament_id": "league-1", "tournament_slug": "vl-kvn",
        "show": "kvn", "participant_type": "team", "year": 2000,
        "title": "Сезон", "slug": "season-2000", "page_collection": "kvn",
        "page_id": "page-1", "page_path": "kvn/vl-kvn/season-2000", "status": "published",
        "teams": [], "winners": [], "stages": [], "legacy_keys": [], "extra": {},
    }


def page_doc():
    return {"_id": "page-1", "updated_at": "page-v1", "title": "Сезон", "season_data": {"year": 1999}}


def run(coro):
    return asyncio.run(coro)


def test_existing_season_without_expected_version_is_never_overwritten():
    db = db_for({**season_doc(), "updated_at": "v1"}, page_doc())
    with pytest.raises(HTTPException) as error:
        run(save_season(db, {**season_doc(), "description": "overwrite"}, write_page=True,
                        people=PersonLookup()))
    assert error.value.status_code == 409
    assert "description" not in db.seasons.docs[0]
    assert db.kvn.docs[0]["season_data"]["year"] == 1999


def test_explicit_null_version_allows_only_unversioned_existing_season():
    db = db_for(season_doc(), page_doc())
    saved = run(save_season(db, {**season_doc(), "description": "first version"}, write_page=True,
                            expected_updated_at=None, expected_page_updated_at="page-v1",
                            people=PersonLookup()))
    assert saved["description"] == "first version"
    assert db.seasons.docs[0]["updated_at"]
    assert db.seasons.docs[0]["created_at"]


def test_failed_projection_can_retry_without_advancing_canonical_version():
    db = db_for({**season_doc(), "updated_at": "v1", "created_at": "created"}, page_doc(),
                fail_page_update=({"season_data"}, RuntimeError("page unavailable")))
    failed = run(save_season(db, {**season_doc(), "updated_at": "v1", "description": "canonical"},
                             write_page=True, expected_updated_at="v1", people=PersonLookup()))
    assert failed["projection_status"] == "error"
    committed = copy.deepcopy(db.seasons.docs[0])
    assert committed["_projection"]["state"] == "error"
    assert "_write_claim" not in committed
    assert db.kvn.docs[0]["_season_write_claim"]["token"] == committed["_projection"]["operation_token"]

    result = run(retry_season_projection(db, "season-1", committed["updated_at"]))
    assert result["updated_at"] == committed["updated_at"]
    assert db.seasons.docs[0]["_projection"]["state"] == "ready"
    assert "_write_claim" not in db.seasons.docs[0]
    assert "_season_write_claim" not in db.kvn.docs[0]
    assert db.kvn.docs[0]["season_data"]["description"] == "canonical"
    assert public_season(db.seasons.docs[0])["_id"] == "season-1"
    assert "_write_claim" not in public_season(db.seasons.docs[0])


def test_foreign_page_claim_conflicts_before_canonical_commit_and_releases_season():
    db = db_for({**season_doc(), "updated_at": "v1"},
                {**page_doc(), "_season_write_claim": {"season_id": "other", "token": "owner"}})
    with pytest.raises(HTTPException) as error:
        run(save_season(db, {**season_doc(), "updated_at": "v1", "description": "new"},
                        write_page=True, expected_updated_at="v1", people=PersonLookup()))
    assert error.value.status_code == 409
    assert db.seasons.docs[0]["updated_at"] == "v1"
    assert "_write_claim" not in db.seasons.docs[0]
    assert db.kvn.docs[0]["_season_write_claim"]["token"] == "owner"


def test_manual_recovery_requires_stopped_worker_and_preserves_committed_page_claim():
    db = db_for({**season_doc(), "updated_at": "v2",
                 "_write_claim": {"token": "stuck", "operation_token": "op-1"},
                 "_projection": {"operation_token": "op-1", "target_version": "v2", "state": "applying",
                                 "page_id": "page-1", "page_db_id": "page-1", "page_updated_at": "page-v2",
                                 "page_base_updated_at": "page-v1", "page_patch": {},
                                 "computed_page_fields": {}, "participation_rows": []}},
                {**page_doc(), "_season_write_claim": {"season_id": "season-1", "token": "op-1"}})
    with pytest.raises(HTTPException) as running:
        run(recover_season_claim(db, "season-1", "stuck", worker_stopped=False,
                                 actor="operator", reason="stalled"))
    assert running.value.status_code == 409
    recovered = run(recover_season_claim(db, "season-1", "stuck", worker_stopped=True,
                                         actor="operator", reason="worker confirmed stopped"))
    assert recovered["phase"] == "postcommit"
    assert "_write_claim" not in db.seasons.docs[0]
    assert db.seasons.docs[0]["_projection"]["state"] == "error"
    assert db.kvn.docs[0]["_season_write_claim"]["token"] == "op-1"


def test_recovery_of_new_precommit_claim_does_not_misclassify_previous_ready_projection():
    db = db_for({**season_doc(), "updated_at": "v2",
                 "_write_claim": {"token": "new-worker", "operation_token": "new-op",
                                  "page_db_id": "page-1", "new_document": False},
                 "_projection": {"operation_token": "old-op", "target_version": "v2", "state": "ready",
                                 "page_id": "page-1", "page_db_id": "page-1", "page_updated_at": "page-v2",
                                 "page_patch": {}, "computed_page_fields": {}, "participation_rows": []}},
                {**page_doc(), "_season_write_claim": {"season_id": "season-1", "token": "new-op"}})
    recovered = run(recover_season_claim(db, "season-1", "new-worker", worker_stopped=True,
                                         actor="operator", reason="precommit worker stopped"))
    assert recovered["phase"] == "precommit"
    assert db.seasons.docs[0]["_projection"]["state"] == "ready"
    assert db.seasons.docs[0]["_projection"]["recovery_audit"][-1]["phase"] == "precommit"
    assert "_write_claim" not in db.seasons.docs[0]
    assert "_season_write_claim" not in db.kvn.docs[0]
