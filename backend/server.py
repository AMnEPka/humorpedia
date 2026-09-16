"""
Humorpedia API Server
Main FastAPI application with modular content management
"""
from fastapi import FastAPI, APIRouter, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

IS_PRODUCTION = os.environ.get("ENVIRONMENT") == "production"

# Rate limiter (общий экземпляр, default 1000/мин на IP)
from utils.rate_limit import limiter

# Use the single DB connection from utils.database (no duplication)
from utils.database import get_db, close_db
from utils.auth import require_admin, SAFE_METHODS
from services.admin_bootstrap import ensure_admin_from_env


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
    
    # Первый администратор из ADMIN_EMAIL / ADMIN_PASSWORD (если админов ещё нет)
    await ensure_admin_from_env(db)
    
    # Запускаем батчевый счётчик просмотров
    from services.views_counter import views_counter
    await views_counter.start(db)

    db_name = os.environ.get('DB_NAME', 'humorpedia')
    logger.info(f"Connected to MongoDB: {db_name}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await views_counter.stop()
    await close_db()


_index_failures: list[str] = []


async def _ensure_index(collection, keys, **kwargs):
    """Создать индекс; ошибка одного индекса (например, дубликаты в данных) не мешает остальным."""
    try:
        await collection.create_index(keys, **kwargs)
    except Exception as e:
        _index_failures.append(f"{collection.name}.{keys}")
        logger.error(f"Index {collection.name} {keys} {kwargs} not created: {e}")


async def create_indexes(db):
    """Create MongoDB indexes for optimal performance"""
    _index_failures.clear()
    try:
        # People indexes
        await _ensure_index(db.people, "slug", unique=True)
        await _ensure_index(db.people, "id", unique=True)
        await _ensure_index(db.people, "title")
        await _ensure_index(db.people, "full_name")
        await _ensure_index(db.people, "tags")
        await _ensure_index(db.people, "status")
        await _ensure_index(db.people, [("title", "text"), ("full_name", "text")])
        await _ensure_index(db.people, "old_urls")
        
        # Teams indexes
        await _ensure_index(db.teams, "slug", unique=True)
        await _ensure_index(db.teams, "id", unique=True)
        await _ensure_index(db.teams, "name")
        await _ensure_index(db.teams, "team_type")
        await _ensure_index(db.teams, "tags")
        await _ensure_index(db.teams, "status")
        await _ensure_index(db.teams, [("status", 1), ("name", 1)], name="status_name_1")
        await _ensure_index(db.teams, [("name", "text"), ("title", "text")])
        await _ensure_index(db.teams, "old_urls")
        
        # Shows indexes
        await _ensure_index(db.shows, "slug", unique=True)
        await _ensure_index(db.shows, "id", unique=True, sparse=True)  # у импортированных шоу поля id нет
        await _ensure_index(db.shows, "name")
        await _ensure_index(db.shows, "tags")
        await _ensure_index(db.shows, "status")
        await _ensure_index(db.shows, [("name", "text"), ("title", "text")])
        await _ensure_index(db.shows, "old_urls")
        
        # Articles indexes
        await _ensure_index(db.articles, "slug", unique=True)
        await _ensure_index(db.articles, "tags")
        await _ensure_index(db.articles, "status")
        await _ensure_index(db.articles, "published_at")
        await _ensure_index(db.articles, "featured")
        await _ensure_index(db.articles, [("title", "text")])
        
        # News indexes
        await _ensure_index(db.news, "slug", unique=True)
        await _ensure_index(db.news, "tags")
        await _ensure_index(db.news, "status")
        await _ensure_index(db.news, "published_at")
        await _ensure_index(db.news, [("title", "text")])
        
        # Quizzes indexes
        await _ensure_index(db.quizzes, "slug", unique=True)
        await _ensure_index(db.quizzes, "tags")
        await _ensure_index(db.quizzes, "status")
        
        # Wiki indexes
        await _ensure_index(db.wiki, "slug", unique=True)
        await _ensure_index(db.wiki, "tags")
        await _ensure_index(db.wiki, "status")
        await _ensure_index(db.wiki, [("title", "text")])
        
        # Users indexes
        await _ensure_index(db.users, "email", unique=True, sparse=True)
        await _ensure_index(db.users, "username", unique=True)
        await _ensure_index(db.users, "oauth.vk_id", sparse=True)
        await _ensure_index(db.users, "oauth.yandex_id", sparse=True)
        
        # Comments indexes
        await _ensure_index(db.comments, [("resource_type", 1), ("resource_id", 1)])
        await _ensure_index(db.comments, "user_id")
        await _ensure_index(db.comments, "parent_id")
        await _ensure_index(db.comments, "created_at")
        
        # Tags indexes
        await _ensure_index(db.tags, "slug", unique=True)
        await _ensure_index(db.tags, "name", unique=True)
        await _ensure_index(db.tags, "usage_count")
        await _ensure_index(db.tags, [("usage_count", -1)], name="usage_count_desc")
        await _ensure_index(db.tags, "type")
        
        # KVN indexes (основная коллекция — самая нагруженная)
        await _ensure_index(db.kvn, "full_path", unique=True, sparse=True)
        await _ensure_index(db.kvn, "slug")
        await _ensure_index(db.kvn, "id", unique=True)
        await _ensure_index(db.kvn, [("parent_id", 1), ("status", 1)], name="parent_id_status_1")
        await _ensure_index(db.kvn, 
            [("season_data.league_slug", 1), ("season_data.year", 1)],
            sparse=True,
            name="league_slug_year_1"
        )
        await _ensure_index(db.kvn, "status")
        await _ensure_index(db.kvn, [("name", "text"), ("title", "text")])
        await _ensure_index(db.kvn, "old_urls")
        
        # Media indexes
        await _ensure_index(db.media, "url")
        await _ensure_index(db.media, "uploaded_at")
        await _ensure_index(db.media, "status")
        
        # Templates indexes
        await _ensure_index(db.templates, "name", unique=True)
        await _ensure_index(db.templates, "content_type")
        
        # Sections indexes
        await _ensure_index(db.sections, "slug")
        await _ensure_index(db.sections, "full_path", unique=True)
        await _ensure_index(db.sections, "parent_id")
        await _ensure_index(db.sections, "level")
        await _ensure_index(db.sections, "status")
        await _ensure_index(db.sections, "in_main_menu")
        await _ensure_index(db.sections, "tags")
        await _ensure_index(db.sections, [("title", "text")])
        
        # Cities indexes
        await _ensure_index(db.cities, "slug", unique=True)
        await _ensure_index(db.cities, "title")
        await _ensure_index(db.cities, "name")
        await _ensure_index(db.cities, "tags")
        await _ensure_index(db.cities, "status")
        await _ensure_index(db.cities, [("title", "text"), ("name", "text")])
        
        if _index_failures:
            logger.warning(f"MongoDB indexes: {len(_index_failures)} not created: {_index_failures}")
        else:
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
@limiter.limit("100/minute")
async def root(request: Request):
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


# ─── Cache management endpoints ───────────────────────────────────────────────
from services.cache import cache_service
from services.views_counter import views_counter as vc_instance

@api_router.get("/cache/stats", dependencies=[Depends(require_admin)])
async def get_cache_stats():
    """Статистика кэша и счётчика просмотров."""
    return {
        **cache_service.stats(),
        "views_counter": vc_instance.stats(),
    }

@api_router.post("/cache/flush", dependencies=[Depends(require_admin)])
async def flush_cache():
    """Полный сброс кэшей во всех воркерах. Использовать после массовых правок БД напрямую."""
    cache_service.flush_all()
    await cache_service.invalidate_everywhere(await get_db())
    return {"success": True, "message": "All caches flushed"}

@api_router.post("/views/flush", dependencies=[Depends(require_admin)])
async def flush_views():
    """Принудительный сброс счётчика просмотров в БД."""
    count = await vc_instance.flush()
    return {"success": True, "flushed_updates": count}


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


# ─── Static files ──────────────────────────────────────────────────────────────

# Загрузки через админку: /uploads/YYYY/MM/...
uploads_dir = Path(os.environ.get("UPLOAD_DIR", "/app/uploads"))
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Импортированные из MODX картинки: /media/imported/images/...
# Основной источник — docker volume imported_images_volume (/app/media/imported/images),
# запасной — старое расположение в исходниках фронтенда.
for media_dir in (Path("/app/media"), Path("/app/frontend/public/media")):
    if media_dir.exists():
        app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")
        break

# Картинки сайта из docker volume images_volume: /images/kvn-team/maximum.jpg
images_dir = Path("/app/images")
if images_dir.exists():
    app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")


# ─── Middleware ────────────────────────────────────────────────────────────────
# Порядок: последний добавленный — внешний. Итоговая цепочка:
# CORS → SlowAPI → CacheSync → CacheControl → приложение
from starlette.middleware.base import BaseHTTPMiddleware
from services.cache import cache_service as _cache


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Cache-Control для публичных GET-ответов (кроме /auth, /admin, /cache)."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.method == "GET" and response.status_code == 200:
            path = request.url.path
            if "/auth/" not in path and "/admin/" not in path and "/cache/" not in path:
                # Публичный контент: кэшируем 60с, stale-while-revalidate 5 мин
                response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
        return response


# Записи, после которых не нужно сбрасывать кэш контента
_CACHE_NEUTRAL_PREFIXES = ("/api/auth/", "/api/views/", "/api/cache/", "/api/comments")


class CacheSyncMiddleware(BaseHTTPMiddleware):
    """
    Держит in-memory кэш согласованным между воркерами:
    перед чтением сверяет поколение кэша, после успешной записи — сбрасывает кэш везде.
    """
    async def dispatch(self, request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        db = await get_db()
        is_write = request.method not in SAFE_METHODS
        if not is_write:
            await _cache.sync_with_peers(db)

        response = await call_next(request)

        if is_write and response.status_code < 400 and not path.startswith(_CACHE_NEUTRAL_PREFIXES):
            await _cache.invalidate_everywhere(db)
        return response


app.add_middleware(CacheControlMiddleware)
app.add_middleware(CacheSyncMiddleware)

# Rate limiting: default_limits применяются ко всем эндпоинтам только через middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS. Авторизация идёт через заголовок Authorization, cookies не используются,
# поэтому credentials не нужны (и несовместимы с "*").
cors_origins = os.environ.get('CORS_ORIGINS', '*')
if cors_origins == '*':
    allow_origins = ['*']
else:
    allow_origins = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Error handlers ────────────────────────────────────────────────────────────
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi import status


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """422 с деталями валидации. Тело запроса не логируем и не возвращаем (там могут быть пароли)."""
    errors = jsonable_encoder(exc.errors(), custom_encoder={Exception: str})
    for err in errors:
        err.pop("input", None)
    logger.warning(f"Validation error {request.method} {request.url.path}: {errors}")
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": errors})


def _cors_headers_for(request: Request) -> dict:
    """500 обрабатывается снаружи CORSMiddleware — заголовки CORS добавляем вручную."""
    origin = request.headers.get("origin")
    if "*" in allow_origins:
        return {"Access-Control-Allow-Origin": "*"}
    if origin and origin in allow_origins:
        return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
    return {}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception {request.method} {request.url.path}: {exc}", exc_info=True)
    detail = "Внутренняя ошибка сервера" if IS_PRODUCTION else f"Internal server error: {exc}"
    return JSONResponse(status_code=500, content={"detail": detail}, headers=_cors_headers_for(request))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
