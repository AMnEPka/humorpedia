#!/usr/bin/env python3
"""
Простой парсер SQL дампа для извлечения одной записи
"""
import re

def extract_one_person_simple(dump_file):
    """Simple extraction using regex"""
    print("Ищем запись с ID=350...")
    
    with open(dump_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the specific INSERT that contains ID 350
    # Pattern: (350,'document',... 
    pattern = r"\(350,'[^']*','[^']*','([^']*)'.*?template['\"]:\s*(\d+)"
    
    # Find INSERT INTO modx_site_content section
    site_content_section = re.search(
        r"INSERT INTO `modx_site_content`.*?VALUES\s+(.*?);",
        content,
        re.DOTALL
    )
    
    if site_content_section:
        values_section = site_content_section.group(1)
        
        # Find record starting with (350,
        record_match = re.search(
            r"\(350,([^)]*(?:\([^)]*\)[^)]*)*)\)",
            values_section
        )
        
        if record_match:
            print("\n✅ Найдена запись!")
            record = record_match.group(0)
            
            # Save raw record
            with open('/app/migration/person_350_raw.txt', 'w', encoding='utf-8') as f:
                f.write(record)
            
            print(f"\nПервые 500 символов:")
            print(record[:500])
            print("\n...")
            print(f"\nПоследние 200 символов:")
            print(record[-200:])
            print(f"\n\nВсего символов: {len(record)}")
            print("\n✅ Полная запись сохранена в /app/migration/person_350_raw.txt")
            return True
    
    print("❌ Запись не найдена")
    return False

if __name__ == "__main__":
    extract_one_person_simple("/app/modx_dump.sql")
