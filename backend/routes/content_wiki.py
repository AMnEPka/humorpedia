"""Wiki routes — CRUD."""
from fastapi import APIRouter, Query
from typing import Optional

from models.base import ContentType, ContentStatus
from models.content import Wiki, WikiCreate, WikiUpdate
from services.crud import (
    check_slug_unique, create_content, update_content,
    delete_content, get_by_id_or_slug, list_content, build_query,
)

router = APIRouter(prefix="/content", tags=["wiki"])


@router.post("/wiki", response_model=dict)
async def create_wiki(data: WikiCreate):
    """Create wiki page."""
    await check_slug_unique("wiki", data.slug)
    content_type = ContentType.WIKI_HEADER if data.has_header else ContentType.WIKI
    wiki = Wiki(
        title=data.title, slug=data.slug, content_type=content_type,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status
    )
    return await create_content("wiki", wiki, data.tags)


@router.get("/wiki", response_model=dict)
async def list_wiki(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """List wiki pages with pagination."""
    query = build_query(status, tag, search, ["title"])
    return await list_content("wiki", skip, limit, query, "title", 1)


@router.get("/wiki/{id_or_slug}", response_model=dict)
async def get_wiki(id_or_slug: str):
    """Get wiki page by ID or slug."""
    return await get_by_id_or_slug("wiki", id_or_slug, "Wiki page not found")


@router.put("/wiki/{id}", response_model=dict)
async def update_wiki(id: str, data: WikiUpdate):
    """Update wiki page."""
    return await update_content("wiki", id, data, "Wiki page not found")


@router.delete("/wiki/{id}")
async def delete_wiki(id: str):
    """Delete wiki page."""
    return await delete_content("wiki", id, "Wiki page not found")
