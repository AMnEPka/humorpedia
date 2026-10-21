"""Parser for the public Telegram preview feed of ЖАБА — медиа-болото."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import re
from urllib.parse import urlsplit

from services.source_adapters.smi24 import _Node, _TreeParser, _classes, _find_all, _first, _walk


_HOST = "t.me"
_CHANNEL = "zhabqua"
_POST_PATH = re.compile(r"^/zhabqua/(\d+)$")
_PREV_PATH = "/s/zhabqua"
_ALLOWED_TAGS = {"p", "strong", "b", "em", "i", "u", "s", "del", "blockquote", "ul", "ol", "li", "a", "br", "code"}
_DROP_TAGS = {"script", "style", "img", "picture", "video", "audio", "iframe", "svg", "canvas", "object", "embed", "form", "button", "input"}
_VOID_TAGS = {"br"}
_BLOCK_TAGS = {"p", "li", "blockquote", "div"}


def _parse_post_url(url: str) -> int:
    try:
        parsed = urlsplit(url)
        match = _POST_PATH.fullmatch(parsed.path)
        if (
            parsed.scheme != "https"
            or parsed.hostname != _HOST
            or parsed.port not in {None, 443}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or not match
        ):
            raise ValueError
        return int(match.group(1))
    except (TypeError, ValueError) as exc:
        raise ValueError("Ожидается ссылка на пост https://t.me/zhabqua/{id}") from exc


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return parsed.isoformat() if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _post_nodes(html: str) -> list[_Node]:
    parser = _TreeParser()
    parser.feed(html)
    return [node for node in _walk(parser.root) if node.attrs.get("data-post", "").startswith(_CHANNEL + "/")]


def _safe_href(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.port in {None, 80 if parsed.scheme == "http" else 443}
        )
    except ValueError:
        return False


def _serialize_text(root: _Node) -> str:
    out: list[str] = []

    def emit(node: _Node) -> None:
        if node.tag in _DROP_TAGS:
            return
        if node.tag == "a":
            href = node.attrs.get("href", "")
            if _safe_href(href):
                out.append(f'<a href="{escape(href, quote=True)}" rel="noopener noreferrer">')
                emit_children(node.children)
                out.append("</a>")
                return
        if node.tag == "br":
            out.append("<br>")
            return
        if node.tag in _ALLOWED_TAGS:
            out.append(f"<{node.tag}>")
        elif node.tag in _BLOCK_TAGS:
            out.append("<br>")
        emit_children(node.children)
        if node.tag in _ALLOWED_TAGS and node.tag not in _VOID_TAGS:
            out.append(f"</{node.tag}>")
        elif node.tag in _BLOCK_TAGS:
            out.append("<br>")

    def emit_children(children: list[_Node | str]) -> None:
        for child in children:
            if isinstance(child, _Node):
                emit(child)
            else:
                out.append(escape(child))

    emit_children(root.children)
    html = "".join(out).strip()
    # Telegram may wrap normal content in nested paragraph containers. Collapse
    # empty block boundaries while retaining actual text breaks.
    html = re.sub(r"(?:<br>\s*){3,}", "<br><br>", html)
    return html


def _plain_text(root: _Node) -> str:
    parts: list[str] = []

    def visit(node: _Node) -> None:
        if node.tag in _DROP_TAGS:
            return
        if node.tag == "br" or node.tag in _BLOCK_TAGS:
            parts.append("\n")
        for child in node.children:
            if isinstance(child, _Node):
                visit(child)
            else:
                parts.append(child)
        if node.tag in _BLOCK_TAGS:
            parts.append("\n")

    visit(root)
    return "\n".join(line.strip() for line in "".join(parts).splitlines() if line.strip())


def _record(post: _Node) -> dict | None:
    raw_id = post.attrs.get("data-post", "")
    match = re.fullmatch(r"zhabqua/(\d+)", raw_id)
    if not match:
        return None
    post_id = int(match.group(1))
    text_node = _first(post, lambda node: "tgme_widget_message_text" in _classes(node))
    body_html = _serialize_text(text_node) if text_node else ""
    plain = _plain_text(text_node) if text_node else ""
    title = (plain.splitlines()[0] if plain else "")[:200]
    time_node = _first(post, lambda node: node.tag == "time" and bool(node.attrs.get("datetime")))
    published_at = _parse_date(time_node.attrs.get("datetime")) if time_node else None
    return {
        "kind": "news",
        "title": title,
        "full_name": None,
        "bio": {},
        "body_html": body_html,
        "excerpt": plain[:500],
        "published_at": published_at,
        "modified_at": None,
        "mentioned_names": [],
        "canonical_url": f"https://t.me/{_CHANNEL}/{post_id}",
        "post_id": post_id,
    }


def parse_feed(html: str) -> list[dict]:
    """Return every unique channel post, including media-only records."""
    records: list[dict] = []
    seen: set[int] = set()
    for node in _post_nodes(html):
        record = _record(node)
        if record is None or record["post_id"] in seen:
            continue
        seen.add(record["post_id"])
        records.append(record)
    return records


def parse_document(html: str, url: str) -> dict:
    """Return exactly the requested channel post from a public feed page."""
    post_id = _parse_post_url(url)
    record = next((item for item in parse_feed(html) if item["post_id"] == post_id), None)
    if record is None:
        raise ValueError(f"Пост ЖАБА с ID {post_id} не найден в загруженной странице ленты")
    if not record["body_html"]:
        raise ValueError(f"У поста ЖАБА с ID {post_id} нет текстового содержания")
    return record


def next_page_url(html: str) -> str | None:
    """Return only the public cursor URL explicitly advertised by rel=prev."""
    parser = _TreeParser()
    parser.feed(html)
    links = _find_all(parser.root, lambda node: node.tag == "link" and "prev" in node.attrs.get("rel", "").lower().split())
    if not links:
        return None
    href = links[0].attrs.get("href", "")
    try:
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc:
            if parsed.scheme != "https" or parsed.hostname != _HOST or parsed.port not in {None, 443}:
                return None
        if parsed.path != _PREV_PATH or parsed.fragment:
            return None
        if not re.fullmatch(r"before=\d+", parsed.query):
            return None
        return f"https://{_HOST}{_PREV_PATH}?{parsed.query}"
    except ValueError:
        return None


def current_page_url(html: str) -> str | None:
    """Return the exact validated canonical cursor URL of this feed page."""
    parser = _TreeParser()
    parser.feed(html)
    links = _find_all(parser.root, lambda node: node.tag == "link" and "canonical" in node.attrs.get("rel", "").lower().split())
    if not links:
        return None
    href = links[0].attrs.get("href", "")
    try:
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc:
            if parsed.scheme != "https" or parsed.hostname != _HOST or parsed.port not in {None, 443}:
                return None
        if parsed.path != _PREV_PATH or parsed.fragment or not re.fullmatch(r"before=\d+", parsed.query):
            return None
        return f"https://{_HOST}{_PREV_PATH}?{parsed.query}"
    except ValueError:
        return None


def discover_news(html: str, since: datetime, limit: int = 100) -> list[str]:
    """Return dated text-post URLs newer than ``since`` from a feed page."""
    if limit <= 0:
        return []
    threshold = since if since.tzinfo is not None else since.replace(tzinfo=timezone.utc)
    urls = []
    for record in parse_feed(html):
        if not record["body_html"] or not record["published_at"]:
            continue
        published = datetime.fromisoformat(record["published_at"])
        if published >= threshold:
            urls.append(record["canonical_url"])
            if len(urls) >= limit:
                break
    return urls
