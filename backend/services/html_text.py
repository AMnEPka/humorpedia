"""Plain text and safe links for the isolated HTML projection; never emits source HTML."""
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import ipaddress

def safe_url(value, *, fragment=True):
    if not isinstance(value, str):
        return None
    value = value.strip()
    decoded = unquote(value)
    if not value or any(ord(c) < 32 for c in decoded) or "\\" in decoded:
        return None
    try:
        parts = urlsplit(value)
        if ".." in unquote(parts.path).split("/"):
            return None
        if value.startswith("/") and not value.startswith("//"):
            return value
        if fragment and value.startswith("#"):
            return value
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return None
        _ = parts.port  # Reject malformed port values without resolving any host.
        host = parts.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith(".localhost"):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        return value
    except ValueError:
        return None

class TextParser(HTMLParser):
    blocked_tags = {"script", "style", "iframe", "object", "svg", "math", "template"}
    boundaries = {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "blockquote", "tr", "td"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []
        self.blocked = []
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        if tag in self.blocked_tags:
            self.blocked.append(tag)
        if self.blocked:
            return
        if tag in self.boundaries:
            self.handle_data(" ")
        if tag == "a":
            self.anchors.append((safe_url(dict(attrs).get("href")), []))

    def handle_endtag(self, tag):
        if tag in self.blocked_tags and tag in self.blocked:
            self.blocked = self.blocked[:len(self.blocked) - 1 - self.blocked[::-1].index(tag)]
            return
        if self.blocked:
            return
        if tag == "a" and self.anchors:
            href, parts = self.anchors.pop()
            label = " ".join("".join(parts).split())
            if href and label:
                self.links.append((label, href))
        if tag in self.boundaries:
            self.handle_data(" ")

    def handle_data(self, data):
        if not self.blocked:
            self.parts.append(data)
            for _, parts in self.anchors:
                parts.append(data)

def parse_text(value):
    parser = TextParser()
    parser.feed(value if isinstance(value, str) else "")
    parser.close()
    return " ".join("".join(parser.parts).split()), tuple(parser.links)

def plain_text(value):
    return parse_text(value)[0]

def normalize_person_rich_text(value: str) -> str:
    """Match the existing person renderer's SQL/JSON escape normalization."""
    import re
    if not isinstance(value, str):
        return ""
    value = re.sub(r"\\+r\\+n", "\n", value)
    value = re.sub(r"\\+[rn]", "\n", value)
    return re.sub(r"""\\+(["'/<>])""", r"\1", value)
