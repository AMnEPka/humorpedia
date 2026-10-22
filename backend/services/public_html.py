"""Read-only text projection for the isolated person/article HTML pilot."""
from copy import deepcopy
from dataclasses import dataclass
from html import escape
from fastapi import HTTPException

from models.module_contract import MODULE_CONTRACT
from services.crud import get_by_id_or_slug
from services.foreign_agent_notices import decorate_document, NOTICE_TEXT
from services.html_text import parse_text
from services.link_resolver import LinkResolver
from services.page_metadata import PageMetadata, build_page_metadata

_SIDEBAR = {m["type"] for m in MODULE_CONTRACT if m.get("rendering", {}).get("placement") == "sidebar"}
_TEXT_TYPES = {"text_block", "quote", "timeline"}

@dataclass(frozen=True)
class TextBlock:
    heading: str
    body_text: str

@dataclass(frozen=True)
class HtmlPage:
    metadata: PageMetadata
    heading: str
    blocks: tuple[TextBlock, ...]
    links: tuple[tuple[str, str], ...]
    notices: tuple[str, ...]
    canonical_path: str
    unsupported_types: tuple[str, ...]

def _text(value):
    return " ".join(value.split()) if isinstance(value, str) else ""

async def load_html_page(kind, slug, *, site_origin, indexing_enabled, default_image_url):
    document = deepcopy(await get_by_id_or_slug(kind, slug, "Page not found", increment_views=False, editor=False))
    if document.get("status") not in {None, "", "published", "draft"}:
        raise HTTPException(status_code=404, detail="Page not found")
    await LinkResolver.resolve_document(document)
    await decorate_document(document)
    metadata = build_page_metadata(kind, document, site_origin=site_origin, indexing_enabled=indexing_enabled, default_image_url=default_image_url)
    raw = document.get("modules") or []
    visible = sorted((m for m in raw if m.get("visible") is not False), key=lambda m: m.get("order") or 0)
    # Article removes its first visible header image before deciding the legacy fallback.
    header_image = kind == "articles" and visible and visible[0].get("type") == "image"
    basis = visible[1:] if header_image else raw
    selected = visible[1:] if header_image else visible
    selected = [m for m in selected if m.get("type") not in _SIDEBAR]
    blocks, links = [], []

    def rich(heading, content):
        text, found = parse_text(content)
        links.extend(found)
        if heading or text:
            blocks.append(TextBlock(_text(heading), text))

    for module in selected:
        data = module.get("data") or {}
        kind_name = module.get("type")
        if kind_name == "text_block":
            rich(data.get("title"), data.get("content"))
        elif kind_name == "quote":
            text = _text(data.get("text"))
            author = _text(data.get("author"))
            blocks.append(TextBlock("", text + (" — " + author if author else "")))
        elif kind_name == "timeline":
            if data.get("title"):
                blocks.append(TextBlock(_text(data["title"]), ""))
            for event in data.get("events") or []:
                heading = " ".join(filter(None, [_text(event.get("date") or event.get("year")), _text(event.get("title"))]))
                rich(heading, event.get("description"))
    if kind == "articles" and not basis and document.get("content"):
        rich("", document["content"])
    excerpt = _text(document.get("excerpt"))
    if excerpt:
        blocks.insert(0, TextBlock("", excerpt))
    # Public React pages pass only visible=flag, so the component uses its default text.
    notices = (NOTICE_TEXT,) if document.get("foreign_agent_notice") else ()
    heading = _text(document.get("title")) or _text(document.get("name")) or "Humorpedia"
    if kind == "people" and document.get("foreign_agent"):
        heading += "*"
    from urllib.parse import urlsplit
    return HtmlPage(metadata, heading, tuple(blocks), tuple(dict.fromkeys(links)), notices,
                    urlsplit(metadata.canonical_url).path,
                    tuple(dict.fromkeys(m.get("type", "unknown") for m in selected if m.get("type") not in _TEXT_TYPES)))

def render_html_page(page):
    meta = page.metadata
    def tag(key, value, attribute="property"):
        return f'<meta {attribute}="{key}" content="{escape(value, quote=True)}">'
    head = [
        '<!doctype html>', f'<html lang="{meta.lang}"><head><meta charset="utf-8">',
        f'<title>{escape(meta.title)}</title>',
        tag("description", meta.description, "name"), tag("robots", meta.robots, "name"),
        f'<link rel="canonical" href="{escape(meta.canonical_url, quote=True)}">',
        tag("og:title", meta.title), tag("og:description", meta.description),
        tag("og:url", meta.canonical_url), tag("og:type", meta.og_type),
        tag("og:image", meta.image_url), tag("og:image:alt", meta.image_alt),
        tag("og:locale", meta.locale), tag("og:site_name", "Humorpedia"),
        '</head><body><main><article>', f'<h1>{escape(page.heading, quote=True)}</h1>',
    ]
    for block in page.blocks:
        if block.heading:
            head.append(f'<h2>{escape(block.heading)}</h2>')
        if block.body_text:
            head.append(f'<p>{escape(block.body_text)}</p>')
    head.extend(f'<p role="note">{escape(note)}</p>' for note in page.notices)
    head.append('</article>')
    if page.links:
        head.append('<nav aria-label="Ссылки в тексте"><ul>')
        head.extend(f'<li><a href="{escape(url, quote=True)}">{escape(label)}</a></li>' for label, url in page.links)
        head.append('</ul></nav>')
    head.append('</main></body></html>')
    return "".join(head)
