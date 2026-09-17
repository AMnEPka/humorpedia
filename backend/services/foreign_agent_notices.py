"""Add foreign-agent markers to public responses without changing stored content."""
from __future__ import annotations

import re
from html import escape, unescape
from typing import Any
from urllib.parse import urlsplit

from utils.database import get_db


NOTICE_TEXT = "* — признан в РФ иностранным агентом."

_MARKABLE_ELEMENT_RE = re.compile(
    r"(<(a|span)\b([^>]*)>)(.*?)(</\2\s*>)(?!\s*<sup\b[^>]*foreign-agent-marker)",
    re.I | re.S,
)
_HREF_RE = re.compile(r"\bhref\s*=\s*([\"'])(.*?)\1", re.I)
_PEOPLE_PATH_RE = re.compile(r"^/?people/([^/?#]+?)/?$")
_PERSON_ATTR_RE = re.compile(r"\bdata-foreign-agent-person\s*=\s*([\"'])(.*?)\1", re.I)
_NOTICE_ATTR_RE = re.compile(r"\bdata-foreign-agent-notice\s*=\s*([\"'])(.*?)\1", re.I)
_MARKER_ATTR_RE = re.compile(r"\bdata-foreign-agent-marker\s*=\s*([\"'])(.*?)\1", re.I)
_LEGACY_NOTICE_RE = re.compile(
    r"<p[^>]*>\s*\*+\s*[-–—]\s*признан(?:а)?\s+в\s+рф\s+иностранным\s+агентом\.?\s*</p>",
    re.I,
)


def _person_slug(href: str) -> str | None:
    parts = urlsplit((href or "").strip())
    match = _PEOPLE_PATH_RE.match(parts.path)
    return match.group(1) if match else None


def mark_html(
    html: str,
    foreign_agent_slugs: set[str],
    *,
    unlink_slug: str | None = None,
    notices: dict[str, str] | None = None,
) -> tuple[str, bool]:
    """Mark annotated names and links, removing links that point to the current person."""
    marked = False

    def replace(match: re.Match[str]) -> str:
        nonlocal marked
        notice_attr = _NOTICE_ATTR_RE.search(match.group(1))
        if notice_attr:
            notice = unescape(notice_attr.group(2)).strip().rstrip(".")
            marker_attr = _MARKER_ATTR_RE.search(match.group(1))
            marker = unescape(marker_attr.group(2)).strip() if marker_attr else "*"
            if not notice or not marker:
                return match.group(0)
            marked = True
            if notices is not None:
                notices[marker] = notice
            return (
                f'{match.group(0)}<sup class="foreign-agent-marker" '
                f'title="{escape(notice, quote=True)}">{escape(marker)}</sup>'
            )

        person_attr = _PERSON_ATTR_RE.search(match.group(1))
        href = _HREF_RE.search(match.group(3)) if match.group(2).lower() == "a" else None
        slug = person_attr.group(2) if person_attr else _person_slug(href.group(2) if href else "")
        if not slug or slug not in foreign_agent_slugs:
            return match.group(0)
        marked = True
        if notices is not None:
            notices["*"] = NOTICE_TEXT[4:-1]
        element = match.group(4) if slug == unlink_slug and match.group(2).lower() == "a" else match.group(0)
        return (
            f'{element}<sup class="foreign-agent-marker" '
            f'title="{NOTICE_TEXT[4:-1]}">*</sup>'
        )

    return _MARKABLE_ELEMENT_RE.sub(replace, html or ""), marked


def _has_legacy_notice(document: dict[str, Any]) -> bool:
    for module in document.get("modules") or []:
        content = str((module.get("data") or {}).get("content") or "")
        if _LEGACY_NOTICE_RE.search(content):
            return True
    return False


def _mark_modules(
    modules: list[dict[str, Any]],
    slugs: set[str],
    unlink_slug: str | None = None,
    notices: dict[str, str] | None = None,
) -> bool:
    marked = False
    for module in modules or []:
        data = module.get("data") or {}
        if isinstance(data.get("content"), str):
            data["content"], changed = mark_html(
                data["content"], slugs, unlink_slug=unlink_slug, notices=notices
            )
            marked = marked or changed
        for event in data.get("events") or data.get("items") or []:
            if isinstance(event, dict) and isinstance(event.get("description"), str):
                event["description"], changed = mark_html(
                    event["description"], slugs, unlink_slug=unlink_slug, notices=notices
                )
                marked = marked or changed
        for row in data.get("rows") or []:
            if not isinstance(row, list):
                continue
            for index, cell in enumerate(row):
                if isinstance(cell, str):
                    row[index], changed = mark_html(
                        cell, slugs, unlink_slug=unlink_slug, notices=notices
                    )
                    marked = marked or changed
    return marked


async def decorate_document(document: dict[str, Any]) -> dict[str, Any]:
    """Decorate one public person/article/news response and add notice metadata."""
    db = await get_db()
    people = await db.people.find(
        {"foreign_agent": True, "status": {"$ne": "archived"}},
        {"slug": 1},
    ).to_list(None)
    slugs = {person.get("slug") for person in people if person.get("slug")}

    legacy_notice = _has_legacy_notice(document)
    own_slug = document.get("slug") if document.get("foreign_agent") else None
    notices: dict[str, str] = {}
    marked = _mark_modules(document.get("modules") or [], slugs, unlink_slug=own_slug, notices=notices)
    if isinstance(document.get("content"), str):
        document["content"], changed = mark_html(
            document["content"], slugs, unlink_slug=own_slug, notices=notices
        )
        marked = marked or changed

    needs_notice = bool(document.get("foreign_agent")) or marked
    if document.get("foreign_agent"):
        notices["*"] = NOTICE_TEXT[4:-1]
    document["foreign_agent_notice"] = needs_notice and not legacy_notice
    document["foreign_agent_notices"] = [
        {"marker": marker, "text": text}
        for marker, text in sorted(notices.items(), key=lambda item: (len(item[0]), item[0]))
        if not (legacy_notice and marker == "*")
    ]
    return document
