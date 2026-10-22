"""Optional native HTML registration. The existing application owns every writer."""
import logging
from urllib.parse import unquote
from fastapi import APIRouter, FastAPI, HTTPException, Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from services.public_html import load_html_page
from services.html_react_shell import render_react_shell
from services.public_html_dispatch import metadata_options, resolve_legacy_html
from services.public_html_release import load_html_release, ReleaseError
from routes.html_pilot import error_response
from services.search_discovery import render_robots, render_sitemap, SitemapError
from utils.database import get_db

logger = logging.getLogger(__name__)

def register_public_html(app: FastAPI, settings) -> None:
    if not settings.enabled:
        return
    app.state.public_html_settings = settings
    app.state.html_page_metadata = metadata_options(settings)
    try:
        app.state.public_html_release = load_html_release(settings.build_dir)
    except ReleaseError:
        logger.exception("Public HTML release validation failed")
        app.state.public_html_release = None
    router = APIRouter()
    options = metadata_options(settings)

    def matching(request):
        release = app.state.public_html_release
        return release is not None and request.headers.get("X-Humorpedia-Release") == release.release_id

    def response(page, *, redirect=False):
        headers = {"Cache-Control":"no-store", "X-Robots-Tag":page.metadata.robots}
        if redirect:
            return RedirectResponse(page.metadata.canonical_url, status_code=301, headers=headers)
        return HTMLResponse(render_react_shell(page, app.state.public_html_release.template_html), headers=headers)

    async def detail(kind, slug, request):
        if not matching(request):
            return error_response(503)
        try:
            try:
                page = await load_html_page(kind, slug, **options)
            except HTTPException as exc:
                if exc.status_code != 404:
                    raise
                # ASGI request.path is already decoded; resolver takes the original URI.
                raw = request.scope.get("raw_path", request.url.path.encode()).decode("ascii")
                legacy = await resolve_legacy_html(raw, settings=settings)
                return response(legacy.page, redirect=True) if legacy.kind == "redirect" else error_response(
                    503 if legacy.kind == "unavailable" else 404)
            return response(page, redirect=request.url.path != unquote(page.canonical_path))
        except Exception:
            logger.exception("Public HTML read failed")
            return error_response(503)

    @router.api_route("/people/{slug}", methods=["GET", "HEAD"])
    @router.api_route("/people/{slug}/", methods=["GET", "HEAD"], include_in_schema=False)
    async def person(slug: str, request: Request):
        result = await detail("people", slug, request)
        if request.method == "HEAD": result.body = b""
        return result

    @router.api_route("/articles/{slug}", methods=["GET", "HEAD"])
    @router.api_route("/articles/{slug}/", methods=["GET", "HEAD"], include_in_schema=False)
    async def article(slug: str, request: Request):
        result = await detail("articles", slug, request)
        if request.method == "HEAD": result.body = b""
        return result

    @router.get("/_internal/public-html/state", include_in_schema=False)
    async def state(request: Request):
        if not matching(request):
            return error_response(503)
        return JSONResponse({"status":"ready", "indexing_enabled":settings.indexing_enabled},
            headers={"Cache-Control":"no-store", "X-Humorpedia-Release":app.state.public_html_release.release_id})

    @router.api_route("/_internal/public-html/dispatch", methods=["GET", "HEAD"], include_in_schema=False)
    async def dispatch(request: Request):
        if not matching(request):
            return error_response(503)
        result = await resolve_legacy_html(request.headers.get("X-Humorpedia-Original-URI", ""), settings=settings)
        if result.kind == "redirect":
            result_response = response(result.page, redirect=True)
        elif result.kind == "no_match":
            result_response = Response(status_code=418, headers={"Cache-Control":"no-store"})
        else:
            result_response = error_response(404 if result.kind == "known_unavailable" else 503)
        if request.method == "HEAD":
            result_response.body = b""
        return result_response

    @router.api_route("/robots.txt", methods=["GET", "HEAD"])
    async def robots(request: Request):
        if not matching(request):
            return error_response(503)
        return Response("" if request.method == "HEAD" else render_robots(settings),
            media_type="text/plain; charset=utf-8", headers={"Cache-Control":"no-store"})

    @router.api_route("/sitemap.xml", methods=["GET", "HEAD"])
    async def sitemap(request: Request):
        if not matching(request):
            return error_response(503)
        try:
            # Closed crawl never touches Mongo.
            data = await render_sitemap(await get_db() if settings.indexing_enabled else None, settings=settings)
            return Response(b"" if request.method == "HEAD" else data, media_type="application/xml; charset=utf-8",
                headers={"Cache-Control":"no-store"})
        except Exception:
            logger.exception("Sitemap unavailable")
            return error_response(503)

    app.include_router(router)
