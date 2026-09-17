"""
Импорт команд шоу со старого сайта (страницы внутри раздела «Шоу», которые не шоу) в формат админки.

Страницы: «Команды ЛГ» / «Команды шоу «Звёзды»» / … (шаблоны «Команда» и «Вики»), команды Лиги Смеха прямо внутри шоу.
Адрес на новом сайте — /shows/{корневое шоу}/teams/{последний сегмент старого адреса}.

`build_show_team(site, resource_id, mapper)` → (payload для POST /api/content/teams без show_id, extra, warnings).

Разбор текста:
- название без пометки шоу: «Это они (ЛГ)» → «Это они» (пометки — название шоу и «Команды X» родителя);
- заголовок секции, равный названию, не повторяется; «Состав» → «Состав команды» (из этих блоков строятся составы);
- факт «Состав» (Импровизация. Команды) → текстовый блок «Состав команды» со ссылками;
- строки с именами в начале текста без заголовка (ИГРА) → «Состав команды»;
- текст без заголовка, начинающийся с подзаголовка, делится по подзаголовкам — если это не продолжение предыдущего
  раздела (в предыдущем разделе уже есть подзаголовки того же уровня: «История команды» → «Второй сезон»);
- прочий текст без заголовка после раздела (таблицы игр) дописывается в этот раздел;
- скрытые на старом сайте секции (пустые таймлайны) не переносятся.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from services.memberships import ROSTER_TITLES
from services.modx_content import (
    LinkMapper, balance_html, clean_html, clean_tables_in_html, fact_cell_html, first_heading, image_url, is_blank_html,
    parse_facts_table, plain_text, split_by_headings, unwrap_search_highlight,
)
from services.modx_dump import ModxSite, json_list
from services.modx_people import SOCIAL_FIELDS, _module, _timeline_events, _timestamp, sidebar_modules
from services.modx_shows import (
    _IGNORED_SECTIONS, is_show_team_page, page_slug, section_id, show_chain, show_path,
)
from services.show_teams import TEAMS_SEGMENT

ROSTER_TITLE = "Состав команды"
_TITLE_ALIASES = {"Состав": ROSTER_TITLE}
_TEMPLATE_PAGE_PREFIX = "Шаблон"  # «Шаблон команды Лиги Городов» — заготовка редакторов, не команда
_NAME_LINE_RE = re.compile(r"\s*<(div|p)\b[^>]*>(.*?)</\1>", re.I | re.S)


def show_team_pages(site: ModxSite) -> Dict[int, dict]:
    cached = site.__dict__.get("_show_team_pages")
    if cached is not None:
        return cached
    root_id = section_id(site)
    pages = {} if root_id is None else {
        rid: r for rid, r in site.resources.items()
        if is_show_team_page(site, r, root_id) and not plain_text(r.get("pagetitle") or "").startswith(_TEMPLATE_PAGE_PREFIX)
    }
    site.__dict__["_show_team_pages"] = pages
    return pages


def team_show_resource(site: ModxSite, resource: dict) -> Optional[dict]:
    """Корневое шоу команды (ресурс MODX)."""
    chain = show_chain(site, resource, section_id(site))
    return chain[0] if chain else None


def _show_markers(site: ModxSite, resource: dict) -> List[str]:
    root = team_show_resource(site, resource)
    markers = []
    if root:
        markers += [root.get("pagetitle") or "", root.get("longtitle") or ""]
    parent = site.resources.get(resource.get("parent"))
    if parent and parent is not root:
        title = plain_text(parent.get("pagetitle") or "")
        title = re.sub(r"^Команды\s+(шоу\s+)?", "", title)
        markers.append(title.strip("«»\"' "))
    return [plain_text(m) for m in markers if plain_text(m)]


def team_name(site: ModxSite, resource: dict) -> str:
    """Название без пометки шоу в скобках: «Союз (Звёзды)» → «Союз»."""
    name = plain_text(resource.get("longtitle") or "") or plain_text(resource.get("pagetitle") or "")
    m = re.match(r"^(.*\S)\s*\(([^()]+)\)$", name)
    if m and m.group(2).strip().lower() in {x.lower() for x in _show_markers(site, resource)}:
        return m.group(1)
    return name


def show_team_url_builder(site: ModxSite):
    """Для LinkMapper: адрес команды шоу на новом сайте (даже если она ещё не перенесена)."""
    pages = show_team_pages(site)
    root_id = section_id(site)

    def build(resource: dict) -> Optional[str]:
        if resource.get("id") not in pages:
            return None
        root = team_show_resource(site, resource)
        show = show_path(site, root, root_id) if root else None
        return f"/shows/{show}/{TEAMS_SEGMENT}/{page_slug(resource)}" if show else None

    return build


def show_team_path_builder(site: ModxSite):
    """Для LinkMapper: старые адреса переехавших страниц команд («igra/team/soyuz.html» — теперь в «Звёздах»).
    Совпадение по последнему сегменту (адрес или alias) среди команд шоу, в тех же разделах старого сайта."""
    pages = show_team_pages(site)
    url_of = show_team_url_builder(site)
    index: Dict[str, List[dict]] = {}
    dirs = set()
    for r in pages.values():
        dirs.add(str(r.get("uri") or "").split("/", 1)[0])
        for key in {page_slug(r), (r.get("alias") or "").strip("/")}:
            if key:
                index.setdefault(key, []).append(r)

    def build(path: str) -> Optional[str]:
        parts = path.strip("/").split("/")
        if len(parts) < 2 or parts[0] not in dirs:
            return None
        last = parts[-1][:-5] if parts[-1].endswith(".html") else parts[-1]
        candidates = index.get(last) or []
        same_dir = [r for r in candidates if str(r.get("uri") or "").startswith(parts[0] + "/")]
        found = same_dir if len(same_dir) == 1 else candidates
        return url_of(found[0]) if len(found) == 1 else None

    return build


def _looks_like_name(inner: str) -> bool:
    text = plain_text(inner)
    return bool(text) and len(text) <= 60 and len(text.split()) <= 5 and not re.search(r"[.:;!?]|\d", text) \
        and "<h" not in inner.lower()


def split_leading_roster(html: str) -> Tuple[Optional[str], str]:
    """Строки с одними именами в начале текста (ИГРА: <div><a>Филипп Воронин</a></div>… или имена через <br>)
    → (список <ul>, остальное)."""
    items = []
    pos = 0
    while True:
        m = _NAME_LINE_RE.match(html, pos)
        if not m:
            break
        lines = [line.strip() for line in re.split(r"<br\s*/?>", m.group(2), flags=re.I)]
        lines = [re.sub(r"^<span[^>]*>(.*)</span>$", r"\1", line, flags=re.S) for line in lines if plain_text(line)]
        if not lines or not all(_looks_like_name(line) for line in lines):
            break
        items += lines
        pos = m.end()
    if len(items) < 3:
        return None, html
    return "<ul>\n" + "\n".join(f"<li>{i}</li>" for i in items) + "\n</ul>", html[pos:].strip()


def _heading_tag_in(html: str, tag: str) -> bool:
    return bool(re.search(rf"<{tag}\b", html or "", re.I))


def build_show_team(site: ModxSite, resource_id: int, mapper: Optional[LinkMapper] = None) -> Tuple[dict, dict, List[str]]:
    resource = site.resources[resource_id]
    warnings: List[str] = []
    page_title = plain_text(resource.get("pagetitle") or "")
    name = team_name(site, resource)
    root = team_show_resource(site, resource)
    show_title = plain_text((root or {}).get("longtitle") or "") or plain_text((root or {}).get("pagetitle") or "")

    facts: Dict[str, str] = {}
    social: Dict[str, str] = {}
    content: List[list] = []  # [type, title, data]
    pending_title = ""

    def normalize_title(title: str) -> str:
        """Заголовок-повтор названия («Ленивые», «Ленивые (Санкт-Петербург)», «Москва» у «Сборной Москвы») — пустой."""
        title = plain_text(title)
        if title in (page_title, name, facts.get("Город")) or title.startswith(name + " ("):
            return ""
        return _TITLE_ALIASES.get(title, title)

    def append(title: str, html: str) -> None:
        html = balance_html(clean_html(html))
        if not is_blank_html(html):
            content.append(["text_block", title, {"title": title, "content": html}])

    def add_text(block_title: str, raw_html: str) -> None:
        nonlocal pending_title
        title = normalize_title(block_title)
        html = clean_html(clean_tables_in_html(unwrap_search_highlight(clean_html(raw_html, mapper))))
        if is_blank_html(html) or plain_text(html) in ("...", "…"):
            pending_title = title or pending_title
            return
        if not title and pending_title:
            title, pending_title = pending_title, ""
        if title:
            append(title, html)
            return
        if not content:
            roster, html = split_leading_roster(html)
            if roster:
                append(ROSTER_TITLE, roster)
        heading = first_heading(html)
        previous = content[-1] if content else None
        continues = (previous is not None and previous[0] == "text_block" and previous[1]
                     and previous[1] not in ROSTER_TITLES)
        if heading and not (continues and _heading_tag_in(previous[2]["content"], heading[0])):
            for part_title, part in split_by_headings(html, heading[0]):
                append(_TITLE_ALIASES.get(part_title, part_title), part)
        elif continues:
            previous[2]["content"] = balance_html(previous[2]["content"] + "\n" + clean_html(html))
        else:
            append("", html)

    for section in site.migx_sections(resource_id):
        form = section.get("MIGX_formname")
        if str(section.get("hide_section") or "").strip() in ("1", "true"):
            continue
        if form == "info":
            table = section.get("table") or ""
            for key, value in parse_facts_table(table):
                if key == "Состав":
                    roster = fact_cell_html(table, key)
                    if roster and not is_blank_html(roster):
                        append(ROSTER_TITLE, clean_html(roster, mapper))
                    continue
                facts[key] = value
            for item in json_list(section.get("list_social")):
                if not isinstance(item, dict):
                    continue
                network = str(item.get("name") or "").strip().lower()
                link = str(item.get("link") or "").strip()
                target = SOCIAL_FIELDS.get(network)
                if link and target and target not in social:
                    social[target] = link
                elif link and not target:
                    warnings.append(f"соцсеть «{network}» не поддерживается: {link}")
            add_text("", section.get("subtitle") or "")
            add_text("", section.get("content") or "")
        elif form == "text":
            add_text(section.get("title") or "", section.get("content") or "")
        elif form == "table":
            add_text("", section.get("content") or "")
        elif form == "timeline":
            events = _timeline_events(section, mapper)
            if events:
                content.append(["timeline", "Хронология", {"title": "Хронология", "events": events}])
        elif form not in _IGNORED_SECTIONS:
            warnings.append(f"секция «{form}» не перенесена")

    if not content:
        warnings.append("на странице нет текста")
    modules = [
        _module(type_, order, module_title, data)
        for order, (type_, module_title, data) in enumerate(sidebar_modules() + [tuple(c) for c in content], start=1)
    ]

    logo = None
    logo_url = image_url(site.tv(resource_id, "img"))
    if logo_url:
        logo = {"url": logo_url, "alt": plain_text(site.tv(resource_id, "img_alt")) or name, "caption": "",
                "thumbnail": logo_url}
    else:
        warnings.append("нет фото")

    published = bool(resource.get("published")) and not resource.get("deleted")
    description = plain_text(resource.get("description") or "")
    payload = {
        "title": name,
        "name": name,
        "slug": page_slug(resource),
        "status": "published" if published else "draft",
        "logo": logo,
        "facts": facts,
        "facts_order": list(facts),
        "social_links": social,
        "modules": modules,
        "tags": site.tags_of(resource_id),
        "seo": {
            "meta_title": f"{name} — команда шоу «{show_title}»" if show_title else name,
            "meta_description": description,
            "keywords": [k.strip() for k in (resource.get("keywords") or "").split(",") if k.strip()],
        },
    }

    votes = int(resource.get("votes") or 0)
    extra = {
        "old_id": int(resource["id"]),
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


def link_builders(site: ModxSite) -> Tuple[list, list]:
    """(url_builders, path_builders) для LinkMapper: адреса шоу и команд шоу, переехавшие страницы команд."""
    from services.modx_shows import show_url_builder

    cached = site.__dict__.get("_link_builders")
    if cached is None:
        cached = [show_url_builder(site), show_team_url_builder(site)], [show_team_path_builder(site)]
        site.__dict__["_link_builders"] = cached
    return cached


def misplaced_show_team_builder(site: ModxSite, kvn_team_slugs: set):
    """Для fix_legacy_links: ссылка «/kvn/teams/{alias}» на команду шоу (так её перевёл импорт до переноса команд шоу),
    если команды КВН с таким slug нет: «/kvn/teams/agar-lg» → «/shows/liga-gorodov/teams/agar»."""
    pages = show_team_pages(site)
    url_of = show_team_url_builder(site)
    by_alias: Dict[str, List[dict]] = {}
    for r in pages.values():
        by_alias.setdefault((r.get("alias") or "").strip("/"), []).append(r)

    def build(path: str) -> Optional[str]:
        parts = path.strip("/").split("/")
        if len(parts) != 3 or parts[:2] != ["kvn", "teams"] or parts[2] in kvn_team_slugs:
            return None
        found = by_alias.get(parts[2]) or []
        return url_of(found[0]) if len(found) == 1 else None

    return build
