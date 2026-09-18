"""Anonymous ratings for articles, people, teams and shows.

New votes are the source of truth and are kept separately from the imported
legacy aggregates. This avoids cross-document counters, which cannot be made
transactional with the project's standalone MongoDB deployment.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from models.rating import RatingEntityType
from utils.auth import JWT_SECRET


ENTITY_COLLECTIONS = {
    RatingEntityType.ARTICLE.value: "articles",
    RatingEntityType.PERSON.value: "people",
    RatingEntityType.TEAM.value: "teams",
    RatingEntityType.SHOW.value: "shows",
}

COOKIE_NAME = "hp_rating_voter"
COOKIE_MAX_AGE = 365 * 24 * 60 * 60
_COOKIE_CONTEXT = b"humorpedia-rating-cookie-v1:"
_VISITOR_CONTEXT = b"humorpedia-rating-visitor-v1:"
_VOTE_CONTEXT = b"humorpedia-rating-vote-v1:"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hmac_hex(context: bytes, value: str) -> str:
    return hmac.new(JWT_SECRET.encode("utf-8"), context + value.encode("utf-8"), hashlib.sha256).hexdigest()


def create_voter_cookie() -> str:
    """Create an opaque, server-signed anonymous visitor cookie."""
    token = secrets.token_urlsafe(32)
    return f"{token}.{_hmac_hex(_COOKIE_CONTEXT, token)}"


def verify_voter_cookie(value: str | None) -> str | None:
    """Return the opaque token when the cookie signature is valid."""
    if not value or "." not in value:
        return None
    token, signature = value.rsplit(".", 1)
    if not token or not hmac.compare_digest(signature, _hmac_hex(_COOKIE_CONTEXT, token)):
        return None
    return token


def visitor_hash(token: str) -> str:
    """Derive a non-reversible database identifier from the cookie token."""
    return _hmac_hex(_VISITOR_CONTEXT, token)


def vote_document_id(entity_type: str, entity_id: str, voter_hash: str) -> str:
    """Stable id makes concurrent retries idempotent even without the compound index."""
    value = f"{entity_type}:{entity_id}:{voter_hash}"
    return hmac.new(JWT_SECRET.encode("utf-8"), _VOTE_CONTEXT + value.encode("utf-8"), hashlib.sha256).hexdigest()


def votes_label(count: int) -> str | None:
    """Return only the public milestone, never the exact vote count."""
    if count <= 0:
        return None
    if count < 50:
        return "менее 50 голосов"
    if count < 100:
        return "50+ голосов"
    if count < 250:
        return "100+ голосов"
    if count < 500:
        return "250+ голосов"
    if count < 1000:
        return "500+ голосов"
    return "1000+ голосов"


def normalize_legacy_rating(document: dict[str, Any]) -> tuple[float, int, float | None]:
    """Convert both imported rating shapes to an immutable weighted baseline."""
    raw_rating = document.get("rating")
    if isinstance(raw_rating, dict):
        raw_average = raw_rating.get("average")
        # Object count is authoritative: imported team votes_count is incomplete.
        raw_count = raw_rating.get("count")
    elif isinstance(raw_rating, (int, float)) and not isinstance(raw_rating, bool):
        raw_average = raw_rating
        raw_count = document.get("votes_count")
    else:
        return 0.0, 0, None

    try:
        average = float(raw_average)
        count = int(raw_count or 0)
    except (TypeError, ValueError):
        return 0.0, 0, None

    if count <= 0 or average < 0 or average > 10:
        return 0.0, 0, None
    return average * count, count, average


async def resolve_entity(db, entity_type: str, entity_id: str) -> dict[str, Any]:
    collection_name = ENTITY_COLLECTIONS.get(entity_type)
    if not collection_name:
        raise HTTPException(status_code=422, detail="Неизвестный тип рейтинга")
    entity = await getattr(db, collection_name).find_one({"_id": entity_id})
    if not entity or entity.get("status") == "archived":
        raise HTTPException(status_code=404, detail="Страница не найдена")
    return entity


async def ensure_baseline(db, entity_type: str, entity: dict[str, Any]) -> dict[str, Any]:
    baseline_id = f"{entity_type}:{entity['_id']}"
    existing = await db.rating_baselines.find_one({"_id": baseline_id})
    if existing:
        return existing

    legacy_sum, legacy_count, legacy_average = normalize_legacy_rating(entity)
    document = {
        "_id": baseline_id,
        "entity_type": entity_type,
        "entity_id": entity["_id"],
        "sum": legacy_sum,
        "count": legacy_count,
        "legacy_average": legacy_average,
        "created_at": _now(),
    }
    await db.rating_baselines.update_one(
        {"_id": baseline_id},
        {"$setOnInsert": document},
        upsert=True,
    )
    return await db.rating_baselines.find_one({"_id": baseline_id}) or document


async def _new_votes_total(db, entity_type: str, entity_id: str) -> tuple[float, int]:
    rows = await db.rating_votes.aggregate([
        {"$match": {"entity_type": entity_type, "entity_id": entity_id}},
        {"$group": {"_id": None, "sum": {"$sum": "$score"}, "count": {"$sum": 1}}},
    ]).to_list(1)
    if not rows:
        return 0.0, 0
    return float(rows[0].get("sum") or 0), int(rows[0].get("count") or 0)


async def get_rating_snapshot(db, entity_type: str, entity_id: str, voter: str) -> dict[str, Any]:
    entity = await resolve_entity(db, entity_type, entity_id)
    baseline = await ensure_baseline(db, entity_type, entity)
    new_sum, new_count = await _new_votes_total(db, entity_type, entity_id)
    total_sum = float(baseline.get("sum") or 0) + new_sum
    total_count = int(baseline.get("count") or 0) + new_count
    own_vote = await db.rating_votes.find_one({
        "_id": vote_document_id(entity_type, entity_id, voter),
    })
    return {
        "average": round(total_sum / total_count, 1) if total_count else None,
        "votes_label": votes_label(total_count),
        "my_score": own_vote.get("score") if own_vote else None,
    }


async def set_rating(db, entity_type: str, entity_id: str, voter: str, score: int) -> dict[str, Any]:
    entity = await resolve_entity(db, entity_type, entity_id)
    await ensure_baseline(db, entity_type, entity)
    now = _now()
    vote_id = vote_document_id(entity_type, entity_id, voter)
    await db.rating_votes.update_one(
        {"_id": vote_id},
        {
            "$set": {"score": score, "updated_at": now},
            "$setOnInsert": {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "voter_hash": voter,
                "created_at": now,
            },
        },
        upsert=True,
    )
    return await get_rating_snapshot(db, entity_type, entity_id, voter)


async def migrate_baselines(db, *, apply: bool = False) -> dict[str, Any]:
    """Audit and optionally create immutable baselines for all supported content."""
    report: dict[str, Any] = {"apply": apply, "types": {}, "created": 0, "existing": 0}
    for entity_type, collection_name in ENTITY_COLLECTIONS.items():
        stats = {"documents": 0, "with_votes": 0, "created": 0, "existing": 0, "count_mismatches": 0}
        async for entity in getattr(db, collection_name).find({}):
            stats["documents"] += 1
            legacy_sum, legacy_count, legacy_average = normalize_legacy_rating(entity)
            if legacy_count:
                stats["with_votes"] += 1
            raw_rating = entity.get("rating")
            if isinstance(raw_rating, dict):
                try:
                    duplicate_count = int(entity.get("votes_count") or 0)
                except (TypeError, ValueError):
                    duplicate_count = 0
                if legacy_count != duplicate_count:
                    stats["count_mismatches"] += 1

            baseline_id = f"{entity_type}:{entity['_id']}"
            if await db.rating_baselines.find_one({"_id": baseline_id}, {"_id": 1}):
                stats["existing"] += 1
                report["existing"] += 1
                continue
            if apply:
                await db.rating_baselines.insert_one({
                    "_id": baseline_id,
                    "entity_type": entity_type,
                    "entity_id": entity["_id"],
                    "sum": legacy_sum,
                    "count": legacy_count,
                    "legacy_average": legacy_average,
                    "created_at": _now(),
                })
            stats["created"] += 1
            report["created"] += 1
        report["types"][entity_type] = stats
    return report
