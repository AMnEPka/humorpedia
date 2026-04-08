"""Search, resolve-link, and duplicate routes."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone
import copy as copy_module
import uuid
import logging

from utils.database import get_db
from services.crud import (
    generate_unique_slug, convert_objectids_to_strings,
)
from services.tags import tag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["search"])


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
            'projection': {"name": 1, "title": 1, "slug": 1},
            'title_fn': lambda d: d.get("name") or d.get("title"),
            'url_fn': lambda d: f"/kvn/teams/{d.get('slug')}",
        },
        'show': {
            'collection': db.shows,
            'search_fields': ["name", "title", "slug"],
            'projection': {"name": 1, "title": 1, "slug": 1},
            'title_fn': lambda d: d.get("name") or d.get("title"),
            'url_fn': lambda d: f"/shows/{d.get('slug')}",
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
    query = {"$or": [{"_id": id_or_slug}, {"id": id_or_slug}, {"slug": id_or_slug}]}
    doc = await collection.find_one(query)

    if not doc:
        raise HTTPException(status_code=404, detail="Content not found")

    if content_type == 'kvn':
        full_path = doc.get('full_path') or doc.get('slug')
        url = f"/{full_path.lstrip('/')}" if full_path else f"{url_prefix}{doc.get('slug')}"
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
async def search_all(
    q: str = Query(..., min_length=2),
    types: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
):
    """Search across all content types."""
    db = await get_db()

    search_types = types.split(",") if types else ["person", "team", "show", "article", "news", "wiki", "section"]

    collection_map = {
        "person": ("people", ["title", "full_name"]),
        "team": ("teams", ["title", "name"]),
        "show": ("shows", ["title", "name"]),
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
        
        # Use MongoDB text search for published content
        query = {
            "$and": [
                {"status": "published"},
                {"$text": {"$search": q}}
            ]
        }
        
        cursor = collection.find(query, {"modules": 0}).limit(limit)
        items = await cursor.to_list(limit)
        if items:
            results[content_type] = items

    return results


@router.get("/search/autocomplete", response_model=list)
async def search_autocomplete(
    q: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=20)
):
    """Fast autocomplete search across all content."""
    db = await get_db()

    suggestions = []
    collections_config = [
        ("people", "full_name", "person"),
        ("teams", "name", "team"),
        ("shows", "name", "show"),
        ("articles", "title", "article"),
        ("news", "title", "news"),
        ("sections", "title", "section"),
    ]

    for coll_name, field, content_type in collections_config:
        collection = getattr(db, coll_name)
        
        # Use MongoDB text search for autocomplete
        query = {
            "status": "published",
            "$text": {"$search": q}
        }
        
        cursor = collection.find(query, {"_id": 1, field: 1, "slug": 1, "full_path": 1}).limit(limit)
        items = await cursor.to_list(limit)

        for item in items:
            suggestions.append({
                "id": item["_id"],
                "title": item.get(field, item.get("title", "")),
                "type": content_type,
                "slug": item.get("slug"),
                "path": item.get("full_path") if content_type == "section" else f"/{content_type}s/{item.get('slug', item['_id'])}"
            })

        if len(suggestions) >= limit:
            break

    return suggestions[:limit]


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
        query = {"status": "published", "tags": tag}
        count = await collection.count_documents(query)
        total_count += count
        if count > 0:
            cursor = collection.find(query, {"modules": 0}).sort("created_at", -1).limit(limit)
            items = await cursor.to_list(limit)
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
