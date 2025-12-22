"""Content API routes - CRUD for all content types"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone

from models.base import ContentType, ContentStatus
from models.content import (
    Person, PersonCreate, PersonUpdate,
    Team, TeamCreate, TeamUpdate,
    Show, ShowCreate, ShowUpdate,
    Article, ArticleCreate, ArticleUpdate,
    News, NewsCreate, NewsUpdate,
    Quiz, QuizCreate, QuizUpdate,
    Wiki, WikiCreate, WikiUpdate
)
from utils.database import get_db
from services.tags import tag_service

router = APIRouter(prefix="/content", tags=["content"])


# === HELPER FUNCTIONS ===

async def check_slug_unique(collection_name: str, slug: str, exclude_id: str = None):
    """Check if slug is unique in collection"""
    db = await get_db()
    collection = getattr(db, collection_name)
    query = {"slug": slug}
    if exclude_id:
        query["_id"] = {"$ne": exclude_id}
    existing = await collection.find_one(query)
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")


async def create_content(collection_name: str, model_instance, tags: list = None):
    """Universal create handler"""
    db = await get_db()
    collection = getattr(db, collection_name)
    
    doc = model_instance.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    # Sync tags
    if tags:
        await tag_service.sync_tags(tags)
    
    await collection.insert_one(doc)
    return {"id": doc["_id"], "slug": doc.get("slug")}


async def update_content(collection_name: str, item_id: str, data, not_found_msg: str):
    """Universal update handler"""
    db = await get_db()
    collection = getattr(db, collection_name)
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Sync tags if present
    if hasattr(data, 'tags') and data.tags:
        await tag_service.sync_tags(data.tags)
    
    result = await collection.update_one({"_id": item_id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=not_found_msg)
    
    return {"id": item_id, "updated": True}


async def delete_content(collection_name: str, item_id: str, not_found_msg: str):
    """Universal delete handler"""
    db = await get_db()
    collection = getattr(db, collection_name)
    result = await collection.delete_one({"_id": item_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=not_found_msg)
    
    return {"id": item_id, "deleted": True}


async def get_by_id_or_slug(collection_name: str, id_or_slug: str, not_found_msg: str, increment_views: bool = True):
    """Universal get by ID or slug handler"""
    db = await get_db()
    collection = getattr(db, collection_name)
    
    query = {"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}
    item = await collection.find_one(query)
    
    if not item:
        raise HTTPException(status_code=404, detail=not_found_msg)
    
    if increment_views:
        await collection.update_one({"_id": item["_id"]}, {"$inc": {"views": 1}})
    
    return item


async def list_content(
    collection_name: str,
    skip: int,
    limit: int,
    query: dict = None,
    sort_field: str = "created_at",
    sort_order: int = -1,
    exclude_modules: bool = True
):
    """Universal list handler"""
    db = await get_db()
    collection = getattr(db, collection_name)
    
    query = query or {}
    projection = {"modules": 0} if exclude_modules else None
    
    total = await collection.count_documents(query)
    cursor = collection.find(query, projection).skip(skip).limit(limit).sort(sort_field, sort_order)
    items = await cursor.to_list(limit)
    
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def build_query(
    status: ContentStatus = None,
    tag: str = None,
    search: str = None,
    search_fields: list = None,
    letter: str = None,
    letter_field: str = "title",
    extra: dict = None
) -> dict:
    """Build MongoDB query from common filters"""
    query = {}
    
    if status:
        query["status"] = status.value
    if tag:
        query["tags"] = tag
    if search and search_fields:
        query["$or"] = [{f: {"$regex": search, "$options": "i"}} for f in search_fields]
    if letter:
        query[letter_field] = {"$regex": f"^{letter}", "$options": "i"}
    if extra:
        query.update(extra)
    
    return query


# === PERSON ROUTES ===

@router.post("/people", response_model=dict)
async def create_person(data: PersonCreate):
    """Create a new person"""
    await check_slug_unique("people", data.slug)
    
    person = Person(
        title=data.title, slug=data.slug, full_name=data.full_name,
        photo=data.photo, bio=data.bio or {}, social_links=data.social_links or {},
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
    """List people with pagination and filters"""
    query = build_query(status, tag, search, ["title", "full_name"], letter)
    return await list_content("people", skip, limit, query, "title", 1)


@router.get("/people/{id_or_slug}", response_model=dict)
async def get_person(id_or_slug: str):
    """Get person by ID or slug"""
    return await get_by_id_or_slug("people", id_or_slug, "Person not found")


@router.put("/people/{id}", response_model=dict)
async def update_person(id: str, data: PersonUpdate):
    """Update person"""
    return await update_content("people", id, data, "Person not found")


@router.delete("/people/{id}")
async def delete_person(id: str):
    """Delete person"""
    return await delete_content("people", id, "Person not found")


# === TEAM ROUTES ===

@router.post("/teams", response_model=dict)
async def create_team(data: TeamCreate):
    """Create a new team"""
    await check_slug_unique("teams", data.slug)
    
    team = Team(
        title=data.title, slug=data.slug, name=data.name, team_type=data.team_type,
        logo=data.logo, facts=data.facts or {}, social_links=data.social_links or {},
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status
    )
    return await create_content("teams", team, data.tags)


@router.get("/teams", response_model=dict)
async def list_teams(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    team_type: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    letter: Optional[str] = None
):
    """List teams with pagination and filters"""
    extra = {"team_type": team_type} if team_type else None
    query = build_query(status, tag, search, ["title", "name"], letter, "name", extra)
    return await list_content("teams", skip, limit, query, "name", 1)


@router.get("/teams/{id_or_slug}", response_model=dict)
async def get_team(id_or_slug: str):
    """Get team by ID or slug"""
    return await get_by_id_or_slug("teams", id_or_slug, "Team not found")


@router.put("/teams/{id}", response_model=dict)
async def update_team(id: str, data: TeamUpdate):
    """Update team"""
    return await update_content("teams", id, data, "Team not found")


@router.delete("/teams/{id}")
async def delete_team(id: str):
    """Delete team"""
    return await delete_content("teams", id, "Team not found")


# === SHOW ROUTES ===

@router.post("/shows", response_model=dict)
async def create_show(data: ShowCreate):
    """Create a new show"""
    await check_slug_unique("shows", data.slug)
    
    show = Show(
        title=data.title, slug=data.slug, name=data.name, poster=data.poster,
        facts=data.facts or {}, description=data.description,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status
    )
    return await create_content("shows", show, data.tags)


@router.get("/shows", response_model=dict)
async def list_shows(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """List shows with pagination"""
    query = build_query(status, tag, search, ["title", "name"])
    return await list_content("shows", skip, limit, query, "name", 1)


@router.get("/shows/{id_or_slug}", response_model=dict)
async def get_show(id_or_slug: str):
    """Get show by ID or slug"""
    return await get_by_id_or_slug("shows", id_or_slug, "Show not found")


@router.put("/shows/{id}", response_model=dict)
async def update_show(id: str, data: ShowUpdate):
    """Update show"""
    return await update_content("shows", id, data, "Show not found")


@router.delete("/shows/{id}")
async def delete_show(id: str):
    """Delete show"""
    return await delete_content("shows", id, "Show not found")


# === ARTICLE ROUTES ===

@router.post("/articles", response_model=dict)
async def create_article(data: ArticleCreate):
    """Create a new article"""
    await check_slug_unique("articles", data.slug)
    
    article = Article(
        title=data.title, slug=data.slug, excerpt=data.excerpt, cover=data.cover,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status,
        featured=data.featured
    )
    
    doc = article.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    if data.status == ContentStatus.PUBLISHED:
        doc["published_at"] = datetime.now(timezone.utc).isoformat()
    
    if data.tags:
        await tag_service.sync_tags(data.tags)
    
    db = await get_db()
    await db.articles.insert_one(doc)
    return {"id": doc["_id"], "slug": doc["slug"]}


@router.get("/articles", response_model=dict)
async def list_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    featured: Optional[bool] = None
):
    """List articles with pagination"""
    extra = {"featured": featured} if featured is not None else None
    query = build_query(status, tag, search, ["title"], extra=extra)
    return await list_content("articles", skip, limit, query)


@router.get("/articles/{id_or_slug}", response_model=dict)
async def get_article(id_or_slug: str):
    """Get article by ID or slug"""
    return await get_by_id_or_slug("articles", id_or_slug, "Article not found")


@router.put("/articles/{id}", response_model=dict)
async def update_article(id: str, data: ArticleUpdate):
    """Update article"""
    db = await get_db()
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    if data.tags:
        await tag_service.sync_tags(data.tags)
    
    # Set published_at if status changed to published
    if data.status == ContentStatus.PUBLISHED:
        article = await db.articles.find_one({"_id": id})
        if article and not article.get("published_at"):
            update_data["published_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.articles.update_one({"_id": id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return {"id": id, "updated": True}


@router.delete("/articles/{id}")
async def delete_article(id: str):
    """Delete article"""
    return await delete_content("articles", id, "Article not found")


# === NEWS ROUTES ===

@router.post("/news", response_model=dict)
async def create_news(data: NewsCreate):
    """Create news item"""
    await check_slug_unique("news", data.slug)
    
    news = News(
        title=data.title, slug=data.slug, excerpt=data.excerpt, cover=data.cover,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status
    )
    
    doc = news.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    if data.status == ContentStatus.PUBLISHED:
        doc["published_at"] = datetime.now(timezone.utc).isoformat()
    
    if data.tags:
        await tag_service.sync_tags(data.tags)
    
    db = await get_db()
    await db.news.insert_one(doc)
    return {"id": doc["_id"], "slug": doc["slug"]}


@router.get("/news", response_model=dict)
async def list_news(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """List news with pagination"""
    query = build_query(status, tag, search, ["title"])
    return await list_content("news", skip, limit, query)


@router.get("/news/{id_or_slug}", response_model=dict)
async def get_news_item(id_or_slug: str):
    """Get news by ID or slug"""
    return await get_by_id_or_slug("news", id_or_slug, "News not found")


@router.put("/news/{id}", response_model=dict)
async def update_news(id: str, data: NewsUpdate):
    """Update news"""
    return await update_content("news", id, data, "News not found")


@router.delete("/news/{id}")
async def delete_news(id: str):
    """Delete news"""
    return await delete_content("news", id, "News not found")


# === QUIZ ROUTES ===

@router.post("/quizzes", response_model=dict)
async def create_quiz(data: QuizCreate):
    """Create a quiz"""
    await check_slug_unique("quizzes", data.slug)
    
    quiz = Quiz(
        title=data.title, slug=data.slug, description=data.description, cover=data.cover,
        questions=data.questions, tags=data.tags, seo=data.seo or {}, status=data.status
    )
    return await create_content("quizzes", quiz, data.tags)


@router.get("/quizzes", response_model=dict)
async def list_quizzes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """List quizzes with pagination"""
    query = build_query(status, tag, search, ["title"])
    return await list_content("quizzes", skip, limit, query)


@router.get("/quizzes/{id_or_slug}", response_model=dict)
async def get_quiz(id_or_slug: str):
    """Get quiz by ID or slug"""
    return await get_by_id_or_slug("quizzes", id_or_slug, "Quiz not found")


@router.put("/quizzes/{id}", response_model=dict)
async def update_quiz(id: str, data: QuizUpdate):
    """Update quiz"""
    return await update_content("quizzes", id, data, "Quiz not found")


@router.delete("/quizzes/{id}")
async def delete_quiz(id: str):
    """Delete quiz"""
    return await delete_content("quizzes", id, "Quiz not found")


# === WIKI ROUTES ===

@router.post("/wiki", response_model=dict)
async def create_wiki(data: WikiCreate):
    """Create wiki page"""
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
    """List wiki pages with pagination"""
    query = build_query(status, tag, search, ["title"])
    return await list_content("wiki", skip, limit, query, "title", 1)


@router.get("/wiki/{id_or_slug}", response_model=dict)
async def get_wiki(id_or_slug: str):
    """Get wiki page by ID or slug"""
    return await get_by_id_or_slug("wiki", id_or_slug, "Wiki page not found")


@router.put("/wiki/{id}", response_model=dict)
async def update_wiki(id: str, data: WikiUpdate):
    """Update wiki page"""
    return await update_content("wiki", id, data, "Wiki page not found")


@router.delete("/wiki/{id}")
async def delete_wiki(id: str):
    """Delete wiki page"""
    return await delete_content("wiki", id, "Wiki page not found")


# === UNIVERSAL SEARCH ===

@router.get("/search", response_model=dict)
async def search_all(
    q: str = Query(..., min_length=2),
    types: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
):
    """Search across all content types"""
    db = await get_db()
    
    search_types = types.split(",") if types else ["person", "team", "show", "article", "news", "wiki"]
    
    results = {}
    collection_map = {
        "person": ("people", ["title", "full_name"]),
        "team": ("teams", ["title", "name"]),
        "show": ("shows", ["title", "name"]),
        "article": ("articles", ["title"]),
        "news": ("news", ["title"]),
        "wiki": ("wiki", ["title"]),
    }
    
    for content_type in search_types:
        if content_type not in collection_map:
            continue
        
        coll_name, fields = collection_map[content_type]
        collection = getattr(db, coll_name)
        
        query = {"$or": [{f: {"$regex": q, "$options": "i"}} for f in fields]}
        cursor = collection.find(query, {"modules": 0}).limit(limit)
        items = await cursor.to_list(limit)
        
        if items:
            results[content_type] = items
    
    return results
