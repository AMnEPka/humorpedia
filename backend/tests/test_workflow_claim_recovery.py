"""Поведенческие тесты ручного освобождения зависших claims на fake storage."""

import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from scripts import recover_workflow_claim as recovery


class _Collection:
    def __init__(self, document):
        self.document = deepcopy(document)
        self.writes = []
        self.before_update = None

    async def find_one(self, query, projection=None):
        if query.get("_id") != self.document.get("_id"):
            return None
        for key, expected in query.items():
            value = self.document
            for part in key.split("."):
                value = value.get(part) if isinstance(value, dict) else None
            if value != expected:
                return None
        result = deepcopy(self.document)
        if projection:
            result = {key: result[key] for key in projection if key in result}
        return result

    async def update_one(self, query, update):
        self.writes.append((deepcopy(query), deepcopy(update)))
        if self.before_update:
            self.before_update(self.document)
        current = await self.find_one(query)
        if current is None:
            return SimpleNamespace(matched_count=0, modified_count=0)
        for key, value in update.get("$set", {}).items():
            target = self.document
            parts = key.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = deepcopy(value)
        for key in update.get("$unset", {}):
            target = self.document
            parts = key.split(".")
            for part in parts[:-1]:
                target = target.get(part, {})
            if isinstance(target, dict):
                target.pop(parts[-1], None)
        for key, value in update.get("$inc", {}).items():
            self.document[key] = self.document.get(key, 0) + value
        for key, value in update.get("$push", {}).items():
            self.document.setdefault(key, []).append(deepcopy(value))
        return SimpleNamespace(matched_count=1, modified_count=1)


class _Db:
    def __init__(self, kind, document):
        self.name = "unit-test-db"
        self.page_package_imports = _Collection(document) if kind == "page-package" else None
        self.editorial_proposals = _Collection(document) if kind == "editorial" else None


def _package():
    return {
        "_id": "pkg-1", "status": "applying", "lease_token": "old-package-token",
        "lease_until": "2030-01-01T00:00:00+00:00", "target_id": "person-1",
        "page": {"title": "Существующая страница"}, "assets": [{"id": "asset-1"}],
        "content": {"preserve": True}, "claim_recovery_audit": [],
    }


def _editorial():
    return {
        "_id": "proposal-1", "status": "in_review", "revision": 7,
        "decision_claim": {"token": "old-editorial-token", "actor": "editor", "started_at": "t0"},
        "person_id": "person-1", "changes": [{"id": "change-1", "status": "pending"}],
        "claim_recovery_audit": [],
    }


@pytest.mark.parametrize(
    "kind,document,token,revision",
    [
        ("page-package", _package(), "old-package-token", None),
        ("editorial", _editorial(), "old-editorial-token", 7),
    ],
)
def test_default_dry_run_reports_claim_without_writing(kind, document, token, revision):
    db = _Db(kind, document)
    before = deepcopy((db.page_package_imports or db.editorial_proposals).document)

    result = asyncio.run(recovery.recover_claim(db, kind, document["_id"]))

    assert result["status"] == ("applying" if kind == "page-package" else "in_review")
    assert result["token"] == token
    assert result["revision"] == revision
    assert result["applied"] is False
    collection = db.page_package_imports or db.editorial_proposals
    assert collection.writes == []
    assert collection.document == before


@pytest.mark.parametrize(
    "kind,document,expected_token,worker_stopped,actor,reason",
    [
        ("page-package", _package(), None, True, "operator", "worker stopped"),
        ("page-package", _package(), "wrong-token", True, "operator", "worker stopped"),
        ("editorial", _editorial(), "old-editorial-token", False, "operator", "worker stopped"),
        ("editorial", _editorial(), "old-editorial-token", True, "", "worker stopped"),
        ("editorial", _editorial(), "old-editorial-token", True, "operator", "  "),
    ],
)
def test_apply_requires_exact_token_stop_confirmation_actor_and_reason(
    kind, document, expected_token, worker_stopped, actor, reason,
):
    db = _Db(kind, document)
    collection = db.page_package_imports or db.editorial_proposals
    before = deepcopy(collection.document)

    with pytest.raises(ValueError):
        asyncio.run(recovery.recover_claim(
            db, kind, document["_id"], expected_token=expected_token, actor=actor,
            reason=reason, apply=True, worker_stopped=worker_stopped,
        ))

    assert collection.writes == []
    assert collection.document == before


def test_page_package_recovery_cas_preserves_target_and_records_operator_audit():
    db = _Db("page-package", _package())
    before = deepcopy(db.page_package_imports.document)

    result = asyncio.run(recovery.recover_claim(
        db, "page-package", "pkg-1", expected_token="old-package-token",
        actor="operator-1", reason="worker confirmed stopped", apply=True, worker_stopped=True,
    ))

    saved = db.page_package_imports.document
    query, update = db.page_package_imports.writes[0]
    assert query == {"_id": "pkg-1", "status": "applying", "lease_token": "old-package-token"}
    assert saved["status"] == "error"
    assert "lease_token" not in saved and "lease_until" not in saved
    assert saved["target_id"] == before["target_id"] and saved["page"] == before["page"]
    assert saved["assets"] == before["assets"] and saved["content"] == before["content"]
    audit = saved["claim_recovery_audit"][-1]
    assert audit["previous_token"] == "old-package-token"
    assert audit["actor"] == "operator-1" and audit["reason"] == "worker confirmed stopped"
    assert audit["at"]
    assert update["$set"]["error"]
    assert result["applied"] is True


def test_editorial_recovery_cas_unsets_claim_increments_revision_and_audits():
    db = _Db("editorial", _editorial())

    result = asyncio.run(recovery.recover_claim(
        db, "editorial", "proposal-1", expected_token="old-editorial-token",
        actor="operator-1", reason="editor stopped and confirmed", apply=True, worker_stopped=True,
    ))

    query, update = db.editorial_proposals.writes[0]
    saved = db.editorial_proposals.document
    assert query == {"_id": "proposal-1", "decision_claim.token": "old-editorial-token", "revision": 7}
    assert update["$inc"] == {"revision": 1}
    assert "decision_claim" not in saved and saved["revision"] == 8
    assert saved["person_id"] == "person-1" and saved["changes"][0]["status"] == "pending"
    audit = saved["claim_recovery_audit"][-1]
    assert audit["previous_token"] == "old-editorial-token"
    assert audit["actor"] == "operator-1" and audit["reason"] == "editor stopped and confirmed"
    assert audit["at"]
    assert result["applied"] is True


@pytest.mark.parametrize("kind,document", [("page-package", _package()), ("editorial", _editorial())])
def test_recovery_cas_does_not_clear_claim_that_changed_after_read(kind, document):
    db = _Db(kind, document)
    collection = db.page_package_imports or db.editorial_proposals

    def replace_claim(current):
        if kind == "page-package":
            current["lease_token"] = "new-worker-token"
        else:
            current["decision_claim"]["token"] = "new-editor-token"
            current["revision"] += 1

    collection.before_update = replace_claim
    with pytest.raises(ValueError):
        asyncio.run(recovery.recover_claim(
            db, kind, document["_id"], expected_token=("old-package-token" if kind == "page-package" else "old-editorial-token"),
            actor="operator-1", reason="worker confirmed stopped", apply=True, worker_stopped=True,
        ))

    assert collection.document["status"] == ("applying" if kind == "page-package" else "in_review")
    assert collection.document.get("lease_token", collection.document.get("decision_claim", {}).get("token")) in {
        "new-worker-token", "new-editor-token",
    }
    assert collection.document["claim_recovery_audit"] == []


def test_second_recovery_cannot_clear_replacement_claim():
    db = _Db("editorial", _editorial())
    asyncio.run(recovery.recover_claim(
        db, "editorial", "proposal-1", expected_token="old-editorial-token",
        actor="operator-1", reason="stopped", apply=True, worker_stopped=True,
    ))
    saved = db.editorial_proposals.document
    saved["decision_claim"] = {"token": "new-worker-token", "actor": "editor-2"}
    before = deepcopy(saved)

    with pytest.raises(ValueError):
        asyncio.run(recovery.recover_claim(
            db, "editorial", "proposal-1", expected_token="old-editorial-token",
            actor="operator-1", reason="stopped", apply=True, worker_stopped=True,
        ))

    assert saved == before


def test_cli_rejects_unconfirmed_apply_before_database_access(monkeypatch, capsys):
    monkeypatch.setenv("MONGO_URL", "mongodb://operator:private-password@mongo.example/test")
    called = False

    async def database_access_must_not_run(_args):
        nonlocal called
        called = True
        raise AssertionError("database helper was called before write confirmation")

    monkeypatch.setattr(recovery, "_run_cli", database_access_must_not_run)
    with pytest.raises(SystemExit) as error:
        recovery.main(["--db-name", "unit-test-db", "--kind", "editorial", "--id", "proposal-1", "--apply"])

    assert error.value.code == 2
    assert called is False
    assert "private-password" not in capsys.readouterr().err


def test_cli_prints_json_summary_without_connection_credentials(monkeypatch, capsys):
    monkeypatch.setenv("MONGO_URL", "mongodb://operator:private-password@mongo.example/test")

    async def fake_run(_args):
        return {"kind": "editorial", "id": "proposal-1", "status": "pending",
                "token": "operator-visible-claim-token", "revision": 3, "applied": False}

    monkeypatch.setattr(recovery, "_run_cli", fake_run)

    assert recovery.main(["--db-name", "unit-test-db", "--kind", "editorial", "--id", "proposal-1"]) == 0

    captured = capsys.readouterr()
    assert json.loads(captured.out)["token"] == "operator-visible-claim-token"
    assert "private-password" not in captured.out + captured.err
