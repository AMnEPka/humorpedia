"""GET-only experimental HTML router; never registered by the production app."""
import logging
from urllib.parse import unquote
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from services.public_html import load_html_page, render_html_page
from utils.database import get_db

logger = logging.getLogger(__name__)

def error_response(status):
    text = "Страница не найдена" if status == 404 else "Страница недоступна"
    return HTMLResponse(f'<!doctype html><html lang="ru"><head><meta name="robots" content="noindex,follow"><title>{text}</title></head><body><h1>{text}</h1></body></html>',
                        status_code=status, headers={"Cache-Control":"no-store","X-Robots-Tag":"noindex,follow"})

def create_router(*, run_id, db_name, indexing_enabled, render_page=render_html_page):
    router = APIRouter()
    options = dict(site_origin="https://humorpedia.ru", indexing_enabled=indexing_enabled, default_image_url="/media/pilot-share.png")

    def response(page, redirect=False):
        headers = {"Cache-Control":"no-store","X-Robots-Tag":page.metadata.robots}
        if redirect:
            return RedirectResponse(page.metadata.canonical_url, status_code=301, headers=headers)
        return HTMLResponse(render_page(page), headers=headers)

    async def legacy(request):
        from services.public_html_dispatch import lookup_legacy
        result = await lookup_legacy(request.url.path.rstrip("/") or "/", options=options,
                                     get_database=get_db, load_page=load_html_page)
        if result.kind == "redirect":
            return response(result.page, redirect=True)
        if result.kind == "unavailable":
            return error_response(503)
        raise HTTPException(404)

    async def record(kind, slug, request):
        try:
            page = await load_html_page(kind, slug, **options)
        except HTTPException as error:
            if error.status_code == 404:
                return await legacy(request)
            raise
        return response(page, redirect=request.url.path != unquote(page.canonical_path))

    async def guarded(coroutine):
        try:
            return await coroutine
        except HTTPException:
            raise
        except Exception:
            logger.exception("HTML pilot read failed")
            return error_response(503)

    @router.get("/__html_pilot__/status")
    async def status():
        return JSONResponse({"run_id":run_id,"database":db_name,"indexing_enabled":indexing_enabled},
                            headers={"Cache-Control":"no-store","X-Robots-Tag":"noindex,follow"})

    @router.get("/people/{slug}")
    async def person(slug: str, request: Request):
        return await guarded(record("people", slug, request))

    @router.get("/articles/{slug}")
    async def article(slug: str, request: Request):
        return await guarded(record("articles", slug, request))

    @router.get("/{path:path}")
    async def old_url(path: str, request: Request):
        return await guarded(legacy(request))
    return router
