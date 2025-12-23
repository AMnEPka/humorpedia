#!/usr/bin/env python3
"""
Импорт ОДНОЙ записи человека для проверки
"""
import sys
import os
import re
import json
from datetime import datetime, timezone
from uuid import uuid4

# Add backend to path
sys.path.insert(0, '/app/backend')

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

# MongoDB connection
MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'humorpedia')

def parse_modx_record(line):
    """Parse a single MODX record line"""
    # Remove leading ( and trailing ),
    line = line.strip()
    if line.startswith('('):
        line = line[1:]
    if line.endswith('),'):
        line = line[:-2]
    elif line.endswith(')'):
        line = line[:-1]
    
    # Field names from CREATE TABLE modx_site_content
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
    
    # Parse fields carefully
    fields = []
    current_field = ""
    in_quotes = False
    escape_next = False
    
    i = 0
    while i < len(line):
        char = line[i]
        
        if escape_next:
            current_field += char
            escape_next = False
            i += 1
            continue
        
        if char == '\\\\':
            current_field += '\\\\'
            escape_next = True
            i += 1
            continue
        
        if char == "'" and not escape_next:
            if not in_quotes:
                in_quotes = True
                i += 1
                continue
            else:
                # Check if next char is also ' (escaped quote)
                if i + 1 < len(line) and line[i + 1] == "'":
                    current_field += "'"
                    i += 2
                    continue
                else:
                    in_quotes = False
                    i += 1
                    continue
        
        if char == ',' and not in_quotes:
            # End of field
            field_value = current_field.strip()
            if field_value == 'NULL':
                fields.append(None)
            else:
                fields.append(field_value)
            current_field = ""
            i += 1
            # Skip spaces after comma
            while i < len(line) and line[i] == ' ':
                i += 1
            continue
        
        current_field += char
        i += 1
    
    # Add last field
    if current_field.strip():
        field_value = current_field.strip()
        if field_value == 'NULL':
            fields.append(None)
        else:
            fields.append(field_value)
    
    # Create dict
    record = {}
    for i, field_name in enumerate(field_names):
        if i < len(fields):
            record[field_name] = fields[i]
        else:
            record[field_name] = None
    
    return record

def strip_html_tags(html):
    """Simple HTML tag stripper"""
    if not html:
        return ""
    clean = re.sub(r'<[^>]+>', '', html)
    clean = re.sub(r'\\s+', ' ', clean).strip()
    return clean

def convert_to_mongodb_person(modx_record):
    """Convert MODX record to MongoDB person format"""
    
    # Extract tags from introtext (keywords after name)
    tags = []
    introtext = modx_record.get('introtext', '') or ''
    
    # Clean HTML from content
    content_html = modx_record.get('content', '') or ''
    content_text = strip_html_tags(content_html)
    
    # Parse timestamp
    createdon = int(modx_record.get('createdon', 0) or 0)
    editedon = int(modx_record.get('editedon', 0) or 0)
    
    created_at = datetime.fromtimestamp(createdon, tz=timezone.utc) if createdon > 0 else datetime.now(timezone.utc)
    updated_at = datetime.fromtimestamp(editedon, tz=timezone.utc) if editedon > 0 else created_at
    
    # Build person record
    person = {
        "_id": str(uuid4()),
        "old_modx_id": int(modx_record['id']),
        "full_name": modx_record.get('pagetitle', ''),
        "title": modx_record.get('pagetitle', ''),  # Use as title too
        "slug": modx_record.get('alias', ''),
        "description": modx_record.get('description', ''),
        "bio": content_text[:500] if content_text else "",  # First 500 chars
        "content_html": content_html,  # Keep original HTML
        "birth_date": None,
        "birth_place": None,
        "social_links": {},
        "teams": [],
        "shows": [],
        "awards": [],
        "tags": tags,
        "status": "published" if int(modx_record.get('published', 0)) == 1 else "draft",
        "views": 0,
        "created_at": created_at.isoformat(),
        "updated_at": updated_at.isoformat(),
        "seo": {
            "meta_title": modx_record.get('longtitle', '') or modx_record.get('pagetitle', ''),
            "meta_description": modx_record.get('description', ''),
            "keywords": []
        }
    }
    
    return person

async def import_one_person():
    """Import one person to MongoDB"""
    # Read the extracted record
    with open('/app/migration/person_350_raw_line.txt', 'r', encoding='utf-8') as f:
        line = f.read()
    
    print("Парсинг записи...")
    modx_record = parse_modx_record(line)
    
    print("\n" + "="*80)
    print("MODX ЗАПИСЬ:")
    print("="*80)
    print(f"ID: {modx_record.get('id')}")
    print(f"Название: {modx_record.get('pagetitle')}")
    print(f"Алиас: {modx_record.get('alias')}")
    print(f"URI: {modx_record.get('uri')}")
    print(f"Описание: {modx_record.get('description')}")
    print(f"Опубликовано: {modx_record.get('published')}")
    print(f"\\nПервые 300 символов контента:")
    print(modx_record.get('content', '')[:300])
    print("...")
    
    # Convert to MongoDB format
    person = convert_to_mongodb_person(modx_record)
    
    print("\\n" + "="*80)
    print("MONGODB ЗАПИСЬ (для импорта):")
    print("="*80)
    print(json.dumps(person, ensure_ascii=False, indent=2))
    
    # Save to file for review
    with open('/app/migration/person_350_mongo.json', 'w', encoding='utf-8') as f:
        json.dump(person, f, ensure_ascii=False, indent=2)
    
    print("\\n✅ Преобразованная запись сохранена в /app/migration/person_350_mongo.json")
    
    # Ask for confirmation
    print("\\n" + "="*80)
    print("ИМПОРТ В MONGODB")
    print("="*80)
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Check if person already exists
    existing = await db.people.find_one({"old_modx_id": int(modx_record['id'])})
    
    if existing:
        print(f"⚠️  Человек с MODX ID {modx_record['id']} уже существует в базе!")
        print(f"   MongoDB ID: {existing['_id']}")
        print(f"   Имя: {existing.get('full_name')}")
        print("\\nПропускаем импорт...")
    else:
        # Import
        print(f"Импортируем: {person['full_name']}...")
        result = await db.people.insert_one(person)
        print(f"\\n✅ УСПЕШНО ИМПОРТИРОВАНО!")
        print(f"   MongoDB ID: {result.inserted_id}")
        print(f"   Имя: {person['full_name']}")
        print(f"   Slug: {person['slug']}")
        print(f"   Status: {person['status']}")
    
    await client.close()

if __name__ == "__main__":
    print("ИМПОРТ ОДНОЙ ЗАПИСИ ЧЕЛОВЕКА\\n")
    asyncio.run(import_one_person())
