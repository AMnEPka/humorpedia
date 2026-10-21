"""Person routes — CRUD + search + linked content."""
from fastapi import APIRouter, HTTPException, Query, Depends, Request
import re
from utils.auth import EDITOR_ROLES, get_current_user, require_editor_on_write
from typing import Optional, Literal

from models.base import ContentStatus
from models.content import PersonCreate, PersonUpdate
from utils.database import get_db
from services import content_commands
from services.content_commands import _without_legacy_marker
from utils.search import literal_search_pattern
from services.crud import (
    update_content,
    delete_content, get_by_id_or_slug, list_alphabetical_content, build_query,
)
from services.link_resolver import LinkResolver
from services.foreign_agent_notices import decorate_document
from services.memberships import unlink_person
from services.catalog_filters import combine_query, person_conditions, people_filter_options

router = APIRouter(prefix="/content", tags=["people"], dependencies=[Depends(require_editor_on_write)])


@router.post("/people", response_model=dict)
async def create_person(data: PersonCreate):
    return await create_person_record(data)


async def create_person_record(data: PersonCreate, *, document_id=None, defer_links=False, page_package_id=None):
    """Совместимая обёртка над доменной операцией создания."""
    return await content_commands.create_person_record(await get_db(), data, document_id=document_id, defer_links=defer_links, page_package_id=page_package_id)


@router.get("/people", response_model=dict)
async def list_people(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    letter: Optional[str] = None,
    city: Optional[str] = Query(None, max_length=100),
    role: Optional[str] = Query(None, max_length=100),
    team: Optional[str] = Query(None, max_length=100),
    show: Optional[str] = Query(None, max_length=100),
    sort: Optional[Literal["popular"]] = None,
):
    """List people with pagination and filters."""
    db = await get_db()
    user = await get_current_user(request)
    editor = bool(user and user.get("role") in EDITOR_ROLES)
    if not editor and status == ContentStatus.ARCHIVED:
        raise HTTPException(status_code=404, detail="People not found")
    visible = {} if editor else {"status": {"$ne": ContentStatus.ARCHIVED.value}}
    conditions = await person_conditions(db, city=city, role=role, team=team, show=show)
    query = combine_query(
        build_query(status, tag, search, ["title", "full_name", "aliases"], letter),
        visible, *conditions,
    )
    availability_query = combine_query(build_query(status, tag), visible, *conditions)
    result = await list_alphabetical_content(
        "people", skip, limit, query, ["title", "full_name"],
        availability_query=availability_query,
        sort=sort,
    )
    result["filters"] = await people_filter_options(db, combine_query(build_query(status, tag), visible))
    return result


@router.get("/people/search", response_model=list)
async def search_people(request: Request, q: str = Query(..., min_length=2), limit: int = Query(10, ge=1, le=50)):
    """Search people by name for editor assistance."""
    db = await get_db()
    search_pattern = literal_search_pattern(q)
    query = {
        "$or": [
            {"full_name": {"$regex": search_pattern, "$options": "i"}},
            {"title": {"$regex": search_pattern, "$options": "i"}},
            {"aliases": {"$regex": search_pattern, "$options": "i"}}
        ]
    }
    user = await get_current_user(request)
    if not user or user.get("role") not in EDITOR_ROLES:
        query = {"$and": [query, {"status": {"$ne": ContentStatus.ARCHIVED.value}}]}
    cursor = db.people.find(query, {"_id": 1, "full_name": 1, "title": 1, "slug": 1}).limit(limit)
    people = await cursor.to_list(limit)
    return [{"id": p["_id"], "name": p.get("full_name") or p.get("title", ""), "slug": p.get("slug")} for p in people]


@router.get("/people/{id_or_slug}", response_model=dict)
async def get_person(id_or_slug: str, request: Request, raw: bool = Query(False, description="без обработки ссылок (для админки)")):
    """Get person by ID or slug."""
    user = await get_current_user(request)
    editor = bool(user and user.get("role") in EDITOR_ROLES)
    person = await get_by_id_or_slug("people", id_or_slug, "Person not found", editor=editor)
    if person.get("status") == ContentStatus.ARCHIVED.value:
        if not editor:
            raise HTTPException(status_code=404, detail="Person not found")
    if not raw:
        await LinkResolver.resolve_document(person)
        await decorate_document(person)
    return person


@router.put("/people/{id}", response_model=dict)
async def update_person(id: str, data: PersonUpdate):
    """Update person."""
    if data.foreign_agent:
        data = data.model_copy(update={
            key: _without_legacy_marker(getattr(data, key))
            for key in ("title", "full_name", "primary_tag")
            if getattr(data, key) is not None
        })
    result = await update_content("people", id, data, "Person not found")
    await _link_person_everywhere(id)
    return result


@router.delete("/people/{id}")
async def delete_person(id: str):
    """Delete person."""
    result = await delete_content("people", id, "Person not found")
    await unlink_person(await get_db(), id)
    await (await get_db()).show_appearances.update_many(
        {"person_id": id}, {"$set": {"person_id": None}, "$unset": {"manual_person_id": ""}})
    return result


async def _link_person_everywhere(person_id: str) -> None:
    """Совместимая обёртка для обновления человека и служебных клиентов."""
    await content_commands.link_person_everywhere(await get_db(), person_id)
