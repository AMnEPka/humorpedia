#!/usr/bin/env python3
"""
Шаг 1: Извлечение всех уникальных путей к изображениям из дампа
"""
import re
import json
from collections import defaultdict

def extract_image_paths(dump_file):
    """Extract all unique image paths from TV values"""
    print("Извлекаем пути к изображениям из TV...\n")
    
    image_paths = set()
    image_tv_fields = ['table-image', 'img_seo', 'timeline-block-image', 'article-img']
    
    with open(dump_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all INSERT INTO modx_site_tmplvar_contentvalues
    pattern = r"INSERT INTO `modx_site_tmplvar_contentvalues`[^;]*;"
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        insert_stmt = match.group(0)
        
        # Extract rows with image paths
        # Look for paths like 'images/people/...' or 'images/teams/...'
        image_matches = re.findall(r"'(images/[^']+\.(?:jpg|jpeg|png|gif|webp))'", insert_stmt, re.IGNORECASE)
        
        for img_path in image_matches:
            image_paths.add(img_path)
    
    return sorted(list(image_paths))

def categorize_images(image_paths):
    """Categorize images by type"""
    categories = defaultdict(list)
    
    for path in image_paths:
        if '/people/' in path:
            categories['people'].append(path)
        elif '/team/' in path or '/teams/' in path:
            categories['teams'].append(path)
        elif '/show/' in path or '/shows/' in path:
            categories['shows'].append(path)
        elif '/article/' in path or '/articles/' in path:
            categories['articles'].append(path)
        elif '/news/' in path:
            categories['news'].append(path)
        else:
            categories['other'].append(path)
    
    return dict(categories)

if __name__ == "__main__":
    dump_file = "/app/modx_dump.sql"
    
    print("="*80)
    print("ИЗВЛЕЧЕНИЕ ПУТЕЙ К ИЗОБРАЖЕНИЯМ")
    print("="*80)
    print()
    
    image_paths = extract_image_paths(dump_file)
    
    print(f"\n✅ Найдено уникальных изображений: {len(image_paths)}\n")
    
    # Categorize
    categories = categorize_images(image_paths)
    
    print("КАТЕГОРИИ:")
    print("-" * 80)
    for category, paths in categories.items():
        print(f"{category.upper()}: {len(paths)} изображений")
        for path in paths[:3]:
            print(f"  - {path}")
        if len(paths) > 3:
            print(f"  ... и ещё {len(paths) - 3}")
        print()
    
    # Save to JSON
    output = {
        "total": len(image_paths),
        "categories": categories,
        "all_paths": image_paths
    }
    
    with open('/app/migration/image_paths.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("✅ Сохранено в /app/migration/image_paths.json")
