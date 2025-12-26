#!/usr/bin/env python3
"""Импорт шоу из humorbd.sql в MongoDB.

Этот скрипт импортирует шоу (parent=33) и их дочерние страницы (сезоны).
Отмечает импортированные шоу в shows_list.json.

Использование:
  # dry-run для одного шоу
  python3 import_shows.py --ids 1629 --dry-run
  
  # импорт одного шоу
  python3 import_shows.py --ids 1629 --apply
  
  # импорт всех pending из shows_list.json
  python3 import_shows.py --all --apply
  
  # импорт первых N pending шоу
  python3 import_shows.py --batch 10 --apply
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo
from import_people_from_sql import (
    _extract_for_ids,
    _load_image_map,
    _load_tv_map,
    _parse_migx,
    _split_rows,
    _split_fields,
)
from utils import DB_NAME, MONGO_URL, normalize_rich_text

# SQL_FILE = "/app/humorbd.sql"
# TAG_MAP_FILE = "/app/migration/tag_mapping.json"
# IMAGE_MAP_FILE = "/app/migration/image_mapping.json"
# SHOWS_LIST_FILE = "/app/migration/shows/shows_list.json"

SQL_FILE = "C:\\Users\\rdp6126443.gmail.com\\humorpedia\\migration\\humorbd.sql"
SHOWS_LIST_FILE = "C:\\Users\\rdp6126443.gmail.com\\humorpedia\\migration\\shows\\shows_list.json"
IMAGE_MAP_FILE = "C:\\Users\\rdp6126443.gmail.com\\humorpedia\\migration\\image_mapping.json"
TAG_MAP_FILE = "C:\\Users\\rdp6126443.gmail.com\\humorpedia\\migration\\tag_mapping.json"


def _load_shows_list() -> list[dict]:
    """Загружает список шоу из JSON."""
    if not os.path.exists(SHOWS_LIST_FILE):
        return []
    with open(SHOWS_LIST_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save_shows_list(shows: list[dict]) -> None:
    """Сохраняет список шоу в JSON."""
    with open(SHOWS_LIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(shows, f, ensure_ascii=False, indent=2)


def _mark_show_imported(show_id: int) -> None:
    """Отмечает шоу как импортированное в shows_list.json."""
    shows = _load_shows_list()
    for show in shows:
        if show['id'] == show_id:
            show['status'] = 'imported'
            show['imported_at'] = datetime.now(timezone.utc).isoformat()
            break
    _save_shows_list(shows)


def _mark_show_error(show_id: int, error: str) -> None:
    """Отмечает шоу с ошибкой."""
    shows = _load_shows_list()
    for show in shows:
        if show['id'] == show_id:
            show['status'] = 'error'
            show['error'] = error[:200]
            break
    _save_shows_list(shows)


# Transliteration map for cyrillic -> latin slugs
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def transliterate_slug(text: str) -> str:
    """Convert cyrillic text to latin slug"""
    slug = text.lower().replace(" ", "-").replace(".", "").replace(",", "")
    slug = ''.join(TRANSLIT_MAP.get(char, char) for char in slug)
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def sync_tags_to_collection(tags: list[str], db) -> None:
    """Синхронизация тегов с коллекцией tags."""
    if not tags:
        return
    
    for tag_name in tags:
        tag_name = tag_name.strip()
        if not tag_name:
            continue
        
        existing = db.tags.find_one({
            "name": {"$regex": f"^{re.escape(tag_name)}$", "$options": "i"}
        })
        
        if not existing:
            tag_doc = {
                "_id": str(uuid4()),
                "name": tag_name,
                "slug": transliterate_slug(tag_name),
                "old_id": None,
                "usage_count": 1,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            try:
                db.tags.insert_one(tag_doc)
            except Exception:
                pass
        else:
            db.tags.update_one(
                {"_id": existing["_id"]},
                {"$inc": {"usage_count": 1}}
            )


def _load_tag_map():
    """Загружает маппинг tag_id -> tag_name из JSON файла."""
    if not os.path.exists(TAG_MAP_FILE):
        return {}
    
    with open(TAG_MAP_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def _tags_from_tv(tv_tags_str: str, tag_map: dict) -> list[str]:
    """Преобразует строку TV 'tags' в список названий тегов."""
    if not tv_tags_str:
        return []
    
    tag_ids = tv_tags_str.split('||')
    tag_names = []
    
    for tag_id in tag_ids:
        tag_id = tag_id.strip()
        if tag_id in tag_map:
            tag_names.append(tag_map[tag_id])
    
    return tag_names


def _parse_facts_table(table_html: str) -> dict:
    """Извлекает факты из HTML-таблицы."""
    if not table_html:
        return {}

    facts = {}
    # Улучшенный regex для таблиц со style атрибутами
    rows = re.findall(r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>', table_html, re.IGNORECASE | re.DOTALL)
    
    for key_html, val_html in rows:
        key = re.sub(r'<[^>]+>', '', key_html).strip()
        val = normalize_rich_text(val_html)
        
        if key and val:
            facts[key] = val
    
    return facts


def get_child_shows(parent_id: int) -> list[dict]:
    """Получает список дочерних шоу для родительского."""
    with open(SQL_FILE, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    inserts = re.finditer(r'INSERT INTO `modx_site_content`.*?VALUES\s*(.*?);', content, re.DOTALL)
    
    children = []
    for match in inserts:
        values_str = match.group(1)
        rows = _split_rows(values_str)
        
        for r in rows:
            parts = _split_fields(r)
            if len(parts) > 12:
                try:
                    rid = int(str(parts[0]).strip())
                    parent = int(str(parts[12]).strip()) if parts[12] else 0
                    title = str(parts[3]).strip("'\"") if parts[3] else ''
                    slug = str(parts[6]).strip("'\"") if parts[6] else ''
                    
                    if parent == parent_id:
                        children.append({
                            'id': rid,
                            'title': title,
                            'slug': slug
                        })
                except:
                    pass
    
    return children


def build_show_doc(sc, tv_by_id: dict[str, str], tv_map: dict[str, str], image_map: dict[str, str], tag_map: dict[str, str], parent_mongo_id: str = None):
    """Строит документ шоу из данных SQL."""
    tv_named = {}
    for tv_id, val in tv_by_id.items():
        tv_name = tv_map.get(tv_id)
        if tv_name:
            tv_named[tv_name] = val

    # Parse MIGX
    sections = _parse_migx(tv_named.get("config", ""))

    # Извлекаем таблицу фактов и ссылки из секции "info"
    facts = {}
    first_text_block = ""
    social_links = {}
    
    for sec in sections:
        if sec.get("MIGX_formname") == "info":
            table_html = sec.get("table", "")
            facts = _parse_facts_table(table_html)
            first_text_block = sec.get("subtitle", "")
            
            # Извлекаем social links из list_social
            list_social = sec.get("list_social", "")
            if list_social:
                try:
                    import json
                    if isinstance(list_social, str):
                        social_data = json.loads(list_social)
                    else:
                        social_data = list_social
                    
                    if isinstance(social_data, list):
                        for item in social_data:
                            if isinstance(item, dict):
                                link = item.get('link', '')
                                name = item.get('name', '').lower()
                                
                                if link:
                                    # Определяем тип ссылки
                                    if 'vk.com' in link or 'vkontakte' in link:
                                        social_links['vk'] = link
                                    elif 'youtube' in link:
                                        social_links['youtube'] = link
                                    elif 'instagram' in link or 'instagr.am' in link:
                                        social_links['instagram'] = link
                                    elif 'telegram' in link or 't.me' in link:
                                        social_links['telegram'] = link
                                    else:
                                        # Всё остальное - официальный сайт
                                        social_links['website'] = link
                except Exception as e:
                    print(f"  ⚠️ Ошибка парсинга list_social: {e}")
            
            break

    # Извлекаем остальные модули
    modules = []
    order = 1
    
    # Первый текстовый блок (из info subtitle)
    if first_text_block:
        # Удаляем заголовок если он дублирует название шоу
        cleaned_text = normalize_rich_text(first_text_block)
        
        # Проверяем, начинается ли текст с названия шоу
        title_lower = sc.pagetitle.lower()
        if cleaned_text.lower().startswith(f'<p>{title_lower}') or cleaned_text.lower().startswith(f'<h'):
            # Удаляем первый параграф/заголовок
            import re
            cleaned_text = re.sub(r'^<[ph]\d?>.*?</[ph]\d?>', '', cleaned_text, count=1, flags=re.IGNORECASE | re.DOTALL).strip()
        
        if cleaned_text:
            modules.append({
                'id': str(uuid4()),
                'type': 'text_block',
                'order': order,
                'title': '',
                'visible': True,
                'data': {
                    'title': '',
                    'content': cleaned_text,
                }
            })
            order += 1
    
    # Остальные секции (текст и таблицы)
    for sec in sections:
        formname = sec.get('MIGX_formname')
        
        if formname == 'text':
            title = sec.get('section_name', '')
            content = sec.get('content', '') or sec.get('subtitle', '')
            
            if content:
                modules.append({
                    'id': str(uuid4()),
                    'type': 'text_block',
                    'order': order,
                    'title': title,
                    'visible': True,
                    'data': {
                        'title': title,
                        'content': normalize_rich_text(content),
                    }
                })
                order += 1
        
        elif formname == 'table':
            title = sec.get('section_name', 'Таблица')
            table_html = sec.get('content', '')
            
            if table_html:
                modules.append({
                    'id': str(uuid4()),
                    'type': 'text_block',
                    'order': order,
                    'title': title,
                    'visible': True,
                    'data': {
                        'title': title,
                        'content': normalize_rich_text(table_html),
                    }
                })
                order += 1

    # Tags
    tags = _tags_from_tv(tv_named.get('tags', ''), tag_map)

    # Image/Poster
    poster_url = None
    tv_img = tv_named.get('img')
    if tv_img:
        if not str(tv_img).startswith('/'):
            poster_url = f"/media/imported/{str(tv_img).lstrip('/')}"
        else:
            poster_url = tv_img

    # Rating - используем из SQL дампа
    avg = float(sc.rating or 0.0)
    if avg < 0:
        avg = 0.0
    if avg > 10:
        avg = 10.0
    rating = {"average": avg, "count": int(sc.votes or 0)}

    doc = {
        '_id': str(uuid4()),
        'content_type': 'show',
        'title': sc.pagetitle,
        'slug': sc.alias,
        'name': sc.longtitle or sc.pagetitle,
        'status': 'published',
        'tags': tags,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'facts': facts,
        'social_links': social_links,  # Добавлено!
        'description': normalize_rich_text(sc.description) if sc.description else '',
        'modules': modules,
        'poster': poster_url,
        'rating': rating,
        'votes_count': int(sc.votes or 0),
        'views': 0,
        'comments_count': 0,
        'participant_ids': [],
        'team_ids': [],
        'article_ids': [],
        'related_show_ids': [],
        'parent_id': parent_mongo_id,  # For child shows
        'child_show_ids': [],
        'featured': False,
        'seo': {
            'meta_title': sc.pagetitle,
            'meta_description': sc.description[:160] if sc.description else '',
        }
    }

    return doc


def main():
    parser = argparse.ArgumentParser(description="Импорт шоу из SQL в MongoDB")
    parser.add_argument("--ids", nargs="+", type=int, help="Конкретные ID шоу для импорта")
    parser.add_argument("--all", action="store_true", help="Импортировать все pending шоу из shows_list.json")
    parser.add_argument("--batch", type=int, help="Импортировать первые N pending шоу")
    parser.add_argument("--dry-run", action="store_true", help="Только показать, не сохранять")
    parser.add_argument("--apply", action="store_true", help="Применить изменения")
    parser.add_argument("--with-children", action="store_true", default=False, help="Импортировать дочерние шоу")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Укажите --dry-run или --apply")
        return

    # Определяем список ID для импорта
    target_ids = set()
    
    if args.ids:
        target_ids = set(args.ids)
    elif args.all or args.batch:
        shows_list = _load_shows_list()
        pending = [s for s in shows_list if s.get('status') == 'pending']
        
        if args.batch:
            pending = pending[:args.batch]
        
        target_ids = {s['id'] for s in pending}
        
        if not target_ids:
            print("Нет pending шоу для импорта")
            return
    else:
        print("Укажите --ids, --all или --batch")
        return

    print(f"Импорт {len(target_ids)} шоу: {sorted(target_ids)}\n")

    # Загружаем данные
    tv_map = _load_tv_map()
    image_map = _load_image_map()
    tag_map = _load_tag_map()

    # Подключение к MongoDB
    client = None
    db = None
    if args.apply:
        client = pymongo.MongoClient(MONGO_URL)
        db = client[DB_NAME]

    imported_count = 0
    error_count = 0
    skipped_count = 0
    
    for show_id in sorted(target_ids):
        # Get parent show data
        site_content, tv_values = _extract_for_ids({show_id})
        sc = site_content.get(show_id)
        
        if not sc:
            print(f"⚠️  ID {show_id}: не найден в SQL")
            if args.apply:
                _mark_show_error(show_id, "Не найден в SQL")
            error_count += 1
            continue

        tv_by_id = tv_values.get(show_id, {})
        
        try:
            # Build parent show document
            parent_doc = build_show_doc(sc, tv_by_id, tv_map, image_map, tag_map)
            
            print(f"\n{'='*60}")
            print(f"ID {show_id}: {parent_doc['title']} ({parent_doc['slug']})")
            print(f"{'='*60}")
            print(f"Description: {parent_doc['description'][:100] if parent_doc['description'] else '(нет)'}...")
            print(f"Facts: {len(parent_doc['facts'])} items")
            for k, v in list(parent_doc['facts'].items())[:5]:
                print(f"  - {k}: {v[:60] if len(v) > 60 else v}")
            if len(parent_doc['facts']) > 5:
                print(f"  ... и ещё {len(parent_doc['facts']) - 5}")
            print(f"Modules: {len(parent_doc['modules'])}")
            for m in parent_doc['modules'][:5]:
                title = m['title'] or '(Без заголовка)'
                content_len = len(m['data']['content'])
                print(f"  - {m['type']}: {title} ({content_len} chars)")
            if len(parent_doc['modules']) > 5:
                print(f"  ... и ещё {len(parent_doc['modules']) - 5}")
            print(f"Tags: {len(parent_doc['tags'])} - {parent_doc['tags'][:5]}")
            print(f"Social links: {parent_doc.get('social_links', {})}")
            print(f"Poster: {parent_doc['poster']}")

            if args.apply:
                # Check if exists
                existing = db.shows.find_one({"slug": parent_doc['slug']})
                if existing:
                    print(f"⚠️  Шоу с slug '{parent_doc['slug']}' уже существует, пропускаем")
                    _mark_show_imported(show_id)  # Отмечаем как импортированное
                    skipped_count += 1
                    continue
                
                # Sync tags
                if parent_doc['tags']:
                    sync_tags_to_collection(parent_doc['tags'], db)
                
                # Insert parent
                db.shows.insert_one(parent_doc)
                parent_mongo_id = parent_doc['_id']
                imported_count += 1
                
                # Отмечаем в shows_list.json
                _mark_show_imported(show_id)
                print(f"✅ Шоу импортировано и отмечено в shows_list.json")
                
                # Import children
                if args.with_children:
                    children = get_child_shows(show_id)
                    print(f"\n📦 Дочерних шоу: {len(children)}")
                    
                    child_mongo_ids = []
                    for child in children:
                        child_site_content, child_tv_values = _extract_for_ids({child['id']})
                        child_sc = child_site_content.get(child['id'])
                        
                        if child_sc:
                            child_tv_by_id = child_tv_values.get(child['id'], {})
                            child_doc = build_show_doc(child_sc, child_tv_by_id, tv_map, image_map, tag_map, parent_mongo_id)
                            
                            # Check if child exists
                            existing_child = db.shows.find_one({"slug": child_doc['slug']})
                            if not existing_child:
                                if child_doc['tags']:
                                    sync_tags_to_collection(child_doc['tags'], db)
                                
                                db.shows.insert_one(child_doc)
                                child_mongo_ids.append(child_doc['_id'])
                                print(f"  ✅ {child_doc['title']}")
                    
                    # Update parent with child_show_ids
                    if child_mongo_ids:
                        db.shows.update_one(
                            {"_id": parent_mongo_id},
                            {"$set": {"child_show_ids": child_mongo_ids}}
                        )
                        print(f"\n✅ Обновлены child_show_ids у родителя ({len(child_mongo_ids)} детей)")

        except Exception as e:
            print(f"❌ Ошибка импорта ID {show_id}: {e}")
            if args.apply:
                _mark_show_error(show_id, str(e))
            error_count += 1
            import traceback
            traceback.print_exc()

    if client:
        client.close()

    print(f"\n{'='*60}")
    print(f"Результат:")
    print(f"  ✅ Импортировано: {imported_count}")
    print(f"  ⏭️  Пропущено (уже есть): {skipped_count}")
    print(f"  ❌ Ошибок: {error_count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
