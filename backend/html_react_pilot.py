"""Guarded HTML/React experiment; no production startup, imports or scheduling."""
from contextlib import asynccontextmanager
import importlib
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.routing import APIRoute
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.staticfiles import StaticFiles
from html_pilot import create_app as create_html_app
from routes.html_pilot import error_response
from services.html_react_shell import render_react_shell
from services.views_counter import views_counter
from utils.database import get_db
from utils.rate_limit import limiter

# Existing route objects retain dependencies and validation; never include a whole writer router.
_PUBLIC = {
    "content_people": {("/content/people/{id_or_slug}", "GET")},
    "content_articles": {("/content/articles/{id_or_slug}", "GET"), ("/content/articles", "GET")},
    "sections": {("/sections", "GET")},
    "memberships": {("/competitions/people/{id_or_slug}/career", "GET")},
    "show_appearances": {("/show-appearances/people/{person_id}", "GET")},
    "recommendations": {("/recommendations", "GET")},
    "related_news": {("/related-news/{entity_type}/{entity_id}", "GET")},
    "ratings": {("/ratings/{entity_type}/{entity_id}", "GET"), ("/ratings/{entity_type}/{entity_id}", "PUT")},
    "polls": {("/polls/{poll_id}", "GET"), ("/polls/{poll_id}/vote", "POST")},
    "correction_suggestions": {("/correction-suggestions", "POST")},
    "auth": {("/auth/login", "POST"), ("/auth/me", "GET")},
}

def create_app():
    if os.environ.get("HTML_REACT_PILOT_ENABLED") != "1":
        raise ValueError("HTML/React pilot must be explicitly enabled")
    build = Path(os.environ.get("HTML_REACT_BUILD_DIR", "")).resolve()
    if not (build / "index.html").is_file():
        raise ValueError("Owned frontend build directory is required")
    template = (build / "index.html").read_text(encoding="utf-8-sig")
    app = create_html_app(render_page=lambda page: render_react_shell(page, template))
    app.state.html_page_metadata = dict(site_origin="https://humorpedia.ru",
        indexing_enabled=os.environ.get("HTML_PILOT_INDEXING_ENABLED") == "1",
        default_image_url="/media/pilot-share.png")
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            await views_counter.start(await get_db())
            try:
                yield
            finally:
                await views_counter.stop()
    app.router.lifespan_context = lifespan
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, error):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": error.detail}, status_code=error.status_code,
                                headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex,follow"})
        return error_response(error.status_code)

    @app.middleware("http")
    async def no_store(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        if "X-Robots-Tag" not in response.headers:
            response.headers["X-Robots-Tag"] = "noindex,follow"
        return response

    # Catch-all is always last, after public API/config/static/known SPA paths.
    legacy = app.router.routes.pop()
    api = APIRouter()
    for name, allowed in _PUBLIC.items():
        router = importlib.import_module("routes." + name).router
        found = set()
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            methods = {(route.path, method) for method in route.methods}
            if methods & allowed:
                if not methods <= allowed:
                    raise ValueError("Unexpected methods on public route")
                api.routes.append(route)
                found.update(methods)
        if found != allowed:
            raise ValueError("Missing public pilot route: " + name + repr(allowed - found))
    app.include_router(api, prefix="/api")

    @app.get("/config.js")
    async def config():
        return Response("window.__HTML_PILOT__ = true;\nwindow.__BACKEND_URL__ = window.location.origin;",
                        media_type="text/javascript")
    if (build / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(build / "assets")), name="pilot-assets")
    for path in ("/", "/people", "/articles", "/news"):
        async def spa():
            return Response(template, media_type="text/html")
        app.add_api_route(path, spa, methods=["GET"], include_in_schema=False)
    for filename in ("favicon.ico", "logo192.png", "logo512.png", "manifest.json"):
        if (build / filename).is_file():
            def fixed_asset(path):
                async def asset():
                    return FileResponse(path)
                return asset
            app.add_api_route("/" + filename, fixed_asset(build / filename), methods=["GET"], include_in_schema=False)
    app.router.routes.append(legacy)
    return app
