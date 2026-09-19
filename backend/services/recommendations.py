"""Global, deterministic recommendations for the public "Читайте также" block."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from models.recommendation import RecommendationSettings
from services.show_teams import team_url


SETTINGS_ID = "recommendations"
CANDIDATE_POOL_PER_TYPE = 60
RELEVANT_POOL_PER_TYPE = 200

SOURCE_COLLECTIONS = {
    "article": "articles", "news": "news", "person": "people", "team": "teams",
    "show": "shows", "city": "cities", "kvn": "kvn",
}

RESULT_COLLECTIONS = {
    "article": "articles", "person": "people", "kvn_team": "teams", "show_team": "teams",
    "show": "shows", "city": "cities", "kvn": "kvn", "quiz": "quizzes", "news": "news",
}

RESULT_LABELS = {
    "article": "Статья", "person": "Человек", "kvn_team": "Команда КВН",
    "show_team": "Команда шоу", "show": "Шоу", "city": "Город", "kvn": "КВН",
    "quiz": "Квиз", "news": "Новость",
}

TARGET_KEYS = {
    "article": "articles", "news": "news", "person": "people", "show": "shows",
    "city": "cities", "kvn": "kvn",
}

RELATION_FIELDS: dict[str, dict[str, tuple[str, ...]]] = {
    "article": {
        "article": ("related_article_ids",), "person": ("related_person_ids",),
        "team": ("related_team_ids",), "show": ("related_show_ids",),
    },
    "news": {
        "article": ("related_article_ids",), "person": ("related_person_ids",),
        "team": ("related_team_ids",), "show": ("related_show_ids",),
    },
    "person": {"article": ("article_ids",), "team": ("team_ids",), "show": ("show_ids",)},
    "team": {
        "article": ("article_ids",), "person": ("member_ids",),
        "team": ("related_team_ids",), "show": ("show_ids", "show_id"),
    },
    "show": {
        "article": ("article_ids",), "person": ("participant_ids", "related_person_ids"),
        "team": ("team_ids",), "show": ("related_show_ids",),
    },
    "city": {"person": ("related_person_ids",), "team": ("related_team_ids",)},
    "kvn": {
        "article": ("article_ids",), "person": ("person_ids",), "team": ("team_ids",),
        "kvn": ("related_kvn_ids", "parent_id", "child_kvn_ids"),
    },
    "quiz": {},
}

PROJECTION = {
    "title": 1, "name": 1, "full_name": 1, "slug": 1, "full_path": 1, "show_id": 1,
    "excerpt": 1, "description": 1, "cover_image": 1, "photo": 1, "logo": 1,
    "poster": 1, "header_image": 1, "published_at": 1, "created_at": 1, "tags": 1,
    "featured": 1, "rating": 1, "views": 1, "status": 1, "related_article_ids": 1,
    "related_person_ids": 1, "related_team_ids": 1, "related_show_ids": 1, "article_ids": 1,
    "team_ids": 1, "show_ids": 1, "member_ids": 1, "participant_ids": 1, "person_ids": 1,
    "related_kvn_ids": 1, "parent_id": 1, "child_kvn_ids": 1,
}


async def get_recommendation_settings(db) -> RecommendationSettings:
    stored = await db.site_settings.find_one({"_id": SETTINGS_ID})
    return RecommendationSettings.model_validate(stored or {})


async def save_recommendation_settings(db, settings: RecommendationSettings) -> dict[str, Any]:
    payload = settings.model_dump()
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.site_settings.update_one({"_id": SETTINGS_ID}, {"$set": payload}, upsert=True)
    return settings.model_dump()


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


def _base_type(value: str) -> str:
    return "team" if value in {"kvn_team", "show_team"} else value


def _relation_ids(document: dict[str, Any], source_type: str, target_type: str) -> set[str]:
    result: set[str] = set()
    for field in RELATION_FIELDS.get(source_type, {}).get(target_type, ()):
        value = document.get(field)
        values = value if isinstance(value, list) else [value]
        result.update(str(item) for item in values if item)
    return result


def _directly_related(source: dict[str, Any], source_type: str, candidate: dict[str, Any]) -> bool:
    source_id = str(source.get("_id") or source.get("id") or "")
    candidate_id = str(candidate.get("_id") or candidate.get("id") or "")
    candidate_type = _base_type(str(candidate.get("_recommendation_type") or ""))
    return (
        candidate_id in _relation_ids(source, source_type, candidate_type)
        or source_id in _relation_ids(candidate, candidate_type, source_type)
    )


def rank_candidates(
    source: dict[str, Any], source_type: str, candidates: list[dict[str, Any]], result_types: list[str],
) -> list[dict[str, Any]]:
    """Rank mixed content stably: explicit relations, tags, then popularity and recency."""
    source_tags = {str(tag).strip().casefold() for tag in source.get("tags") or [] if str(tag).strip()}
    type_order = {item_type: index for index, item_type in enumerate(result_types)}

    def key(item: dict[str, Any]):
        tags = {str(tag).strip().casefold() for tag in item.get("tags") or [] if str(tag).strip()}
        return (
            -int(_directly_related(source, source_type, item)), -len(source_tags & tags),
            -int(bool(item.get("featured"))), -_number(item.get("rating")),
            -int(item.get("views") or 0), -_timestamp(item.get("published_at") or item.get("created_at")),
            type_order.get(str(item.get("_recommendation_type")), len(type_order)),
            str(item.get("_id") or item.get("id") or ""),
        )

    return sorted(candidates, key=key)


def rank_articles(source: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Backward-compatible helper for existing callers and focused tests."""
    source_type = str(source.get("content_type") or "article")
    prepared = [{**item, "_recommendation_type": "article"} for item in candidates]
    return rank_candidates(source, source_type, prepared, ["article"])


def _media(document: dict[str, Any]) -> dict[str, Any] | None:
    for field in ("cover_image", "photo", "logo", "poster", "header_image"):
        value = document.get(field)
        if isinstance(value, str) and value:
            return {"url": value}
        if isinstance(value, dict) and (value.get("url") or value.get("thumbnail")):
            return value
    return None


def _summary(document: dict[str, Any]) -> str | None:
    value = document.get("excerpt") or document.get("description")
    if not isinstance(value, str) or not value.strip():
        return None
    text = re.sub(r"<[^>]+>", " ", html.unescape(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:177] + "…" if len(text) > 180 else text


def _url(document: dict[str, Any], result_type: str) -> str:
    slug = str(document.get("slug") or "").strip("/")
    full_path = str(document.get("full_path") or "").strip("/")
    if result_type == "article":
        return f"/articles/{slug}" if slug else ""
    if result_type == "news":
        return f"/news/{slug}" if slug else ""
    if result_type == "person":
        return f"/people/{slug}" if slug else ""
    if result_type in {"kvn_team", "show_team"}:
        return team_url(document) if slug else ""
    if result_type == "show":
        return f"/shows/{full_path or slug}" if (full_path or slug) else ""
    if result_type == "city":
        return f"/city/{slug}" if slug else ""
    if result_type == "kvn":
        return f"/{full_path or ('kvn/' + slug if slug else '')}" if (full_path or slug) else ""
    if result_type == "quiz":
        return f"/quizzes/{slug}" if slug else ""
    return ""


def public_item(document: dict[str, Any], result_type: str, *, manual: bool = False) -> dict[str, Any] | None:
    url = _url(document, result_type)
    if not url:
        return None
    return {
        "id": str(document.get("_id") or document.get("id") or ""), "type": result_type,
        "type_label": RESULT_LABELS[result_type],
        "title": document.get("title") or document.get("name") or document.get("full_name") or "",
        "slug": document.get("slug") or "", "excerpt": _summary(document),
        "cover_image": _media(document), "published_at": document.get("published_at"),
        "manual": manual, "url": url,
    }


def _candidate_query(result_type: str) -> dict[str, Any]:
    query: dict[str, Any] = {"status": {"$ne": "archived"}}
    if result_type == "kvn_team":
        query["show_id"] = None
    elif result_type == "show_team":
        query["show_id"] = {"$ne": None}
    return query


def _relevance_clauses(source: dict[str, Any], source_type: str, result_type: str) -> list[dict[str, Any]]:
    target_type = _base_type(result_type)
    source_id = str(source.get("_id") or source.get("id") or "")
    clauses: list[dict[str, Any]] = []
    direct_ids = _relation_ids(source, source_type, target_type)
    if direct_ids:
        clauses.append({"_id": {"$in": list(direct_ids)}})
    for field in RELATION_FIELDS.get(target_type, {}).get(source_type, ()):
        clauses.append({field: source_id})
    tags = [str(tag).strip() for tag in source.get("tags") or [] if str(tag).strip()]
    if tags:
        clauses.append({"tags": {"$in": tags}})
    return clauses


async def _candidate_documents(db, source: dict[str, Any], source_type: str, result_type: str) -> list[dict[str, Any]]:
    collection = db[RESULT_COLLECTIONS[result_type]]
    base_query = _candidate_query(result_type)
    documents: list[dict[str, Any]] = []
    clauses = _relevance_clauses(source, source_type, result_type)
    if clauses:
        relevant_query = {**base_query, "$or": clauses}
        documents.extend(await collection.find(relevant_query, PROJECTION).to_list(RELEVANT_POOL_PER_TYPE))

    fallback = collection.find(base_query, PROJECTION).sort([
        ("featured", -1), ("views", -1), ("published_at", -1), ("_id", 1),
    ]).limit(CANDIDATE_POOL_PER_TYPE)
    documents.extend(await fallback.to_list(CANDIDATE_POOL_PER_TYPE))
    unique: dict[str, dict[str, Any]] = {}
    for document in documents:
        item_id = str(document.get("_id") or document.get("id") or "")
        if item_id and item_id not in unique:
            unique[item_id] = document
    return list(unique.values())


async def _resolve_source(db, content_type: str, content_id: str) -> tuple[dict[str, Any] | None, str]:
    query = {"$or": [{"_id": content_id}, {"id": content_id}, {"slug": content_id}, {"full_path": content_id}]}
    collection_name = SOURCE_COLLECTIONS[content_type]
    source = await db[collection_name].find_one(query)
    if content_type == "kvn" and not source:
        source = await db.sections.find_one(query)
        collection_name = "sections"
    return source, collection_name


def _target_key(content_type: str, source: dict[str, Any]) -> str:
    if content_type == "team":
        return "show_teams" if source.get("show_id") else "kvn_teams"
    return TARGET_KEYS[content_type]


async def recommendations_for(db, content_type: str, content_id: str, limit: int | None = None) -> dict[str, Any]:
    if content_type not in SOURCE_COLLECTIONS:
        raise HTTPException(status_code=422, detail="Неподдерживаемый тип страницы")
    source, source_collection = await _resolve_source(db, content_type, content_id)
    if not source or source.get("status") == "archived":
        raise HTTPException(status_code=404, detail="Страница не найдена")

    settings = await get_recommendation_settings(db)
    effective_limit = min(settings.max_items, limit) if limit else settings.max_items
    base = {"enabled": False, "items": [], "max_items": effective_limit}
    if not settings.enabled or not getattr(settings.apply_to, _target_key(content_type, source)):
        return base

    result_types = list(settings.result_types)
    source_id = str(source.get("_id") or source.get("id") or "")
    excluded: set[tuple[str, str]] = {(source_collection, source_id)}
    source_result_type = (
        "show_team" if content_type == "team" and source.get("show_id")
        else "kvn_team" if content_type == "team"
        else content_type
    )
    source_url = _url(source, source_result_type)
    excluded_urls = {source_url} if source_url else set()

    manual_items: list[dict[str, Any]] = []
    manual_ids = list(dict.fromkeys(str(item) for item in source.get("related_article_ids") or [] if item))
    if "article" in result_types and manual_ids:
        documents = await db.articles.find(
            {"_id": {"$in": manual_ids}, "status": {"$ne": "archived"}}, PROJECTION,
        ).to_list(None)
        by_id = {str(item.get("_id")): item for item in documents}
        for item_id in manual_ids:
            key = ("articles", item_id)
            if key in excluded or item_id not in by_id:
                continue
            serialized = public_item(by_id[item_id], "article", manual=True)
            if serialized:
                manual_items.append(serialized)
                excluded.add(key)
                excluded_urls.add(serialized["url"])
            if len(manual_items) >= effective_limit:
                break

    candidates: list[dict[str, Any]] = []
    if len(manual_items) < effective_limit:
        for result_type in result_types:
            collection_name = RESULT_COLLECTIONS[result_type]
            documents = await _candidate_documents(db, source, content_type, result_type)
            for document in documents:
                item_id = str(document.get("_id") or document.get("id") or "")
                key = (collection_name, item_id)
                item_url = _url(document, result_type)
                if not item_id or key in excluded or not item_url or item_url in excluded_urls:
                    continue
                candidates.append({**document, "_recommendation_type": result_type})

    items = list(manual_items)
    for candidate in rank_candidates(source, content_type, candidates, result_types):
        serialized = public_item(candidate, str(candidate["_recommendation_type"]))
        if serialized and serialized["url"] not in excluded_urls:
            items.append(serialized)
            excluded_urls.add(serialized["url"])
        if len(items) >= effective_limit:
            break

    return {**base, "enabled": True, "items": items}
