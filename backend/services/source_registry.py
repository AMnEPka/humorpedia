"""Explicit source definitions shared by HTTP, parsing and editorial attribution."""
from dataclasses import dataclass
from importlib import import_module
import re
from urllib.parse import parse_qsl, urlsplit, urlunsplit


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    host: str
    hosts: tuple[str, ...]
    document_pattern: str
    discovery_url: str
    adapter: str


SOURCES = {
    '24smi': Source('24smi', '24СМИ', '24smi.org', ('24smi.org', 'www.24smi.org'),
        r'/(?:news|celebrity)/[0-9]+-[a-z0-9-]+\.html', 'https://24smi.org/sitemap-news.xml', 'smi24'),
    'vokrugtv': Source('vokrugtv', 'Вокруг ТВ', 'www.vokrug.tv', ('vokrug.tv', 'www.vokrug.tv'),
        r'/(?:person|article)/show/[a-zA-Z0-9_-]+/?', 'https://www.vokrug.tv/article/', 'vokrugtv'),
    'gostandup': Source('gostandup', 'GoStandup', 'gostandup.ru', ('gostandup.ru', 'www.gostandup.ru'),
        r'/(?:comedians|articles)/[a-zA-Z0-9_-]+/?', 'https://gostandup.ru/articles', 'gostandup'),
    'zhaba': Source('zhaba', 'ЖАБА — медиа-болото', 't.me', ('t.me', 'telegram.me'),
        r'/(?:s/)?zhabqua/[1-9][0-9]{0,17}/?', 'https://t.me/s/zhabqua', 'zhaba'),
}


def get_source(source_id='24smi'):
    try:
        return SOURCES[source_id]
    except (KeyError, TypeError) as exc:
        raise ValueError('Неизвестный источник импорта') from exc


def canonical_url(value: str, *, resource=False) -> str:
    if not isinstance(value, str) or len(value) > 2000:
        raise ValueError('Слишком длинный URL')
    parsed = urlsplit(value.strip())
    source = next((item for item in SOURCES.values() if parsed.hostname in item.hosts), None)
    if (not source or parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError('Разрешены только HTTPS-адреса подключённых источников без логина и нестандартного порта')
    path = parsed.path
    document = bool(re.fullmatch(source.document_pattern, path))
    query = ''
    if source.id == 'zhaba':
        path = path.rstrip('/')
        if document:
            path = path.removeprefix('/s')
        elif path == '/s/zhabqua' and resource and parsed.query:
            pairs = parse_qsl(parsed.query, keep_blank_values=True)
            if len(pairs) != 1 or pairs[0][0] != 'before' or not re.fullmatch(r'[1-9][0-9]{0,17}', pairs[0][1]):
                raise ValueError('Разрешена только объявленная лентой пагинация before')
            query = 'before=' + pairs[0][1]
    if document and source.id == 'vokrugtv':
        path = path.rstrip('/') + '/'
    elif source.id == 'gostandup':
        path = path.rstrip('/')
    resources = {'/robots.txt', urlsplit(source.discovery_url).path}
    if not document and not (resource and path in resources):
        raise ValueError('Нужна ссылка на биографию или статью поддерживаемого источника')
    return urlunsplit(('https', source.host, path, query, ''))


def request_url(value):
    """Use Telegram's public preview transport while retaining canonical post identity."""
    url = canonical_url(value, resource=True)
    parsed = urlsplit(url)
    if source_for_url(url, resource=True).id == 'zhaba' and parsed.path.startswith('/zhabqua/'):
        return urlunsplit(('https', 't.me', '/s' + parsed.path, '', ''))
    return url


def source_for_url(value: str, *, resource=False):
    host = urlsplit(canonical_url(value, resource=resource)).hostname
    return next(source for source in SOURCES.values() if source.host == host)


def parse_document(html, url):
    source = source_for_url(url)
    return import_module('services.source_adapters.' + source.adapter).parse_document(html, canonical_url(url))


def discover_news(text, since, limit=100, *, source_id='24smi'):
    source = get_source(source_id)
    return import_module('services.source_adapters.' + source.adapter).discover_news(text, since, limit=limit)
