"""Small, dependency-free HTML and sitemap parser for 24СМИ pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html import escape, unescape
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlsplit
from xml.etree import ElementTree


_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_DROP_TAGS = {"script", "style", "iframe", "svg", "img", "picture", "figure", "video", "audio", "canvas", "noscript", "form", "button"}
_BODY_TAGS = {"p", "h2", "h3", "h4", "strong", "b", "em", "i", "ul", "ol", "li", "blockquote", "a", "br"}
_SKIP_MARKERS = ("adfox", "popular-news", "comment", "sidebar", "recommend", "article-footer", "share", "related")
_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["_Node | str"] = field(default_factory=list)


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag.lower(), {key.lower(): value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if node.tag not in _VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].children.append(data)


def _walk(node: _Node):
    for child in node.children:
        if isinstance(child, _Node):
            yield child
            yield from _walk(child)


def _classes(node: _Node) -> set[str]:
    return set(node.attrs.get("class", "").lower().split())


def _text(node: _Node) -> str:
    parts: list[str] = []
    for child in node.children:
        parts.append(_text(child) if isinstance(child, _Node) else child)
    return re.sub(r"\s+", " ", unescape("".join(parts))).strip()


def _find_all(node: _Node, predicate) -> list[_Node]:
    return [candidate for candidate in _walk(node) if predicate(candidate)]


def _first(node: _Node, predicate) -> _Node | None:
    return next((candidate for candidate in _walk(node) if predicate(candidate)), None)


def _is_24smi_url(value: str, expected_path: str | None = None) -> bool:
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and parsed.hostname in {"24smi.org", "www.24smi.org"}
            and parsed.port in {None, 443}
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and (expected_path is None or parsed.path == expected_path)
        )
    except ValueError:
        return False


def _canonical(root: _Node, url: str, kind: str) -> str:
    requested = urlsplit(url)
    expected_prefix = "/celebrity/" if kind == "biography" else "/news/"
    if not _is_24smi_url(url) or not requested.path.startswith(expected_prefix):
        raise ValueError("URL is not a supported 24СМИ page")

    links = _find_all(root, lambda node: node.tag == "link" and node.attrs.get("rel", "").lower() == "canonical")
    canonical = links[0].attrs.get("href", "") if links else url
    if not _is_24smi_url(canonical, requested.path):
        raise ValueError("Suspicious canonical URL")
    return canonical


def _parse_datetime(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    for fmt in ("%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def _metadata(root: _Node) -> tuple[str | None, str | None]:
    published = modified = None
    scripts = _find_all(root, lambda node: node.tag == "script" and "application/ld+json" in node.attrs.get("type", "").lower())
    for script in scripts:
        try:
            data = json.loads("".join(child for child in script.children if isinstance(child, str)))
        except (TypeError, ValueError):
            continue
        records = data if isinstance(data, list) else [data]
        expanded = []
        for record in records:
            if isinstance(record, dict) and isinstance(record.get("@graph"), list):
                expanded.extend(record["@graph"])
            elif isinstance(record, dict):
                expanded.append(record)
        for record in expanded:
            if not isinstance(record, dict):
                continue
            types = record.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if not any(kind in {"Article", "NewsArticle", "ReportageNewsArticle", "BlogPosting"} for kind in types):
                continue
            published = published or _parse_datetime(record.get("datePublished"))
            modified = modified or _parse_datetime(record.get("dateModified"))
    return published, modified


def _bio_date(value: str) -> str | None:
    text = value.strip().lower().replace("ё", "е")
    match = re.search(r"(\d{1,2})\s+([а-я]+)\s+(\d{4})", text)
    if match and match.group(2) in _MONTHS:
        try:
            return date(int(match.group(3)), _MONTHS[match.group(2)], int(match.group(1))).isoformat()
        except ValueError:
            return None
    match = re.search(r"\b(\d{1,2})[.]([01]?\d)[.](\d{4})\b", text)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
        except ValueError:
            return None
    return None


def _noise(node: _Node) -> bool:
    marker = " ".join((node.attrs.get("id", ""), node.attrs.get("class", ""))).lower()
    return any(item in marker for item in _SKIP_MARKERS)


def _safe_href(value: str) -> bool:
    if not value:
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme in {"", "http", "https"}
            and not parsed.username
            and not parsed.password
            and not (not parsed.scheme and parsed.netloc)
        )
    except ValueError:
        return False


def _serialize_body(node: _Node) -> tuple[str, list[str]]:
    output: list[str] = []
    names: list[str] = []

    def emit(current: _Node, inside_anchor: bool = False) -> None:
        if current.tag in _DROP_TAGS or _noise(current):
            return
        if current.tag == "h1":
            return
        if current.tag == "a":
            href = current.attrs.get("href", "")
            try:
                is_celebrity_link = "/celebrity/" in urlsplit(href).path
            except ValueError:
                is_celebrity_link = False
            if is_celebrity_link and _text(current):
                names.append(_text(current))
            if _safe_href(href):
                output.append(f'<a href="{escape(href, quote=True)}">')
                for child in current.children:
                    if isinstance(child, _Node):
                        emit(child, True)
                    else:
                        output.append(escape(child))
                output.append("</a>")
                return
        if current.tag in _BODY_TAGS:
            output.append(f"<{current.tag}>")
        for child in current.children:
            if isinstance(child, _Node):
                emit(child, inside_anchor or current.tag == "a")
            else:
                output.append(escape(child))
        if current.tag in _BODY_TAGS and current.tag != "br":
            output.append(f"</{current.tag}>")

    for child in node.children:
        if isinstance(child, _Node):
            emit(child)
        else:
            output.append(escape(child))
    body = "".join(output).strip()
    # Empty wrappers and whitespace alone do not count as an article body.
    if not re.sub(r"<[^>]+>", "", body).strip():
        return "", []
    return body, list(dict.fromkeys(names))


def _body_node(root: _Node, kind: str) -> _Node | None:
    expected = "celebrity" if kind == "biography" else "news"
    return _first(
        root,
        lambda node: node.tag == "article"
        and node.attrs.get("data-type", "").lower() == expected
        and "article" in _classes(node),
    )


def _card_fields(root: _Node) -> dict[str, str]:
    fields: dict[str, str] = {}
    labels = {"дата рождения": "birth_date", "дата смерти": "death_date", "место рождения": "birth_place"}
    for field_node in _find_all(root, lambda node: "cardtable__field" in _classes(node)):
        label_node = _first(field_node, lambda node: "cardtable__left" in _classes(node))
        value_node = _first(field_node, lambda node: "cardtable__right" in _classes(node))
        if label_node is None or value_node is None:
            continue
        key = labels.get(_text(label_node).rstrip(":").lower())
        if not key:
            continue
        value = _text(value_node)
        if key.endswith("_date"):
            value = _bio_date(value) or ""
        if value:
            fields[key] = value
    return fields


def parse_document(html: str, url: str) -> dict:
    """Extract a biography or news item from a 24СМИ HTML document."""
    parser = _TreeParser()
    parser.feed(html)
    root = parser.root
    article = _body_node(root, "biography") or _body_node(root, "news")
    if article is None:
        raise ValueError("Unrecognized 24СМИ document type")
    kind = "biography" if article.attrs.get("data-type") == "celebrity" else "news"
    canonical = _canonical(root, url, kind)

    h1 = _first(article, lambda node: node.tag == "h1")
    if h1 is None and kind == "biography":
        h1 = _first(root, lambda node: node.tag == "h1" and "head__title" in _classes(node))
    title = _text(h1) if h1 else ""
    if not title:
        raise ValueError("Document has no title")

    body_html, mentioned_names = _serialize_body(article)
    if not body_html:
        raise ValueError("Document has no main text")
    excerpt = ""
    first_p = _first(article, lambda node: node.tag == "p" and not _noise(node))
    if first_p:
        excerpt = _text(first_p)

    full_name = None
    bio: dict[str, str] = {}
    if kind == "biography":
        name_node = _first(root, lambda node: "head__description" in _classes(node))
        full_name = _text(name_node) or None if name_node else None
        bio = _card_fields(root)

    published_at, modified_at = _metadata(root)
    return {
        "kind": kind,
        "title": title,
        "full_name": full_name,
        "bio": bio,
        "body_html": body_html,
        "excerpt": excerpt,
        "published_at": published_at,
        "modified_at": modified_at,
        "mentioned_names": mentioned_names,
        "canonical_url": canonical,
    }


def _sitemap_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def discover_news(xml: str, since: datetime, limit: int = 100) -> list[str]:
    """Return recent 24СМИ news URLs from one sitemap page, newest first."""
    if limit <= 0:
        return []
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ValueError("Invalid sitemap XML") from exc
    since_utc = since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since.astimezone(timezone.utc)
    found: dict[str, datetime] = {}
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1] != "url":
            continue
        values = {child.tag.rsplit("}", 1)[-1]: child.text or "" for child in item}
        url = values.get("loc", "").strip()
        modified = _sitemap_datetime(values.get("lastmod", ""))
        if not modified or modified < since_utc:
            continue
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if parsed.scheme != "https" or parsed.hostname != "24smi.org" or not parsed.path.startswith("/news/"):
            continue
        found[url] = max(modified, found.get(url, modified))
    return [url for url, _ in sorted(found.items(), key=lambda item: (-item[1].timestamp(), item[0]))[:limit]]
