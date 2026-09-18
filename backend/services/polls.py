"""Poll result aggregation and atomic one-user-one-vote writes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError


def serialize_poll(poll: dict, live_counts: dict[str, int], *, selected_option_id: str | None = None,
                   reveal_results: bool = False) -> dict:
    options = []
    total = 0
    for option in poll.get("options") or []:
        votes = int(option.get("historical_votes") or 0) + int(live_counts.get(str(option.get("id")), 0))
        total += votes
        options.append({"id": str(option.get("id")), "text": option.get("text") or "", "votes": votes})
    for option in options:
        option["percent"] = round(option["votes"] * 100 / total, 1) if total else 0.0
        if not reveal_results:
            option.pop("votes", None)
            option.pop("percent", None)
    return {
        "id": str(poll.get("_id")),
        "question": poll.get("question") or "",
        "status": poll.get("status") or "draft",
        "options": options,
        "selected_option_id": selected_option_id,
        "results_visible": reveal_results,
        "total_votes": total if reveal_results else None,
    }


async def live_vote_counts(db, poll_id: str) -> dict[str, int]:
    rows = await db.poll_votes.aggregate([
        {"$match": {"poll_id": poll_id}},
        {"$group": {"_id": "$option_id", "count": {"$sum": 1}}},
    ]).to_list(None)
    return {str(row["_id"]): int(row["count"]) for row in rows}


async def poll_for_public(db, poll_id: str, user: dict | None = None) -> dict:
    poll = await db.polls.find_one({"_id": poll_id})
    if not poll or poll.get("status") != "published":
        raise HTTPException(status_code=404, detail="Опрос не найден")
    selected = None
    if user:
        vote = await db.poll_votes.find_one({"poll_id": poll_id, "user_id": str(user["_id"])})
        selected = str(vote["option_id"]) if vote else None
    reveal = bool(poll.get("show_results_before_vote")) or selected is not None
    counts = await live_vote_counts(db, poll_id) if reveal else {}
    return serialize_poll(poll, counts, selected_option_id=selected, reveal_results=reveal)


async def record_vote(db, poll_id: str, user_id: str, option_id: str) -> dict:
    poll = await db.polls.find_one({"_id": poll_id})
    if not poll or poll.get("status") != "published":
        raise HTTPException(status_code=404, detail="Опрос не найден")
    if option_id not in {str(option.get("id")) for option in poll.get("options") or []}:
        raise HTTPException(status_code=422, detail="Вариант ответа не найден")
    now = datetime.now(timezone.utc).isoformat()
    try:
        await db.poll_votes.insert_one({
            "_id": f"{poll_id}:{user_id}",
            "poll_id": poll_id,
            "user_id": str(user_id),
            "option_id": option_id,
            "created_at": now,
        })
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Вы уже голосовали в этом опросе") from None
    counts = await live_vote_counts(db, poll_id)
    return serialize_poll(poll, counts, selected_option_id=option_id, reveal_results=True)
