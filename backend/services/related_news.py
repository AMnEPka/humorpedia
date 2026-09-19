"""Resolve global settings and fresh news related to a page entity."""

from datetime import datetime, timedelta, timezone
from typing import Any

from models.related_news import RelatedNewsSettings


SETTINGS_ID = "related_news"


async def get_related_news_settings(db) -> RelatedNewsSettings:
    stored = await db.site_settings.find_one({"_id": SETTINGS_ID})
    if not stored:
        return RelatedNewsSettings()
    return RelatedNewsSettings.model_validate(stored)


async def save_related_news_settings(db, settings: RelatedNewsSettings) -> dict[str, Any]:
    payload = settings.model_dump()
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.site_settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": payload},
        upsert=True,
    )
    return settings.model_dump()


async def _entity_target(db, entity_type: str, entity_id: str) -> tuple[str, str, str] | None:
    if entity_type == "person":
        entity = await db.people.find_one(
            {"$or": [{"_id": entity_id}, {"slug": entity_id}]},
            {"_id": 1},
        )
        return ("people", "related_person_ids", entity["_id"]) if entity else None

    if entity_type == "team":
        entity = await db.teams.find_one(
            {"$or": [{"_id": entity_id}, {"slug": entity_id}, {"full_path": entity_id}]},
            {"_id": 1, "show_id": 1},
        )
        if not entity:
            return None
        return (
            "show_teams" if entity.get("show_id") else "kvn_teams",
            "related_team_ids",
            entity["_id"],
        )

    if entity_type == "show":
        entity = await db.shows.find_one(
            {"$or": [{"_id": entity_id}, {"slug": entity_id}, {"full_path": entity_id}]},
            {"_id": 1},
        )
        return ("shows", "related_show_ids", entity["_id"]) if entity else None

    return None


async def related_news_for(db, entity_type: str, entity_id: str) -> dict[str, Any]:
    settings = await get_related_news_settings(db)
    base = {
        "enabled": False,
        "items": [],
        "freshness_days": settings.freshness_days,
        "max_items": settings.max_items,
    }
    if not settings.enabled:
        return base

    target = await _entity_target(db, entity_type, entity_id)
    if not target:
        return base
    target_key, relation_field, resolved_entity_id = target
    if not getattr(settings.apply_to, target_key):
        return base

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.freshness_days)
    query = {
        relation_field: resolved_entity_id,
        "status": {"$ne": "archived"},
        "published_at": {"$gte": cutoff.isoformat()},
    }
    projection = {
        "title": 1,
        "slug": 1,
        "excerpt": 1,
        "cover_image": 1,
        "published_at": 1,
    }
    items = await db.news.find(query, projection).sort("published_at", -1).limit(settings.max_items).to_list(settings.max_items)
    for item in items:
        item["id"] = item.pop("_id")

    return {**base, "enabled": True, "items": items}
