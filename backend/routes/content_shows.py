"""Шоу: CRUD, иерархия и выдача по пути.

Шоу может быть дочерней страницей другого шоу (сезон, подпроект, раздел): `parent_id` = `_id` родителя,
`full_path` = путь родителя + "/" + slug, публичный адрес — `/shows/{full_path}`. slug уникален только
среди соседей (у разных шоу бывает «season1»), уникален `full_path`.
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from utils.auth import get_current_user, require_editor_on_write
from typing import Optional, Literal
from datetime import datetime, timezone
import logging

from models.base import ContentStatus
from models.content import ShowCreate, ShowUpdate
from utils.database import get_db
from services import content_commands
from services.content_commands import _full_path, _get_parent, _check_path_free
from services.crud import delete_content, get_by_id_or_slug, list_alphabetical_content, build_query
from services.tags import tag_service
from services.link_resolver import LinkResolver
from services.show_teams import move_show_teams
from services.show_appearances import link_participant_cards
from services.foreign_agent_notices import decorate_document
from services.content_visibility import editor_can_view_archived, require_visible, visible_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["shows"], dependencies=[Depends(require_editor_on_write)])

ROOT_QUERY = {"$or": [{"parent_id": None}, {"parent_id": ""}, {"parent_id": {"$exists": False}}]}
PUBLIC_STATUS = {"status": {"$ne": "archived"}}
LINK_FIELDS = ("modules", "facts", "description")


async def _move_descendants(db, show_id: str, full_path: str, level: int) -> None:
    """Пересчитать full_path и level у всех потомков (и адреса команд шоу) после смены slug или родителя."""
    await move_show_teams(db, show_id, full_path)
    async for child in db.shows.find({"parent_id": show_id}, {"slug": 1}):
        child_path = f"{full_path}/{child['slug']}"
        await db.shows.update_one({"_id": child["_id"]}, {"$set": {"full_path": child_path, "level": level + 1}})
        await _move_descendants(db, child["_id"], child_path, level + 1)


async def _add_hierarchy(db, show: dict, include_archived: bool = False) -> dict:
    """Дочерние неархивные страницы (по order) и хлебные крошки для публичной страницы."""
    child_query = {"parent_id": show["_id"]}
    if not include_archived:
        child_query.update(PUBLIC_STATUS)
    children = await db.shows.find(
        child_query,
        {"title": 1, "name": 1, "slug": 1, "full_path": 1, "poster": 1, "order": 1, "description": 1},
    ).sort([("order", 1), ("title", 1)]).to_list(500)
    show["children"] = children
    crumbs = []
    parent_id = show.get("parent_id")
    while parent_id and len(crumbs) < 10:
        parent_query = {"_id": parent_id}
        if not include_archived:
            parent_query.update(PUBLIC_STATUS)
        parent = await db.shows.find_one(parent_query, {"title": 1, "full_path": 1, "slug": 1, "parent_id": 1})
        if not parent:
            break
        crumbs.insert(0, {"title": parent.get("title"), "path": "/shows/" + (parent.get("full_path") or parent["slug"])})
        parent_id = parent.get("parent_id")
    show["breadcrumbs"] = crumbs
    return show


@router.post("/shows", response_model=dict)
async def create_show(data: ShowCreate):
    return await create_show_record(data)


async def create_show_record(data: ShowCreate, *, document_id=None, page_package_id=None):
    """Совместимая обёртка над доменной операцией создания."""
    return await content_commands.create_show_record(await get_db(), data, document_id=document_id, page_package_id=page_package_id)


@router.get("/shows", response_model=dict)
async def list_shows(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    letter: Optional[str] = None,
    include_children: bool = Query(False, description="Include child shows"),
    sort: Optional[Literal["popular"]] = None,
    request: Request = None,
):
    """List shows with pagination (excludes child shows by default)."""
    editor = await editor_can_view_archived(request, get_current_user)
    if not editor and status == ContentStatus.ARCHIVED:
        raise HTTPException(status_code=404, detail="Shows not found")
    query = visible_query(build_query(status, tag, search, ["title", "name", "aliases"], letter), editor)
    availability_query = build_query(status, tag)
    availability_query = visible_query(availability_query, editor)
    if not include_children:
        query = {"$and": [query, ROOT_QUERY]} if query else ROOT_QUERY
        availability_query = (
            {"$and": [availability_query, ROOT_QUERY]}
            if availability_query else ROOT_QUERY
        )
    return await list_alphabetical_content(
        "shows", skip, limit, query, ["title", "name"],
        availability_query=availability_query,
        sort=sort,
    )


@router.get("/shows/by-path/{path:path}", response_model=dict)
async def get_show_by_path(path: str, request: Request = None):
    """Шоу по полному пути (например, comedy-battle/season1) — с дочерними страницами и хлебными крошками."""
    db = await get_db()
    path = path.strip("/")
    editor = await editor_can_view_archived(request, get_current_user)
    show = await db.shows.find_one(visible_query({"full_path": path}, editor))
    if not show and "/" not in path:
        show = await db.shows.find_one(visible_query({"$and": [{"slug": path}, ROOT_QUERY]}, editor))
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    require_visible(show, editor, "Show not found")
    await _add_hierarchy(db, show, include_archived=editor)
    await link_participant_cards(db, show)
    await LinkResolver.resolve_document(show, LINK_FIELDS)
    return await decorate_document(show)


@router.get("/shows/{parent_slug}/children", response_model=dict)
async def get_show_children(parent_slug: str, request: Request = None):
    """Get children of a show (по slug корневого шоу или _id)."""
    db = await get_db()
    editor = await editor_can_view_archived(request, get_current_user)
    parent = await db.shows.find_one(visible_query({"$or": [{"_id": parent_slug}, {"full_path": parent_slug}]}, editor))
    if not parent:
        raise HTTPException(status_code=404, detail="Parent show not found")
    require_visible(parent, editor, "Parent show not found")
    children = await db.shows.find(visible_query({"parent_id": parent["_id"]}, editor)).sort([("order", 1), ("title", 1)]).to_list(500)
    return {"items": children, "total": len(children), "parent": parent.get("title")}


@router.get("/shows/{id_or_slug}", response_model=dict)
async def get_show(id_or_slug: str, raw: bool = Query(False, description="без обработки ссылок (для админки)"), request: Request = None):
    """Get show by ID or slug."""
    editor = await editor_can_view_archived(request, get_current_user)
    show = require_visible(await get_by_id_or_slug("shows", id_or_slug, "Show not found", editor=editor), editor, "Show not found")
    if not raw:
        await link_participant_cards(await get_db(), show)
        await LinkResolver.resolve_document(show, LINK_FIELDS)
        await decorate_document(show)
    return show


@router.get("/shows-hierarchy", response_model=dict)
async def get_shows_hierarchy(status: Optional[ContentStatus] = None, request: Request = None):
    """Get all shows with hierarchy for admin panel."""
    db = await get_db()
    editor = await editor_can_view_archived(request, get_current_user)
    if not editor and status == ContentStatus.ARCHIVED:
        raise HTTPException(status_code=404, detail="Shows not found")
    query = visible_query({"status": status.value} if status else {}, editor)
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
