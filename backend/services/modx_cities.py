"""Build Geography city pages from the legacy MODX dump."""
from __future__ import annotations

import html as html_lib
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from services.modx_content import LinkMapper, clean_html, image_url, is_blank_html, parse_facts_table, plain_text
from services.modx_dump import ModxSite


CITY_PARENT_ID = 34
CITY_TEMPLATE = 19
_IGNORED_SECTIONS = {"tags", "popular_articles", "post_footer", "ad_250", "ad_block_120", "table_of_contents"}
_HREF_RE = re.compile(r"\bhref\s*=\s*([\"'])(.*?)\1", re.I | re.S)
_MODX_LINK_RE = re.compile(r"^\[\[~(\d+)[^\]]*\]\]$")
_HEADING_RE = re.compile(
    r"<h([1-6])\b[^>]*>.*?</h\1\s*>"
    r"|<p\b[^>]*>\s*(?:<span\b[^>]*>\s*)?<strong\b[^>]*>.*?</strong>\s*(?:</span>\s*)?</p\s*>",
    re.I | re.S,
)
_SITE_HOSTS = {"humorpedia.ru", "www.humorpedia.ru", "dev.humorpedia.ru"}
CITY_ALIASES = {
    "Санкт-Петербург": ["Ленинград"],
    "Екатеринбург": ["Свердловск"],
}


def _timestamp(value) -> Optional[str]:
    try:
        seconds = int(value or 0)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def _module(order: int, title: str, content: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "type": "text_block",
        "order": order,
        "title": title,
        "visible": True,
        "data": {"title": title, "content": content},
    }


def city_resources(site: ModxSite, include_unpublished: bool = False) -> List[dict]:
    return [
        resource for resource in site.resources.values()
        if resource.get("parent") == CITY_PARENT_ID
        and resource.get("template") == CITY_TEMPLATE
        and not resource.get("deleted")
        and (include_unpublished or resource.get("published"))
    ]


def _linked_resources(site: ModxSite, value: str) -> List[dict]:
    """Return linked MODX resources in editorial order."""
    result = []
    seen = set()
    for match in _HREF_RE.finditer(value or ""):
        href = html_lib.unescape(match.group(2)).strip()
        modx = _MODX_LINK_RE.match(href)
        resource = site.resources.get(int(modx.group(1))) if modx else None
        if resource is None:
            parts = urlsplit(href)
            if (parts.scheme or parts.netloc) and parts.hostname not in _SITE_HOSTS:
                continue
            resource = site.resource_by_uri(parts.path.lstrip("/"))
        if resource and resource.get("id") not in seen:
            seen.add(resource["id"])
            result.append(resource)
    return result


def _relation_heading_kind(value: str) -> Optional[str]:
    """Classify a legacy heading represented by city relation cards."""
    heading = re.sub(r"\s+", " ", plain_text(value).replace("ё", "е").lower()).strip(" .:")
    normalized = re.sub(r"[«»„“\"']", "", heading)
    if (
        heading.startswith("комики из")
        or heading.startswith("юмористы из")
        or heading.startswith("известные комики")
        or heading.startswith("известные юмористы")
        or heading.startswith("известные люди")
    ):
        return "people"
    if (
        heading.startswith("команд")
        or ". команды" in heading
        or "лига город" in normalized
        or "лига смех" in normalized
        or (normalized.startswith("шоу ") and ("игра" in normalized or "концерт" in normalized))
    ):
        return "teams"
    return None


def strip_relation_sections(value: str) -> str:
    """Remove legacy people/team lists while preserving the rest of the article.

    A relation section starts at its heading and ends at the next heading. Its linked resources are
    collected before this function is called, so the same entities can be rendered once as cards.
    """
    matches = list(_HEADING_RE.finditer(value or ""))
    if not matches:
        return value or ""

    chunks = [(value or "")[:matches[0].start()]]
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value or "")
        section = (value or "")[match.start():end]
        if not _relation_heading_kind(match.group(0)):
            chunks.append(section)
    return "".join(chunks).strip()


def extract_team_mentions(value: str) -> List[dict]:
    """Extract team names from legacy lists, including entries without their own page."""
    matches = list(_HEADING_RE.finditer(value or ""))
    result = []
    seen = set()
    for index, match in enumerate(matches):
        if _relation_heading_kind(match.group(0)) != "teams":
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value or "")
        section = (value or "")[match.end():end]
        context = plain_text(match.group(0)).strip()
        for item in re.findall(r"<li\b[^>]*>(.*?)</li\s*>", section, flags=re.I | re.S):
            label = plain_text(item).strip()
            name = re.split(r"\s+[–—-]\s+", label, maxsplit=1)[0].strip(" \u00a0«»")
            key = name.replace("ё", "е").casefold()
            if name and key not in seen:
                seen.add(key)
                result.append({"name": name, "context": context})
    return result


def _relation_candidates(site: ModxSite, mapper: Optional[LinkMapper], info_html: str, all_html: str) -> dict:
    """Use the old editors' shortlist instead of inferring celebrity status from birthplace.

    People explicitly linked in the `info.content` block are the preferred shortlist. Moscow and
    Odessa have no such block, so their main article is used as a fallback. Teams are collected from
    the whole article. The importer later keeps only candidates that exist in the current database.
    """
    info_resources = _linked_resources(site, info_html)
    all_resources = _linked_resources(site, all_html)

    def target(resource: dict) -> str:
        if mapper:
            return mapper.resource_url(resource) or ""
        if resource.get("template") == 20:
            return f"/people/{resource.get('alias', '')}"
        if resource.get("template") == 21:
            return f"/kvn/teams/{resource.get('alias', '')}"
        return ""

    info_people = [r for r in info_resources if target(r).startswith("/people/")]
    people = info_people or [r for r in all_resources if target(r).startswith("/people/")]
    teams = [r for r in all_resources if target(r).startswith("/kvn/teams/") or "/teams/" in target(r)]

    def pack(resources: List[dict]) -> List[dict]:
        return [
            {"old_id": int(r["id"]), "slug": (r.get("alias") or "").strip(), "url": target(r)}
            for r in resources
        ]

    return {"people": pack(people), "teams": pack(teams)}


def build_city(
    site: ModxSite,
    resource_id: int,
    mapper: Optional[LinkMapper] = None,
) -> Tuple[dict, dict, dict, List[str]]:
    resource = site.resources[resource_id]
    warnings: List[str] = []
    title = plain_text(resource.get("pagetitle") or "")
    facts: Dict[str, str] = {}
    content: List[Tuple[str, str]] = []
    info_relation_html = ""
    relation_html_parts: List[str] = []
    team_mentions: List[dict] = []

    for section in site.migx_sections(resource_id):
        if str(section.get("hide_section") or "").strip().lower() in ("1", "true"):
            continue
        form = section.get("MIGX_formname")
        if form == "info":
            for key, value in parse_facts_table(section.get("table") or ""):
                facts[key] = value
            for field in ("subtitle", "content"):
                raw = section.get(field) or ""
                relation_html_parts.append(raw)
                team_mentions.extend(extract_team_mentions(raw))
                cleaned = clean_html(strip_relation_sections(raw), mapper)
                if not is_blank_html(cleaned):
                    content.append(("", cleaned))
            info_relation_html = section.get("content") or ""
        elif form == "text":
            raw = section.get("content") or ""
            relation_html_parts.append(raw)
            team_mentions.extend(extract_team_mentions(raw))
            cleaned = clean_html(strip_relation_sections(raw), mapper)
            if not is_blank_html(cleaned):
                block_title = plain_text(section.get("title") or "")
                content.append(("" if block_title == title else block_title, cleaned))
        elif form not in _IGNORED_SECTIONS:
            warnings.append(f"секция «{form}» не перенесена")

    if not content:
        warnings.append("на странице нет текста")

    poster = None
    poster_url = image_url(site.tv(resource_id, "img"))
    if poster_url:
        poster = {
            "url": poster_url,
            "alt": plain_text(site.tv(resource_id, "img_alt")) or title,
            "caption": "",
            "thumbnail": poster_url,
        }
    else:
        warnings.append("нет изображения")

    published = bool(resource.get("published")) and not resource.get("deleted")
    description = plain_text(resource.get("description") or "")
    payload = {
        "title": title,
        "name": title,
        "slug": (resource.get("alias") or "").strip(),
        "status": "published" if published else "draft",
        "poster": poster,
        "description": description or None,
        "aliases": CITY_ALIASES.get(title, []),
        "facts": facts,
        "facts_order": list(facts),
        "modules": [_module(order, module_title, html) for order, (module_title, html) in enumerate(content, 1)],
        "tags": site.tags_of(resource_id),
        "seo": {
            "meta_title": title,
            "meta_description": description,
            "keywords": [k.strip() for k in (resource.get("keywords") or "").split(",") if k.strip()],
        },
        "related_person_ids": [],
        "related_team_ids": [],
        "related_team_mentions": list({item["name"].replace("ё", "е").casefold(): item for item in team_mentions}.values()),
    }

    votes = int(resource.get("votes") or 0)
    extra = {
        "old_id": int(resource["id"]),
        "old_urls": ["/" + str(resource["uri"]).strip("/")] if resource.get("uri") else [],
        "rating": round(min(10.0, max(0.0, float(resource.get("rating") or 0))), 2),
        "votes_count": votes,
    }
    created_at = _timestamp(resource.get("createdon"))
    if created_at:
        extra["created_at"] = created_at
    published_at = (_timestamp(resource.get("publishedon")) or created_at) if published else None
    if published_at:
        extra["published_at"] = published_at

    relations = _relation_candidates(site, mapper, info_relation_html, "\n".join(relation_html_parts))
    return payload, extra, relations, warnings
