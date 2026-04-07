"""Person routes — CRUD + search + linked content."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from models.base import ContentStatus
from models.content import Person, PersonCreate, PersonUpdate
from utils.database import get_db
from services.crud import (
    check_slug_unique, create_content, update_content,
    delete_content, get_by_id_or_slug, list_content, build_query,
)
from services.linking import linking_service
from services.link_resolver import LinkResolver

router = APIRouter(prefix="/content", tags=["people"])


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

    primary_tag = data.primary_tag
    if not primary_tag:
        primary_tag = swap_name_order(data.title) or swap_name_order(data.full_name)

    person = Person(
        title=data.title, slug=data.slug, full_name=data.full_name,
        photo=data.photo, bio=data.bio or {}, social_links=data.social_links or {},
        facts=data.facts or {}, facts_order=data.facts_order or [], primary_tag=primary_tag,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status
    )
    return await create_content("people", person, data.tags)


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
    return await list_content("people", skip, limit, query, "title", 1)


@router.get("/people/search", response_model=list)
async def search_people(q: str = Query(..., min_length=2), limit: int = Query(10, ge=1, le=50)):
    """Search people by name for editor assistance."""
    db = await get_db()
    query = {
        "$or": [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"title": {"$regex": q, "$options": "i"}}
        ]
    }
    cursor = db.people.find(query, {"_id": 1, "full_name": 1, "title": 1, "slug": 1}).limit(limit)
    people = await cursor.to_list(limit)
    return [{"id": p["_id"], "name": p.get("full_name") or p.get("title", ""), "slug": p.get("slug")} for p in people]


@router.get("/people/{id_or_slug}/linked-content", response_model=dict)
async def get_person_linked_content(
    id_or_slug: str,
    types: Optional[str] = Query(None, description="Comma-separated content types: news,article,show"),
    limit: int = Query(20, ge=1, le=100)
):
    """Get content linked to a person (for humor_chronicles module)."""
    db = await get_db()
    person = await db.people.find_one({
        "$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]
    })
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    person_id = person["_id"]
    content_types = types.split(",") if types else None
    return await linking_service.get_linked_content(person_id, content_types, limit)


@router.get("/people/{id_or_slug}", response_model=dict)
async def get_person(id_or_slug: str):
    """Get person by ID or slug."""
    person = await get_by_id_or_slug("people", id_or_slug, "Person not found")
    if person.get('modules'):
        person['modules'] = await LinkResolver.resolve_links_in_modules(person['modules'])
    return person


@router.put("/people/{id}", response_model=dict)
async def update_person(id: str, data: PersonUpdate):
    """Update person."""
    return await update_content("people", id, data, "Person not found")


@router.delete("/people/{id}")
async def delete_person(id: str):
    """Delete person."""
    return await delete_content("people", id, "Person not found")
