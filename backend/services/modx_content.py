"""
Общие преобразования контента MODX при импорте: HTML текстовых блоков, ссылки, картинки, таблицы фактов.

Результат должен быть таким же, каким его сохранила бы админка: абсолютные ссылки нового сайта,
картинки из volume (`/media/imported/images/...`), обычные символы вместо HTML-сущностей.
"""
from __future__ import annotations

import html as html_lib
import re
from html.parser import HTMLParser
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from services.modx_dump import ModxSite

IMPORTED_IMAGES_PREFIX = "/media/imported/"

# Сущности, которые нельзя раскрывать: они экранируют разметку
_KEEP_ENTITIES = {"lt", "gt", "amp", "quot", "#60", "#62", "#38", "#34", "#x3c", "#x3e", "#x26", "#x22"}
_ENTITY_RE = re.compile(r"&(#\d+|#[xX][0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);")
_ATTR_RE = re.compile(r"""(\s(?:href|src)\s*=\s*)(["'])(.*?)\2""", re.I | re.S)
_MODX_LINK_RE = re.compile(r"^\[\[~(\d+)[^\]]*\]\]$")
_TAG_RE = re.compile(r"<[^>]+>")
_EMPTY_TAIL_RE = re.compile(r"(?:\s*<p[^>]*>(?:\s|&nbsp;| |<br\s*/?>)*</p>)+\s*$", re.I)
_SITE_HOSTS = {"humorpedia.ru", "www.humorpedia.ru", "dev.humorpedia.ru"}

# Шаблоны MODX → адрес страницы на новом сайте (slug = alias ресурса)
TEMPLATE_URLS = {
    20: "/people/{alias}",      # Человек
    21: "/kvn/teams/{alias}",   # Команда КВН
}


def decode_entities(text: str) -> str:
    """Раскрыть HTML-сущности (&nbsp; &laquo; &ndash; …), кроме экранирующих разметку."""

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name.lower() in _KEEP_ENTITIES:
            return m.group(0)
        decoded = html_lib.unescape(m.group(0))
        return decoded if decoded != m.group(0) else m.group(0)

    return _ENTITY_RE.sub(repl, text or "")


def plain_text(value: str) -> str:
    """Текст без тегов и сущностей, с нормализованными пробелами (для заголовков, фактов, годов)."""
    text = html_lib.unescape(_TAG_RE.sub(" ", value or ""))
    return re.sub(r"\s+", " ", text.replace(" ", " ")).strip()


def is_blank_html(value: str) -> bool:
    return plain_text(value) == "" and "<img" not in (value or "").lower()


def image_url(path: str) -> Optional[str]:
    """Путь картинки MODX (`images/people/x.jpg`) → URL в volume нового сайта."""
    path = (path or "").strip()
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        parts = urlsplit(path)
        if parts.hostname not in _SITE_HOSTS:
            return path
        path = parts.path
    path = path.lstrip("/")
    if path.startswith("media/"):
        return "/" + path
    return IMPORTED_IMAGES_PREFIX + path


class LinkMapper:
    """Переводит ссылки старого сайта в адреса нового.

    Порядок: ресурс MODX по uri (или `[[~id]]`) → адрес по шаблону (люди, команды);
    иначе известный паттерн старых URL (routes/redirects.py); иначе абсолютный старый путь —
    его разрешит поиск редиректов, когда страница появится.
    """

    def __init__(self, site: ModxSite, pattern_redirect: Optional[Callable[[str], Optional[str]]] = None,
                 known_urls: Optional[Dict[int, str]] = None,
                 url_builders: Optional[List[Callable[[dict], Optional[str]]]] = None):
        self.site = site
        self.pattern_redirect = pattern_redirect
        # id ресурса MODX → адрес уже перенесённой страницы (документы с old_id)
        self.known_urls = known_urls or {}
        # адреса по разделам старого сайта для ещё не перенесённых страниц (например, шоу)
        self.url_builders = url_builders or []
        self.unresolved: List[str] = []

    def resource_url(self, resource: dict) -> Optional[str]:
        known = self.known_urls.get(resource.get("id"))
        if known:
            return known
        template_url = TEMPLATE_URLS.get(resource.get("template"))
        if template_url and resource.get("alias"):
            return template_url.format(alias=resource["alias"])
        for build in self.url_builders:
            url = build(resource)
            if url:
                return url
        return None

    def map(self, href: str) -> str:
        href = (href or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            return href
        modx = _MODX_LINK_RE.match(href)
        if modx:
            resource = self.site.resources.get(int(modx.group(1)))
            if resource:
                return self.resource_url(resource) or "/" + str(resource.get("uri") or "").lstrip("/")
            self.unresolved.append(href)
            return href
        parts = urlsplit(href)
        if parts.scheme or parts.netloc:
            if parts.hostname not in _SITE_HOSTS:
                return href
        path = parts.path.lstrip("/")
        suffix = ("?" + parts.query if parts.query else "") + ("#" + parts.fragment if parts.fragment else "")
        if path.startswith("images/"):
            return (image_url(path) or href) + suffix
        if path.startswith("media/") or path.startswith("uploads/"):
            return "/" + path + suffix
        if not path:
            return "/" + suffix
        resource = self.site.resource_by_uri(path)
        if resource:
            url = self.resource_url(resource)
            if url:
                return url + suffix
        old_path = "/" + path.rstrip("/")
        if self.pattern_redirect:
            new_path = self.pattern_redirect(old_path)
            if new_path:
                return new_path + suffix
        if not resource:
            self.unresolved.append(href)
        return "/" + path + suffix


def rewrite_links(value: str, mapper: LinkMapper) -> str:
    """Перевести href/src старого сайта на адреса нового, не трогая остальной HTML (для уже сохранённого контента)."""
    return _ATTR_RE.sub(
        lambda m: m.group(1) + m.group(2) + _keep_or_map(m.group(3), mapper) + m.group(2), value or "")


def _keep_or_map(raw: str, mapper: LinkMapper) -> str:
    mapped = mapper.map(html_lib.unescape(raw))
    return raw if mapped == html_lib.unescape(raw) else html_lib.escape(mapped, quote=True)


def clean_html(value: str, mapper: Optional[LinkMapper] = None) -> str:
    """HTML из MODX → HTML текстового блока нового сайта."""
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = decode_entities(text)
    if mapper is not None:
        text = _ATTR_RE.sub(lambda m: m.group(1) + m.group(2) + mapper.map(html_lib.unescape(m.group(3))) + m.group(2), text)
    text = _EMPTY_TAIL_RE.sub("", text)
    return text.strip()


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.rows: List[List[str]] = []
        self._row: Optional[List[str]] = None
        self._cell: Optional[List[str]] = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append("".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_entityref(self, name):
        if self._cell is not None:
            self._cell.append(f"&{name};")

    def handle_charref(self, name):
        if self._cell is not None:
            self._cell.append(f"&#{name};")


def parse_facts_table(value: str) -> List[Tuple[str, str]]:
    """Таблица «ключ — значение» (факты о человеке/команде) → [(ключ, значение)] в исходном порядке."""
    if not value or "<t" not in value.lower():
        return []
    parser = _TableParser()
    parser.feed(value)
    parser.close()
    facts: List[Tuple[str, str]] = []
    seen = set()
    for row in parser.rows:
        cells = [plain_text(c) for c in row]
        if len(cells) < 2 or not cells[0] or not cells[1] or cells[0] in seen:
            continue
        seen.add(cells[0])
        facts.append((cells[0], cells[1]))
    return facts


# ─── Разбор длинных страниц: разделы, спойлеры, таблицы ─────────────────────

_DETAILS_RE = re.compile(r"<details\b[^>]*>\s*(?:<summary\b[^>]*>(.*?)</summary>)?(.*?)</details>", re.I | re.S)
_HEADING_RE = re.compile(r"<h3\b[^>]*>(.*?)</h3>", re.I | re.S)
_TABLE_RE = re.compile(r"<table\b.*?</table>", re.I | re.S)


def split_by_headings(html: str) -> List[Tuple[str, str]]:
    """HTML → [(заголовок h3, содержимое до следующего h3)]; текст до первого заголовка — с пустым заголовком."""
    parts: List[Tuple[str, str]] = []
    matches = list(_HEADING_RE.finditer(html or ""))
    intro = (html or "")[:matches[0].start()] if matches else (html or "")
    if not is_blank_html(intro):
        parts.append(("", intro.strip()))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        parts.append((plain_text(m.group(1)), html[m.end():end].strip()))
    return parts


def extract_details(html: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Вынуть раскрывающиеся блоки <details>: (HTML без них, [(summary, содержимое)])."""
    blocks = [(plain_text(m.group(1) or ""), m.group(2)) for m in _DETAILS_RE.finditer(html or "")]
    return _DETAILS_RE.sub("", html or ""), blocks


def table_rows(table_html: str) -> Tuple[List[str], List[List[str]]]:
    """HTML-таблица → (заголовки, строки) обычным текстом; заголовки — первая строка из <th>."""
    parser = _TableParser()
    parser.feed(table_html)
    parser.close()
    rows = [[plain_text(c) for c in row] for row in parser.rows]
    headers: List[str] = []
    if rows and re.search(r"<th\b", table_html, re.I):
        headers = rows.pop(0)
    return headers, [r for r in rows if any(r)]


_TAG_ATTRS_RE = re.compile(r"<(table|thead|tbody|tfoot|tr|td|th|div|col)\b([^>]*)>", re.I)
_SPAN_ATTR_RE = re.compile(r"""\b(colspan|rowspan)\s*=\s*["']?(\d+)["']?""", re.I)
WINNER_MARK = '<mark data-color="#bbf7d0" style="background-color: #bbf7d0; color: inherit">{}</mark>'


def clean_office_tables(html: str, winner_marker: str = "green_table") -> str:
    """Таблицы, вставленные из Excel/Word: убрать оформление (class, width, height, colgroup, обёртки div),
    оставить colspan/rowspan. Клетки с id=winner_marker (на старом сайте — зелёные, победители) подсветить <mark>."""
    html = re.sub(r"<colgroup\b.*?</colgroup>", "", html or "", flags=re.I | re.S)
    html = re.sub(r"<col\b[^>]*>", "", html, flags=re.I)
    html = re.sub(r"<div\b[^>]*>|</div>", "", html, flags=re.I)
    html = re.sub(r"(<br\s*/?>\s*)+(?=<table)", "", html, flags=re.I)

    def cell(m: re.Match) -> str:
        tag, attrs = m.group(1).lower(), m.group(2)
        kept = " ".join(f'{a.lower()}="{v}"' for a, v in _SPAN_ATTR_RE.findall(attrs) if v != "1")
        opening = f"<{tag}{(' ' + kept) if kept else ''}>"
        if tag in ("td", "th") and winner_marker and winner_marker in attrs:
            return opening + "\x00WIN\x00"
        return opening

    html = _TAG_ATTRS_RE.sub(cell, html)
    html = re.sub(r"<p>(?:\s|&nbsp;| )*</p>", "", html)
    html = re.sub(r"\x00WIN\x00(.*?)(?=</t[dh]>)",
                  lambda m: WINNER_MARK.format(m.group(1)) if plain_text(m.group(1)) else m.group(1),
                  html, flags=re.S)
    return html.strip()


_HIGHLIGHT_RE = re.compile(r'<span class="highlight">(.*?)</span>', re.I | re.S)
_TABLE_WRAP_RE = re.compile(
    r'<div\b[^>]*class="[^"]*(?:big-table|table-wrap)[^"]*"[^>]*>((?:\s|<br\s*/?>)*<table\b.*?</table>(?:\s|&nbsp;| )*)</div>',
    re.I | re.S)


def unwrap_search_highlight(html: str) -> str:
    """Убрать подсветку поиска MODX (<span class="highlight">кино</span>театр), попавшую в сохранённый текст."""
    return _HIGHLIGHT_RE.sub(r"\1", html or "")


def clean_tables_in_html(html: str) -> str:
    """Очистить все таблицы внутри HTML (clean_office_tables), снять обёртки div вокруг таблиц; остальной текст не трогается."""
    html = _TABLE_WRAP_RE.sub(r"\1", html or "")
    return _TABLE_RE.sub(lambda m: clean_office_tables(m.group(0)), html)


def split_details_in_order(html: str) -> List[Tuple[str, ...]]:
    """HTML → последовательность ("html", фрагмент) и ("details", summary, содержимое) в исходном порядке."""
    parts: List[Tuple[str, ...]] = []
    pos = 0
    for m in _DETAILS_RE.finditer(html or ""):
        if m.start() > pos:
            parts.append(("html", html[pos:m.start()]))
        parts.append(("details", plain_text(m.group(1) or ""), m.group(2)))
        pos = m.end()
    if pos < len(html or ""):
        parts.append(("html", html[pos:]))
    return parts


def split_tables(html: str) -> List[str]:
    """Все таблицы HTML по отдельности."""
    return _TABLE_RE.findall(html or "")
