"""Deterministic regressions for concurrent editorial decisions."""

import asyncio
from copy import deepcopy

from fastapi import HTTPException
import pytest

from models.editorial_proposal import EditorialDecisionRequest
from routes import editorial_proposals as route
from services import editorial_decisions
from test_editorial_proposals import _proposal, editorial_client


def test_reject_claim_prevents_concurrent_accept_from_changing_person(monkeypatch, editorial_client):
    client, db = editorial_client
    card = client.post("/api/editorial-proposals", json=_proposal()).json()
    original_persist = route._persist_proposal_progress

    async def race():
        rejection_ready = asyncio.Event()
        release_rejection = asyncio.Event()

        async def pause_rejection(*args, **kwargs):
            proposal = args[1]
            if proposal["changes"][0]["status"] == "rejected":
                rejection_ready.set()
                await release_rejection.wait()
            return await original_persist(*args, **kwargs)

        monkeypatch.setattr(route, "_persist_proposal_progress", pause_rejection)

        async def decide(value):
            request = EditorialDecisionRequest(decisions=[{
                "change_id": "change-1", "decision": value,
            }])
            return await route.decide_editorial_proposal(
                card["id"], request, {"_id": f"editor-{value}"},
            )

        reject_task = asyncio.create_task(decide("reject"))
        try:
            # The rejecter has already read and changed its local snapshot, but has
            # not yet touched the stored proposal. No sleeps or timing assumptions.
            await asyncio.wait_for(rejection_ready.wait(), timeout=5)
            accept_error = None
            try:
                await decide("accept")
            except HTTPException as exc:
                accept_error = exc
            return accept_error
        finally:
            release_rejection.set()
            await reject_task

    error = asyncio.run(race())

    assert error is not None and error.status_code == 409
    assert db.people.docs["p1"]["facts"]["show"] == "старое"
    assert "_editorial_change_ids" not in db.people.docs["p1"]
    saved = db.editorial_proposals.docs[card["id"]]
    assert saved["changes"][0]["status"] == "rejected"
    assert saved["status"] == "rejected"


@pytest.mark.parametrize("cas_failure", ["wrong_token", "stale_revision"])
def test_progress_persist_rejects_lost_claim_or_stale_revision(editorial_client, cas_failure):
    client, db = editorial_client
    card = client.post("/api/editorial-proposals", json=_proposal()).json()
    saved = db.editorial_proposals.docs[card["id"]]
    saved["revision"] = 4
    saved["decision_claim"] = {"token": "owner-token", "actor": "editor", "started_at": "t0"}
    before = deepcopy(saved)
    proposal = deepcopy(saved)
    proposal["changes"][0]["status"] = "rejected"
    proposal["status"] = "rejected"
    if cas_failure == "wrong_token":
        proposal["decision_claim"]["token"] = "other-token"
    else:
        proposal["revision"] = 3

    with pytest.raises(HTTPException) as error:
        asyncio.run(route._persist_proposal_progress(db, proposal))

    assert error.value.status_code == 409
    assert db.editorial_proposals.docs[card["id"]] == before


def test_request_does_not_borrow_claim_replaced_after_acquisition(monkeypatch, editorial_client):
    client, db = editorial_client
    card = client.post("/api/editorial-proposals", json=_proposal()).json()
    acquire_claim = editorial_decisions.claim_decision
    replacement = {"token": "operator-recovery-token", "actor": "recovery", "started_at": "t1"}

    async def replace_owner_after_claim(database, proposal, actor, revision):
        claim = await acquire_claim(database, proposal, actor, revision)
        await database.editorial_proposals.update_one(
            {"_id": proposal["_id"], "decision_claim.token": claim["token"]},
            {"$set": {"decision_claim": replacement}},
        )
        return claim

    monkeypatch.setattr(editorial_decisions, "claim_decision", replace_owner_after_claim)

    async def decide():
        return await route.decide_editorial_proposal(
            card["id"], EditorialDecisionRequest(decisions=[{
                "change_id": "change-1", "decision": "accept",
            }]), {"_id": "editor-1"},
        )

    with pytest.raises(HTTPException) as error:
        asyncio.run(decide())

    assert error.value.status_code == 409
    assert db.people.docs["p1"]["facts"]["show"] == "старое"
    assert db.editorial_proposals.docs[card["id"]]["changes"][0]["status"] == "pending"
    assert db.editorial_proposals.docs[card["id"]]["decision_claim"] == replacement


@pytest.mark.parametrize("retry_decision,retry_value", [("reject", None), ("accept", "B")])
def test_interrupted_person_write_rejects_incompatible_retry(
    monkeypatch, editorial_client, retry_decision, retry_value,
):
    client, db = editorial_client
    card = client.post("/api/editorial-proposals", json=_proposal()).json()
    original_persist = route._persist_proposal_progress

    async def fail_after_person_write(*_args, **_kwargs):
        raise RuntimeError("injected failure after person write")

    monkeypatch.setattr(route, "_persist_proposal_progress", fail_after_person_write)
    first = client.post(f"/api/editorial-proposals/{card['id']}/decide", json={
        "decisions": [{"change_id": "change-1", "decision": "accept", "edited_value": "A"}],
    })
    assert first.status_code == 500
    assert db.people.docs["p1"]["facts"]["show"] == "A"
    assert len(db.people.docs["p1"]["editorial_audit"]) == 1
    assert db.editorial_proposals.docs[card["id"]]["changes"][0]["status"] == "pending"

    monkeypatch.setattr(route, "_persist_proposal_progress", original_persist)
    decision = {"change_id": "change-1", "decision": retry_decision}
    if retry_value is not None:
        decision["edited_value"] = retry_value
    retry = client.post(f"/api/editorial-proposals/{card['id']}/decide", json={"decisions": [decision]})

    assert retry.status_code == 409
    assert db.people.docs["p1"]["facts"]["show"] == "A"
    assert len(db.people.docs["p1"]["editorial_audit"]) == 1
    assert db.editorial_proposals.docs[card["id"]]["changes"][0]["status"] == "pending"


def test_interrupted_person_write_same_value_retry_preserves_later_manual_edit(monkeypatch, editorial_client):
    client, db = editorial_client
    card = client.post("/api/editorial-proposals", json=_proposal()).json()
    original_persist = route._persist_proposal_progress

    async def fail_after_person_write(*_args, **_kwargs):
        raise RuntimeError("injected failure after person write")

    monkeypatch.setattr(route, "_persist_proposal_progress", fail_after_person_write)
    first = client.post(f"/api/editorial-proposals/{card['id']}/decide", json={
        "decisions": [{"change_id": "change-1", "decision": "accept", "edited_value": "A"}],
    })
    assert first.status_code == 500
    db.people.docs["p1"]["facts"]["show"] = "ручная правка"

    monkeypatch.setattr(route, "_persist_proposal_progress", original_persist)
    retry = client.post(f"/api/editorial-proposals/{card['id']}/decide", json={
        "decisions": [{"change_id": "change-1", "decision": "accept", "edited_value": "A"}],
    })

    assert retry.status_code == 200
    assert retry.json()["changes"][0]["status"] == "accepted"
    assert db.people.docs["p1"]["facts"]["show"] == "ручная правка"
    assert len(db.people.docs["p1"]["editorial_audit"]) == 1
    assert db.editorial_proposals.docs[card["id"]]["changes"][0]["status"] == "accepted"


def test_wire_hides_claim_and_recovery_audit_and_defaults_legacy_revision_to_zero():
    proposal = {
        "_id": "legacy", "kind": "update_person", "changes": [],
        "claim_recovery_audit": [{"previous_token": "old-internal-token"}],
        "decision_claim": {"token": "secret-owner-token", "actor": "editor", "started_at": "t0"},
    }

    wire = route._wire(proposal)

    assert wire["revision"] == 0
    assert "decision_claim" not in wire
    assert "claim_recovery_audit" not in wire
    assert wire["id"] == "legacy"
    assert proposal["decision_claim"]["token"] == "secret-owner-token"
