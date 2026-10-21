"""Parser for publicly accessible Vokrug TV biography and article pages."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
import json
import re
from urllib.parse import urljoin, urlsplit

from services.source_adapters.smi24 import (
    _BODY_TAGS,
    _DROP_TAGS,
    _Node,
    _TreeParser,
    _classes,
    _find_all,
    _first,
    _text,
    _walk,
)


_HOST = "www.vokrug.tv"
_MOSCOW = timezone(timedelta(hours=3))
_SKIP_MARKERS = (
    "adfox", "comment", "recommend", "related", "article__tags", "article-tags",
    "post-entries", "share", "infinity-compact", "buttons", "discounts", "tg",
)
_PERSON_PATH = re.compile(r"^/person/show/[A-Za-z0-9_-]+/$")
_ARTICLE_PATH = re.compile(r"^/article/show/[A-Za-z0-9_-]+/$")
_RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}


def _supported_url(value: str, kind: str | None = None) -> bool:
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname != _HOST
            or parsed.port not in {None, 443}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            return False
        if kind == "biography":
            return bool(_PERSON_PATH.fullmatch(parsed.path))
        if kind == "news":
            return bool(_ARTICLE_PATH.fullmatch(parsed.path))
        return bool(_PERSON_PATH.fullmatch(parsed.path) or _ARTICLE_PATH.fullmatch(parsed.path))
    except ValueError:
        return False


def _parse_datetime(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    match = re.search(r"(\d{1,2}):(\d{2}),?\s+(\d{1,2})\.(\d{1,2})\.(\d{4})", raw)
    if match:
        try:
            return datetime(
                int(match.group(5)), int(match.group(4)), int(match.group(3)),
                int(match.group(1)), int(match.group(2)), tzinfo=_MOSCOW,
            ).isoformat()
        except ValueError:
            return None
    match = re.search(r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})(?:\s*(\d{1,2}):(\d{2}))?", raw.lower())
    if match and match.group(2) in _RU_MONTHS:
        try:
            return datetime(
                int(match.group(3)), _RU_MONTHS[match.group(2)], int(match.group(1)),
                int(match.group(4) or 0), int(match.group(5) or 0), tzinfo=_MOSCOW,
            ).isoformat()
        except ValueError:
            return None
    return None


def _jsonld(root: _Node) -> list[dict]:
    items: list[dict] = []
    scripts = _find_all(
        root,
        lambda node: node.tag == "script" and "application/ld+json" in node.attrs.get("type", "").lower(),
    )
    for script in scripts:
        try:
            data = json.loads("".join(child for child in script.children if isinstance(child, str)))
        except (TypeError, ValueError):
            continue
        records = data if isinstance(data, list) else [data]
        for record in records:
            if isinstance(record, dict):
                items.extend(record.get("@graph", []) if isinstance(record.get("@graph"), list) else [record])
    return [record for record in items if isinstance(record, dict)]


def _title(root: _Node) -> str:
    title_box = _first(root, lambda node: node.tag == "div" and "title" in _classes(node))
    heading = _first(title_box, lambda node: node.tag == "h1") if title_box else None
    return _text(heading) if heading else ""


def _canonical(root: _Node, requested_url: str, kind: str) -> str:
    requested = urlsplit(requested_url)
    expected = _PERSON_PATH if kind == "biography" else _ARTICLE_PATH
    if not _supported_url(requested_url, kind) or not expected.fullmatch(requested.path):
        raise ValueError("URL is not a supported Vokrug TV page")
    links = _find_all(root, lambda node: node.tag == "link" and "canonical" in node.attrs.get("rel", "").lower().split())
    canonical = links[0].attrs.get("href", "") if links else requested_url
    if not _supported_url(canonical, kind) or urlsplit(canonical).path != requested.path:
        raise ValueError("Suspicious canonical URL")
    return canonical


def _has_media(node: _Node) -> bool:
    return node.tag in {"img", "picture", "video", "audio", "iframe", "figure"} or any(
        _has_media(child) for child in node.children if isinstance(child, _Node)
    )


def _noise(node: _Node) -> bool:
    marker = " ".join((node.attrs.get("id", ""), node.attrs.get("class", ""))).lower()
    return any(term in marker for term in _SKIP_MARKERS)


def _is_recommendation(node: _Node) -> bool:
    value = _text(node).strip().lower()
    return value.startswith(("читайте также", "читайте еще", "вам может быть интересно"))


def _is_caption(node: _Node) -> bool:
    marker = " ".join((node.attrs.get("class", ""), node.attrs.get("style", ""))).lower()
    if "caption" in marker or "подпись" in marker:
        return True
    if "text-align:center" not in marker.replace(" ", ""):
        return False
    return all(
        not isinstance(child, _Node) or child.tag in {"em", "i", "strong", "b", "span"}
        for child in node.children
    )


def _serialize_body(root: _Node) -> tuple[str, list[str]]:
    out: list[str] = []
    names: list[str] = []
    stopped = False

    def emit(node: _Node) -> None:
        nonlocal stopped
        if stopped or node.tag in _DROP_TAGS or _noise(node) or node.tag == "p" and _has_media(node):
            return
        if _is_recommendation(node):
            stopped = True
            return
        if node.tag == "h1":
            return
        if node.tag == "a":
            href = node.attrs.get("href", "")
            absolute = urljoin(f"https://{_HOST}/", href)
            try:
                parsed = urlsplit(href)
                safe = parsed.scheme in {"", "http", "https"} and not parsed.username and not parsed.password and not (not parsed.scheme and parsed.netloc)
            except ValueError:
                safe = False
            if safe and "/person/show/" in urlsplit(absolute).path and _text(node):
                names.append(_text(node))
            if safe:
                out.append(f'<a href="{escape(href, quote=True)}">')
                emit_children(node.children)
                out.append("</a>")
                return
        if node.tag in _BODY_TAGS:
            out.append(f"<{node.tag}>")
        emit_children(node.children)
        if node.tag in _BODY_TAGS and node.tag != "br":
            out.append(f"</{node.tag}>")

    def emit_children(children: list[_Node | str]) -> None:
        nonlocal stopped
        media_caption_pending = False
        for child in children:
            if stopped:
                return
            if isinstance(child, str):
                out.append(escape(child))
                continue
            if child.tag == "p" and _has_media(child):
                media_caption_pending = True
                continue
            if media_caption_pending and child.tag == "p" and _is_caption(child):
                media_caption_pending = False
                continue
            media_caption_pending = False
            emit(child)

    emit_children(root.children)
    html = "".join(out).strip()
    if not re.sub(r"<[^>]+>", "", html).strip():
        return "", []
    return html, list(dict.fromkeys(names))


def _bio_fields(records: list[dict]) -> tuple[str | None, dict[str, str]]:
    person = None
    for record in records:
        entity = record.get("mainEntity") if record.get("@type") == "ProfilePage" else record
        if isinstance(entity, dict):
            types = entity.get("@type", [])
            if types == "Person" or isinstance(types, list) and "Person" in types:
                person = entity
                break
    if person is None:
        return None, {}
    name = person.get("name")
    full_name = name.strip() if isinstance(name, str) and name.strip() else None
    bio: dict[str, str] = {}
    birth_date = person.get("birthDate")
    if isinstance(birth_date, str) and re.match(r"^\d{4}-\d{2}-\d{2}", birth_date):
        try:
            bio["birth_date"] = datetime.strptime(birth_date[:10], "%Y-%m-%d").date().isoformat()
        except ValueError:
            pass
    value = person.get("birthPlace")
    if isinstance(value, dict):
        value = value.get("name")
    if isinstance(value, str) and value.strip():
        bio["birth_place"] = value.strip()
    death_date = person.get("deathDate")
    if isinstance(death_date, str) and re.match(r"^\d{4}-\d{2}-\d{2}", death_date):
        try:
            bio["death_date"] = datetime.strptime(death_date[:10], "%Y-%m-%d").date().isoformat()
        except ValueError:
            pass
    return full_name, bio


def parse_document(html: str, url: str) -> dict:
    """Parse a supported Vokrug TV person page or dated editorial article."""
    try:
        path = urlsplit(url).path
    except ValueError as exc:
        raise ValueError("URL is not a supported Vokrug TV page") from exc
    if _PERSON_PATH.fullmatch(path):
        kind = "biography"
        parser = _TreeParser()
        parser.feed(html)
        root = parser.root
        container = _first(root, lambda node: node.tag == "div" and node.attrs.get("id") == "biography" and "product-detail-content" in _classes(node))
    elif _ARTICLE_PATH.fullmatch(path):
        kind = "news"
        parser = _TreeParser()
        parser.feed(html)
        root = parser.root
        container = _first(root, lambda node: node.tag == "div" and "post-detail-content" in _classes(node) and "curart" in _classes(node))
    else:
        raise ValueError("Unsupported Vokrug TV document type")

    canonical = _canonical(root, url, kind)
    title = _title(root)
    if not title:
        raise ValueError("Document type has no title")
    if container is None:
        raise ValueError("Document type has no main text")
    body_html, mentioned_names = _serialize_body(container)
    if not body_html:
        raise ValueError("Document has no main text")

    records = _jsonld(root)
    published = modified = None
    full_name = None
    bio: dict[str, str] = {}
    if kind == "biography":
        full_name, bio = _bio_fields(records)
    else:
        for record in records:
            types = record.get("@type", [])
            if types == "Article" or isinstance(types, list) and "Article" in types:
                published = published or _parse_datetime(record.get("datePublished"))
                modified = modified or _parse_datetime(record.get("dateModified"))
        if not published:
            raise ValueError("News article has no publication date")
    excerpt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body_html)).strip()[:500]
    return {
        "kind": kind,
        "title": title,
        "full_name": full_name,
        "bio": bio,
        "body_html": body_html,
        "excerpt": excerpt,
        "published_at": published,
        "modified_at": modified,
        "mentioned_names": mentioned_names,
        "canonical_url": canonical,
    }


def _since_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=_MOSCOW) if value.tzinfo is None else value


def discover_news(text: str, since: datetime, limit: int = 100) -> list[str]:
    """Return recent article URLs from the public latest-publications page HTML."""
    if limit <= 0:
        return []
    parser = _TreeParser()
    parser.feed(text)
    threshold = _since_datetime(since)
    result: list[str] = []
    for link in _find_all(parser.root, lambda node: node.tag == "a" and "article__items" in _classes(node)):
        href = link.attrs.get("href", "")
        absolute = urljoin(f"https://{_HOST}/", href)
        if not _supported_url(absolute, "news"):
            continue
        date_node = _first(link, lambda node: "article__items-date" in _classes(node))
        stamp = _parse_datetime(_text(date_node) if date_node else None)
        if not stamp:
            continue
        published = datetime.fromisoformat(stamp)
        if published < threshold:
            continue
        if absolute not in result:
            result.append(absolute)
            if len(result) >= limit:
                break
    return result
