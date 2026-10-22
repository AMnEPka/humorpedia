"""Live, bounded search discovery for the two covered public content types."""
from xml.sax.saxutils import escape
from services.page_metadata import canonical_document_url
MAX_URLS = 50000
MAX_BYTES = 52428800
class SitemapError(ValueError):
    pass

def render_robots(settings) -> str:
    if not settings.indexing_enabled:
        return "User-agent: *\nDisallow: /\n"
    return ("User-agent: *\nDisallow: /admin\nDisallow: /preview\nDisallow: /search\n"
            f"Sitemap: {settings.site_origin}/sitemap.xml\n")

async def render_sitemap(db, *, settings) -> bytes:
    parts = [b'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n']
    end = b"</urlset>\n"
    size = len(parts[0]) + len(end)
    seen = set()
    try:
        if settings.indexing_enabled:
            for kind in ("people", "articles"):
                cursor = db[kind].find({"status":"published"}, {"_id":1,"slug":1,"status":1}).sort("_id",1).batch_size(500)
                async for doc in cursor:
                    try:
                        url = canonical_document_url(kind, doc, site_origin=settings.site_origin)
                    except (ValueError, TypeError):
                        continue
                    if len(url) > 2048 or url in seen:
                        continue
                    seen.add(url)
                    line = ("<url><loc>" + escape(url) + "</loc></url>\n").encode("utf-8")
                    size += len(line)
                    if len(seen) > MAX_URLS or size > MAX_BYTES:
                        raise SitemapError("Sitemap exceeds single document limits")
                    parts.append(line)
        if size > MAX_BYTES:
            raise SitemapError("Sitemap exceeds single document limits")
        return b"".join([*parts, end])
    except SitemapError:
        raise
    except Exception as exc:
        raise SitemapError("Search discovery unavailable") from exc
