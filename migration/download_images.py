#!/usr/bin/env python3
"""
Шаг 2: Скачивание изображений и создание mapping
"""
import os
import json
import requests
from pathlib import Path
import time

BASE_URL = "https://humorpedia.ru"
MEDIA_DIR = "/app/frontend/public/media/imported"

def download_images(image_paths, limit=None):
    """Download images from old site"""
    
    # Create media directory
    os.makedirs(MEDIA_DIR, exist_ok=True)
    
    mapping = {}
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    paths_to_process = image_paths[:limit] if limit else image_paths
    
    print(f"Скачиваем {len(paths_to_process)} изображений...\n")
    
    for i, old_path in enumerate(paths_to_process, 1):
        # Build URL
        url = f"{BASE_URL}/{old_path}"
        
        # Create local path preserving structure
        local_path = Path(MEDIA_DIR) / old_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if already downloaded
        if local_path.exists():
            skip_count += 1
            # Create mapping entry
            new_url = f"/media/imported/{old_path}"
            mapping[old_path] = new_url
            if i % 50 == 0:
                print(f"  [{i}/{len(paths_to_process)}] Пропущено (уже есть): {old_path}")
            continue
        
        try:
            # Download
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Save
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            # Create mapping entry
            new_url = f"/media/imported/{old_path}"
            mapping[old_path] = new_url
            
            success_count += 1
            
            if i % 10 == 0:
                print(f"  [{i}/{len(paths_to_process)}] ✅ {old_path}")
            
            # Small delay to avoid overwhelming server
            time.sleep(0.1)
            
        except Exception as e:
            fail_count += 1
            print(f"  [{i}/{len(paths_to_process)}] ❌ {old_path}: {str(e)[:50]}")
            mapping[old_path] = None
    
    print("\n" + "="*80)
    print(f"✅ Успешно: {success_count}")
    print(f"⏭️  Пропущено: {skip_count}")
    print(f"❌ Ошибок: {fail_count}")
    print(f"📊 Всего в mapping: {len(mapping)}")
    
    return mapping

if __name__ == "__main__":
    # Load image paths
    with open('/app/migration/image_paths.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    image_paths = data['all_paths']
    
    print("="*80)
    print("СКАЧИВАНИЕ ИЗОБРАЖЕНИЙ")
    print("="*80)
    print(f"Всего изображений: {len(image_paths)}")
    print()
    
    # Ask for confirmation
    print("⚠️  ВНИМАНИЕ: Это скачает все 1041 изображение!")
    print("Для теста можно ограничить количество, передав limit")
    print()
    
    # For initial test, download only first 50 people images
    people_images = data['categories'].get('people', [])
    print(f"Начнём с {min(50, len(people_images))} изображений людей для теста...\n")
    
    mapping = download_images(people_images, limit=50)
    
    # Save mapping
    with open('/app/migration/image_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    
    print("\n✅ Mapping сохранён в /app/migration/image_mapping.json")
