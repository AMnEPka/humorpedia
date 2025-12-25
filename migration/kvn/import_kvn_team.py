#!/usr/bin/env python3
"""Импорт команд КВН из humorbd.sql в MongoDB.

Этот скрипт импортирует команды КВН (parent=1031), извлекая:
- Таблицу с фактами (Город, Год основания, Капитан, Высшая лига, КиВиНы и т.д.)
- Несколько текстовых блоков (Состав, История, и т.п.)
- Таймлайн (если есть)
- Фото, рейтинги, теги

Использование:
  # dry-run для одной команды
  python3 import_kvn_team.py --ids 1138 --dry-run
  
  # импорт одной команды
  python3 import_kvn_team.py --ids 1138 --apply
  
  # импорт пачки из kvn_teams_list.json
  python3 import_kvn_team.py --from-list --limit 10 --apply
"""

from __future__ import annotations

import argparse
import json
import os
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
    _tags_from_keywords,
    _timeline_from_migx_sections,
)
from utils import DB_NAME, MONGO_URL, normalize_rich_text

SQL_FILE = "/app/humorbd.sql"
KVN_TEAMS_LIST_FILE = "/app/migration/kvn/kvn_teams_list.json"
IMAGE_MAP_FILE = "/app/migration/image_mapping.json"


def create_team_document(
    title: str,
    slug: str,
    name: str = None,
    logo_url: str = None,
    facts: dict = None,
    text_blocks: list[dict] = None,
    timeline_events: list[dict] = None,
    tags: list[str] = None,
    rating: dict = None,
    social_links: dict = None,
):
    """Создаёт документ команды для MongoDB."""
    modules = []
    order = 1

    # Первый блок - основной текст (без заголовка)
    if text_blocks and len(text_blocks) > 0 and not text_blocks[0].get('title'):
        modules.append({
            'id': str(uuid4()),
            'type': 'text_block',
            'order': order,
            'title': '',
            'visible': True,
            'data': {
                'title': '',
                'content': normalize_rich_text(text_blocks[0]['content']),
            }
        })
        order += 1
        text_blocks = text_blocks[1:]  # Убираем первый блок из списка

    # Таймлайн идёт вторым
    if timeline_events:
        normalized_events = []
        for ev in timeline_events:
            if not isinstance(ev, dict):
                continue
            normalized_events.append({
                'year': normalize_rich_text(str(ev.get('year', ''))) if ev.get('year') else None,
                'title': normalize_rich_text(str(ev.get('title', ''))) if ev.get('title') else None,
                'description': normalize_rich_text(str(ev.get('description', ''))) if ev.get('description') else None,
            })

        if normalized_events:
            modules.append({
                'id': str(uuid4()),
                'type': 'timeline',
                'order': order,
                'title': 'Хронология',
                'visible': True,
                'data': {
                    'title': 'Хронология',
                    'items': normalized_events,
                }
            })
            order += 1

    # Остальные текстовые блоки (4 стандартных)
    if text_blocks:
        for block in text_blocks:
            if block.get('content'):
                modules.append({
                    'id': str(uuid4()),
                    'type': 'text_block',
                    'order': order,
                    'title': block.get('title', 'Без названия'),
                    'visible': True,
                    'data': {
                        'title': block.get('title', 'Без названия'),
                        'content': normalize_rich_text(block['content']),
                    }
                })
                order += 1

    return {
        '_id': str(uuid4()),
        'content_type': 'team',
        'team_type': 'kvn',
        'title': title,
        'slug': slug,
        'name': name or title,
        'status': 'published',
        'tags': tags or [],
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'facts': facts or {},
        'social_links': social_links or {},
        'modules': modules,
        'rating': rating or {'average': 0.0, 'count': 0},
        'votes_count': rating.get('count', 0) if rating else 0,
        'views': 0,
        'member_ids': [],
        'show_ids': [],
        'featured': False,
        'logo': logo_url,
        'seo': {
            'meta_title': title,
            'meta_description': '',
        }
    }


def _parse_facts_table(table_html: str) -> dict:
    """Извлекает факты из HTML-таблицы."""
    if not table_html:
        return {}

    import re
    facts = {}
    
    # Ищем строки таблицы <tr><td>Key</td><td>Value</td></tr>
    rows = re.findall(r'<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>', table_html, re.IGNORECASE | re.DOTALL)
    
    for key_html, val_html in rows:
        # Убираем теги
        key = re.sub(r'<[^>]+>', '', key_html).strip()
        val = normalize_rich_text(val_html)
        
        if key and val:
            facts[key] = val
    
    return facts


def build_team_doc(sc, tv_by_id: dict[str, str], tv_map: dict[str, str], image_map: dict[str, str]):
    """Строит документ команды из данных SQL."""
    tv_named = {}
    for tv_id, val in tv_by_id.items():
        tv_name = tv_map.get(tv_id)
        if tv_name:
            tv_named[tv_name] = val

    # Parse MIGX
    sections = _parse_migx(tv_named.get("config", ""))

    # Извлекаем таблицу фактов из секции "info"
    facts = {}
    main_content = ""
    for sec in sections:
        if sec.get("MIGX_formname") == "info":
            table_html = sec.get("table", "")
            facts = _parse_facts_table(table_html)
            # subtitle обычно содержит основной текст о команде
            main_content = sec.get("subtitle", "")
            break

    # Извлекаем текстовые блоки
    all_text_sections = []
    for sec in sections:
        if sec.get("MIGX_formname") == "text":
            title = sec.get("section_name", "")
            # Контент может быть в 'content' или 'subtitle'
            content = sec.get("content", "") or sec.get("subtitle", "")
            if content:
                all_text_sections.append({
                    'title': title,
                    'content': content,
                })
    
    # Формируем стандартные 4 блока для команд КВН
    text_blocks = []
    
    # Добавляем основной контент как первый блок (без заголовка)
    if main_content:
        text_blocks.append({
            'title': '',
            'content': main_content,
        })
    
    # 1. Состав команды КВН
    sostav = None
    for block in all_text_sections:
        if 'Состав' in block['title']:
            sostav = block
            break
    if sostav:
        text_blocks.append(sostav)
    
    # 2. История команды - объединяем все блоки с "История"
    history_blocks = [b for b in all_text_sections if 'История' in b['title']]
    if history_blocks:
        combined_history = '\n\n'.join([b['content'] for b in history_blocks])
        text_blocks.append({
            'title': 'История команды',
            'content': combined_history,
        })
    
    # 3. Сторонние проекты
    projects = None
    for block in all_text_sections:
        if 'Сторонние проекты' in block['title']:
            projects = block
            break
    if projects:
        text_blocks.append({
            'title': 'Сторонние проекты команды после/во время игры в КВН',
            'content': projects['content'],
        })
    
    # 4. Список игр команды
    games = None
    for block in all_text_sections:
        if 'Список игр' in block['title']:
            games = block
            break
    if games:
        text_blocks.append({
            'title': 'Список игр команды',
            'content': games['content'],
        })

    # Таймлайн
    timeline_events = _timeline_from_migx_sections(sections)

    # Tags
    tags = _tags_from_keywords(sc.keywords)

    # Rating
    avg = float(sc.rating or 0.0)
    if avg < 0:
        avg = 0.0
    if avg > 10:
        avg = 10.0
    rating = {"average": avg, "count": int(sc.votes or 0)}

    # Image - убираем префикс /media/imported/
    image_url = None
    tv_img = tv_named.get('img')
    if tv_img:
        # Просто берём путь как есть, без префикса
        image_url = str(tv_img).lstrip('/')

    # Social links - добавляем веб-сайт для Уральских пельменей
    social_links = {}
    if sc.alias == 'uralskie-pelmeni':
        social_links['website'] = 'https://pelmeny.net/'

    doc = create_team_document(
        title=sc.pagetitle,
        slug=sc.alias,
        name=sc.longtitle or sc.pagetitle,
        logo_url=image_url,
        facts=facts,
        text_blocks=text_blocks,
        timeline_events=timeline_events,
        tags=tags,
        rating=rating,
        social_links=social_links,
    )

    return doc


def main():
    parser = argparse.ArgumentParser(description="Импорт команд КВН из SQL в MongoDB")
    parser.add_argument("--ids", nargs="+", type=int, help="Конкретные ID команд для импорта")
    parser.add_argument("--from-list", action="store_true", help="Импорт из kvn_teams_list.json")
    parser.add_argument("--limit", type=int, default=1, help="Количество команд для импорта из списка")
    parser.add_argument("--dry-run", action="store_true", help="Только показать, не сохранять")
    parser.add_argument("--apply", action="store_true", help="Применить изменения")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Укажите --dry-run или --apply")
        return

    # Определяем список ID для импорта
    if args.ids:
        target_ids = set(args.ids)
    elif args.from_list:
        if not os.path.exists(KVN_TEAMS_LIST_FILE):
            print(f"Файл {KVN_TEAMS_LIST_FILE} не найден. Запустите сначала build_kvn_teams_list.py")
            return
        
        with open(KVN_TEAMS_LIST_FILE, "r", encoding="utf-8") as f:
            teams_list = json.load(f)
        
        # Берём первые pending
        pending = [t for t in teams_list if t.get("status") == "pending"]
        target_ids = set([t["id"] for t in pending[:args.limit]])
        
        if not target_ids:
            print("Нет pending команд для импорта")
            return
    else:
        print("Укажите --ids или --from-list")
        return

    print(f"Импорт {len(target_ids)} команд: {sorted(target_ids)}\n")

    # Загружаем данные
    tv_map = _load_tv_map()
    image_map = _load_image_map()
    site_content, tv_values = _extract_for_ids(target_ids)

    # Подключение к MongoDB
    client = None
    collection = None
    if args.apply:
        client = pymongo.MongoClient(MONGO_URL)
        db = client[DB_NAME]
        collection = db["teams"]  # Store teams in 'teams' collection

    imported_count = 0
    
    for team_id in sorted(target_ids):
        sc = site_content.get(team_id)
        if not sc:
            print(f"⚠️  ID {team_id}: не найден в SQL")
            continue

        tv_by_id = tv_values.get(team_id, {})
        
        try:
            doc = build_team_doc(sc, tv_by_id, tv_map, image_map)
            
            print(f"\n{'='*60}")
            print(f"ID {team_id}: {doc['title']} ({doc['slug']})")
            print(f"{'='*60}")
            print(f"Facts: {len(doc['facts'])} items")
            for k, v in doc['facts'].items():
                print(f"  - {k}: {v[:60]}")
            print(f"Text blocks: {len([m for m in doc['modules'] if m['type'] == 'text_block'])}")
            for m in doc['modules']:
                if m['type'] == 'text_block':
                    print(f"  - {m['title'] or '(Без заголовка)'}: {len(m['data']['content'])} chars")
            
            timeline_count = len([m for m in doc['modules'] if m['type'] == 'timeline'])
            if timeline_count:
                timeline = [m for m in doc['modules'] if m['type'] == 'timeline'][0]
                print(f"Timeline: {len(timeline['data']['items'])} events")
            
            print(f"Tags: {doc['tags']}")
            print(f"Rating: {doc['rating']['average']} ({doc['rating']['count']} votes)")
            print(f"Logo: {doc['logo']}")

            if args.apply:
                # Проверяем, не существует ли уже
                existing = collection.find_one({"slug": doc['slug'], "content_type": "team"})
                if existing:
                    print(f"⚠️  Команда с slug '{doc['slug']}' уже существует, пропускаем")
                    continue
                
                collection.insert_one(doc)
                imported_count += 1
                print(f"✅ Импортирован")
                
                # Обновляем статус в списке
                if args.from_list:
                    for t in teams_list:
                        if t["id"] == team_id:
                            t["status"] = "imported"
                    with open(KVN_TEAMS_LIST_FILE, "w", encoding="utf-8") as f:
                        json.dump(teams_list, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"❌ Ошибка импорта ID {team_id}: {e}")
            import traceback
            traceback.print_exc()

    if client:
        client.close()

    print(f"\n{'='*60}")
    print(f"Импортировано: {imported_count} из {len(target_ids)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
