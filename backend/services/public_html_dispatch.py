"""Anonymous legacy classification, shared without exposing the pilot router."""
from dataclasses import dataclass
from typing import Literal
from urllib.parse import unquote
from fastapi import HTTPException
from routes.redirects import _try_pattern_redirect
from services.public_html import HtmlPage, load_html_page
from utils.database import get_db

@dataclass(frozen=True)
class LegacyResult:
    kind: Literal["redirect", "known_unavailable", "no_match", "unavailable"]
    page: HtmlPage | None = None

def metadata_options(settings):
    return dict(site_origin=settings.site_origin, indexing_enabled=settings.indexing_enabled,
                default_image_url=settings.default_image_url)

def legacy_path(raw_uri):
    try:
        path = unquote(raw_uri.split("?", 1)[0], errors="strict")
    except (UnicodeError, ValueError):
        return None
    if not path.startswith("/") or "\\" in path or any(ord(c) < 32 for c in path):
        return None
    first = path.lstrip("/").split("/", 1)[0].lower()
    if first in {"api", "assets", "static", "media", "uploads", "images", "admin", "preview",
                 "health", "healthz", "_internal", "__html_pilot__", "config.js", "robots.txt", "sitemap.xml"}:
        return None
    return path.rstrip("/") or "/"

async def lookup_legacy(path, *, options, get_database, load_page):
    """Path is already decoded once; do not unquote stored canonical slugs twice."""
    try:
        db = await get_database()
        for kind in ("people", "articles"):
            doc = await db[kind].find_one({"old_urls": path}, {"slug": 1})
            if doc:
                page = await load_page(kind, str(doc["_id"]), **options)
                return LegacyResult("known_unavailable") if unquote(page.canonical_path) == path else LegacyResult("redirect", page)
        target = _try_pattern_redirect(path)
        if target:
            parts = target.strip("/").split("/")
            if len(parts) == 2 and parts[0] in {"people", "articles"}:
                page = await load_page(parts[0], parts[1], **options)
                return LegacyResult("known_unavailable") if unquote(page.canonical_path) == path else LegacyResult("redirect", page)
        return LegacyResult("no_match")
    except HTTPException as exc:
        return LegacyResult("known_unavailable" if exc.status_code == 404 else "unavailable")
    except Exception:
        return LegacyResult("unavailable")

async def resolve_legacy_html(path, *, settings):
    path = legacy_path(path)
    if path is None:
        return LegacyResult("no_match")
    return await lookup_legacy(path, options=metadata_options(settings), get_database=get_db, load_page=load_html_page)
