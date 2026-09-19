"""Data cleanup helpers for the contextual fresh-news feature."""

from __future__ import annotations

import copy
import html
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit


NEWS_HEADING_RE = re.compile(
    r"<h(?P<level>[34])\b[^>]*>(?P<body>.*?)</h(?P=level)\s*>",
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


def plain_text(value: str) -> str:
    return html.unescape(TAG_RE.sub("", value)).replace("\xa0", " ").strip()


class _OpenTags(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag not in VOID_ELEMENTS:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.stack:
            index = len(self.stack) - 1 - self.stack[::-1].index(tag)
            del self.stack[index:]


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.hrefs.append(href)


def _close_open_tags(value: str) -> str:
    parser = _OpenTags()
    parser.feed(value)
    return value + "".join(f"</{tag}>" for tag in reversed(parser.stack))


def split_legacy_news_section(value: str) -> tuple[str, list[str]] | None:
    """Return cleaned prefix and links when a standalone trailing News heading exists."""
    for match in NEWS_HEADING_RE.finditer(value):
        if plain_text(match.group("body")).casefold() != "новости":
            continue
        suffix = value[match.start():]
        links = _Links()
        links.feed(suffix)
        prefix = _close_open_tags(value[:match.start()].rstrip())
        return prefix, links.hrefs
    return None


def clean_document(document: dict) -> tuple[dict, list[str], int, int]:
    """Remove legacy News tails and humor_chronicles markers from a page document."""
    updated = copy.deepcopy(document)
    links: list[str] = []
    news_sections = 0
    chronicles = 0
    modules = []

    for module in updated.get("modules") or []:
        if module.get("type") == "humor_chronicles":
            chronicles += 1
            continue
        data = module.get("data") or {}
        content = data.get("content")
        result = split_legacy_news_section(content) if isinstance(content, str) else None
        if not result:
            modules.append(module)
            continue
        prefix, found_links = result
        links.extend(found_links)
        news_sections += 1
        if plain_text(prefix):
            data["content"] = prefix
            module["data"] = data
            modules.append(module)

    updated["modules"] = modules
    return updated, links, news_sections, chronicles


def normalized_internal_path(href: str) -> str | None:
    parsed = urlsplit(href)
    if parsed.scheme and parsed.netloc not in {"humorpedia.ru", "www.humorpedia.ru"}:
        return None
    path = "/" + parsed.path.lstrip("/")
    return path.rstrip("/") or "/"


async def _find_news(db, href: str) -> dict | None:
    path = normalized_internal_path(href)
    if not path:
        return None
    parts = path.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "news":
        return await db.news.find_one({"slug": parts[1]}, {"_id": 1})
    candidates = [path]
    if not path.endswith(".html"):
        candidates.append(path + ".html")
    return await db.news.find_one({"old_urls": {"$in": candidates}}, {"_id": 1})


async def migrate_legacy_related_news(db, *, apply: bool = False) -> dict:
    stats = {
        "documents_changed": 0,
        "news_sections_removed": 0,
        "text_modules_removed": 0,
        "chronicles_removed": 0,
        "news_links_backfilled": 0,
        "unresolved_news_links": [],
    }
    relation_fields = {
        "people": "related_person_ids",
        "teams": "related_team_ids",
        "shows": "related_show_ids",
    }

    for collection_name, relation_field in relation_fields.items():
        collection = db[collection_name]
        async for document in collection.find({"modules": {"$exists": True}}):
            before_modules = document.get("modules") or []
            updated, hrefs, sections, chronicles = clean_document(document)
            if updated == document:
                continue

            stats["documents_changed"] += 1
            stats["news_sections_removed"] += sections
            stats["chronicles_removed"] += chronicles
            stats["text_modules_removed"] += max(
                0, len(before_modules) - len(updated.get("modules") or []) - chronicles
            )

            for href in hrefs:
                news = await _find_news(db, href)
                if not news:
                    path = normalized_internal_path(href)
                    if path and path.startswith(("/news/", "/novosti/")):
                        stats["unresolved_news_links"].append(path)
                    continue
                stats["news_links_backfilled"] += 1
                if apply:
                    await db.news.update_one(
                        {"_id": news["_id"]},
                        {"$addToSet": {relation_field: document["_id"]}},
                    )

            if apply:
                await collection.update_one(
                    {"_id": document["_id"]},
                    {"$set": {
                        "modules": updated["modules"],
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )

    stats["unresolved_news_links"] = sorted(set(stats["unresolved_news_links"]))
    return stats
