"""Deterministic article recommendations for public detail pages."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException


COLLECTIONS = {
    "article": "articles",
    "news": "news",
    "person": "people",
    "team": "teams",
    "show": "shows",
    "city": "cities",
    "kvn": "kvn",
}

# Old pages normally showed two or three cards. Keep this policy in one place
# instead of importing hundreds of identical MODX marker modules.
LIMITS = {
    "article": 3,
    "news": 3,
    "person": 3,
    "team": 3,
    "show": 3,
    "city": 2,
    "kvn": 3,
}


def _number(value: Any) -> float:
    if isinstance(value, dict):
        value = value.get("average", 0)
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def rank_articles(source: dict, candidates: list[dict]) -> list[dict]:
    """Rank candidates stably; the final id tie-breaker makes runs reproducible."""
    source_tags = {str(tag).strip().casefold() for tag in source.get("tags") or [] if str(tag).strip()}
    source_id = str(source.get("_id") or source.get("id") or "")
    source_type = str(source.get("content_type") or "")

    def key(article: dict):
        tags = {str(tag).strip().casefold() for tag in article.get("tags") or [] if str(tag).strip()}
        direct = 0
        if source_type == "person" and source_id in (article.get("related_person_ids") or []):
            direct = 1
        elif source_type == "team" and source_id in (article.get("related_team_ids") or []):
            direct = 1
        return (
            -direct,
            -len(source_tags & tags),
            -int(bool(article.get("featured"))),
            -_number(article.get("rating")),
            -int(article.get("views") or 0),
            -_timestamp(article.get("published_at") or article.get("created_at")),
            str(article.get("_id") or article.get("id") or ""),
        )

    return sorted(candidates, key=key)


def public_article(article: dict, *, manual: bool = False) -> dict:
    cover = article.get("cover_image")
    if isinstance(cover, str):
        cover = {"url": cover}
    return {
        "id": str(article.get("_id") or article.get("id") or ""),
        "title": article.get("title") or "",
        "slug": article.get("slug") or "",
        "excerpt": article.get("excerpt"),
        "cover_image": cover,
        "published_at": article.get("published_at"),
        "manual": manual,
        "url": f"/articles/{article.get('slug')}" if article.get("slug") else "",
    }


async def recommendations_for(db, content_type: str, content_id: str, limit: int | None = None) -> dict:
    collection_name = COLLECTIONS.get(content_type)
    if not collection_name:
        raise HTTPException(status_code=422, detail="Неподдерживаемый тип страницы")

    collection = db[collection_name]
    source = await collection.find_one({"$or": [{"_id": content_id}, {"id": content_id}, {"slug": content_id}]})
    if not source or source.get("status") == "archived":
        raise HTTPException(status_code=404, detail="Страница не найдена")

    effective_limit = min(limit or LIMITS[content_type], LIMITS[content_type])
    source_id = str(source.get("_id") or source.get("id") or "")
    excluded = {source_id} if content_type == "article" else set()
    manual_ids = []
    for item_id in source.get("related_article_ids") or []:
        item_id = str(item_id)
        if item_id and item_id not in excluded and item_id not in manual_ids:
            manual_ids.append(item_id)

    projection = {
        "title": 1, "slug": 1, "excerpt": 1, "cover_image": 1, "published_at": 1,
        "created_at": 1, "tags": 1, "featured": 1, "rating": 1, "views": 1,
        "related_person_ids": 1, "related_team_ids": 1, "status": 1,
    }
    manual_docs = []
    if manual_ids:
        found = await db.articles.find(
            {"_id": {"$in": manual_ids}, "status": "published"}, projection
        ).to_list(None)
        by_id = {str(item.get("_id")): item for item in found}
        manual_docs = [by_id[item_id] for item_id in manual_ids if item_id in by_id][:effective_limit]
        excluded.update(by_id)

    remaining = effective_limit - len(manual_docs)
    dynamic_docs: list[dict] = []
    if remaining > 0:
        query: dict = {"status": "published"}
        if excluded:
            query["_id"] = {"$nin": list(excluded)}
        candidates = await db.articles.find(query, projection).to_list(None)
        dynamic_docs = rank_articles({**source, "_id": source_id, "content_type": content_type}, candidates)[:remaining]

    items = [public_article(item, manual=True) for item in manual_docs]
    items.extend(public_article(item) for item in dynamic_docs)
    return {"items": items, "limit": effective_limit}
