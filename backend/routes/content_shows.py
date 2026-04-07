"""Show routes — CRUD + hierarchy + path."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone
import logging

from models.base import ContentStatus
from models.content import Show, ShowCreate, ShowUpdate, ShowFacts
from utils.database import get_db
from services.crud import (
    check_slug_unique, create_content, delete_content,
    get_by_id_or_slug, list_content, build_query,
)
from services.tags import tag_service
from services.linking import linking_service
from services.link_resolver import LinkResolver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["shows"])


@router.post("/shows", response_model=dict)
async def create_show(data: ShowCreate):
    """Create a new show."""
    await check_slug_unique("shows", data.slug)

    facts_data = data.facts
    if facts_data is None:
        facts_data = ShowFacts()
    elif isinstance(facts_data, dict):
        try:
            facts_data = ShowFacts(**facts_data)
        except Exception:
            facts_data = ShowFacts()

    show = Show(
        title=data.title, slug=data.slug, name=data.name, poster=data.poster,
        facts=facts_data, description=data.description,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status,
        related_person_ids=data.related_person_ids or []
    )
    result = await create_content("shows", show, data.tags)

    if data.related_person_ids:
        await linking_service.update_person_links("show", result["id"], data.related_person_ids)

    return result


@router.get("/shows", response_model=dict)
async def list_shows(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    include_children: bool = Query(False, description="Include child shows")
):
    """List shows with pagination (excludes child shows by default)."""
    query = build_query(status, tag, search, ["title", "name"])
    if not include_children:
        query["$or"] = [{"level": 0}, {"level": {"$exists": False}}]
    return await list_content("shows", skip, limit, query, "name", 1)


@router.get("/shows/by-path/{path:path}", response_model=dict)
async def get_show_by_path(path: str):
    """Get show by full path (e.g., comedy-battle/season1)."""
    db = await get_db()
    show = await db.shows.find_one({"full_path": path}, {"_id": 0})
    if not show:
        show = await db.shows.find_one({"slug": path}, {"_id": 0})
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    return show


@router.get("/shows/{parent_slug}/children", response_model=dict)
async def get_show_children(parent_slug: str):
    """Get children of a show."""
    db = await get_db()
    parent = await db.shows.find_one({"slug": parent_slug})
    if not parent:
        raise HTTPException(status_code=404, detail="Parent show not found")

    parent_id = parent.get("id")
    children = await db.shows.find(
        {"parent_id": parent_id}, {"_id": 0}
    ).sort("title", 1).to_list(100)

    return {"items": children, "total": len(children), "parent": parent.get("title")}


@router.get("/shows/{id_or_slug}", response_model=dict)
async def get_show(id_or_slug: str):
    """Get show by ID or slug."""
    show = await get_by_id_or_slug("shows", id_or_slug, "Show not found")
    if show.get('modules'):
        show['modules'] = await LinkResolver.resolve_links_in_modules(show['modules'])
    return show


@router.get("/shows-hierarchy", response_model=dict)
async def get_shows_hierarchy(status: Optional[ContentStatus] = None):
    """Get all shows with hierarchy for admin panel."""
    db = await get_db()
    query = {}
    if status:
        query["status"] = status.value
    all_shows = await db.shows.find(query, {"_id": 0}).sort([("level", 1), ("title", 1)]).to_list(1000)

    shows_by_id = {s.get('id'): s for s in all_shows}
    root_shows = []
    for show in all_shows:
        show['children'] = []
        parent_id = show.get('parent_id')
        if not parent_id:
            root_shows.append(show)
        else:
            parent = shows_by_id.get(parent_id)
            if parent:
                if 'children' not in parent:
                    parent['children'] = []
                parent['children'].append(show)
    return {"items": root_shows, "total": len(all_shows)}


@router.put("/shows/{id}", response_model=dict)
async def update_show(id: str, data: ShowUpdate):
    """Update show."""
    try:
        logger.info(f"Update show {id}, received data: {data.model_dump(exclude_unset=True)}")
    except Exception as e:
        logger.error(f"Error logging data: {e}")

    db = await get_db()
    update_data = {}

    if data.title is not None:
        update_data["title"] = data.title
    if data.slug is not None:
        update_data["slug"] = data.slug
    if data.name is not None:
        update_data["name"] = data.name
    if data.poster is not None:
        if isinstance(data.poster, dict) and not data.poster.get('url'):
            update_data["poster"] = None
        else:
            update_data["poster"] = data.poster.model_dump() if hasattr(data.poster, 'model_dump') else data.poster
    if data.facts is not None:
        try:
            if isinstance(data.facts, dict):
                facts_obj = ShowFacts(**data.facts)
                update_data["facts"] = facts_obj.model_dump()
            else:
                update_data["facts"] = data.facts.model_dump() if hasattr(data.facts, 'model_dump') else data.facts
        except Exception:
            update_data["facts"] = data.facts if isinstance(data.facts, dict) else {}
    if data.description is not None:
        update_data["description"] = data.description
    if data.parent_id is not None:
        update_data["parent_id"] = data.parent_id
    if data.modules is not None:
        try:
            update_data["modules"] = [
                m.model_dump() if hasattr(m, 'model_dump') else (m if isinstance(m, dict) else {})
                for m in data.modules
            ]
        except Exception as e:
            logger.error(f"Error processing modules: {e}")
            update_data["modules"] = data.modules if isinstance(data.modules, list) else []
    if data.tags is not None:
        update_data["tags"] = data.tags
        await tag_service.sync_tags(data.tags)
    if data.seo is not None:
        update_data["seo"] = data.seo.model_dump() if hasattr(data.seo, 'model_dump') else data.seo
    if data.status is not None:
        update_data["status"] = data.status.value if hasattr(data.status, 'value') else data.status
    if data.participant_ids is not None:
        update_data["participant_ids"] = data.participant_ids
    if data.team_ids is not None:
        update_data["team_ids"] = data.team_ids
    if data.related_person_ids is not None:
        update_data["related_person_ids"] = data.related_person_ids

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        result = await db.shows.update_one({"_id": id}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Show not found")
        if data.related_person_ids is not None:
            try:
                await linking_service.update_person_links("show", id, data.related_person_ids)
            except Exception as e:
                logger.error(f"Error updating person links: {e}")
        return {"id": id, "updated": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating show {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating show: {str(e)}")


@router.delete("/shows/{id}")
async def delete_show(id: str):
    """Delete show."""
    return await delete_content("shows", id, "Show not found")
