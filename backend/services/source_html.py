"""HTML cleaning helpers for imported source text."""
from html import escape
from html.parser import HTMLParser
import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit


def _safe_url(value, media=False):
    if not value:
        return value
    if not isinstance(value, str) or any(ord(c) < 32 for c in value) or '\\' in value:
        raise ValueError('Недопустимый адрес')
    if re.fullmatch(r'asset:[a-zA-Z0-9_-]{1,80}', value):
        return value
    parsed = urlsplit(value)
    if parsed.scheme in ('http', 'https') and parsed.hostname:
        host = parsed.hostname.lower()
        if host in ('localhost', '127.0.0.1', '::1', '0.0.0.0') or host.endswith('.localhost'):
            raise ValueError('Адрес localhost нельзя перенести на другой сайт')
        if not media:
            return value
    if value.startswith('/') and not value.startswith('//') and not parsed.scheme:
        if '..' not in PurePosixPath(parsed.path).parts and not media:
            return value
    if value.startswith('#') and not media:
        return value
    raise ValueError('Изображение нужно добавить в пакет' if media else 'Допустимы только http(s) и внутренние пути сайта')


class _HTML(HTMLParser):
    allowed = {'p', 'br', 'strong', 'em', 'b', 'i', 'u', 's', 'ul', 'ol', 'li', 'h2', 'h3', 'h4',
               'blockquote', 'a', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'span', 'div'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.blocked = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'iframe', 'object', 'svg', 'math'}:
            self.blocked += 1
        if self.blocked or tag not in self.allowed:
            return
        allowed_attrs = []
        for key, value in attrs:
            if tag == 'a' and key == 'href':
                try:
                    allowed_attrs.append(f'href="{escape(_safe_url(value or ""), quote=True)}"')
                except ValueError:
                    pass
            if key in ('colspan', 'rowspan') and tag in ('td', 'th') and re.fullmatch(r'[1-9][0-9]?', value or ''):
                allowed_attrs.append(f'{key}="{value}"')
        self.out.append('<' + tag + (' ' + ' '.join(allowed_attrs) if allowed_attrs else '') + '>')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'iframe', 'object', 'svg', 'math'}:
            self.blocked = max(0, self.blocked - 1)
            return
        if not self.blocked and tag in self.allowed and tag != 'br':
            self.out.append(f'</{tag}>')

    def handle_data(self, value):
        if not self.blocked:
            self.out.append(escape(value, quote=False))


def sanitize(value):
    """Keep the existing page-package allowlist and strip active content/unsafe links."""
    parser = _HTML()
    parser.feed(value)
    parser.close()
    return ''.join(parser.out)
