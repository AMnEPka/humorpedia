"""
Импорт людей со старого сайта (MODX, шаблон «Человек») в формат, который сохраняет админка.

`build_person(site, resource_id, mapper)` возвращает:
- payload — тело запроса `POST /api/content/people` (PersonCreate): ровно те поля, что заполняет
  страница редактирования человека в админке, и модули в её формате;
- extra — служебные поля, которых нет в форме: old_id, old_urls, рейтинг, даты старого сайта;
- warnings — что не удалось перенести.

Раскладка страницы MODX (TV `config`, MIGX-секции):
  info      → subtitle = «Биография», content = «Личная жизнь», table = факты, list_social = соцсети
  text      → текстовый блок без заголовка (сноски вроде «* признан иноагентом»)
  timeline  → «Хронология» (list_triple: title / subtitle = годы / content)
  tags, table_of_contents, popular_articles, реклама — на новом сайте выводятся автоматически или не нужны
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from services.modx_content import (
    LinkMapper, clean_html, image_url, is_blank_html, parse_facts_table, plain_text,
)
from services.modx_dump import ModxSite, json_list

TEMPLATE_PERSON = 20

# name в list_social MODX → поле social_links (models/base.py:SocialLinks)
SOCIAL_FIELDS = {
    "vk": "vk", "telegram": "telegram", "tg": "telegram", "youtube": "youtube",
    "instagram": "instagram", "global": "website", "website": "website", "site": "website",
}

_IGNORED_SECTIONS = {"tags", "table_of_contents", "popular_articles", "ad_250", "ad_block_120"}


_json_list = json_list


def _module(type_: str, order: int, title: str, data: dict) -> dict:
    return {"id": str(uuid.uuid4()), "type": type_, "order": order, "title": title, "visible": True, "data": data}


def sidebar_modules() -> List[Tuple[str, str, dict]]:
    """Системные модули сайдбара — как у страниц, созданных в админке: только настройки вида,
    сами данные (фото, факты, теги, ссылки, рейтинг) лежат в полях документа."""
    return [
        ("poster_photo", "", {"size": "medium", "shape": "rounded"}),
        ("facts_table", "Информация", {"title": "Информация", "style": "card"}),
        ("rating_widget", "Оценка", {"title": "Оценка", "style": "smileys"}),
        ("tags_cloud", "", {"title": "", "style": "badges", "max_tags": 0}),
        ("social_links", "Ссылки", {"title": "Ссылки", "style": "icons"}),
    ]


def swap_name_order(name: str) -> str:
    """«Фамилия Имя» → «Имя Фамилия» (как админка при выборе базового тега)."""
    parts = (name or "").split()
    return f"{parts[1]} {parts[0]}" if len(parts) == 2 else (name or "").strip()


def _timestamp(value) -> Optional[str]:
    try:
        seconds = int(value or 0)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def _timeline_events(section: dict, mapper: Optional[LinkMapper]) -> list:
    events = []
    for item in _json_list(section.get("list_triple")):
        if not isinstance(item, dict):
            continue
        title = plain_text(item.get("title") or "")
        description = clean_html(item.get("content") or "", mapper)
        if not title and is_blank_html(description):
            continue
        events.append({
            "year": plain_text(item.get("subtitle") or ""),
            "date": "",
            "title": title,
            "description": "" if is_blank_html(description) else description,
        })
    return events


def build_person(site: ModxSite, resource_id: int, mapper: Optional[LinkMapper] = None) -> Tuple[dict, dict, List[str]]:
    resource = site.resources[resource_id]
    warnings: List[str] = []
    title = (resource.get("pagetitle") or "").strip()
    full_name = (resource.get("longtitle") or "").strip() or title

    sections = site.migx_sections(resource_id)
    facts: dict = {}
    social: dict = {}
    content: List[Tuple[str, str, dict]] = []

    for section in sections:
        form = section.get("MIGX_formname")
        if form == "info":
            for key, value in parse_facts_table(section.get("table") or ""):
                facts[key] = value
            for item in _json_list(section.get("list_social")):
                name = str(item.get("name") or "").strip().lower()
                link = str(item.get("link") or "").strip()
                if not link:
                    continue
                target = SOCIAL_FIELDS.get(name)
                if target and target not in social:
                    social[target] = link
                elif not target:
                    warnings.append(f"соцсеть «{name}» не поддерживается: {link}")
            bio = clean_html(section.get("subtitle") or "", mapper)
            if not is_blank_html(bio):
                content.append(("text_block", "Биография", {"title": "Биография", "content": bio}))
            personal = clean_html(section.get("content") or "", mapper)
            if not is_blank_html(personal):
                content.append(("text_block", "Личная жизнь", {"title": "Личная жизнь", "content": personal}))
        elif form == "text":
            text = clean_html(section.get("content") or "", mapper)
            if not is_blank_html(text):
                content.append(("text_block", "", {"title": "", "content": text}))
        elif form == "timeline":
            events = _timeline_events(section, mapper)
            if events:
                content.append(("timeline", "Хронология", {"title": "Хронология", "events": events}))
        elif form not in _IGNORED_SECTIONS:
            warnings.append(f"секция «{form}» не перенесена")

    modules = [
        _module(type_, order, module_title, data)
        for order, (type_, module_title, data) in enumerate(sidebar_modules() + content, start=1)
    ]

    photo = None
    photo_url = image_url(site.tv(resource_id, "img"))
    if photo_url:
        alt = plain_text(site.tv(resource_id, "img_alt"))
        photo = {"url": photo_url, "alt": alt, "caption": "", "thumbnail": photo_url}
    else:
        warnings.append("нет фото")

    keywords = [k.strip() for k in (resource.get("keywords") or "").split(",") if k.strip()]
    published = bool(resource.get("published")) and not resource.get("deleted")

    payload = {
        "title": title,
        "slug": (resource.get("alias") or "").strip(),
        "full_name": full_name,
        "status": "published" if published else "draft",
        "photo": photo,
        "social_links": social,
        "facts": facts,
        "facts_order": list(facts.keys()),
        "primary_tag": swap_name_order(title),
        "modules": modules,
        "tags": site.tags_of(resource_id),
        "seo": {
            "meta_title": title,
            "meta_description": plain_text(resource.get("description") or ""),
            "keywords": keywords,
        },
    }

    votes = int(resource.get("votes") or 0)
    average = min(10.0, max(0.0, float(resource.get("rating") or 0)))
    extra = {
        "old_id": int(resource["id"]),
        "old_urls": ["/" + str(resource["uri"]).lstrip("/")] if resource.get("uri") else [],
        "rating": {"average": round(average, 2), "count": votes},
        "votes_count": votes,
    }
    created_at = _timestamp(resource.get("createdon"))
    if created_at:
        extra["created_at"] = created_at
    published_at = (_timestamp(resource.get("publishedon")) or created_at) if published else None
    if published_at:
        extra["published_at"] = published_at
    return payload, extra, warnings


def person_resources(site: ModxSite, include_unpublished: bool = False) -> List[dict]:
    """Страницы людей старого сайта (без удалённых; черновики — по флагу)."""
    return [
        r for r in site.resources.values()
        if r.get("template") == TEMPLATE_PERSON and not r.get("deleted")
        and (include_unpublished or r.get("published"))
    ]
