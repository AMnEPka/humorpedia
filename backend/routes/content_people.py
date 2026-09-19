"""Person routes — CRUD + search + linked content."""
from fastapi import APIRouter, HTTPException, Query, Depends
import re
from utils.auth import require_editor_on_write
from typing import Optional

from models.base import ContentStatus
from models.content import Person, PersonCreate, PersonUpdate
from utils.database import get_db
from utils.search import literal_search_pattern
from services.crud import (
    check_slug_unique, create_content, update_content,
    delete_content, get_by_id_or_slug, list_alphabetical_content, build_query,
)
from services.link_resolver import LinkResolver
from services.foreign_agent_notices import decorate_document
from services.memberships import link_person, unlink_person

router = APIRouter(prefix="/content", tags=["people"], dependencies=[Depends(require_editor_on_write)])


def _without_legacy_marker(value: Optional[str]) -> Optional[str]:
    return re.sub(r"\s*\*+\s*", " ", value).strip() if value else value


@router.post("/people", response_model=dict)
async def create_person(data: PersonCreate):
    """Create a new person."""
    await check_slug_unique("people", data.slug)

    def swap_name_order(name):
        if not name:
            return name
        parts = name.strip().split()
        if len(parts) == 2:
            return f"{parts[1]} {parts[0]}"
        return name

    title = _without_legacy_marker(data.title) if data.foreign_agent else data.title
    full_name = _without_legacy_marker(data.full_name) if data.foreign_agent else data.full_name
    primary_tag = _without_legacy_marker(data.primary_tag) if data.foreign_agent else data.primary_tag
    if not primary_tag:
        primary_tag = swap_name_order(title) or swap_name_order(full_name)

    person = Person(
        title=title, slug=data.slug, full_name=full_name,
        foreign_agent=data.foreign_agent,
        photo=data.photo, bio=data.bio or {}, social_links=data.social_links or {},
        facts=data.facts or {}, facts_order=data.facts_order or [], primary_tag=primary_tag,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status
    )
    result = await create_content("people", person, data.tags)
    await _link_person_everywhere(result["id"])
    return result


@router.get("/people", response_model=dict)
async def list_people(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    letter: Optional[str] = None
):
    """List people with pagination and filters."""
    query = build_query(status, tag, search, ["title", "full_name"], letter)
    availability_query = build_query(status, tag)
    return await list_alphabetical_content(
        "people", skip, limit, query, ["title", "full_name"],
        availability_query=availability_query,
    )


@router.get("/people/search", response_model=list)
async def search_people(q: str = Query(..., min_length=2), limit: int = Query(10, ge=1, le=50)):
    """Search people by name for editor assistance."""
    db = await get_db()
    search_pattern = literal_search_pattern(q)
    query = {
        "$or": [
            {"full_name": {"$regex": search_pattern, "$options": "i"}},
            {"title": {"$regex": search_pattern, "$options": "i"}}
        ]
    }
    cursor = db.people.find(query, {"_id": 1, "full_name": 1, "title": 1, "slug": 1}).limit(limit)
    people = await cursor.to_list(limit)
    return [{"id": p["_id"], "name": p.get("full_name") or p.get("title", ""), "slug": p.get("slug")} for p in people]


@router.get("/people/{id_or_slug}", response_model=dict)
async def get_person(id_or_slug: str, raw: bool = Query(False, description="без обработки ссылок (для админки)")):
    """Get person by ID or slug."""
    person = await get_by_id_or_slug("people", id_or_slug, "Person not found")
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
    """Связать человека с записями составов, где он упомянут по slug старого сайта или однозначному имени."""
    db = await get_db()
    person = await db.people.find_one({"_id": person_id})
    if person:
        await link_person(db, person)
        from services.show_appearances import link_new_person
        await link_new_person(db, person)
