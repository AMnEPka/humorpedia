"""
Импорт шоу со старого сайта (раздел «Шоу» MODX, uri `show/`) в формат, который сохраняет админка.

Страницы раздела — шаблоны «Шоу» и «Вики»; вложенные (сезоны, подпроекты, разделы) становятся дочерними
шоу с адресом /shows/{путь из alias}. Команды шоу (шаблон «Команда» и страницы внутри «Команды …»)
сюда не входят — это отдельные сущности коллекции teams (services/modx_show_teams.py); страница-список
«Команды …» получает адрес /shows/{шоу}/teams, команды — /shows/{шоу}/teams/{slug}.

`build_show(site, resource_id, mapper)` → (payload для POST /api/content/shows, extra, warnings).

Секции MIGX (TV `config`):
  info          → table = факты, list_social = соцсети, subtitle/content = текстовые блоки без заголовка
  text          → текстовый блок (title = заголовок)
  table         → текстовый блок с таблицей
  timeline      → «Хронология»
  people_cards  → модуль «Участники» (participants)
  tags, post_footer, popular_articles, table_of_contents, base, реклама — не переносятся
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from services.modx_content import (
    LinkMapper, clean_html, clean_office_tables, clean_tables_in_html, extract_details, image_url, is_blank_html,
    parse_facts_table, plain_text, split_by_headings, split_details_in_order, split_tables, table_rows,
    unwrap_search_highlight,
)
from services.modx_dump import ModxSite, json_list
from services.modx_people import SOCIAL_FIELDS, TEMPLATE_PERSON, _module, _timeline_events, _timestamp, sidebar_modules
from services.show_teams import TEAMS_SEGMENT

SECTION_URI = "show/"
TEMPLATE_TEAM = 21
_IGNORED_SECTIONS = {"tags", "post_footer", "popular_articles", "table_of_contents", "base", "ad_250", "ad_block_120"}
_FIRST_BLOCK_RE = re.compile(r"^\s*<(p|div)\b[^>]*>(.*?)</\1>\s*", re.S | re.I)


def section_id(site: ModxSite) -> Optional[int]:
    resource = site.resource_by_uri(SECTION_URI)
    return resource["id"] if resource else None


def show_chain(site: ModxSite, resource: dict, root_id: int) -> Optional[List[dict]]:
    """Цепочка ресурсов от верхнего шоу до данного (None — ресурс не внутри раздела «Шоу»)."""
    chain = []
    current = resource
    for _ in range(12):
        chain.insert(0, current)
        parent = site.resources.get(current.get("parent"))
        if parent is None:
            return None
        if parent["id"] == root_id:
            return chain
        current = parent
    return None


def looks_like_team(site: ModxSite, resource: dict) -> bool:
    """Страница-вики команды: в фактах «Капитан» или «Город» + «Год основания» (команды Лиги Смеха,
    Импровизации). У студий («Квартал-95») год основания есть, города нет — это шоу."""
    cache = site.__dict__.setdefault("_team_like_cache", {})
    rid = resource["id"]
    if rid not in cache:
        keys = set()
        if site.tv_values.get(rid):
            for section in site.migx_sections(rid):
                if section.get("MIGX_formname") == "info":
                    keys |= {k for k, _ in parse_facts_table(section.get("table") or "")}
        cache[rid] = "Капитан" in keys or {"Город", "Год основания"} <= keys
    return cache[rid]


def is_show_page(site: ModxSite, resource: dict, root_id: int) -> bool:
    """Страница шоу (а не команда шоу): внутри раздела, не шаблон «Команда», не внутри страницы «Команды …»,
    не вики-страница команды."""
    if resource.get("deleted") or resource.get("template") == TEMPLATE_TEAM:
        return False
    chain = show_chain(site, resource, root_id)
    if not chain:
        return False
    if any(plain_text(r.get("pagetitle") or "").startswith("Команды") for r in chain[:-1]):
        return False
    return not looks_like_team(site, resource)


def page_slug(resource: dict) -> str:
    """slug страницы — последний сегмент её адреса на старом сайте (без .html).

    alias в MODX часто не совпадает с адресом (uri задан вручную: improv-teams/ при alias improv-kom),
    а знакомы читателям и поисковикам именно адреса.
    """
    uri = str(resource.get("uri") or "").strip("/")
    last = uri.rsplit("/", 1)[-1]
    if last.endswith(".html"):
        last = last[:-5]
    return last or (resource.get("alias") or "").strip("/")


def is_show_team_page(site: ModxSite, resource: dict, root_id: int) -> bool:
    """Страница команды шоу: внутри раздела «Шоу», но не страница шоу."""
    return (not resource.get("deleted") and show_chain(site, resource, root_id) is not None
            and not is_show_page(site, resource, root_id))


def is_teams_list_page(site: ModxSite, resource: dict, root_id: int) -> bool:
    """Страница-список «Команды …», внутри которой лежат страницы команд."""
    if not plain_text(resource.get("pagetitle") or "").startswith("Команды"):
        return False
    cache = site.__dict__.setdefault("_children_cache", {})
    if not cache:
        for r in site.resources.values():
            cache.setdefault(r.get("parent"), []).append(r)
    return any(is_show_team_page(site, child, root_id) for child in cache.get(resource["id"], []))


def show_slug(site: ModxSite, resource: dict, root_id: int) -> str:
    """slug страницы шоу на новом сайте: у списка «Команды …» — «teams» (как у команд КВН), иначе page_slug."""
    return TEAMS_SEGMENT if is_teams_list_page(site, resource, root_id) else page_slug(resource)


def show_path(site: ModxSite, resource: dict, root_id: int) -> Optional[str]:
    chain = show_chain(site, resource, root_id)
    return "/".join(show_slug(site, r, root_id) for r in chain) if chain else None


def show_url_builder(site: ModxSite):
    """Для LinkMapper: адрес страницы раздела «Шоу» на новом сайте (даже если она ещё не перенесена)."""
    root_id = section_id(site)

    def build(resource: dict) -> Optional[str]:
        if root_id is None or not is_show_page(site, resource, root_id):
            return None
        path = show_path(site, resource, root_id)
        return f"/shows/{path}" if path else None

    return build


def strip_nav_paragraph(html: str) -> str:
    """Убрать строку навигации «< предыдущий сезон … следующий >» в начале текста — на новом сайте её строит страница."""
    m = _FIRST_BLOCK_RE.match(html or "")
    if not m:
        return html
    text = plain_text(m.group(2))
    if "<a" in m.group(2) and len(text) < 200 and (text.startswith("<") or text.endswith(">")):
        return html[m.end():]
    return html


def _participants(site: ModxSite, section: dict, mapper: Optional[LinkMapper]) -> Optional[dict]:
    items = []
    for card in json_list(section.get("list_people")):
        if not isinstance(card, dict):
            continue
        facts = []
        for row in json_list(card.get("list_double")):
            if isinstance(row, dict) and row.get("title"):
                value = plain_text(row.get("content") or "")
                if value:
                    facts.append({"title": plain_text(row["title"]), "value": value})
        person = site.resources.get(int(card["link"])) if str(card.get("link") or "").isdigit() else None
        person_slug = person.get("alias") if person and person.get("template") == TEMPLATE_PERSON else None
        stage_name = next((f["value"] for f in facts if f["title"].lower() == "сценическое имя"), None)
        name = stage_name or (person and ((person.get("longtitle") or "").strip() or person.get("pagetitle"))) or ""
        items.append({"name": name, "person_slug": person_slug, "photo": image_url(card.get("photo")) or "", "facts": facts})
    if not items:
        return None
    return {"title": plain_text(section.get("title") or "") or "Участники", "items": items}


# ─── Разбор текста страницы ──────────────────────────────────────────────────

def text_blocks(block_title: str, html: str) -> List[Tuple[str, str, dict]]:
    """Очищенный HTML секции → модули, как у Убойной лиги:
    - спойлеры <details> на своих местах → свёрнутые блоки (одна таблица table_sort → сортируемая таблица);
    - длинный текст без заголовка с несколькими подзаголовками h3 → блоки по разделам;
    - таблицы очищены от оформления Excel/Word, победители (id="green_table") подсвечены."""
    blocks: List[Tuple[str, str, dict]] = []
    current_title = block_title
    for part in split_details_in_order(unwrap_search_highlight(html)):
        if part[0] == "html":
            fragment = clean_html(clean_tables_in_html(part[1]))
            if is_blank_html(fragment):
                continue
            if not current_title and len(re.findall(r"<h3\b", fragment, re.I)) >= 2 and len(fragment) > 5000:
                for heading, section in split_by_headings(fragment):
                    if not is_blank_html(section):
                        blocks.append(("text_block", heading, {"title": heading, "content": clean_html(section)}))
            else:
                blocks.append(("text_block", current_title, {"title": current_title, "content": fragment}))
            current_title = ""
            continue
        summary, inner = part[1].rstrip(":").strip(), part[2]
        tables = split_tables(inner)
        if len(tables) == 1 and "table_sort" in tables[0]:
            headers, rows = table_rows(tables[0])
            blocks.append(("table", summary, {
                "title": summary, "description": plain_text(inner[:inner.find("<table")]), "headers": headers,
                "rows": rows, "hasHeaders": True, "sortable": True, "collapsed": True,
            }))
        else:
            fragment = clean_html(clean_tables_in_html(inner))
            if not is_blank_html(fragment):
                blocks.append(("text_block", summary, {"title": summary, "content": fragment, "collapsed": True}))
    return blocks


# ─── Страницы с уникальной структурой ────────────────────────────────────────

def _ubojnaya_liga(content: List[Tuple[str, str, dict]], warnings: List[str]) -> List[Tuple[str, str, dict]]:
    """«Убойная лига» (show/ubojnaya-liga.html): один текстовый блок на 388 КБ.

    Разделы h3 → отдельные текстовые блоки; спойлеры со статистикой участников и дуэтов → сортируемые таблицы;
    125 таблиц выпусков (из Excel, победители отмечены id="green_table") → три свёрнутых блока по сезонам
    (границы сезонов — из раздела «Деление на сезоны»: выпуски 1–14, 15–86, 87–125).
    """
    texts = [c for c in content if c[0] == "text_block"]
    if len(texts) != 1:
        warnings.append("Убойная лига: ожидался один текстовый блок — структура страницы изменилась, перенесено как есть")
        return content
    html = texts[0][2]["content"]
    body, details = extract_details(html)
    footnote = ""
    fm = re.search(r"<p>\s*\*\s*[-–].*?</p>\s*$", body, re.S)
    if fm:
        footnote, body = fm.group(0), body[:fm.start()]

    result: List[Tuple[str, str, dict]] = []
    for heading, part in split_by_headings(body):
        if not is_blank_html(part):
            result.append(("text_block", heading, {"title": heading, "content": clean_html(part)}))

    seasons = [(1, 1, 14), (2, 15, 86), (3, 87, 125)]
    for summary, inner in details:
        tables = split_tables(inner)
        if "table_sort" in inner and len(tables) == 1:
            headers, rows = table_rows(tables[0])
            legend = inner[:inner.find("<table")]
            title = {"Посмотреть подробную статистику участников": "Подробная статистика участников",
                     "Статистика смешаных дуэтов участников": "Статистика смешанных дуэтов участников"}.get(summary, summary)
            result.append(("table", title, {
                "title": title, "description": plain_text(legend), "headers": headers, "rows": rows,
                "hasHeaders": True, "sortable": True, "collapsed": True,
            }))
        elif len(tables) > 1:
            by_season = {n: [] for n, _, _ in seasons}
            for table in tables:
                m = re.search(r"Выпуск.*?</t[dh]>\s*<t[dh][^>]*>(?:\s|<[^>]+>)*(\d+)", table, re.S)
                number = int(m.group(1)) if m else 0
                season = next((n for n, lo, hi in seasons if lo <= number <= hi), None)
                if season is None:
                    warnings.append(f"Убойная лига: таблица без номера выпуска ({plain_text(table)[:40]}…)")
                    season = seasons[-1][0]
                by_season[season].append(clean_office_tables(table))
            for n, lo, hi in seasons:
                if by_season[n]:
                    title = f"Статистика выпусков: {n}-й сезон (выпуски {lo}–{hi})"
                    result.append(("text_block", title, {"title": title, "content": "\n".join(by_season[n]),
                                                         "collapsed": True}))
        else:
            warnings.append(f"Убойная лига: неизвестный спойлер «{summary}» — перенесён текстом")
            result.append(("text_block", summary, {"title": summary, "content": inner, "collapsed": True}))
    if footnote:
        result.append(("text_block", "", {"title": "", "content": footnote.strip()}))
    return result


# id ресурса MODX → обработчик уникальной структуры страницы (контентные модули после общего разбора)
SPECIAL_PAGES = {
    1628: _ubojnaya_liga,
}


def build_show(site: ModxSite, resource_id: int, mapper: Optional[LinkMapper] = None) -> Tuple[dict, dict, List[str]]:
    resource = site.resources[resource_id]
    warnings: List[str] = []
    title = (resource.get("longtitle") or "").strip() or (resource.get("pagetitle") or "").strip()

    facts: Dict[str, str] = {}
    social: Dict[str, str] = {}
    content: List[Tuple[str, str, dict]] = []
    first_text = True
    pending_title = ""  # заголовок пустого блока («Сезоны и победители» + «...») переходит к следующему

    def add_text(block_title: str, html: str) -> None:
        nonlocal first_text, pending_title
        if block_title == title:
            block_title = ""
        html = clean_html(html, mapper)
        if first_text:
            html = strip_nav_paragraph(html)
        if is_blank_html(html) or plain_text(html) in ("...", "…"):
            pending_title = block_title or pending_title
            return
        if not block_title and pending_title:
            block_title, pending_title = pending_title, ""
        first_text = False
        if resource_id in SPECIAL_PAGES:  # у особых страниц текст разбирает свой обработчик
            content.append(("text_block", block_title, {"title": block_title, "content": html}))
        else:
            content.extend(text_blocks(block_title, html))

    for section in site.migx_sections(resource_id):
        form = section.get("MIGX_formname")
        if form == "info":
            for key, value in parse_facts_table(section.get("table") or ""):
                facts[key] = value
            for item in json_list(section.get("list_social")):
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip().lower()
                link = str(item.get("link") or "").strip()
                target = SOCIAL_FIELDS.get(name)
                if link and target and target not in social:
                    social[target] = link
                elif link and not target:
                    warnings.append(f"соцсеть «{name}» не поддерживается: {link}")
            add_text("", section.get("subtitle") or "")
            add_text("", section.get("content") or "")
        elif form == "text":
            add_text(plain_text(section.get("title") or ""), section.get("content") or "")
        elif form == "table":
            add_text("", section.get("content") or "")
        elif form == "timeline":
            events = _timeline_events(section, mapper)
            if events:
                content.append(("timeline", "Хронология", {"title": "Хронология", "events": events}))
        elif form == "people_cards":
            data = _participants(site, section, mapper)
            if data:
                content.append(("participants", data["title"], data))
        elif form not in _IGNORED_SECTIONS:
            warnings.append(f"секция «{form}» не перенесена")

    if resource_id in SPECIAL_PAGES:
        content = SPECIAL_PAGES[resource_id](content, warnings)
    if not content:
        warnings.append("на странице нет текста")

    modules = [
        _module(type_, order, module_title, data)
        for order, (type_, module_title, data) in enumerate(sidebar_modules() + content, start=1)
    ]

    poster = None
    poster_url = image_url(site.tv(resource_id, "img"))
    if poster_url:
        poster = {"url": poster_url, "alt": plain_text(site.tv(resource_id, "img_alt")) or title,
                  "caption": "", "thumbnail": poster_url}

    published = bool(resource.get("published")) and not resource.get("deleted")
    description = plain_text(resource.get("description") or "")
    payload = {
        "title": title,
        "name": title,
        "slug": show_slug(site, resource, section_id(site)),
        "status": "published" if published else "draft",
        "poster": poster,
        "facts": facts,
        "facts_order": list(facts),
        "social_links": social,
        "description": description or None,
        "order": int(resource.get("menuindex") or 0),
        "modules": modules,
        "tags": site.tags_of(resource_id),
        "seo": {
            "meta_title": title,
            "meta_description": description,
            "keywords": [k.strip() for k in (resource.get("keywords") or "").split(",") if k.strip()],
        },
    }

    votes = int(resource.get("votes") or 0)
    extra = {
        "old_id": int(resource["id"]),
        # без завершающего «/» — так нормализует путь поиск редиректов
        "old_urls": ["/" + str(resource["uri"]).strip("/")] if resource.get("uri") else [],
        "rating": {"average": round(min(10.0, max(0.0, float(resource.get("rating") or 0))), 2), "count": votes},
        "votes_count": votes,
    }
    created_at = _timestamp(resource.get("createdon"))
    if created_at:
        extra["created_at"] = created_at
    published_at = (_timestamp(resource.get("publishedon")) or created_at) if published else None
    if published_at:
        extra["published_at"] = published_at
    return payload, extra, warnings
