"""Content API routes - CRUD for all content types"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
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
from utils.slugify import generate_slug

router = APIRouter(prefix="/content", tags=["content"])


# === HELPER FUNCTIONS ===

async def get_collection(content_type: str):
    """Get MongoDB collection by content type"""
    db = await get_db()
    collection_map = {
        "person": db.people,
        "team": db.teams,
        "show": db.shows,
        "article": db.articles,
        "news": db.news,
        "quiz": db.quizzes,
        "wiki": db.wiki,
    }
    return collection_map.get(content_type)


async def sync_tags_to_collection(tags: List[str]):
    """Sync content tags to the tags collection"""
    if not tags:
        return
    
    db = await get_db()
    for tag_name in tags:
        tag_name = tag_name.strip()
        if not tag_name:
            continue
        
        # Check if tag already exists (case-insensitive)
        existing = await db.tags.find_one({"name": {"$regex": f"^{tag_name}$", "$options": "i"}})
        if not existing:
            # Create new tag
            from uuid import uuid4
            slug = tag_name.lower().replace(" ", "-").replace(".", "").replace(",", "")
            # Transliterate cyrillic for slug
            translit_map = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
                'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
            }
            slug_chars = []
            for char in slug:
                slug_chars.append(translit_map.get(char, char))
            slug = ''.join(slug_chars)
            
            tag_doc = {
                "_id": str(uuid4()),
                "name": tag_name,
                "slug": slug,
                "old_id": None,
                "usage_count": 1,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            try:
                await db.tags.insert_one(tag_doc)
            except Exception:
                pass  # Ignore if duplicate
        else:
            # Increment usage count
            await db.tags.update_one(
                {"_id": existing["_id"]},
                {"$inc": {"usage_count": 1}}
            )


async def prepare_document(data: dict, content_type: ContentType, is_update: bool = False):
    """Prepare document for insert/update"""
    doc = {k: v for k, v in data.items() if v is not None}
    
    if not is_update:
        doc["content_type"] = content_type.value
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
    
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Generate slug if not provided
    if "slug" not in doc and "title" in doc:
        doc["slug"] = generate_slug(doc["title"])
    
    return doc


# === PERSON ROUTES ===

@router.post("/people", response_model=dict)
async def create_person(data: PersonCreate):
    """Create a new person"""
    db = await get_db()
    
    # Check slug uniqueness
    existing = await db.people.find_one({"slug": data.slug})
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")
    
    person = Person(
        title=data.title,
        slug=data.slug,
        full_name=data.full_name,
        photo=data.photo,
        bio=data.bio or {},
        social_links=data.social_links or {},
        modules=data.modules,
        tags=data.tags,
        seo=data.seo or {},
        status=data.status
    )
    
    doc = person.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    # Sync tags to tags collection
    await sync_tags_to_collection(data.tags)
    
    await db.people.insert_one(doc)
    return {"id": doc["_id"], "slug": doc["slug"]}


@router.get("/people", response_model=dict)
async def list_people(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    letter: Optional[str] = None  # For alphabetical filter
):
    """List people with pagination and filters"""
    db = await get_db()
    
    query = {}
    if status:
        query["status"] = status.value
    if tag:
        query["tags"] = tag
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"full_name": {"$regex": search, "$options": "i"}}
        ]
    if letter:
        query["title"] = {"$regex": f"^{letter}", "$options": "i"}
    
    total = await db.people.count_documents(query)
    cursor = db.people.find(query, {"modules": 0}).skip(skip).limit(limit).sort("title", 1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/people/{id_or_slug}", response_model=dict)
async def get_person(id_or_slug: str):
    """Get person by ID or slug"""
    db = await get_db()
    
    query = {"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}
    person = await db.people.find_one(query)
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Increment views
    await db.people.update_one({"_id": person["_id"]}, {"$inc": {"views": 1}})
    
    return person


@router.put("/people/{id}", response_model=dict)
async def update_person(id: str, data: PersonUpdate):
    """Update person"""
    db = await get_db()
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Sync tags to tags collection
    if data.tags:
        await sync_tags_to_collection(data.tags)
    
    result = await db.people.update_one({"_id": id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Person not found")
    
    return {"id": id, "updated": True}


@router.delete("/people/{id}")
async def delete_person(id: str):
    """Delete person"""
    db = await get_db()
    result = await db.people.delete_one({"_id": id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Person not found")
    
    return {"id": id, "deleted": True}


# === TEAM ROUTES ===

@router.post("/teams", response_model=dict)
async def create_team(data: TeamCreate):
    """Create a new team"""
    db = await get_db()
    
    existing = await db.teams.find_one({"slug": data.slug})
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")
    
    team = Team(
        title=data.title,
        slug=data.slug,
        name=data.name,
        team_type=data.team_type,
        logo=data.logo,
        facts=data.facts or {},
        social_links=data.social_links or {},
        modules=data.modules,
        tags=data.tags,
        seo=data.seo or {},
        status=data.status
    )
    
    doc = team.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    # Sync tags to tags collection
    await sync_tags_to_collection(data.tags)
    
    await db.teams.insert_one(doc)
    return {"id": doc["_id"], "slug": doc["slug"]}


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
    db = await get_db()
    
    query = {}
    if status:
        query["status"] = status.value
    if team_type:
        query["team_type"] = team_type
    if tag:
        query["tags"] = tag
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}}
        ]
    if letter:
        query["name"] = {"$regex": f"^{letter}", "$options": "i"}
    
    total = await db.teams.count_documents(query)
    cursor = db.teams.find(query, {"modules": 0}).skip(skip).limit(limit).sort("name", 1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/teams/{id_or_slug}", response_model=dict)
async def get_team(id_or_slug: str):
    """Get team by ID or slug"""
    db = await get_db()
    
    query = {"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}
    team = await db.teams.find_one(query)
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    await db.teams.update_one({"_id": team["_id"]}, {"$inc": {"views": 1}})
    return team


@router.put("/teams/{id}", response_model=dict)
async def update_team(id: str, data: TeamUpdate):
    """Update team"""
    db = await get_db()
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.teams.update_one({"_id": id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return {"id": id, "updated": True}


@router.delete("/teams/{id}")
async def delete_team(id: str):
    """Delete team"""
    db = await get_db()
    result = await db.teams.delete_one({"_id": id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return {"id": id, "deleted": True}


# === SHOW ROUTES ===

@router.post("/shows", response_model=dict)
async def create_show(data: ShowCreate):
    """Create a new show"""
    db = await get_db()
    
    existing = await db.shows.find_one({"slug": data.slug})
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")
    
    show = Show(
        title=data.title,
        slug=data.slug,
        name=data.name,
        poster=data.poster,
        facts=data.facts or {},
        description=data.description,
        modules=data.modules,
        tags=data.tags,
        seo=data.seo or {},
        status=data.status
    )
    
    doc = show.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    await db.shows.insert_one(doc)
    return {"id": doc["_id"], "slug": doc["slug"]}


@router.get("/shows", response_model=dict)
async def list_shows(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """List shows with pagination"""
    db = await get_db()
    
    query = {}
    if status:
        query["status"] = status.value
    if tag:
        query["tags"] = tag
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}}
        ]
    
    total = await db.shows.count_documents(query)
    cursor = db.shows.find(query, {"modules": 0}).skip(skip).limit(limit).sort("name", 1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/shows/{id_or_slug}", response_model=dict)
async def get_show(id_or_slug: str):
    """Get show by ID or slug"""
    db = await get_db()
    
    query = {"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}
    show = await db.shows.find_one(query)
    
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    
    await db.shows.update_one({"_id": show["_id"]}, {"$inc": {"views": 1}})
    return show


@router.put("/shows/{id}", response_model=dict)
async def update_show(id: str, data: ShowUpdate):
    """Update show"""
    db = await get_db()
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.shows.update_one({"_id": id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Show not found")
    
    return {"id": id, "updated": True}


@router.delete("/shows/{id}")
async def delete_show(id: str):
    """Delete show"""
    db = await get_db()
    result = await db.shows.delete_one({"_id": id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Show not found")
    
    return {"id": id, "deleted": True}


# === ARTICLE ROUTES ===

@router.post("/articles", response_model=dict)
async def create_article(data: ArticleCreate):
    """Create a new article"""
    db = await get_db()
    
    existing = await db.articles.find_one({"slug": data.slug})
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")
    
    article = Article(
        title=data.title,
        slug=data.slug,
        excerpt=data.excerpt,
        cover_image=data.cover_image,
        author_id=data.author_id,
        author_name=data.author_name,
        modules=data.modules,
        tags=data.tags,
        seo=data.seo or {},
        status=data.status
    )
    
    doc = article.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    if data.status == ContentStatus.PUBLISHED:
        doc["published_at"] = datetime.now(timezone.utc).isoformat()
    
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
    db = await get_db()
    
    query = {}
    if status:
        query["status"] = status.value
    if tag:
        query["tags"] = tag
    if search:
        query["title"] = {"$regex": search, "$options": "i"}
    if featured is not None:
        query["featured"] = featured
    
    total = await db.articles.count_documents(query)
    cursor = db.articles.find(query, {"modules": 0}).skip(skip).limit(limit).sort("published_at", -1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/articles/{id_or_slug}", response_model=dict)
async def get_article(id_or_slug: str):
    """Get article by ID or slug"""
    db = await get_db()
    
    query = {"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}
    article = await db.articles.find_one(query)
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    await db.articles.update_one({"_id": article["_id"]}, {"$inc": {"views": 1}})
    return article


@router.put("/articles/{id}", response_model=dict)
async def update_article(id: str, data: ArticleUpdate):
    """Update article"""
    db = await get_db()
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
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
    db = await get_db()
    result = await db.articles.delete_one({"_id": id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return {"id": id, "deleted": True}


# === NEWS ROUTES ===

@router.post("/news", response_model=dict)
async def create_news(data: NewsCreate):
    """Create news item"""
    db = await get_db()
    
    existing = await db.news.find_one({"slug": data.slug})
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")
    
    news = News(
        title=data.title,
        slug=data.slug,
        excerpt=data.excerpt,
        cover_image=data.cover_image,
        content=data.content,
        important=data.important,
        tags=data.tags,
        seo=data.seo or {},
        status=data.status
    )
    
    doc = news.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    if data.status == ContentStatus.PUBLISHED:
        doc["published_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.news.insert_one(doc)
    return {"id": doc["_id"], "slug": doc["slug"]}


@router.get("/news", response_model=dict)
async def list_news(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    important: Optional[bool] = None
):
    """List news with pagination"""
    db = await get_db()
    
    query = {}
    if status:
        query["status"] = status.value
    if tag:
        query["tags"] = tag
    if search:
        query["title"] = {"$regex": search, "$options": "i"}
    if important is not None:
        query["important"] = important
    
    total = await db.news.count_documents(query)
    cursor = db.news.find(query).skip(skip).limit(limit).sort("published_at", -1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/news/{id_or_slug}", response_model=dict)
async def get_news(id_or_slug: str):
    """Get news by ID or slug"""
    db = await get_db()
    
    query = {"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}
    news = await db.news.find_one(query)
    
    if not news:
        raise HTTPException(status_code=404, detail="News not found")
    
    await db.news.update_one({"_id": news["_id"]}, {"$inc": {"views": 1}})
    return news


@router.put("/news/{id}", response_model=dict)
async def update_news(id: str, data: NewsUpdate):
    """Update news"""
    db = await get_db()
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.news.update_one({"_id": id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="News not found")
    
    return {"id": id, "updated": True}


@router.delete("/news/{id}")
async def delete_news(id: str):
    """Delete news"""
    db = await get_db()
    result = await db.news.delete_one({"_id": id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="News not found")
    
    return {"id": id, "deleted": True}


# === QUIZ ROUTES ===

@router.post("/quizzes", response_model=dict)
async def create_quiz(data: QuizCreate):
    """Create a quiz"""
    db = await get_db()
    
    existing = await db.quizzes.find_one({"slug": data.slug})
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")
    
    quiz = Quiz(
        title=data.title,
        slug=data.slug,
        description=data.description,
        cover_image=data.cover_image,
        modules=data.modules,
        tags=data.tags,
        seo=data.seo or {},
        status=data.status
    )
    
    doc = quiz.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    await db.quizzes.insert_one(doc)
    return {"id": doc["_id"], "slug": doc["slug"]}


@router.get("/quizzes", response_model=dict)
async def list_quizzes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None
):
    """List quizzes"""
    db = await get_db()
    
    query = {}
    if status:
        query["status"] = status.value
    if tag:
        query["tags"] = tag
    
    total = await db.quizzes.count_documents(query)
    cursor = db.quizzes.find(query, {"modules": 0}).skip(skip).limit(limit).sort("created_at", -1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/quizzes/{id_or_slug}", response_model=dict)
async def get_quiz(id_or_slug: str):
    """Get quiz by ID or slug"""
    db = await get_db()
    
    query = {"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}
    quiz = await db.quizzes.find_one(query)
    
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    await db.quizzes.update_one({"_id": quiz["_id"]}, {"$inc": {"views": 1}})
    return quiz


@router.put("/quizzes/{id}", response_model=dict)
async def update_quiz(id: str, data: QuizUpdate):
    """Update quiz"""
    db = await get_db()
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.quizzes.update_one({"_id": id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    return {"id": id, "updated": True}


@router.delete("/quizzes/{id}")
async def delete_quiz(id: str):
    """Delete quiz"""
    db = await get_db()
    result = await db.quizzes.delete_one({"_id": id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    return {"id": id, "deleted": True}


# === WIKI ROUTES ===

@router.post("/wiki", response_model=dict)
async def create_wiki(data: WikiCreate):
    """Create wiki page"""
    db = await get_db()
    
    existing = await db.wiki.find_one({"slug": data.slug})
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")
    
    content_type = ContentType.WIKI_HEADER if data.has_header else ContentType.WIKI
    
    wiki = Wiki(
        title=data.title,
        slug=data.slug,
        content_type=content_type,
        content=data.content,
        cover_image=data.cover_image,
        has_header=data.has_header,
        header_image=data.header_image,
        header_facts=data.header_facts,
        modules=data.modules,
        tags=data.tags,
        seo=data.seo or {},
        status=data.status
    )
    
    doc = wiki.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    await db.wiki.insert_one(doc)
    return {"id": doc["_id"], "slug": doc["slug"]}


@router.get("/wiki", response_model=dict)
async def list_wiki(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """List wiki pages"""
    db = await get_db()
    
    query = {}
    if status:
        query["status"] = status.value
    if tag:
        query["tags"] = tag
    if search:
        query["title"] = {"$regex": search, "$options": "i"}
    
    total = await db.wiki.count_documents(query)
    cursor = db.wiki.find(query, {"modules": 0, "content": 0}).skip(skip).limit(limit).sort("title", 1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/wiki/{id_or_slug}", response_model=dict)
async def get_wiki(id_or_slug: str):
    """Get wiki page by ID or slug"""
    db = await get_db()
    
    query = {"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}
    wiki = await db.wiki.find_one(query)
    
    if not wiki:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    
    await db.wiki.update_one({"_id": wiki["_id"]}, {"$inc": {"views": 1}})
    return wiki


@router.put("/wiki/{id}", response_model=dict)
async def update_wiki(id: str, data: WikiUpdate):
    """Update wiki page"""
    db = await get_db()
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.wiki.update_one({"_id": id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    
    return {"id": id, "updated": True}


@router.delete("/wiki/{id}")
async def delete_wiki(id: str):
    """Delete wiki page"""
    db = await get_db()
    result = await db.wiki.delete_one({"_id": id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    
    return {"id": id, "deleted": True}


# === UNIVERSAL SEARCH ===

@router.get("/search", response_model=dict)
async def search_all(
    q: str = Query(..., min_length=2),
    types: Optional[str] = None,  # Comma-separated: person,team,article
    limit: int = Query(20, ge=1, le=100)
):
    """Search across all content types"""
    db = await get_db()
    
    search_types = types.split(",") if types else ["person", "team", "show", "article", "news", "wiki"]
    
    results = {}
    
    search_query = {
        "$or": [
            {"title": {"$regex": q, "$options": "i"}},
            {"name": {"$regex": q, "$options": "i"}},
            {"full_name": {"$regex": q, "$options": "i"}}
        ],
        "status": "published"
    }
    
    collection_map = {
        "person": ("people", db.people),
        "team": ("teams", db.teams),
        "show": ("shows", db.shows),
        "article": ("articles", db.articles),
        "news": ("news", db.news),
        "wiki": ("wiki", db.wiki)
    }
    
    for content_type in search_types:
        if content_type in collection_map:
            name, collection = collection_map[content_type]
            items = await collection.find(
                search_query,
                {"_id": 1, "title": 1, "slug": 1, "content_type": 1}
            ).limit(limit // len(search_types)).to_list(limit)
            results[name] = items
    
    return {"query": q, "results": results}
