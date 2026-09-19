"""Search, resolve-link, and duplicate routes."""
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from utils.auth import require_editor_on_write
from typing import Optional
from datetime import datetime, timezone

import copy as copy_module
import logging
import re
import uuid

from utils.database import get_db
from services.crud import (
    generate_unique_slug, convert_objectids_to_strings,
)
from services.tags import tag_service
from services.show_teams import attach_show_info, team_id_or_kvn_slug_query, team_url

logger = logging.getLogger(__name__)

# Rate limiter for search endpoints (общий экземпляр)
from utils.rate_limit import limiter


def _normalized_search_query(query: str) -> str:
    """Normalize user whitespace without changing the displayed spelling."""
    return " ".join(query.split())


def _partial_search_query(query: str, fields: list[str]) -> dict:
    """Build a literal, case-insensitive substring search for MongoDB."""
    escaped_query = re.escape(query)
    return {
        "$and": [
            {"status": {"$ne": "archived"}},
            {"$or": [
                {field: {"$regex": escaped_query, "$options": "i"}}
                for field in fields
            ]},
        ]
    }


def _relevance_key(document: dict, fields: list[str], query: str, type_order: int = 0) -> tuple:
    """Rank exact, title-prefix, word-prefix and substring matches in that order."""
    needle = _normalized_search_query(query).casefold()
    best = (4, 10**9, 10**9, len(fields), "")

    for field_order, field in enumerate(fields):
        value = _normalized_search_query(str(document.get(field) or ""))
        haystack = value.casefold()
        position = haystack.find(needle)
        if position < 0:
            continue

        if haystack == needle:
            match_kind = 0
        elif position == 0:
            match_kind = 1
        elif re.search(rf"(?<!\w){re.escape(needle)}", haystack):
            match_kind = 2
        else:
            match_kind = 3

        best = min(best, (match_kind, position, len(haystack), field_order, haystack))

    return (
        best[0], best[1], type_order, best[3], best[4], best[2],
        str(document.get("_id", "")),
    )


async def _find_ranked_matches(
    collection,
    fields: list[str],
    query: str,
    limit: int,
    projection: dict,
) -> list[dict]:
    """Fetch a bounded candidate set and return its most relevant matches."""
    candidate_limit = min(max(limit * 5, 100), 500)
    cursor = collection.find(_partial_search_query(query, fields), projection).limit(candidate_limit)
    items = await cursor.to_list(candidate_limit)
    return sorted(items, key=lambda item: _relevance_key(item, fields, query))[:limit]

router = APIRouter(prefix="/content", tags=["search"], dependencies=[Depends(require_editor_on_write)])


# ---------------------------------------------------------------------------
#  Content search (for link insertion in editor)
# ---------------------------------------------------------------------------

@router.get("/search-for-links")
async def search_content_for_links(
    query: str = Query(..., description="Поисковый запрос"),
    types: Optional[str] = Query(None, description="Типы контента через запятую: person,team,show,kvn"),
    limit: int = Query(10, ge=1, le=50)
):
    """Поиск контента для вставки ссылок (для админ-редактора)."""
    db = await get_db()

    types_list = [t.strip() for t in types.split(',')] if types else ['person', 'team', 'show', 'kvn']

    search_configs = {
        'person': {
            'collection': db.people,
            'search_fields': ["title", "full_name", "slug"],
            'projection': {"title": 1, "full_name": 1, "slug": 1},
            'title_fn': lambda d: d.get("full_name") or d.get("title"),
            'url_fn': lambda d: f"/people/{d.get('slug')}",
        },
        'team': {
            'collection': db.teams,
            'search_fields': ["name", "title", "slug"],
            'projection': {"name": 1, "title": 1, "slug": 1, "full_path": 1, "show_id": 1},
            'title_fn': lambda d: d.get("name") or d.get("title"),
            'url_fn': team_url,
        },
        'show': {
            'collection': db.shows,
            'search_fields': ["name", "title", "slug", "full_path"],
            'projection': {"name": 1, "title": 1, "slug": 1, "full_path": 1},
            'title_fn': lambda d: d.get("name") or d.get("title"),
            'url_fn': lambda d: f"/shows/{d.get('full_path') or d.get('slug')}",
        },
        'kvn': {
            'collection': db.kvn,
            'search_fields': ["name", "title", "slug", "full_path"],
            'projection': {"name": 1, "title": 1, "slug": 1, "full_path": 1},
            'title_fn': lambda d: d.get("name") or d.get("title"),
            'url_fn': lambda d: (
                f"/{(d.get('full_path') or d.get('slug', '')).lstrip('/')}"
                if d.get('full_path') else f"/kvn/{d.get('slug')}"
            ),
        },
    }

    results = []
    for content_type in types_list:
        cfg = search_configs.get(content_type)
        if not cfg:
            continue
        
        # Use MongoDB text search instead of regex for better performance
        mongo_query = {
            "$text": {"$search": query}
        }
        
        async for doc in cfg['collection'].find(mongo_query, cfg['projection']).limit(limit):
            results.append({
                "type": content_type,
                "id": str(doc["_id"]),
                "slug": doc.get("slug"),
                "title": cfg['title_fn'](doc),
                "url": cfg['url_fn'](doc),
            })

    return {"results": results[:limit]}


@router.get("/{content_type}/{id_or_slug}/resolve-link")
async def resolve_content_link(content_type: str, id_or_slug: str):
    """Получить актуальный URL для контента."""
    db = await get_db()

    collection_map = {
        'person': (db.people, '/people/'),
        'team': (db.teams, '/kvn/teams/'),
        'show': (db.shows, '/shows/'),
        'kvn': (db.kvn, '/kvn/'),
    }

    if content_type not in collection_map:
        raise HTTPException(status_code=404, detail="Unknown content type")

    collection, url_prefix = collection_map[content_type]
    if content_type == 'team':
        query = team_id_or_kvn_slug_query(id_or_slug)
    else:
        query = {"$or": [{"_id": id_or_slug}, {"id": id_or_slug}, {"slug": id_or_slug}]}
    doc = await collection.find_one(query)

    if not doc:
        raise HTTPException(status_code=404, detail="Content not found")

    if content_type == 'kvn':
        full_path = doc.get('full_path') or doc.get('slug')
        url = f"/{full_path.lstrip('/')}" if full_path else f"{url_prefix}{doc.get('slug')}"
    elif content_type == 'show':
        url = f"{url_prefix}{doc.get('full_path') or doc.get('slug')}"
    elif content_type == 'team':
        url = team_url(doc)
    else:
        url = f"{url_prefix}{doc.get('slug')}"

    return {
        "id": str(doc["_id"]),
        "slug": doc.get("slug"),
        "title": doc.get("title") or doc.get("name") or doc.get("full_name"),
        "url": url
    }


# ---------------------------------------------------------------------------
#  Universal search (public)
# ---------------------------------------------------------------------------

@router.get("/search", response_model=dict)
@limiter.limit("60/minute")  # 60 requests per minute for public search
async def search_all(
    request: Request,
    q: str = Query(..., min_length=2),
    types: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
):
    """Search across all content types by a literal fragment of two or more characters."""
    db = await get_db()
    query_text = _normalized_search_query(q)
    if len(query_text) < 2:
        raise HTTPException(status_code=422, detail="Поисковый запрос должен содержать минимум 2 символа")

    search_types = [item.strip() for item in types.split(",")] if types else ["person", "team", "show", "article", "news", "wiki", "section"]

    collection_map = {
        "person": ("people", ["full_name", "title"]),
        "team": ("teams", ["name", "title"]),
        "show": ("shows", ["name", "title"]),
        "article": ("articles", ["title"]),
        "news": ("news", ["title"]),
        "wiki": ("wiki", ["title"]),
        "section": ("sections", ["title", "description"]),
    }

    results = {}
    for content_type in search_types:
        if content_type not in collection_map:
            continue
        coll_name, fields = collection_map[content_type]
        collection = getattr(db, coll_name)

        # Draft pages are valid public results; only archived content is hidden.
        items = await _find_ranked_matches(
            collection, fields, query_text, limit, {"modules": 0}
        )
        if content_type == "team":
            await attach_show_info(db, items)
        if items:
            results[content_type] = items

    return results


@router.get("/search/autocomplete", response_model=list)
@limiter.limit("120/minute")  # Higher limit for autocomplete (fast typing)
async def search_autocomplete(
    request: Request,
    q: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=20)
):
    """Autocomplete by a literal fragment, globally ordered by relevance."""
    db = await get_db()
    query_text = _normalized_search_query(q)
    if len(query_text) < 2:
        raise HTTPException(status_code=422, detail="Поисковый запрос должен содержать минимум 2 символа")

    suggestions = []
    collections_config = [
        ("people", ["full_name", "title"], "person"),
        ("teams", ["name", "title"], "team"),
        ("shows", ["name", "title"], "show"),
        ("articles", ["title"], "article"),
        ("news", ["title"], "news"),
        ("sections", ["title"], "section"),
    ]

    for type_order, (coll_name, fields, content_type) in enumerate(collections_config):
        collection = getattr(db, coll_name)

        projection = {
            "_id": 1, "slug": 1, "full_path": 1, "show_id": 1,
            **{field: 1 for field in fields},
        }
        items = await _find_ranked_matches(collection, fields, query_text, limit, projection)

        if content_type == "team":
            await attach_show_info(db, items)
        for item in items:
            if content_type == "section":
                path = item.get("full_path")
            elif content_type == "team":
                path = item["url"]
            elif content_type == "person":
                path = f"/people/{item.get('slug', item['_id'])}"
            elif content_type == "show":
                path = f"/shows/{item.get('full_path') or item.get('slug', item['_id'])}"
            else:
                path = f"/{content_type}s/{item.get('slug', item['_id'])}"
            suggestions.append({
                "id": str(item["_id"]),
                "title": next((item.get(field) for field in fields if item.get(field)), ""),
                "type": content_type,
                "slug": item.get("slug"),
                "path": path,
                "_relevance": _relevance_key(item, fields, query_text, type_order),
                **({"show": item["show"]} if item.get("show") else {}),
            })

    suggestions.sort(key=lambda item: item["_relevance"])
    result = suggestions[:limit]
    for item in result:
        item.pop("_relevance")
    return result


@router.get("/search/by-tag/{tag}", response_model=dict)
async def search_by_tag(
    tag: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """Search all content by tag."""
    db = await get_db()

    results = {}
    total_count = 0

    collection_map = {
        "people": "person",
        "teams": "team",
        "shows": "show",
        "articles": "article",
        "news": "news",
        "wiki": "wiki",
        "quizzes": "quiz",
        "sections": "section",
    }

    for coll_name, content_type in collection_map.items():
        collection = getattr(db, coll_name)
        query = {"status": {"$ne": "archived"}, "tags": tag}
        count = await collection.count_documents(query)
        total_count += count
        if count > 0:
            cursor = collection.find(query, {"modules": 0}).sort("created_at", -1).limit(limit)
            items = await cursor.to_list(limit)
            if content_type == "team":
                await attach_show_info(db, items)
            results[content_type] = {"count": count, "items": items}

    return {"tag": tag, "total": total_count, "results": results, "skip": skip, "limit": limit}


# ---------------------------------------------------------------------------
#  Duplicate content
# ---------------------------------------------------------------------------

COLLECTION_MAP = {
    "person": "people", "people": "people",
    "team": "teams", "teams": "teams",
    "show": "shows", "shows": "shows",
    "article": "articles", "articles": "articles",
    "news": "news",
    "quiz": "quizzes", "quizzes": "quizzes",
    "wiki": "wiki",
    "kvn": "kvn",
    "section": "sections", "sections": "sections"
}


@router.post("/{content_type}/{id}/duplicate", response_model=dict)
async def duplicate_content(content_type: str, id: str):
    """Create a copy of a content page."""
    try:
        db = await get_db()

        collection_name = COLLECTION_MAP.get(content_type)
        if not collection_name:
            raise HTTPException(status_code=400, detail=f"Unknown content type: {content_type}")

        collection = getattr(db, collection_name)

        # Find original content
        if content_type == "kvn":
            original = await collection.find_one({"id": id})
            if not original:
                original = await collection.find_one({"_id": id})
        else:
            original = await collection.find_one({"_id": id})

        if not original:
            raise HTTPException(status_code=404, detail="Content not found")

        # Deep copy
        copy_data = copy_module.deepcopy(dict(original))
        copy_data.pop("_id", None)
        copy_data.pop("created_at", None)
        copy_data.pop("updated_at", None)
        copy_data.pop("views", None)
        copy_data = convert_objectids_to_strings(copy_data)

        # Generate unique slug
        base_slug = copy_data.get("slug", "")
        if not base_slug:
            raise HTTPException(status_code=400, detail="Original content has no slug")

        parent_path_for_slug = None
        if content_type in ["kvn", "section", "sections"]:
            parent_id = copy_data.get("parent_id")
            if parent_id:
                if content_type == "kvn":
                    parent_doc = await db.kvn.find_one({"id": parent_id})
                    if not parent_doc:
                        parent_doc = await db.kvn.find_one({"_id": parent_id})
                else:
                    parent_doc = await db.sections.find_one({"_id": parent_id})
                if parent_doc:
                    parent_path_for_slug = parent_doc.get("full_path", parent_doc.get("slug", ""))

        new_slug = await generate_unique_slug(collection_name, base_slug, parent_path_for_slug)
        copy_data["slug"] = new_slug

        now = datetime.now(timezone.utc).isoformat()
        copy_data["created_at"] = now
        copy_data["updated_at"] = now
        copy_data["views"] = 0

        # KVN-specific: new UUID id + clear children
        if content_type == "kvn":
            copy_data["id"] = str(uuid.uuid4())
            copy_data["child_kvn_ids"] = []

        result = await collection.insert_one(copy_data)

        # Update full_path for sections
        if content_type in ["section", "sections"]:
            from routes.sections import build_full_path
            parent_id = copy_data.get("parent_id")
            new_full_path, new_level = await build_full_path(parent_id, new_slug, db)
            await collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {"full_path": new_full_path, "level": new_level}}
            )

        # Update full_path for KVN
        if content_type == "kvn":
            parent_id = copy_data.get("parent_id")
            level = 0
            full_path = new_slug

            if parent_id:
                parent = await db.kvn.find_one({"id": parent_id})
                if not parent:
                    parent = await db.kvn.find_one({"_id": parent_id})
                if parent:
                    parent_level = parent.get("level", 0)
                    if parent_level >= 4:
                        level = 0
                        full_path = new_slug
                    else:
                        level = parent_level + 1
                        parent_path = parent.get("full_path", parent.get("slug", ""))
                        full_path = f"{parent_path}/{new_slug}"

            await collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {"full_path": full_path, "level": level}}
            )

            if parent_id:
                new_id = copy_data.get("id")
                if new_id:
                    parent_doc = await db.kvn.find_one({"id": parent_id})
                    if not parent_doc:
                        parent_doc = await db.kvn.find_one({"_id": parent_id})
                    if parent_doc:
                        await db.kvn.update_one(
                            {"_id": parent_doc["_id"]},
                            {"$addToSet": {"child_kvn_ids": new_id}}
                        )

        if "tags" in copy_data and copy_data["tags"]:
            await tag_service.sync_tags(copy_data["tags"])

        inserted_id_str = str(result.inserted_id)

        if content_type == "kvn":
            return {
                "id": copy_data.get("id") or inserted_id_str,
                "_id": inserted_id_str,
                "slug": new_slug,
                "message": "Content duplicated successfully"
            }
        return {"id": inserted_id_str, "slug": new_slug, "message": "Content duplicated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating {content_type} {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error duplicating content: {str(e)}")
