#!/usr/bin/env python3
"""
Полноценный импорт person с TV и модулями
"""
import sys
import os
import re
import json
from datetime import datetime, timezone
from uuid import uuid4

sys.path.insert(0, '/app/backend')

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

MONGO_URL = os.getenv('MONGO_URL')
DB_NAME = os.getenv('DB_NAME')

def parse_date(date_str):
    """Parse Russian date format"""
    if not date_str:
        return None
    
    # Example: "9 февраля 1989 года"
    months = {
        'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
        'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
        'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
    }
    
    match = re.search(r'(\d+)\s+(\w+)\s+(\d{4})', date_str)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))
        month = months.get(month_name, 1)
        return f"{year}-{month:02d}-{day:02d}"
    
    return None

def strip_html(html):
    """Strip HTML tags"""
    if not html:
        return ""
    clean = re.sub(r'<[^>]+>', '', html)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def extract_social_links(tv_data):
    """Extract social links from TV"""
    links = {}
    
    vk = tv_data.get('table-vk', '')
    if 'vk.com' in vk:
        match = re.search(r'https?://vk\.com/([^`\'"]+)', vk)
        if match:
            links['vk'] = f"https://vk.com/{match.group(1)}"
    
    ig = tv_data.get('table-ig', '')
    if 'instagram.com' in ig:
        match = re.search(r'https?://[^/]*instagram\.com/([^`\'"]+)', ig)
        if match:
            links['instagram'] = f"https://www.instagram.com/{match.group(1).rstrip('/')}"
    
    youtube = tv_data.get('table-youtube', '')
    if 'youtube.com' in youtube:
        match = re.search(r'https?://[^/]*youtube\.com/([^`\'"]+)', youtube)
        if match:
            links['youtube'] = f"https://www.youtube.com/{match.group(1)}"
    
    return links

def create_timeline_modules(tv_data):
    """Create timeline modules from TV data"""
    modules = []
    
    # Find all timeline blocks
    for i in range(1, 10):
        suffix = '' if i == 1 else str(i)
        date_key = f'timeline-block-date{suffix}'
        name_key = f'timeline-block-name{suffix}'
        value_key = f'timeline-block-value{suffix}'
        
        if date_key in tv_data and name_key in tv_data and value_key in tv_data:
            date = tv_data[date_key]
            name = tv_data[name_key]
            value = tv_data[value_key]
            
            # Clean HTML from value
            clean_text = strip_html(value)
            
            modules.append({
                "type": "timeline",
                "data": {
                    "period": date,
                    "title": name,
                    "content": clean_text,
                    "content_html": value
                }
            })
    
    return modules

def convert_to_person(modx_record, tv_data):
    """Convert MODX + TV data to MongoDB person"""
    
    # Parse dates
    birth_date = parse_date(tv_data.get('table-value2', ''))
    
    # Extract tags
    tags_str = tv_data.get('tags', '')
    tags = [t.strip() for t in tags_str.split(',') if t.strip()]
    
    # Social links
    social_links = extract_social_links(tv_data)
    
    # Timeline modules
    timeline_modules = create_timeline_modules(tv_data)
    
    # Add bio as text module
    bio_html = modx_record.get('content', '')
    bio_text = strip_html(bio_html)
    
    modules = []
    
    # Add bio module
    if bio_text:
        modules.append({
            "type": "text",
            "data": {
                "content": bio_text,
                "content_html": bio_html
            }
        })
    
    # Add timeline modules
    modules.extend(timeline_modules)
    
    # Parse timestamps
    createdon = int(modx_record.get('createdon', 0) or 0)
    editedon = int(modx_record.get('editedon', 0) or 0)
    
    created_at = datetime.fromtimestamp(createdon, tz=timezone.utc) if createdon > 0 else datetime.now(timezone.utc)
    updated_at = datetime.fromtimestamp(editedon, tz=timezone.utc) if editedon > 0 else created_at
    
    # Cover image
    cover_image = None
    img_url = tv_data.get('table-image', '') or tv_data.get('img_seo', '')
    if img_url:
        cover_image = {
            "url": f"https://humorpedia.ru/{img_url}",
            "alt": tv_data.get('table-image-tags', '') or modx_record.get('pagetitle', '')
        }
    
    person = {
        "_id": str(uuid4()),
        "old_modx_id": int(modx_record['id']),
        "full_name": tv_data.get('table-value', '') or modx_record.get('pagetitle', ''),
        "title": modx_record.get('pagetitle', ''),
        "slug": modx_record.get('alias', ''),
        "description": modx_record.get('description', ''),
        "bio": bio_text[:500] if bio_text else "",
        "birth_date": birth_date,
        "birth_place": tv_data.get('table-value3', ''),
        "cover_image": cover_image,
        "social_links": social_links,
        "modules": modules,
        "teams": [],
        "shows": [],
        "awards": [],
        "tags": tags,
        "status": "published",  # Set to published!
        "views": 0,
        "created_at": created_at.isoformat(),
        "updated_at": updated_at.isoformat(),
        "seo": {
            "meta_title": modx_record.get('longtitle', '') or modx_record.get('pagetitle', ''),
            "meta_description": modx_record.get('description', ''),
            "keywords": tags
        }
    }
    
    return person

async def import_person_with_tv():
    """Import person with TV data"""
    
    # Load raw MODX record
    with open('/app/migration/person_350_raw_line.txt', 'r', encoding='utf-8') as f:
        line = f.read()
    
    # Parse MODX record (using simple split - good enough)
    print("Парсинг MODX record...")
    line = line.strip()
    if line.startswith('('):
        line = line[1:]
    if line.endswith('),'):
        line = line[:-2]
    elif line.endswith(')'):
        line = line[:-1]
    
    # Simple field extraction
    parts = []
    current = ""
    in_quotes = False
    
    for char in line:
        if char == "'" and (not current or current[-1] != '\\'):
            in_quotes = not in_quotes
            if not in_quotes:
                continue
            elif current and current[-1] != ',':
                continue
        
        if char == ',' and not in_quotes:
            parts.append(current)
            current = ""
            continue
        
        current += char
    
    if current:
        parts.append(current)
    
    field_names = [
        'id', 'type', 'contentType', 'pagetitle', 'longtitle', 'description',
        'alias', 'alias_visible', 'link_attributes', 'published', 'pub_date',
        'unpub_date', 'parent', 'isfolder', 'introtext', 'content', 'richtext',
        'template', 'menuindex', 'searchable', 'cacheable', 'createdby',
        'createdon', 'editedby', 'editedon', 'deleted', 'deletedon',
        'deletedby', 'publishedon', 'publishedby', 'menutitle', 'donthit',
        'privateweb', 'privatemgr', 'content_dispo', 'hidemenu', 'class_key',
        'context_key', 'content_type', 'uri', 'uri_override',
        'hide_children_in_tree', 'show_in_tree', 'properties'
    ]
    
    modx_record = {}
    for i, name in enumerate(field_names):
        if i < len(parts):
            modx_record[name] = parts[i]
    
    # Load TV data
    with open('/app/migration/person_350_tv_mapped.json', 'r', encoding='utf-8') as f:
        tv_data = json.load(f)
    
    print("\n" + "="*80)
    print("ПРЕОБРАЗОВАНИЕ В MONGODB")
    print("="*80)
    
    # Convert
    person = convert_to_person(modx_record, tv_data)
    
    print(json.dumps(person, ensure_ascii=False, indent=2))
    
    # Save for review
    with open('/app/migration/person_350_final.json', 'w', encoding='utf-8') as f:
        json.dump(person, f, ensure_ascii=False, indent=2)
    
    print("\n✅ Сохранено в person_350_final.json")
    
    # Import to MongoDB
    print("\n" + "="*80)
    print("ИМПОРТ В MONGODB")
    print("="*80)
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Check if exists
    existing = await db.people.find_one({"old_modx_id": int(modx_record['id'])})
    
    if existing:
        print(f"⚠️  Обновляем существующую запись...")
        await db.people.replace_one({"_id": existing['_id']}, person)
        print(f"✅ ОБНОВЛЕНО!")
        print(f"   ID: {existing['_id']}")
    else:
        result = await db.people.insert_one(person)
        print(f"✅ ИМПОРТИРОВАНО!")
        print(f"   ID: {result.inserted_id}")
    
    print(f"   Имя: {person['full_name']}")
    print(f"   Дата рождения: {person['birth_date']}")
    print(f"   Место рождения: {person['birth_place']}")
    print(f"   Модулей: {len(person['modules'])}")
    print(f"   Тегов: {len(person['tags'])}")
    print(f"   Соцсети: {list(person['social_links'].keys())}")
    print(f"   Status: {person['status']}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(import_person_with_tv())
