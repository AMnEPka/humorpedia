"""Parser for public GoStandup.ru comedian profiles and journal articles."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import re
from urllib.parse import urlsplit, urljoin
from xml.etree import ElementTree

from .smi24 import _TreeParser, _Node, _walk, _find_all, _first, _text, _classes, _bio_date, _MONTHS


_CANONICAL_HOST = "gostandup.ru"
_BIO_PATH = re.compile(r"^/comedians/[a-z0-9_-]+/?$")
_NEWS_PATH = re.compile(r"^/articles/[a-z0-9_-]+/?$")
_BODY_TAGS = {"p", "h2", "h3", "h4", "strong", "b", "em", "i", "ul", "ol", "li", "blockquote", "a", "br"}
_DROP_TAGS = {"script", "style", "iframe", "svg", "img", "picture", "figure", "video", "audio", "canvas", "noscript", "form", "button", "source"}
_NOISE = ("advert", "promo", "subscribe", "social", "share", "recommend", "related", "event", "ticket", "tour", "video", "gallery", "photo", "widget", "sidebar", "footer", "comment", "banner", "tabs-with-content")


def _allowed_url(value: str, path_pattern: re.Pattern[str] | None = None) -> bool:
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and parsed.hostname in {_CANONICAL_HOST, "www." + _CANONICAL_HOST}
                and parsed.port in {None, 443} and parsed.username is None and parsed.password is None
                and not parsed.query and not parsed.fragment
                and (path_pattern is None or path_pattern.fullmatch(parsed.path) is not None))
    except ValueError:
        return False


def _canonical(root: _Node, url: str, kind: str) -> str:
    pattern = _BIO_PATH if kind == "biography" else _NEWS_PATH
    if not _allowed_url(url, pattern):
        raise ValueError("URL is not a supported GoStandup page")
    requested = urlsplit(url)
    canonical_link = _first(root, lambda n: n.tag == "link" and "canonical" in n.attrs.get("rel", "").lower().split())
    canonical = canonical_link.attrs.get("href", "") if canonical_link else url
    if not _allowed_url(canonical, pattern) or urlsplit(canonical).path.rstrip("/") != requested.path.rstrip("/"):
        raise ValueError("Suspicious canonical URL")
    return "https://gostandup.ru" + requested.path.rstrip("/")


def _noise(node: _Node) -> bool:
    marker = " ".join((node.attrs.get("id", ""), node.attrs.get("class", ""), node.attrs.get("data-testid", ""))).lower()
    if any(part in marker for part in _NOISE):
        return True
    text = _text(node).lower()
    if text.startswith(("подписывайтесь на наш", "смотрите также")) or "маршрут стендап-тура" in text or "выбирайте свой город" in text:
        return True
    return node.tag in {"li", "ul", "ol"} and any(
        "/tickets/" in child.attrs.get("href", "") or "/event/" in child.attrs.get("href", "")
        for child in _find_all(node, lambda candidate: candidate.tag == "a")
    )


def _safe_href(value: str) -> bool:
    if not value:
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"", "http", "https"} and not parsed.username and not parsed.password and not (not parsed.scheme and parsed.netloc)
    except ValueError:
        return False


def _serialize_body(node: _Node) -> tuple[str, list[str]]:
    out: list[str] = []
    names: list[str] = []

    def emit(current: _Node) -> None:
        if current.tag in _DROP_TAGS or _noise(current) or current.tag == "h1":
            return
        if current.tag == "a":
            href = current.attrs.get("href", "")
            if "/comedians/" in urlsplit(href).path and _text(current):
                names.append(_text(current))
            if _safe_href(href):
                out.append(f'<a href="{escape(href, quote=True)}">')
                for child in current.children:
                    if isinstance(child, _Node):
                        emit(child)
                    else:
                        out.append(escape(child))
                out.append("</a>")
                return
        if current.tag in _BODY_TAGS:
            out.append(f"<{current.tag}>")
        for child in current.children:
            if isinstance(child, _Node):
                emit(child)
            else:
                out.append(escape(child))
        if current.tag in _BODY_TAGS and current.tag != "br":
            out.append(f"</{current.tag}>")

    children = node.children
    for index, child in enumerate(children):
        if isinstance(child, _Node) and _text(child).lower().startswith("выбирайте свой город"):
            children = children[:index]
            break
    for child in children:
        emit(child) if isinstance(child, _Node) else out.append(escape(child))
    body = "".join(out).strip()
    if not re.sub(r"<[^>]+>", "", body).strip():
        return "", []
    return body, list(dict.fromkeys(names))


def _body_container(root: _Node, kind: str) -> _Node | None:
    content_class = "comic-page-header__description" if kind == "biography" else "article-page__content"
    return _first(root, lambda node: content_class in _classes(node))


def _metadata(root: _Node) -> tuple[str | None, str | None]:
    published = modified = None
    for script in _find_all(root, lambda n: n.tag == "script" and "ld+json" in n.attrs.get("type", "").lower()):
        raw = "".join(child for child in script.children if isinstance(child, str))
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        records = data if isinstance(data, list) else [data]
        for record in records:
            if isinstance(record, dict) and isinstance(record.get("@graph"), list):
                records.extend(record["@graph"])
            if not isinstance(record, dict):
                continue
            types = record.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if not any(t in {"Article", "NewsArticle", "BlogPosting"} for t in types):
                continue
            published = published or _parse_datetime(record.get("datePublished"))
            modified = modified or _parse_datetime(record.get("dateModified"))
    return published, modified


def _parse_datetime(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.isoformat()
        except ValueError:
            continue
    match = re.search(r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})", raw.lower())
    if match and match.group(2) in _MONTHS:
        try:
            return date(int(match.group(3)), _MONTHS[match.group(2)], int(match.group(1))).isoformat()
        except ValueError:
            pass
    return None


def _profile_fields(root: _Node) -> dict[str, str]:
    fields: dict[str, str] = {}
    birth_date = _first(root, lambda node: "comic-page-birthdate__info-date" in _classes(node))
    birth_place = _first(root, lambda node: "comic-page-birthdate__info-place" in _classes(node))
    if birth_date:
        value = _bio_date(_text(birth_date))
        if value:
            fields["birth_date"] = value
    if birth_place:
        value = _text(birth_place)
        if value:
            fields["birth_place"] = value
    return fields


def parse_document(html: str, url: str) -> dict:
    """Extract a biography or journal article from an allowed public URL."""
    requested = urlsplit(url)
    kind = "biography" if _BIO_PATH.fullmatch(requested.path) else "news" if _NEWS_PATH.fullmatch(requested.path) else None
    if kind is None:
        raise ValueError("Unrecognized GoStandup document type")
    parser = _TreeParser()
    parser.feed(html)
    root = parser.root
    canonical = _canonical(root, url, kind)
    container = _body_container(root, kind)
    if container is None:
        raise ValueError("Document has no main text")
    title_class = "comic-page-header__title" if kind == "biography" else "article-page__title"
    h1 = _first(root, lambda node: node.tag == "h1" and title_class in _classes(node))
    title = _text(h1) if h1 else ""
    if not title:
        raise ValueError("Document has no title")
    body_html, mentioned_names = _serialize_body(container)
    if not body_html:
        raise ValueError("Document has no main text")
    first_p = _first(container, lambda n: n.tag == "p" and not _noise(n))
    excerpt = _text(first_p) if first_p else ""
    full_name = title if kind == "biography" else None
    bio = _profile_fields(root) if kind == "biography" else {}
    published_at, modified_at = _metadata(root)
    if kind == "news" and not published_at:
        date_node = _first(root, lambda node: "article-page__date" in _classes(node))
        if date_node:
            published_at = _parse_datetime(_text(date_node))
    return {"kind": kind, "title": title, "full_name": full_name, "bio": bio,
            "body_html": body_html, "excerpt": excerpt, "published_at": published_at,
            "modified_at": modified_at, "mentioned_names": mentioned_names, "canonical_url": canonical}


def discover_news(text: str, since: datetime, limit: int = 100) -> list[str]:
    """Return recent article links from the public journal index or sitemap XML."""
    if limit <= 0:
        return []
    since_utc = since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since.astimezone(timezone.utc)
    found: dict[str, datetime] = {}
    try:
        root = ElementTree.fromstring(text) if "<html" not in text[:1000].lower() else None
    except ElementTree.ParseError:
        root = None
    if root is None:
        # The canonical discovery source is /articles, an HTML index. The sitemap
        # format remains accepted for callers that already fetched it.
        parser = _TreeParser()
        parser.feed(text)
        html_root = parser.root
        if not _find_all(html_root, lambda node: node.tag == "html"):
            raise ValueError("Invalid sitemap or journal index")
        for anchor in _find_all(html_root, lambda node: node.tag == "a"):
            href = anchor.attrs.get("href", "")
            absolute = urljoin("https://gostandup.ru/articles", href)
            try:
                parsed = urlsplit(absolute)
            except ValueError:
                continue
            if not _allowed_url(absolute, _NEWS_PATH):
                continue
            # Find a nearby card/container and use a machine-readable datetime
            # when present, then a visible relative date such as "3 недели назад".
            parents: list[_Node] = []
            for candidate in _walk(html_root):
                if anchor in candidate.children:
                    parents.append(candidate)
            date_value = ""
            dated = _first(anchor, lambda node: node.tag == "time")
            if dated:
                date_value = dated.attrs.get("datetime") or _text(dated)
            if not date_value:
                date_value = _text(anchor)
            # Some rendered index cards put their <time> outside the link. Use
            # a small direct-parent card only; the full journal container is too broad.
            if not dated and parents and len(_text(parents[0])) < 500:
                card = parents[0]
                dated = _first(card, lambda node: node.tag == "time")
                if dated:
                    date_value = dated.attrs.get("datetime") or _text(dated)
            modified = _parse_datetime(date_value)
            if not modified:
                relative = re.search(r"\b(\d+)\s*(час|день|дня|дней|недел|месяц|месяца|месяцев)\w*\s+назад\b", date_value.lower())
                if relative:
                    amount = int(relative.group(1))
                    unit = relative.group(2)
                    seconds = amount * (3600 if unit == "час" else 86400 if unit.startswith("д") else 604800 if unit.startswith("н") else 2592000)
                    modified = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()
            if modified:
                try:
                    stamp_value = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                    stamp = stamp_value.replace(tzinfo=timezone.utc) if stamp_value.tzinfo is None else stamp_value.astimezone(timezone.utc)
                except ValueError:
                    continue
                if stamp >= since_utc:
                    canonical = "https://gostandup.ru" + parsed.path.rstrip("/")
                    found[canonical] = max(stamp, found.get(canonical, stamp))
        return [url for url, _ in sorted(found.items(), key=lambda entry: (-entry[1].timestamp(), entry[0]))[:limit]]
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1] != "url":
            continue
        values = {child.tag.rsplit("}", 1)[-1]: child.text or "" for child in item}
        url = values.get("loc", "").strip()
        modified = _parse_datetime(values.get("lastmod", ""))
        if not url or not modified:
            continue
        try:
            parsed_date = datetime.fromisoformat(modified.replace("Z", "+00:00"))
            stamp = parsed_date.replace(tzinfo=timezone.utc) if parsed_date.tzinfo is None else parsed_date.astimezone(timezone.utc)
            parsed = urlsplit(url)
        except ValueError:
            continue
        if not _allowed_url(url, _NEWS_PATH) or stamp < since_utc:
            continue
        canonical = "https://gostandup.ru" + parsed.path.rstrip("/")
        found[canonical] = max(stamp, found.get(canonical, stamp))
    return [url for url, _ in sorted(found.items(), key=lambda entry: (-entry[1].timestamp(), entry[0]))[:limit]]
