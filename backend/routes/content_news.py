"""News routes — CRUD."""
from fastapi import APIRouter, Query, Depends, Request
from utils.auth import get_current_user, require_editor_on_write
from services.content_visibility import editor_can_view_archived
from typing import Optional

from models.base import ContentStatus
from models.content import News, NewsCreate, NewsUpdate
from services.crud import (
    check_slug_unique, create_content, update_content,
    delete_content, get_by_id_or_slug, list_content, build_query,
)
from services.link_resolver import LinkResolver
from services.foreign_agent_notices import decorate_document

router = APIRouter(prefix="/content", tags=["news"], dependencies=[Depends(require_editor_on_write)])


@router.post("/news", response_model=dict)
async def create_news(data: NewsCreate):
    """Create news item."""
    await check_slug_unique("news", data.slug)
    news = News(
        title=data.title, slug=data.slug, excerpt=data.excerpt,
        cover_image=data.cover_image, content=data.content, important=data.important,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status,
        related_person_ids=data.related_person_ids or [], related_team_ids=data.related_team_ids or [],
        related_show_ids=data.related_show_ids or [],
        related_article_ids=data.related_article_ids or []
    )
    return await create_content(
        "news", news, data.tags,
        published_status=ContentStatus.PUBLISHED,
    )


@router.get("/news", response_model=dict)
async def list_news(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    request: Request = None,
):
    """List news with pagination."""
    query = build_query(status, tag, search, ["title"])
    editor = await editor_can_view_archived(request, get_current_user)
    return await list_content("news", skip, limit, query, editor=editor)


@router.get("/news/{id_or_slug}", response_model=dict)
async def get_news_item(id_or_slug: str, raw: bool = Query(False, description="без обработки ссылок и пометок (для админки)"), request: Request = None):
    """Get news by ID or slug."""
    editor = await editor_can_view_archived(request, get_current_user)
    news = await get_by_id_or_slug("news", id_or_slug, "News not found", editor=editor)
    if not raw:
        await LinkResolver.resolve_document(news)
        await decorate_document(news)
    return news


@router.put("/news/{id}", response_model=dict)
async def update_news(id: str, data: NewsUpdate):
    """Update news."""
    return await update_content(
        "news", id, data, "News not found",
        published_status=ContentStatus.PUBLISHED,
    )


@router.delete("/news/{id}")
async def delete_news(id: str):
    """Delete news."""
    return await delete_content("news", id, "News not found")
