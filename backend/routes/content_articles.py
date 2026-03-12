"""Article routes — CRUD + random."""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional

from models.base import ContentStatus
from models.content import Article, ArticleCreate, ArticleUpdate
from utils.database import get_db
from services.crud import (
    check_slug_unique, create_content, update_content,
    delete_content, get_by_id_or_slug, list_content, build_query,
)

router = APIRouter(prefix="/content", tags=["articles"])


@router.get("/articles/random", response_model=dict)
async def get_random_article(request: Request):
    """Return a random published article."""
    db = await get_db()
    pipeline = [
        {"$match": {"status": "published"}},
        {"$sample": {"size": 1}},
    ]
    result = await db.articles.aggregate(pipeline).to_list(1)
    if not result:
        raise HTTPException(status_code=404, detail="No published articles found")
    return result[0]


@router.post("/articles", response_model=dict)
async def create_article(data: ArticleCreate):
    """Create a new article."""
    await check_slug_unique("articles", data.slug)
    article = Article(
        title=data.title, slug=data.slug, excerpt=data.excerpt, cover_image=data.cover_image,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status,
        featured=data.featured, related_person_ids=data.related_person_ids or []
    )
    return await create_content(
        "articles", article, data.tags,
        published_status=ContentStatus.PUBLISHED,
        related_person_ids=data.related_person_ids,
        content_label="article"
    )


@router.get("/articles", response_model=dict)
async def list_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    featured: Optional[bool] = None
):
    """List articles with pagination."""
    extra = {"featured": featured} if featured is not None else None
    query = build_query(status, tag, search, ["title"], extra=extra)
    return await list_content("articles", skip, limit, query)


@router.get("/articles/{id_or_slug}", response_model=dict)
async def get_article(id_or_slug: str):
    """Get article by ID or slug."""
    return await get_by_id_or_slug("articles", id_or_slug, "Article not found")


@router.put("/articles/{id}", response_model=dict)
async def update_article(id: str, data: ArticleUpdate):
    """Update article."""
    return await update_content(
        "articles", id, data, "Article not found",
        published_status=ContentStatus.PUBLISHED,
        related_person_ids=data.related_person_ids,
        content_label="article"
    )


@router.delete("/articles/{id}")
async def delete_article(id: str):
    """Delete article."""
    return await delete_content("articles", id, "Article not found")
