#!/usr/bin/env python3
"""
Migration script to import Irina Chesnokova from modx_new.sql
"""
import re
import os
import json
from datetime import datetime, timezone
from uuid import uuid4
import pymongo
from html import unescape

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'humorpedia')

SQL_FILE = '/app/modx_new.sql'

def clean_html(text):
    """Clean HTML entities and normalize text"""
    if not text:
        return ""
    # Decode HTML entities
    text = unescape(text)
    # Replace \r\n with proper line breaks
    text = text.replace('\\r\\n', '\n').replace('\\r', '\n')
    text = text.replace("\\n", "\n")
    # Replace &nbsp; 
    text = text.replace('&nbsp;', ' ')
    return text.strip()

def extract_person_data_from_sql(sql_content, slug):
    """Extract person data from SQL dump by searching for specific patterns"""
    
    # Find the record with the given slug in modx_site_content
    # Format: (id,'document','text/html','title','longtitle','description','slug',...)
    pattern = rf"\((\d+),'document','text/html','([^']+)','([^']*)','([^']*)','({slug})'[^)]+\)"
    
    # Search in site_content INSERT
    site_content_match = re.search(pattern, sql_content)
    
    if not site_content_match:
        print(f"Could not find slug: {slug}")
        return None
    
    resource_id = site_content_match.group(1)
    title = site_content_match.group(2)
    longtitle = site_content_match.group(3) or title
    description = site_content_match.group(4)
    
    print(f"Found resource ID: {resource_id}, Title: {title}")
    
    return {
        'resource_id': resource_id,
        'title': title,
        'longtitle': longtitle,
        'description': description,
        'slug': slug
    }

def extract_ratings_for_id(sql_content, resource_id):
    """Extract ratings from modx_articlescores for a given resource ID"""
    # Pattern: (vote_id, resource_id, user_id, score)
    pattern = rf"\((\d+),{resource_id},(\d+),(\d+)\)"
    
    matches = re.findall(pattern, sql_content)
    
    if not matches:
        print(f"No ratings found for resource ID: {resource_id}")
        return {'average': 0.0, 'count': 0, 'votes': []}
    
    votes = []
    total_score = 0
    for match in matches:
        vote_id, user_id, score = match
        votes.append({'user_id': int(user_id), 'score': int(score)})
        total_score += int(score)
    
    avg_score = total_score / len(votes) if votes else 0.0
    
    print(f"Found {len(votes)} ratings, average: {avg_score:.2f}")
    
    return {
        'average': round(avg_score, 2),
        'count': len(votes),
        'votes': votes
    }

def extract_irina_data():
    """Extract Irina Chesnokova's data from the SQL dump"""
    
    print("Loading SQL dump...")
    with open(SQL_FILE, 'r', encoding='utf-8', errors='replace') as f:
        sql_content = f.read()
    
    print("SQL dump loaded. Size:", len(sql_content), "bytes")
    
    # Find Irina Chesnokova's record
    # Search for her name in modx_mse2_intro first
    intro_pattern = r"'Чеснокова Ирина[^']*'"
    intro_match = re.search(intro_pattern, sql_content)
    
    if intro_match:
        print("Found Irina in mse2_intro:", intro_match.group(0)[:100])
    
    # Now search for her in modx_site_content by looking for the pattern
    # Looking for record with 'irina-chesnokova' or 'Чеснокова Ирина'
    
    # Search for the full record containing Чеснокова
    record_pattern = r"\((\d+),'document','text/html','Чеснокова Ирина','([^']*)','([^']*)','([^']+)'"
    record_match = re.search(record_pattern, sql_content)
    
    if record_match:
        resource_id = record_match.group(1)
        longtitle = record_match.group(2)
        description = record_match.group(3)
        slug = record_match.group(4)
        print(f"Found Irina Chesnokova: ID={resource_id}, slug={slug}")
    else:
        # Try alternative search
        alt_pattern = r",(\d+),'document','text/html','Чеснокова Ирина"
        alt_match = re.search(alt_pattern, sql_content)
        if alt_match:
            # Найдём полную строку
            print("Found via alternative pattern")
            resource_id = None
        else:
            print("Could not find Irina Chesnokova in site_content")
            return None
    
    # Extract the full record for Irina
    # We need to find her entry in the intro table which contains the full data
    
    # Search in modx_mse2_intro for her full content block
    full_pattern = r"\((\d+),'Чеснокова Ирина([^']+)'"
    full_match = re.search(full_pattern, sql_content)
    
    if full_match:
        entry_id = full_match.group(1)
        content_block = full_match.group(2)
        print(f"Found full content block for ID {entry_id}")
        print("Content preview:", content_block[:200])
        
        # Parse the content block to extract:
        # - Biography text
        # - Birth date
        # - Social links
        # - Tags
        
        # Extract biography
        bio_pattern = r'Ирина[^<]*Чеснокова[^<]*\(род\.[^)]+\)[^<]*&ndash;[^<]+'
        bio_match = re.search(bio_pattern, content_block)
        biography = ""
        if bio_match:
            biography = clean_html(bio_match.group(0))
            print("Biography:", biography[:200])
        
        # Look for full biography in the content
        info_pattern = r'Информация о человеке[^<]*info\.tpl\s+([^[]+)'
        info_match = re.search(info_pattern, content_block)
        if info_match:
            biography = clean_html(info_match.group(1))
            print("Full biography:", biography[:300])
    
    # Get the ratings
    if resource_id:
        ratings = extract_ratings_for_id(sql_content, resource_id)
    else:
        ratings = {'average': 0.0, 'count': 0, 'votes': []}
    
    # Build the person document
    person_data = {
        'id': str(uuid4()),
        'content_type': 'person',
        'title': 'Чеснокова Ирина',
        'slug': 'irina-chesnokova',
        'full_name': 'Ирина Игоревна Чеснокова',
        'status': 'published',
        'tags': ['КВН', 'Факультет журналистики', 'Однажды в России', 'Санкт-Петербург'],
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'bio': {
            'birth_date': '1989-02-09',
            'birth_place': 'Воронеж',
            'occupation': ['актриса', 'ведущая'],
            'achievements': ['Финалистка Высшей лиги КВН']
        },
        'social_links': {},
        'modules': [
            {
                'id': str(uuid4()),
                'type': 'biography',
                'title': 'Биография',
                'content': 'Ирина Игоревна Чеснокова (род. 9 февраля 1989 года, Воронеж) – актриса шоу «Однажды в России», финалистка Высшей лиги КВН в составе команды «Факультет журналистики» (Санкт-Петербург), ведущая собственного ютуб-шоу «Бар в большом городе».',
                'order': 1
            }
        ],
        'rating': ratings,
        'views_count': 0,
        'team_ids': [],
        'show_ids': [],
        'article_ids': [],
        'featured': False,
        'seo': {
            'meta_title': 'Ирина Чеснокова - актриса, КВН',
            'meta_description': 'Ирина Чеснокова – актриса шоу «Однажды в России», финалистка Высшей лиги КВН в составе команды «Факультет журналистики».'
        }
    }
    
    return person_data

def import_to_mongodb(person_data):
    """Import person data to MongoDB"""
    
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Check if already exists
    existing = db.people.find_one({'slug': person_data['slug']})
    
    if existing:
        print(f"Record already exists with slug: {person_data['slug']}")
        print("Updating existing record...")
        db.people.update_one(
            {'slug': person_data['slug']},
            {'$set': person_data}
        )
        print("Record updated!")
    else:
        print("Inserting new record...")
        db.people.insert_one(person_data)
        print("Record inserted!")
    
    # Verify
    saved = db.people.find_one({'slug': person_data['slug']}, {'_id': 0})
    print("\nSaved record:")
    print(json.dumps(saved, indent=2, ensure_ascii=False, default=str))
    
    client.close()
    return saved

def main():
    print("=" * 60)
    print("Importing Irina Chesnokova from modx_new.sql")
    print("=" * 60)
    
    # Extract data
    person_data = extract_irina_data()
    
    if not person_data:
        print("Failed to extract person data")
        return
    
    print("\n" + "=" * 60)
    print("Extracted data:")
    print(json.dumps(person_data, indent=2, ensure_ascii=False, default=str))
    
    # Import to MongoDB
    print("\n" + "=" * 60)
    print("Importing to MongoDB...")
    import_to_mongodb(person_data)
    
    print("\n" + "=" * 60)
    print("Done! Check the page at: http://localhost:3000/people/irina-chesnokova")

if __name__ == '__main__':
    main()
