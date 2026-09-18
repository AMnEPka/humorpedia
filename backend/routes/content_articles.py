"""Article routes — CRUD + random."""
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from utils.auth import require_editor_on_write
from typing import Optional, Literal

from models.base import ContentStatus
from models.content import Article, ArticleCreate, ArticleUpdate
from utils.database import get_db
from services.crud import (
    check_slug_unique, create_content, update_content,
    delete_content, get_by_id_or_slug, list_content, build_query,
)
from services.link_resolver import LinkResolver
from services.foreign_agent_notices import decorate_document

router = APIRouter(prefix="/content", tags=["articles"], dependencies=[Depends(require_editor_on_write)])


@router.get("/articles/random", response_model=dict)
async def get_random_article(request: Request):
    """Return a random non-archived article."""
    db = await get_db()
    pipeline = [
        {"$match": {"status": {"$ne": "archived"}}},
        {"$sample": {"size": 1}},
    ]
    result = await db.articles.aggregate(pipeline).to_list(1)
    if not result:
        raise HTTPException(status_code=404, detail="No articles found")
    return result[0]


@router.post("/articles", response_model=dict)
async def create_article(data: ArticleCreate):
    """Create a new article."""
    await check_slug_unique("articles", data.slug)
    article = Article(
        title=data.title, slug=data.slug, excerpt=data.excerpt, cover_image=data.cover_image,
        author_id=data.author_id, author_name=data.author_name,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status,
        featured=data.featured, related_person_ids=data.related_person_ids or [],
        related_team_ids=data.related_team_ids or [], related_article_ids=data.related_article_ids or []
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
    featured: Optional[bool] = None,
    sort: Literal['-created_at', '-published_at', '-rating'] = '-created_at',
    exclude_archived: bool = False,
):
    """List articles with pagination."""
    extra = {"featured": featured} if featured is not None else None
    query = build_query(status, tag, search, ["title"], extra=extra)
    if exclude_archived:
        query = {"$and": [query, {"status": {"$ne": "archived"}}]}
    return await list_content("articles", skip, limit, query, sort_field=sort[1:])


@router.get("/articles/{id_or_slug}", response_model=dict)
async def get_article(id_or_slug: str, raw: bool = Query(False, description="без обработки ссылок и пометок (для админки)")):
    """Get article by ID or slug."""
    article = await get_by_id_or_slug("articles", id_or_slug, "Article not found")
    if not raw:
        await LinkResolver.resolve_document(article)
        await decorate_document(article)
    return article


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
