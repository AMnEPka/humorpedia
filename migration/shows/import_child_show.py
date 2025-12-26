#!/usr/bin/env python3
"""Импорт дочерних страниц шоу.

Использование:
  # Импорт одной дочерней страницы (по SQL ID)
  python3 import_child_show.py --parent-slug comedy-battle --child-id 1703 --apply
  
  # Все дочерние страницы родителя
  python3 import_child_show.py --parent-slug comedy-battle --all --apply
  
  # Dry-run
  python3 import_child_show.py --parent-slug comedy-battle --child-id 1703 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo
from import_people_from_sql import (
    _extract_for_ids,
    _load_image_map,
    _load_tv_map,
    _parse_migx,
    _split_rows,
    _split_fields,
    _unescape_sql_string,
)
from utils import DB_NAME, MONGO_URL, normalize_rich_text

SQL_FILE = "/app/humorbd.sql"
TAG_MAP_FILE = "/app/migration/tag_mapping.json"


def _load_tag_map():
    if not os.path.exists(TAG_MAP_FILE):
        return {}
    with open(TAG_MAP_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_sql_parent_id_for_show(slug: str, db) -> int:
    """Получает SQL ID родителя по slug из MongoDB."""
    # Находим шоу по slug
    show = db.shows.find_one({"slug": slug}, {"_id": 1, "title": 1})
    if not show:
        return None
    
    # Теперь найдём SQL ID по title в SQL дампе
    with open(SQL_FILE, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if 'INSERT INTO `modx_site_content`' in line:
                break
        
        content = f.read()
    
    # Ищем полный INSERT
    in_sc = False
    buf = []
    
    with open(SQL_FILE, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if not in_sc:
                if line.startswith('INSERT INTO `modx_site_content`'):
                    in_sc = True
                    buf = [line]
                continue
            
            buf.append(line)
            if not line.strip().endswith(';'):
                continue
            
            blob = ''.join(buf)
            in_sc = False
            buf = []
            
            m = re.search(r'VALUES\s*(.*);\s*$', blob, flags=re.DOTALL)
            if not m:
                continue
            
            rows = _split_rows(m.group(1))
            for r in rows:
                parts = _split_fields(r)
                if not parts or parts[0] is None:
                    continue
                
                if len(parts) <= 6:
                    continue
                
                try:
                    rid = int(str(parts[0]).strip())
                    alias = _unescape_sql_string(parts[6]) if parts[6] else ''
                    
                    if alias == slug:
                        return rid
                except:
                    continue
    
    return None


def get_children_from_sql(parent_sql_id: int) -> list[dict]:
    """Получает список дочерних страниц из SQL."""
    children = []
    
    in_sc = False
    buf = []
    
    with open(SQL_FILE, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if not in_sc:
                if line.startswith('INSERT INTO `modx_site_content`'):
                    in_sc = True
                    buf = [line]
                continue
            
            buf.append(line)
            if not line.strip().endswith(';'):
                continue
            
            blob = ''.join(buf)
            in_sc = False
            buf = []
            
            m = re.search(r'VALUES\s*(.*);\s*$', blob, flags=re.DOTALL)
            if not m:
                continue
            
            rows = _split_rows(m.group(1))
            for r in rows:
                parts = _split_fields(r)
                if not parts or parts[0] is None:
                    continue
                
                if len(parts) <= 12:
                    continue
                
                try:
                    rid = int(str(parts[0]).strip())
                    parent = int(str(parts[12]).strip()) if parts[12] else 0
                    
                    if parent == parent_sql_id:
                        title = _unescape_sql_string(parts[3]) if parts[3] else ''
                        alias = _unescape_sql_string(parts[6]) if parts[6] else ''
                        children.append({
                            'sql_id': rid,
                            'title': title,
                            'slug': alias
                        })
                except:
                    continue
    
    return children


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
            # Транслитерация для slug
            translit_map = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
                'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
            }
            slug = tag_name.lower().replace(" ", "-")
            slug = ''.join(translit_map.get(c, c) for c in slug)
            slug = re.sub(r'[^a-z0-9-]', '', slug)
            
            tag_doc = {
                "_id": str(uuid4()),
                "name": tag_name,
                "slug": slug,
                "old_id": None,
                "usage_count": 1,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            try:
                db.tags.insert_one(tag_doc)
            except:
                pass
        else:
            db.tags.update_one({"_id": existing["_id"]}, {"$inc": {"usage_count": 1}})


def _tags_from_tv(tv_tags_str: str, tag_map: dict) -> list[str]:
    if not tv_tags_str:
        return []
    tag_ids = tv_tags_str.split('||')
    return [tag_map[tid.strip()] for tid in tag_ids if tid.strip() in tag_map]


def _parse_facts_table(table_html: str) -> dict:
    if not table_html:
        return {}
    facts = {}
    rows = re.findall(r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>', table_html, re.IGNORECASE | re.DOTALL)
    for key_html, val_html in rows:
        key = re.sub(r'<[^>]+>', '', key_html).strip()
        val = normalize_rich_text(val_html)
        if key and val:
            facts[key] = val
    return facts


def build_child_doc(sc, tv_by_id, tv_map, tag_map, parent_mongo_id: str, parent_full_path: str, level: int):
    """Строит документ дочернего шоу."""
    tv_named = {}
    for tv_id, val in tv_by_id.items():
        tv_name = tv_map.get(tv_id)
        if tv_name:
            tv_named[tv_name] = val

    sections = _parse_migx(tv_named.get("config", ""))

    # Извлекаем факты и ссылки из info секции
    facts = {}
    social_links = {}
    
    for sec in sections:
        if sec.get("MIGX_formname") == "info":
            table_html = sec.get("table", "")
            facts = _parse_facts_table(table_html)
            
            list_social = sec.get("list_social", "")
            if list_social:
                try:
                    if isinstance(list_social, str):
                        social_data = json.loads(list_social)
                    else:
                        social_data = list_social
                    
                    if isinstance(social_data, list):
                        for item in social_data:
                            if isinstance(item, dict):
                                link = item.get('link', '')
                                if link:
                                    if 'vk.com' in link:
                                        social_links['vk'] = link
                                    elif 'youtube' in link:
                                        social_links['youtube'] = link
                                    elif 'telegram' in link or 't.me' in link:
                                        social_links['telegram'] = link
                                    else:
                                        social_links['website'] = link
                except:
                    pass
            break

    # Модули контента
    modules = []
    order = 1
    
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

    # Poster
    poster_url = None
    tv_img = tv_named.get('img')
    if tv_img:
        if not str(tv_img).startswith('/'):
            poster_url = f"/media/imported/{str(tv_img).lstrip('/')}"
        else:
            poster_url = tv_img

    # Rating
    avg = float(sc.rating or 0.0)
    if avg < 0:
        avg = 0.0
    if avg > 10:
        avg = 10.0
    rating = {"average": avg, "count": int(sc.votes or 0)}

    # Полный путь
    full_path = f"{parent_full_path}/{sc.alias}"

    doc = {
        '_id': str(uuid4()),
        'content_type': 'show',
        'title': sc.pagetitle,
        'slug': sc.alias,
        'full_path': full_path,
        'level': level,
        'name': sc.longtitle or sc.pagetitle,
        'status': 'published',
        'tags': tags,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'facts': facts,
        'social_links': social_links,
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
        'parent_id': parent_mongo_id,
        'child_show_ids': [],
        'featured': False,
        'seo': {
            'meta_title': sc.pagetitle,
            'meta_description': sc.description[:160] if sc.description else '',
        }
    }

    return doc


def main():
    parser = argparse.ArgumentParser(description="Импорт дочерних страниц шоу")
    parser.add_argument("--parent-slug", required=True, help="Slug родительского шоу (напр. comedy-battle)")
    parser.add_argument("--child-id", type=int, help="SQL ID конкретной дочерней страницы")
    parser.add_argument("--all", action="store_true", help="Импортировать все дочерние страницы")
    parser.add_argument("--dry-run", action="store_true", help="Только показать")
    parser.add_argument("--apply", action="store_true", help="Применить изменения")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Укажите --dry-run или --apply")
        return

    if not args.child_id and not args.all:
        print("Укажите --child-id или --all")
        return

    # Подключение к MongoDB
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]

    # Находим родителя
    parent = db.shows.find_one({"slug": args.parent_slug})
    if not parent:
        print(f"❌ Родительское шоу '{args.parent_slug}' не найдено в MongoDB")
        client.close()
        return

    parent_mongo_id = parent['_id']
    parent_full_path = parent.get('full_path', parent['slug'])
    parent_level = parent.get('level', 0)
    child_level = parent_level + 1

    print(f"Родитель: {parent['title']} (ID: {parent_mongo_id})")
    print(f"Путь: {parent_full_path}")
    print(f"Уровень дочерних: {child_level}")
    print()

    # Находим SQL ID родителя
    parent_sql_id = get_sql_parent_id_for_show(args.parent_slug, db)
    if not parent_sql_id:
        print(f"❌ Не удалось найти SQL ID для '{args.parent_slug}'")
        client.close()
        return

    print(f"SQL ID родителя: {parent_sql_id}")

    # Получаем дочерние из SQL
    children = get_children_from_sql(parent_sql_id)
    print(f"Найдено дочерних в SQL: {len(children)}")
    print()

    if args.child_id:
        children = [c for c in children if c['sql_id'] == args.child_id]
        if not children:
            print(f"❌ Дочерняя страница с SQL ID {args.child_id} не найдена")
            client.close()
            return

    # Загружаем данные для импорта
    tv_map = _load_tv_map()
    tag_map = _load_tag_map()

    imported_count = 0
    child_mongo_ids = list(parent.get('child_show_ids', []))

    for child in children:
        sql_id = child['sql_id']
        
        # Получаем данные из SQL
        site_content, tv_values = _extract_for_ids({sql_id})
        sc = site_content.get(sql_id)
        
        if not sc:
            print(f"⚠️ SQL ID {sql_id}: не найден")
            continue

        tv_by_id = tv_values.get(sql_id, {})

        try:
            doc = build_child_doc(sc, tv_by_id, tv_map, tag_map, parent_mongo_id, parent_full_path, child_level)

            print(f"{'='*60}")
            print(f"SQL ID {sql_id}: {doc['title']}")
            print(f"{'='*60}")
            print(f"Slug: {doc['slug']}")
            print(f"Full path: {doc['full_path']}")
            print(f"Level: {doc['level']}")
            print(f"Description: {doc['description'][:100] if doc['description'] else '(нет)'}...")
            print(f"Facts: {len(doc['facts'])} items")
            print(f"Modules: {len(doc['modules'])}")
            print(f"Tags: {len(doc['tags'])}")
            print(f"Social links: {doc['social_links']}")
            print()

            if args.apply:
                # Проверяем, существует ли уже
                existing = db.shows.find_one({"full_path": doc['full_path']})
                if existing:
                    print(f"⚠️ Страница с full_path '{doc['full_path']}' уже существует")
                    continue

                # Синхронизируем теги
                if doc['tags']:
                    sync_tags_to_collection(doc['tags'], db)

                # Вставляем документ
                db.shows.insert_one(doc)
                child_mongo_ids.append(doc['_id'])
                imported_count += 1
                print(f"✅ Импортировано: {doc['full_path']}")

        except Exception as e:
            print(f"❌ Ошибка импорта SQL ID {sql_id}: {e}")
            import traceback
            traceback.print_exc()

    # Обновляем child_show_ids у родителя
    if args.apply and imported_count > 0:
        db.shows.update_one(
            {"_id": parent_mongo_id},
            {"$set": {"child_show_ids": child_mongo_ids}}
        )
        print(f"\n✅ Обновлён родитель: {len(child_mongo_ids)} дочерних страниц")

    client.close()

    print(f"\n{'='*60}")
    print(f"Импортировано: {imported_count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
