#!/usr/bin/env python3
"""
Извлечение рейтингов из дампа
"""
import re
import json

def extract_ratings(dump_file):
    """Extract all ratings from goodstar_vote_count"""
    print("Извлекаем рейтинги...\n")
    
    with open(dump_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find INSERT INTO modx_goodstar_vote_count
    pattern = r"INSERT INTO `modx_goodstar_vote_count`[^;]*;"
    matches = re.finditer(pattern, content, re.DOTALL)
    
    ratings = {}
    
    for match in matches:
        insert_stmt = match.group(0)
        
        # Extract rows
        rows = re.findall(r"\((\d+),\s*'(\d+)',\s*'([\d.]+)',\s*(\d+)\)", insert_stmt)
        
        for row in rows:
            row_id, thread_id, avg_rating, vote_count = row
            
            if thread_id and thread_id != '':
                ratings[thread_id] = {
                    'average_rating': float(avg_rating),
                    'vote_count': int(vote_count)
                }
                print(f"  Content {thread_id}: {avg_rating} ★ ({vote_count} голосов)")
    
    return ratings

if __name__ == "__main__":
    dump_file = "/app/modx_dump.sql"
    
    ratings = extract_ratings(dump_file)
    
    print(f"\n✅ Найдено рейтингов: {len(ratings)}")
    
    # Save to JSON
    with open('/app/migration/ratings.json', 'w', encoding='utf-8') as f:
        json.dump(ratings, f, ensure_ascii=False, indent=2)
    
    print("✅ Сохранено в /app/migration/ratings.json")
