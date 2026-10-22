"""Read-only text projection shared by the isolated HTML pilots."""
from copy import deepcopy
from dataclasses import dataclass
from html import escape
import re
from urllib.parse import urlsplit

from fastapi import HTTPException
from models.module_contract import MODULE_CONTRACT
from services.crud import get_by_id_or_slug
from services.foreign_agent_notices import decorate_document, NOTICE_TEXT
from services.html_text import parse_text, normalize_person_rich_text
from services.link_resolver import LinkResolver
from services.page_metadata import PageMetadata, build_page_metadata

_SIDEBAR = {m["type"] for m in MODULE_CONTRACT if m.get("rendering", {}).get("placement") == "sidebar"}
_TEXT_TYPES = {"text_block", "quote", "timeline"}
_HAS_HTML = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")

@dataclass(frozen=True)
class TextBlock:
    heading: str
    body_text: str
    anchor_id: str | None = None

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
    header_image = kind == "articles" and visible and visible[0].get("type") == "image"
    basis = visible[1:] if header_image else raw
    selected = visible[1:] if header_image else visible
    selected = [m for m in selected if m.get("type") not in _SIDEBAR]
    blocks, links = [], []
    person = kind == "people"

    def rich(heading, content, anchor=None, as_html=True):
        if as_html:
            text, found = parse_text(content)
            links.extend(found)
        else:
            text = _text(content)
        if heading or text or anchor:
            blocks.append(TextBlock(_text(heading), text, anchor))

    def normalize(value):
        return normalize_person_rich_text(value) if person else value

    for index, module in enumerate(selected):
        data = module.get("data") or {}
        kind_name = module.get("type")
        if kind_name == "text_block":
            title = data.get("title") or ("Подробнее" if not person and data.get("collapsed") else "")
            anchor = f"section-{index}" if person else (data.get("anchor_id") or re.sub(r"\s+", "-", _text(data.get("title")).lower()) or None)
            rich(title, normalize(data.get("content")), anchor)
        elif kind_name == "quote":
            text = _text(data.get("text"))
            author = _text(data.get("author"))
            blocks.append(TextBlock("", text + (" — " + author if author else "")))
        elif kind_name == "timeline":
            title = data.get("title") or ("Хронология" if person else "")
            period = _text(data.get("period")) if person else ""
            rich(" ".join(filter(None, [period, _text(title)])), "", f"timeline-{index}" if person else None)
            events = data.get("events") or []
            for number, event in enumerate(events):
                heading = " ".join(filter(None, [_text(event.get("date") or event.get("year")), _text(event.get("title"))]))
                description = normalize(event.get("description") or "")
                rich(heading, description, f"timeline-{index}-event-{number}" if person else None,
                     bool(_HAS_HTML.search(description)))
            if person and not events:
                content = data.get("content_html") or normalize(data.get("content") or "")
                rich("", content, as_html=bool(data.get("content_html") or _HAS_HTML.search(content)))
        elif kind_name == "text" and person:
            content = data.get("content_html") or normalize(data.get("content") or "")
            rich("", content, f"text-{index}", bool(data.get("content_html") or _HAS_HTML.search(content)))
    if kind == "articles" and not basis and document.get("content"):
        rich("", document["content"])
    excerpt = _text(document.get("excerpt"))
    if excerpt:
        blocks.insert(0, TextBlock("", excerpt))
    notices = (NOTICE_TEXT,) if document.get("foreign_agent_notice") else ()
    heading = _text(document.get("title")) or _text(document.get("name")) or "Humorpedia"
    if person and document.get("foreign_agent"):
        heading += "*"
    supported = _TEXT_TYPES | ({"text"} if person else set())
    return HtmlPage(metadata, heading, tuple(blocks), tuple(dict.fromkeys(links)), notices,
                    urlsplit(metadata.canonical_url).path,
                    tuple(dict.fromkeys(m.get("type", "unknown") for m in selected if m.get("type") not in supported)))

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
        anchor = f' id="{escape(str(block.anchor_id), quote=True)}"' if block.anchor_id is not None else ""
        head.append(f"<section{anchor}>")
        if block.heading:
            head.append(f'<h2>{escape(block.heading)}</h2>')
        if block.body_text:
            head.append(f'<p>{escape(block.body_text)}</p>')
        head.append("</section>")
    head.extend(f'<p role="note">{escape(note)}</p>' for note in page.notices)
    head.append('</article>')
    if page.links:
        head.append('<nav aria-label="Ссылки в тексте"><ul>')
        head.extend(f'<li><a href="{escape(url, quote=True)}">{escape(label)}</a></li>' for label, url in page.links)
        head.append('</ul></nav>')
    head.append('</main></body></html>')
    return "".join(head)
