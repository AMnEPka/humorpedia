"""
Ссылки в HTML контента при выдаче на публичный сайт.

- ссылка на существующую опубликованную страницу → её актуальный адрес (в том числе по старому URL MODX
  из `old_urls`, по `[[~id]]` через `old_id` и по известным паттернам старых адресов);
- ссылка на страницу, которой пока нет или которая не опубликована → обычный текст. В данных ссылка
  остаётся и «оживёт», когда страница появится (кэш сбрасывается при любой записи);
- внешние ссылки, якоря, файлы и служебные разделы сайта не трогаются.

Документы в данных не меняются. Админка читает их с `?raw=true`, чтобы при сохранении не потерять ссылки.

Все ссылки одного ответа проверяются пачкой: по одному запросу `$in` на коллекцию.
"""
from __future__ import annotations

import html as html_lib
import re
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlsplit

from services.cache import cache_service
from utils.database import get_db

_A_RE = re.compile(r"<a\b([^>]*)>(.*?)</a\s*>", re.I | re.S)
_HREF_RE = re.compile(r"""(\bhref\s*=\s*)(["'])(.*?)\2""", re.I | re.S)
_MODX_LINK_RE = re.compile(r"^\[\[~(\d+)[^\]]*\]\]$")
_SITE_HOSTS = {"humorpedia.ru", "www.humorpedia.ru", "dev.humorpedia.ru"}

# Разделы нового сайта без документа в БД (списки, служебные страницы) — ссылки на них всегда живые
STATIC_PATHS = {
    "", "news", "articles", "people", "kvn/teams", "shows", "quizzes", "city", "contacts", "policy",
    "search", "kvn/vl-kvn/vl-jury",
}
PASS_PREFIXES = ("tags/", "admin", "media/", "images/", "uploads/", "api/", "static/", "assets/")

PUBLISHED = {"status": {"$nin": ["draft", "archived"]}}

# Коллекция → адрес документа на сайте
URL_BUILDERS: Dict[str, Callable[[dict], str]] = {
    "people": lambda d: f"/people/{d['slug']}",
    "teams": lambda d: f"/kvn/teams/{d['slug']}",
    "kvn": lambda d: "/" + (d.get("full_path") or f"kvn/{d['slug']}").strip("/"),
    "shows": lambda d: "/shows/" + (d.get("full_path") or d["slug"]).strip("/"),
    "articles": lambda d: f"/articles/{d['slug']}",
    "news": lambda d: f"/news/{d['slug']}",
    "quizzes": lambda d: f"/quizzes/{d['slug']}",
    "cities": lambda d: f"/city/{d['slug']}",
}
OLD_URL_COLLECTIONS = ("people", "teams", "kvn", "shows", "articles", "news")


def link_key(href: str) -> Optional[str]:
    """Ключ проверки ссылки: путь без слэшей по краям, `~<id>` для `[[~id]]`; None — ссылку не трогаем."""
    href = html_lib.unescape((href or "").strip())
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    modx = _MODX_LINK_RE.match(href)
    if modx:
        return "~" + modx.group(1)
    parts = urlsplit(href)
    if (parts.scheme or parts.netloc) and parts.hostname not in _SITE_HOSTS:
        return None
    path = parts.path.strip("/")
    if path in STATIC_PATHS or path.startswith(PASS_PREFIXES):
        return None
    return path


def link_suffix(href: str) -> str:
    parts = urlsplit(html_lib.unescape((href or "").strip()))
    return ("?" + parts.query if parts.query else "") + ("#" + parts.fragment if parts.fragment else "")


def direct_query(path: str) -> Optional[Tuple[str, str, str]]:
    """Путь нового сайта → (коллекция, поле, значение) для поиска документа."""
    parts = path.split("/")
    if parts[0] == "people" and len(parts) == 2:
        return "people", "slug", parts[1]
    if path.startswith("kvn/teams/") and len(parts) == 3:
        return "teams", "slug", parts[2]
    if parts[0] == "kvn":
        return "kvn", "full_path", path
    if parts[0] == "shows" and len(parts) >= 2:
        return "shows", "full_path", "/".join(parts[1:])
    if parts[0] in ("news", "articles", "quizzes") and len(parts) == 2:
        return parts[0], "slug", parts[1]
    if parts[0] == "city" and len(parts) == 2:
        return "cities", "slug", parts[1]
    return None


def replace_links(html: str, targets: Dict[str, Optional[str]]) -> str:
    """Подставить найденные адреса; ссылки на отсутствующие страницы превратить в текст."""

    def repl(m: re.Match) -> str:
        attrs, inner = m.group(1), m.group(2)
        href_m = _HREF_RE.search(attrs)
        if not href_m:
            return m.group(0)
        href = href_m.group(3)
        key = link_key(href)
        if key is None or key not in targets:
            return m.group(0)
        url = targets[key]
        if url is None:
            return inner
        new_href = url + link_suffix(href)
        if new_href == href:
            return m.group(0)
        new_attrs = attrs[:href_m.start(3)] + html_lib.escape(new_href, quote=True) + attrs[href_m.end(3):]
        return f"<a{new_attrs}>{inner}</a>"

    return _A_RE.sub(repl, html)


def collect_keys(html: str) -> Set[str]:
    keys = set()
    for m in _A_RE.finditer(html or ""):
        href_m = _HREF_RE.search(m.group(1))
        if href_m:
            key = link_key(href_m.group(3))
            if key is not None:
                keys.add(key)
    return keys


def _html_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        if "<a" in value:
            yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _html_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _html_strings(v)


def _replace_strings(value: Any, resolved: Dict[str, str]) -> Any:
    if isinstance(value, str):
        return resolved.get(value, value)
    if isinstance(value, dict):
        return {k: _replace_strings(v, resolved) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace_strings(v, resolved) for v in value]
    return value


async def _find_urls(db, queries: Dict[str, Tuple[str, str, str]]) -> Dict[str, str]:
    """{ключ: (коллекция, поле, значение)} → {ключ: адрес} для найденных опубликованных документов."""
    grouped: Dict[Tuple[str, str], Dict[Any, List[str]]] = defaultdict(lambda: defaultdict(list))
    for key, (coll, field, value) in queries.items():
        grouped[(coll, field)][value].append(key)
    found: Dict[str, str] = {}
    for (coll, field), values in grouped.items():
        query = {field: {"$in": list(values)}, **PUBLISHED}
        async for doc in db[coll].find(query, {"slug": 1, "full_path": 1, field: 1}):
            for key in values.get(doc.get(field), []):
                found[key] = URL_BUILDERS[coll](doc)
    return found


async def resolve_targets(db, keys: Set[str]) -> Dict[str, Optional[str]]:
    """Ключи ссылок → адрес на сайте или None, если страницы нет."""
    from routes.redirects import _try_pattern_redirect

    result: Dict[str, Optional[str]] = {}
    pending = set(keys)

    # 1. Адреса нового сайта
    queries = {k: q for k in pending if not k.startswith("~") and (q := direct_query(k))}
    result.update(await _find_urls(db, queries))
    # у части шоу нет full_path — ищем по slug последнего сегмента
    show_slugs = {k: ("shows", "slug", k.split("/")[-1]) for k in pending
                  if k.startswith("shows/") and k not in result}
    result.update(await _find_urls(db, show_slugs))
    pending -= result.keys()

    # 2. [[~id]] и старые адреса MODX (old_id / old_urls)
    old_ids = {k: int(k[1:]) for k in pending if k.startswith("~")}
    if old_ids:
        for coll in URL_BUILDERS:
            if not old_ids:
                break
            async for doc in db[coll].find({"old_id": {"$in": list(old_ids.values())}, **PUBLISHED},
                                           {"slug": 1, "full_path": 1, "old_id": 1}):
                for k in [k for k, v in old_ids.items() if v == doc.get("old_id")]:
                    result[k] = URL_BUILDERS[coll](doc)
                    old_ids.pop(k)
    # старый адрес хранится в old_urls как «/show/x.html»; в тексте после перевода ссылок — «/show/x»
    old_paths = {}
    for k in pending:
        if not k.startswith("~") and k not in result:
            old_paths["/" + k] = k
            if not k.endswith(".html"):
                old_paths.setdefault("/" + k + ".html", k)
    if old_paths:
        for coll in OLD_URL_COLLECTIONS:
            async for doc in db[coll].find({"old_urls": {"$in": list(old_paths)}, **PUBLISHED},
                                           {"slug": 1, "full_path": 1, "old_urls": 1}):
                for url in doc.get("old_urls") or []:
                    if url in old_paths and old_paths[url] not in result:
                        result[old_paths[url]] = URL_BUILDERS[coll](doc)
    pending -= result.keys()

    # 3. Известные паттерны старых адресов → адрес нового сайта
    patterned = {}
    for k in pending:
        if k.startswith("~"):
            continue
        new_path = _try_pattern_redirect("/" + k)
        if new_path and new_path.strip("/") != k:
            new_key = new_path.strip("/")
            if new_key in STATIC_PATHS:
                result[k] = "/" + new_key
            elif (q := direct_query(new_key)):
                patterned[k] = q
    result.update(await _find_urls(db, patterned))
    pending -= result.keys()

    for k in pending:
        result[k] = None
    return result


async def load_old_id_urls(db) -> Dict[int, str]:
    """id ресурса старого сайта (old_id) → адрес перенесённой страницы. Для перевода ссылок при импорте."""
    urls: Dict[int, str] = {}
    for coll, build in URL_BUILDERS.items():
        async for doc in db[coll].find({"old_id": {"$ne": None}}, {"slug": 1, "full_path": 1, "old_id": 1}):
            try:
                urls.setdefault(int(doc["old_id"]), build(doc))
            except (TypeError, ValueError, KeyError):
                continue
    return urls


class LinkResolver:
    """Обработка ссылок в ответах публичного API."""

    @staticmethod
    async def resolve_value(value: Any) -> Any:
        """Вернуть копию структуры (строка / dict / list), где все HTML-строки обработаны."""
        strings = set(_html_strings(value))
        if not strings:
            return value
        resolved: Dict[str, str] = {}
        todo = []
        for s in strings:
            cached = cache_service.get_resolved_html(s)
            if cached is not None:
                resolved[s] = cached
            else:
                todo.append(s)
        if todo:
            keys = set().union(*(collect_keys(s) for s in todo))
            targets = await resolve_targets(await get_db(), keys) if keys else {}
            for s in todo:
                out = replace_links(s, targets) if keys else s
                cache_service.set_resolved_html(s, out)
                resolved[s] = out
        return _replace_strings(value, resolved)

    @staticmethod
    async def resolve_links_in_html(html: str) -> str:
        return await LinkResolver.resolve_value(html) if html else html

    @staticmethod
    async def resolve_links_in_modules(modules: List[Dict]) -> List[Dict]:
        return await LinkResolver.resolve_value(modules) if modules else modules

    @staticmethod
    async def resolve_document(doc: dict, fields: Iterable[str] = ("modules", "facts")) -> dict:
        """Обработать ссылки в указанных полях документа (на месте)."""
        present = {f: doc[f] for f in fields if doc.get(f)}
        if present:
            resolved = await LinkResolver.resolve_value(present)
            doc.update(resolved)
        return doc
