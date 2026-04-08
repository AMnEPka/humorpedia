"""
Humorpedia API Server
Main FastAPI application with modular content management
"""
from fastapi import FastAPI, APIRouter, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import sys
import logging
import bcrypt
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Use the single DB connection from utils.database (no duplication)
from utils.database import get_db, close_db

# Default admin credentials
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_EMAIL = "admin@humorpedia.local"
DEFAULT_ADMIN_PASSWORD = "admin"


async def ensure_default_admin(db):
    """Create default admin user if not exists"""
    try:
        existing = await db.users.find_one({
            "$or": [
                {"username": DEFAULT_ADMIN_USERNAME},
                {"email": DEFAULT_ADMIN_EMAIL}
            ]
        })
        
        if existing:
            logger.info(f"Default admin already exists: {existing.get('username')}")
            return
        
        password_hash = bcrypt.hashpw(DEFAULT_ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
        
        admin_doc = {
            "_id": str(uuid4()),
            "username": DEFAULT_ADMIN_USERNAME,
            "email": DEFAULT_ADMIN_EMAIL,
            "password_hash": password_hash,
            "profile": {
                "full_name": "Administrator",
                "avatar": None,
                "bio": None,
                "birth_date": None,
                "location": None
            },
            "role": "admin",
            "permissions": ["comment", "vote", "edit", "delete", "moderate", "admin"],
            "oauth": {
                "vk_id": None,
                "yandex_id": None,
                "vk_data": None,
                "yandex_data": None
            },
            "auth_provider": "email",
            "stats": {
                "articles_count": 0,
                "comments_count": 0,
                "votes_count": 0,
                "quiz_attempts": 0
            },
            "active": True,
            "verified": True,
            "banned": False,
            "old_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_login_at": None
        }
        
        await db.users.insert_one(admin_doc)
        logger.info(f"✅ Default admin created: {DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}")
    except Exception as e:
        logger.error(f"Failed to create default admin: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown"""
    # Startup
    logger.info("Starting Humorpedia API server...")

    # Single DB connection via get_db() — shared with all routes and services
    db = await get_db()
    app.state.db = db  # keep for backward compat (sections.py, cities.py, stats)

    # Create indexes
    await create_indexes(db)
    
    # Create default admin if not exists
    await ensure_default_admin(db)
    
    db_name = os.environ.get('DB_NAME', 'humorpedia')
    logger.info(f"Connected to MongoDB: {db_name}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await close_db()


async def create_indexes(db):
    """Create MongoDB indexes for optimal performance"""
    try:
        # People indexes
        await db.people.create_index("slug", unique=True)
        await db.people.create_index("id", unique=True)
        await db.people.create_index("title")
        await db.people.create_index("full_name")
        await db.people.create_index("tags")
        await db.people.create_index("status")
        await db.people.create_index([("title", "text"), ("full_name", "text")])
        await db.people.create_index("old_urls")
        
        # Teams indexes
        await db.teams.create_index("slug", unique=True)
        await db.teams.create_index("id", unique=True)
        await db.teams.create_index("name")
        await db.teams.create_index("team_type")
        await db.teams.create_index("tags")
        await db.teams.create_index("status")
        await db.teams.create_index([("status", 1), ("name", 1)], name="status_name_1")
        await db.teams.create_index([("name", "text"), ("title", "text")])
        await db.teams.create_index("old_urls")
        
        # Shows indexes
        await db.shows.create_index("slug", unique=True)
        await db.shows.create_index("id", unique=True)
        await db.shows.create_index("name")
        await db.shows.create_index("tags")
        await db.shows.create_index("status")
        await db.shows.create_index("old_urls")
        
        # Articles indexes
        await db.articles.create_index("slug", unique=True)
        await db.articles.create_index("tags")
        await db.articles.create_index("status")
        await db.articles.create_index("published_at")
        await db.articles.create_index("featured")
        await db.articles.create_index([("title", "text")])
        
        # News indexes
        await db.news.create_index("slug", unique=True)
        await db.news.create_index("tags")
        await db.news.create_index("status")
        await db.news.create_index("published_at")
        
        # Quizzes indexes
        await db.quizzes.create_index("slug", unique=True)
        await db.quizzes.create_index("tags")
        await db.quizzes.create_index("status")
        
        # Wiki indexes
        await db.wiki.create_index("slug", unique=True)
        await db.wiki.create_index("tags")
        await db.wiki.create_index("status")
        await db.wiki.create_index([("title", "text")])
        
        # Users indexes
        await db.users.create_index("email", unique=True, sparse=True)
        await db.users.create_index("username", unique=True)
        await db.users.create_index("oauth.vk_id", sparse=True)
        await db.users.create_index("oauth.yandex_id", sparse=True)
        
        # Comments indexes
        await db.comments.create_index([("resource_type", 1), ("resource_id", 1)])
        await db.comments.create_index("user_id")
        await db.comments.create_index("parent_id")
        await db.comments.create_index("created_at")
        
        # Tags indexes
        await db.tags.create_index("slug", unique=True)
        await db.tags.create_index("name", unique=True)
        await db.tags.create_index("usage_count")
        await db.tags.create_index([("usage_count", -1)], name="usage_count_desc")
        await db.tags.create_index("type")
        
        # KVN indexes (основная коллекция — самая нагруженная)
        await db.kvn.create_index("full_path", unique=True, sparse=True)
        await db.kvn.create_index("slug")
        await db.kvn.create_index("id", unique=True)
        await db.kvn.create_index([("parent_id", 1), ("status", 1)], name="parent_id_status_1")
        await db.kvn.create_index(
            [("season_data.league_slug", 1), ("season_data.year", 1)],
            sparse=True,
            name="league_slug_year_1"
        )
        await db.kvn.create_index("status")
        await db.kvn.create_index("old_urls")
        
        # Media indexes
        await db.media.create_index("url")
        await db.media.create_index("uploaded_at")
        await db.media.create_index("status")
        
        # Templates indexes
        await db.templates.create_index("name", unique=True)
        await db.templates.create_index("content_type")
        
        # Sections indexes
        await db.sections.create_index("slug")
        await db.sections.create_index("full_path", unique=True)
        await db.sections.create_index("parent_id")
        await db.sections.create_index("level")
        await db.sections.create_index("status")
        await db.sections.create_index("in_main_menu")
        await db.sections.create_index("tags")
        await db.sections.create_index([("title", "text")])
        
        # Cities indexes
        await db.cities.create_index("slug", unique=True)
        await db.cities.create_index("title")
        await db.cities.create_index("name")
        await db.cities.create_index("tags")
        await db.cities.create_index("status")
        await db.cities.create_index([("title", "text"), ("name", "text")])
        
        logger.info("MongoDB indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")


# Create FastAPI app
app = FastAPI(
    title="Humorpedia API",
    description="API для энциклопедии российского юмора и КВН",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False  # Disable trailing slash redirects to avoid HTTP/HTTPS issues
)

# Create API router
api_router = APIRouter(prefix="/api")


# Health check
@api_router.get("/")
async def root():
    return {"message": "Humorpedia API", "version": "1.0.0"}


@api_router.get("/health")
async def health_check():
    return {"status": "healthy"}


# Import and include routers
# Content routes (split from monolithic content.py)
from routes.content_people import router as content_people_router
from routes.content_teams import router as content_teams_router
from routes.content_shows import router as content_shows_router
from routes.content_kvn import router as content_kvn_router
from routes.content_articles import router as content_articles_router
from routes.content_news import router as content_news_router
from routes.content_quizzes import router as content_quizzes_router
from routes.content_wiki import router as content_wiki_router
from routes.content_search import router as content_search_router

from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.tags import router as tags_router
from routes.comments import router as comments_router
from routes.media import router as media_router
from routes.templates import router as templates_router
from routes.sections import router as sections_router
from routes.mongo_admin import router as mongo_admin_router
from routes.cities import router as cities_router
from routes.redirects import router as redirects_router

# Content routes (order matters — specific routes before generic catch-alls)
api_router.include_router(content_articles_router)
api_router.include_router(content_news_router)
api_router.include_router(content_quizzes_router)
api_router.include_router(content_wiki_router)
api_router.include_router(content_people_router)
api_router.include_router(content_teams_router)
api_router.include_router(content_shows_router)
api_router.include_router(content_kvn_router)
api_router.include_router(content_search_router)

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(tags_router)
api_router.include_router(comments_router)
api_router.include_router(media_router)
api_router.include_router(templates_router)
api_router.include_router(sections_router)
api_router.include_router(mongo_admin_router)
api_router.include_router(cities_router)
api_router.include_router(redirects_router)


# Statistics endpoint
@api_router.get("/stats")
async def get_stats(request: Request):
    """Get site statistics"""
    db = await get_db()
    
    stats = {
        "people": await db.people.count_documents({"status": "published"}),
        "teams": await db.teams.count_documents({"status": "published"}),
        "shows": await db.shows.count_documents({"status": "published"}),
        "articles": await db.articles.count_documents({"status": "published"}),
        "news": await db.news.count_documents({"status": "published"}),
        "quizzes": await db.quizzes.count_documents({"status": "published"}),
        "wiki": await db.wiki.count_documents({"status": "published"}),
        "sections": await db.sections.count_documents({"status": "published"}),
        "cities": await db.cities.count_documents({"status": "published"}),
        "users": await db.users.count_documents({"active": True}),
        "comments": await db.comments.count_documents({"deleted": False}),
        "tags": await db.tags.count_documents({})
    }
    
    return stats


# Random content endpoint
@api_router.get("/random/{content_type}")
async def get_random_content(content_type: str, request: Request):
    """Get random content item"""
    db = await get_db()
    
    collection_map = {
        "person": db.people,
        "team": db.teams,
        "show": db.shows,
        "article": db.articles,
        "news": db.news,
        "quiz": db.quizzes,
        "wiki": db.wiki
    }
    
    if content_type not in collection_map:
        return {"error": "Unknown content type"}
    
    collection = collection_map[content_type]
    
    # Get random document
    pipeline = [
        {"$match": {"status": "published"}},
        {"$sample": {"size": 1}},
        {"$project": {"_id": 1, "title": 1, "slug": 1, "content_type": 1}}
    ]
    
    result = await collection.aggregate(pipeline).to_list(1)
    
    if not result:
        return {"error": "No content found"}
    
    return result[0]


# Include router in app
app.include_router(api_router)


# Static files for uploads
uploads_dir = Path(os.environ.get("UPLOAD_DIR", "/app/uploads"))
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Static files for imported media (from migration)
# Frontend references files like: /media/imported/images/people/...
imported_media_dir = Path("/app/frontend/public/media")
if imported_media_dir.exists():
    app.mount("/media", StaticFiles(directory=str(imported_media_dir)), name="media")

# Static files for Docker volume images (site images)
# Files accessible via https://humorpedia.ru/images/kvn-team/maximum.jpg
images_dir = Path("/app/images")
if images_dir.exists():
    app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")


# CORS middleware
cors_origins = os.environ.get('CORS_ORIGINS', '*')
if cors_origins == '*':
    allow_origins = ['*']
else:
    allow_origins = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Validation error handler
from fastapi.exceptions import RequestValidationError
from fastapi import status

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with detailed messages"""
    errors = exc.errors()
    logger.error(f"Validation error: {errors}")
    logger.error(f"Request path: {request.url.path}")
    logger.error(f"Request method: {request.method}")
    
    # Try to get body if available
    body = None
    try:
        body_bytes = await request.body()
        if body_bytes:
            import json
            body = json.loads(body_bytes.decode())
    except:
        pass
    
    logger.error(f"Request body: {body}")
    
    # Ensure CORS headers are included in validation error responses
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors, "body": body},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")
    logger.error(f"Request path: {request.url.path}")
    logger.error(f"Request method: {request.method}")
    # Ensure CORS headers are included in error responses
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
