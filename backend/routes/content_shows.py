"""Шоу: CRUD, иерархия и выдача по пути.

Шоу может быть дочерней страницей другого шоу (сезон, подпроект, раздел): `parent_id` = `_id` родителя,
`full_path` = путь родителя + "/" + slug, публичный адрес — `/shows/{full_path}`. slug уникален только
среди соседей (у разных шоу бывает «season1»), уникален `full_path`.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from utils.auth import require_editor_on_write
from typing import Optional
from datetime import datetime, timezone
import logging

from models.base import ContentStatus
from models.content import Show, ShowCreate, ShowUpdate
from utils.database import get_db
from services.crud import create_content, delete_content, get_by_id_or_slug, list_alphabetical_content, build_query
from services.tags import tag_service
from services.linking import linking_service
from services.link_resolver import LinkResolver
from services.show_teams import move_show_teams
from services.show_appearances import link_participant_cards
from services.foreign_agent_notices import decorate_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["shows"], dependencies=[Depends(require_editor_on_write)])

ROOT_QUERY = {"$or": [{"parent_id": None}, {"parent_id": ""}, {"parent_id": {"$exists": False}}]}
PUBLIC_STATUS = {"status": {"$ne": "archived"}}
LINK_FIELDS = ("modules", "facts", "description")


def _full_path(parent: Optional[dict], slug: str) -> str:
    return f"{parent['full_path'].strip('/')}/{slug}" if parent else slug


async def _get_parent(db, parent_id: Optional[str]) -> Optional[dict]:
    if not parent_id:
        return None
    parent = await db.shows.find_one({"_id": parent_id})
    if not parent:
        raise HTTPException(status_code=400, detail="Родительское шоу не найдено")
    if not parent.get("full_path"):
        raise HTTPException(status_code=400, detail="У родительского шоу не задан путь (full_path)")
    return parent


async def _check_path_free(db, full_path: str, exclude_id: Optional[str] = None) -> None:
    query = {"full_path": full_path}
    if exclude_id:
        query["_id"] = {"$ne": exclude_id}
    if await db.shows.find_one(query, {"_id": 1}) or await db.teams.find_one({"full_path": full_path}, {"_id": 1}):
        raise HTTPException(status_code=400, detail=f"Адрес /shows/{full_path} уже занят")


async def _move_descendants(db, show_id: str, full_path: str, level: int) -> None:
    """Пересчитать full_path и level у всех потомков (и адреса команд шоу) после смены slug или родителя."""
    await move_show_teams(db, show_id, full_path)
    async for child in db.shows.find({"parent_id": show_id}, {"slug": 1}):
        child_path = f"{full_path}/{child['slug']}"
        await db.shows.update_one({"_id": child["_id"]}, {"$set": {"full_path": child_path, "level": level + 1}})
        await _move_descendants(db, child["_id"], child_path, level + 1)


async def _add_hierarchy(db, show: dict) -> dict:
    """Дочерние неархивные страницы (по order) и хлебные крошки для публичной страницы."""
    children = await db.shows.find(
        {"parent_id": show["_id"], **PUBLIC_STATUS},
        {"title": 1, "name": 1, "slug": 1, "full_path": 1, "poster": 1, "order": 1, "description": 1},
    ).sort([("order", 1), ("title", 1)]).to_list(500)
    show["children"] = children
    crumbs = []
    parent_id = show.get("parent_id")
    while parent_id and len(crumbs) < 10:
        parent = await db.shows.find_one({"_id": parent_id}, {"title": 1, "full_path": 1, "slug": 1, "parent_id": 1})
        if not parent:
            break
        crumbs.insert(0, {"title": parent.get("title"), "path": "/shows/" + (parent.get("full_path") or parent["slug"])})
        parent_id = parent.get("parent_id")
    show["breadcrumbs"] = crumbs
    return show


@router.post("/shows", response_model=dict)
async def create_show(data: ShowCreate):
    """Create a new show."""
    db = await get_db()
    parent = await _get_parent(db, data.parent_id)
    full_path = _full_path(parent, data.slug)
    await _check_path_free(db, full_path)

    facts = data.facts or {}
    show = Show(
        title=data.title, slug=data.slug, name=data.name, poster=data.poster,
        facts=facts, facts_order=data.facts_order or list(facts), social_links=data.social_links or {},
        description=data.description,
        parent_id=parent["_id"] if parent else None, full_path=full_path,
        level=(parent.get("level", 0) + 1) if parent else 0, order=data.order or 0,
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
    letter: Optional[str] = None,
    include_children: bool = Query(False, description="Include child shows")
):
    """List shows with pagination (excludes child shows by default)."""
    query = build_query(status, tag, search, ["title", "name"], letter)
    if not include_children:
        query = {"$and": [query, ROOT_QUERY]} if query else ROOT_QUERY
    return await list_alphabetical_content(
        "shows", skip, limit, query, ["title", "name"]
    )


@router.get("/shows/by-path/{path:path}", response_model=dict)
async def get_show_by_path(path: str):
    """Шоу по полному пути (например, comedy-battle/season1) — с дочерними страницами и хлебными крошками."""
    db = await get_db()
    path = path.strip("/")
    show = await db.shows.find_one({"full_path": path})
    if not show and "/" not in path:
        show = await db.shows.find_one({"slug": path, **ROOT_QUERY})
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    await _add_hierarchy(db, show)
    await link_participant_cards(db, show)
    await LinkResolver.resolve_document(show, LINK_FIELDS)
    return await decorate_document(show)


@router.get("/shows/{parent_slug}/children", response_model=dict)
async def get_show_children(parent_slug: str):
    """Get children of a show (по slug корневого шоу или _id)."""
    db = await get_db()
    parent = await db.shows.find_one({"$or": [{"_id": parent_slug}, {"full_path": parent_slug}]})
    if not parent:
        raise HTTPException(status_code=404, detail="Parent show not found")
    children = await db.shows.find({"parent_id": parent["_id"]}).sort([("order", 1), ("title", 1)]).to_list(500)
    return {"items": children, "total": len(children), "parent": parent.get("title")}


@router.get("/shows/{id_or_slug}", response_model=dict)
async def get_show(id_or_slug: str, raw: bool = Query(False, description="без обработки ссылок (для админки)")):
    """Get show by ID or slug."""
    show = await get_by_id_or_slug("shows", id_or_slug, "Show not found")
    if not raw:
        await link_participant_cards(await get_db(), show)
        await LinkResolver.resolve_document(show, LINK_FIELDS)
        await decorate_document(show)
    return show


@router.get("/shows-hierarchy", response_model=dict)
async def get_shows_hierarchy(status: Optional[ContentStatus] = None):
    """Get all shows with hierarchy for admin panel."""
    db = await get_db()
    query = {"status": status.value} if status else {}
    all_shows = await db.shows.find(query, {"modules": 0}).sort([("level", 1), ("order", 1), ("title", 1)]).to_list(5000)

    by_id = {s["_id"]: s for s in all_shows}
    roots = []
    for show in all_shows:
        show.setdefault("children", [])
        parent = by_id.get(show.get("parent_id"))
        if parent is not None:
            parent.setdefault("children", []).append(show)
        else:
            roots.append(show)
    return {"items": roots, "total": len(all_shows)}


@router.put("/shows/{id}", response_model=dict)
async def update_show(id: str, data: ShowUpdate):
    """Update show."""
    db = await get_db()
    current = await db.shows.find_one({"_id": id})
    if not current:
        raise HTTPException(status_code=404, detail="Show not found")

    incoming = data.model_dump(exclude_unset=True, mode="json")
    update_data = {
        key: value for key, value in incoming.items()
        if value is not None and key not in ("slug", "parent_id", "poster")
    }
    if "poster" in incoming:
        poster = incoming["poster"]
        update_data["poster"] = poster if poster and poster.get("url") else None
    if "facts" in update_data and "facts_order" not in update_data:
        keys = list(update_data["facts"])
        kept = [k for k in current.get("facts_order") or [] if k in keys]
        update_data["facts_order"] = kept + [k for k in keys if k not in kept]

    # slug / родитель → новый full_path (и у всех потомков)
    new_slug = incoming.get("slug") or current["slug"]
    new_parent_id = current.get("parent_id")
    if "parent_id" in incoming:
        new_parent_id = incoming["parent_id"] or None
    if new_slug != current["slug"] or new_parent_id != current.get("parent_id") or not current.get("full_path"):
        parent = await _get_parent(db, new_parent_id)
        if parent and (parent["_id"] == id or (current.get("full_path")
                                                and parent["full_path"].startswith(current["full_path"] + "/"))):
            raise HTTPException(status_code=400, detail="Шоу нельзя вложить в само себя или в своего потомка")
        full_path = _full_path(parent, new_slug)
        await _check_path_free(db, full_path, exclude_id=id)
        level = (parent.get("level", 0) + 1) if parent else 0
        update_data.update({"slug": new_slug, "parent_id": parent["_id"] if parent else None,
                            "full_path": full_path, "level": level})
        await _move_descendants(db, id, full_path, level)

    if "tags" in update_data:
        await tag_service.sync_tags(update_data["tags"])
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.shows.update_one({"_id": id}, {"$set": update_data})

    if data.related_person_ids is not None:
        try:
            await linking_service.update_person_links("show", id, data.related_person_ids)
        except Exception as e:
            logger.error(f"Error updating person links: {e}")
    return {"id": id, "updated": True}


@router.delete("/shows/{id}")
async def delete_show(id: str):
    """Delete show (только без дочерних страниц)."""
    db = await get_db()
    if await db.shows.find_one({"parent_id": id}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="У шоу есть дочерние страницы — сначала удалите или перенесите их")
    if await db.teams.find_one({"show_id": id}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="У шоу есть команды — сначала удалите их или перенесите в другое шоу")
    return await delete_content("shows", id, "Show not found")
