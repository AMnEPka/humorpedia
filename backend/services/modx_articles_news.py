"""Build article and news payloads from the legacy MODX dump.

The returned payloads match the public/admin content models. Legacy-only fields
(`old_id`, `old_urls`, original timestamps and rating counters) are returned in
``extra`` so an import script can add them after the normal CRUD path runs.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from services.modx_content import LinkMapper, clean_html, image_url, is_blank_html, plain_text
from services.modx_dump import ModxSite
from services.modx_people import _module, _timestamp


CONTENT_CONFIG = {
    "news": {"parent_id": 14, "template": 7, "path": "news"},
    "article": {"parent_id": 29, "template": 13, "path": "articles"},
}

_IGNORED_SECTIONS = {
    "ad_250", "ad_block_120", "all_articles", "article_header", "comments",
    "news_header", "popular_articles", "post_footer", "related_articles",
    "table_of_contents", "tags",
}
_PERSON_LINK_RE = re.compile(r'href=["\']/people/([^"\'/#?]+)', re.I)
_BLOB_IMAGE_RE = re.compile(r'<img\b[^>]*\bsrc=["\']blob:[^"\']*["\'][^>]*>', re.I)
_IMAGE_FILE_RE = re.compile(r"\.(?:avif|gif|jpe?g|png|svg|webp)(?:[?#].*)?$", re.I)
_IMAGE_OVERRIDES = {
    # MODX stored a generated phpThumb cache URL, while its source JPEG is present in the media archive.
    "https://humorpedia.ru/assets/components/phpthumbof/cache/"
    "000003.e2aeb0a67a81d3ad204fc179c1ae15e3.webp": "images/article/000003.jpg",
}


def content_resources(site: ModxSite, kind: str, *, include_unpublished: bool = False) -> List[dict]:
    """Return non-deleted direct children of the legacy article/news section."""
    config = CONTENT_CONFIG[kind]
    return [
        resource for resource in site.resources.values()
        if resource.get("parent") == config["parent_id"]
        and resource.get("template") == config["template"]
        and not resource.get("deleted")
        and (include_unpublished or resource.get("published"))
    ]


def content_url_builder(site: ModxSite, kind: str):
    """Return a LinkMapper builder for legacy article/news resources."""
    config = CONTENT_CONFIG[kind]

    def build(resource: dict) -> Optional[str]:
        if (resource.get("parent") != config["parent_id"]
                or resource.get("template") != config["template"]):
            return None
        slug = str(resource.get("alias") or "").strip("/")
        return f"/{config['path']}/{slug}" if slug else None

    return build


def _excerpt(resource: dict, modules: List[dict], limit: int = 320) -> str:
    description = plain_text(resource.get("description") or "")
    if description:
        return description
    for module in modules:
        if module["type"] == "text_block":
            text = plain_text(module["data"].get("content") or "")
        elif module["type"] == "quote":
            text = plain_text(module["data"].get("text") or "")
        else:
            continue
        if text:
            return text if len(text) <= limit else text[:limit].rstrip() + "…"
    return ""


def _legacy_image(value: str, field: str, warnings: List[str]) -> Optional[str]:
    """Convert a legacy image path, rejecting labels accidentally stored in image TVs."""
    value = str(value or "").strip()
    if not value:
        return None
    value = _IMAGE_OVERRIDES.get(value, value)
    if not _IMAGE_FILE_RE.search(value):
        warnings.append(f"поле {field} не похоже на путь к изображению: {value}")
        return None
    return image_url(value)


def _content_modules(site: ModxSite, resource_id: int, mapper: Optional[LinkMapper]) -> Tuple[List[dict], List[str]]:
    modules: List[dict] = []
    warnings: List[str] = []

    for section in site.migx_sections(resource_id):
        form = section.get("MIGX_formname")
        if section.get("hide_section") in (1, "1", True):
            continue
        if form in ("text", "table"):
            raw_html = section.get("content") or ""
            if _BLOB_IMAGE_RE.search(raw_html):
                warnings.append("встроенное blob:-изображение удалено: исходного файла нет в дампе")
                raw_html = _BLOB_IMAGE_RE.sub("", raw_html)
            html = clean_html(raw_html, mapper)
            if is_blank_html(html):
                continue
            title = plain_text(section.get("title") or "") if form == "text" else ""
            modules.append(_module("text_block", len(modules) + 1, title,
                                   {"title": title, "content": html}))
        elif form == "quote":
            text = plain_text(clean_html(section.get("content") or "", mapper))
            if text:
                author = plain_text(section.get("title") or "") or None
                modules.append(_module("quote", len(modules) + 1, "",
                                       {"text": text, "author": author, "source": None}))
        elif form == "voting":
            old_poll_id = str(section.get("vote") or "").strip()
            if old_poll_id.isdigit():
                modules.append(_module(
                    "poll", len(modules) + 1, section.get("section_name") or "Опрос",
                    {"poll_id": f"legacy-poll-{old_poll_id}"},
                ))
            else:
                warnings.append("секция опроса не содержит корректный идентификатор")
        elif form not in _IGNORED_SECTIONS:
            warnings.append(f"секция «{form}» не перенесена")

    if not modules:
        fallback = clean_html(site.resources[resource_id].get("content") or "", mapper)
        if not is_blank_html(fallback):
            modules.append(_module("text_block", 1, "", {"title": "", "content": fallback}))
        else:
            warnings.append("на странице нет текста")
    return modules, warnings


def build_content(
    site: ModxSite,
    resource_id: int,
    kind: str,
    mapper: Optional[LinkMapper] = None,
    author_names: Optional[Dict[int, str]] = None,
) -> Tuple[dict, dict, List[str]]:
    """Build an ArticleCreate/NewsCreate payload plus legacy-only fields."""
    if kind not in CONTENT_CONFIG:
        raise ValueError(f"Unsupported content kind: {kind}")
    resource = site.resources[resource_id]
    config = CONTENT_CONFIG[kind]
    if resource.get("parent") != config["parent_id"] or resource.get("template") != config["template"]:
        raise ValueError(f"Resource {resource_id} is not a legacy {kind}")

    title = plain_text(resource.get("pagetitle") or "")
    slug = str(resource.get("alias") or "").strip("/")
    published = bool(resource.get("published")) and not resource.get("deleted")
    modules, warnings = _content_modules(site, resource_id, mapper)
    missing_tag_ids = [part.strip() for part in site.tv(resource_id, "tags").split("||")
                       if part.strip().isdigit() and int(part.strip()) not in site.tags]
    if missing_tag_ids:
        warnings.append(f"в дампе нет тегов с id: {', '.join(missing_tag_ids)}")
    excerpt = _excerpt(resource, modules)

    cover_image = None
    header_url = _legacy_image(site.tv(resource_id, "img"), "img", warnings)
    preview_url = _legacy_image(site.tv(resource_id, "preview"), "preview", warnings) if kind == "article" else None
    cover_url = preview_url or header_url
    if cover_url:
        alt = plain_text(site.tv(resource_id, "img_alt")) or title
        cover_image = {"url": cover_url, "alt": alt, "caption": "", "thumbnail": cover_url}
    if kind == "article" and header_url and header_url != cover_url:
        modules.insert(0, _module("image", 1, "", {"url": header_url, "caption": ""}))
        for order, module in enumerate(modules, start=1):
            module["order"] = order

    meta_title = plain_text(resource.get("longtitle") or "") or title
    payload = {
        "title": title,
        "slug": slug,
        "status": "published" if published else "draft",
        "excerpt": excerpt or None,
        "cover_image": cover_image,
        "modules": modules,
        "tags": site.tags_of(resource_id),
        "seo": {
            "meta_title": meta_title,
            "meta_description": plain_text(resource.get("description") or "") or excerpt,
            "keywords": [k.strip() for k in (resource.get("keywords") or "").split(",") if k.strip()],
        },
        "related_person_ids": [],
    }

    if kind == "article":
        author_id = int(resource.get("createdby") or 0)
        payload.update({
            "author_name": (author_names or {}).get(author_id) or None,
            "featured": bool(resource.get("popular")),
        })
    else:
        payload.update({
            "content": "\n".join(
                module["data"]["content"] for module in modules if module["type"] == "text_block"
            ) or None,
            "important": bool(resource.get("popular")),
        })

    votes = int(resource.get("votes") or 0)
    extra = {
        "old_id": int(resource_id),
        "old_urls": ["/" + str(resource["uri"]).strip("/")] if resource.get("uri") else [],
        "rating": round(min(10.0, max(0.0, float(resource.get("rating") or 0))), 2),
        "votes_count": votes,
    }
    created_at = _timestamp(resource.get("createdon"))
    updated_at = _timestamp(resource.get("editedon"))
    published_at = (_timestamp(resource.get("publishedon")) or created_at) if published else None
    if created_at:
        extra["created_at"] = created_at
    if updated_at:
        extra["updated_at"] = updated_at
    if published_at:
        extra["published_at"] = published_at
    return payload, extra, warnings


def person_slugs_in_modules(modules: List[dict]) -> List[str]:
    """Collect stable person slugs from rewritten links in content modules."""
    slugs: List[str] = []
    for module in modules:
        data = module.get("data") or {}
        value = data.get("content") or ""
        for slug in _PERSON_LINK_RE.findall(value):
            if slug not in slugs:
                slugs.append(slug)
    return slugs
