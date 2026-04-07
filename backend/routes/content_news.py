"""News routes — CRUD."""
from fastapi import APIRouter, Query
from typing import Optional

from models.base import ContentStatus
from models.content import News, NewsCreate, NewsUpdate
from services.crud import (
    check_slug_unique, create_content, update_content,
    delete_content, get_by_id_or_slug, list_content, build_query,
)

router = APIRouter(prefix="/content", tags=["news"])


@router.post("/news", response_model=dict)
async def create_news(data: NewsCreate):
    """Create news item."""
    await check_slug_unique("news", data.slug)
    news = News(
        title=data.title, slug=data.slug, excerpt=data.excerpt,
        cover_image=data.cover_image, content=data.content, important=data.important,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status,
        related_person_ids=data.related_person_ids or []
    )
    return await create_content(
        "news", news, data.tags,
        published_status=ContentStatus.PUBLISHED,
        related_person_ids=data.related_person_ids,
        content_label="news"
    )


@router.get("/news", response_model=dict)
async def list_news(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """List news with pagination."""
    query = build_query(status, tag, search, ["title"])
    return await list_content("news", skip, limit, query)


@router.get("/news/{id_or_slug}", response_model=dict)
async def get_news_item(id_or_slug: str):
    """Get news by ID or slug."""
    return await get_by_id_or_slug("news", id_or_slug, "News not found")


@router.put("/news/{id}", response_model=dict)
async def update_news(id: str, data: NewsUpdate):
    """Update news."""
    return await update_content(
        "news", id, data, "News not found",
        published_status=ContentStatus.PUBLISHED,
        related_person_ids=data.related_person_ids,
        content_label="news"
    )


@router.delete("/news/{id}")
async def delete_news(id: str):
    """Delete news."""
    return await delete_content("news", id, "News not found")
