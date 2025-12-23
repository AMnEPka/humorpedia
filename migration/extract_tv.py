#!/usr/bin/env python3
"""
Извлечение Template Variables (TV) для person ID=350
"""
import re
import json

def get_tv_names_map(dump_file):
    """Get mapping of TV ID to TV name"""
    print("Извлекаем названия Template Variables...\n")
    
    with open(dump_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find INSERT INTO modx_site_tmplvars
    pattern = r"INSERT INTO `modx_site_tmplvars`[^;]*;"
    matches = re.finditer(pattern, content, re.DOTALL)
    
    tv_map = {}
    
    for match in matches:
        insert_stmt = match.group(0)
        
        # Extract VALUES
        values_match = re.search(r'VALUES\s*\((.*)\);?$', insert_stmt, re.DOTALL)
        if not values_match:
            continue
        
        values_str = values_match.group(1)
        
        # Split by ),( for multiple rows
        rows = re.split(r'\),\s*\(', values_str)
        
        for row in rows:
            # Parse row: (id, source, property_preprocess, type, name, caption, ...)
            # We need id (field 0) and name (field 4)
            parts = []
            current = ""
            in_quotes = False
            
            for char in row:
                if char == "'" and (not current or current[-1] != '\\'):
                    in_quotes = not in_quotes
                elif char == ',' and not in_quotes:
                    parts.append(current.strip().strip("'"))
                    current = ""
                    continue
                current += char
            
            if current:
                parts.append(current.strip().strip("'"))
            
            if len(parts) >= 5:
                tv_id = parts[0]
                tv_name = parts[4]
                tv_map[tv_id] = tv_name
                print(f"  TV {tv_id}: {tv_name}")
    
    return tv_map

def get_tv_values_for_content(dump_file, content_id):
    """Get all TV values for a content ID"""
    print(f"\nИзвлекаем TV values для content ID={content_id}...\n")
    
    with open(dump_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find INSERT INTO modx_site_tmplvar_contentvalues
    pattern = r"INSERT INTO `modx_site_tmplvar_contentvalues`[^;]*;"
    matches = re.finditer(pattern, content, re.DOTALL)
    
    tv_values = {}
    
    for match in matches:
        insert_stmt = match.group(0)
        
        # Extract VALUES
        values_match = re.search(r'VALUES\s*\((.*)\);?$', insert_stmt, re.DOTALL)
        if not values_match:
            continue
        
        values_str = values_match.group(1)
        
        # Split by ),( for multiple rows
        rows = re.split(r'\),\s*\(', values_str)
        
        for row in rows:
            # Parse row: (id, tmplvarid, contentid, value)
            parts = []
            current = ""
            in_quotes = False
            escape_next = False
            
            for char in row:
                if escape_next:
                    current += char
                    escape_next = False
                    continue
                
                if char == '\\':
                    current += char
                    escape_next = True
                    continue
                
                if char == "'" and not escape_next:
                    in_quotes = not in_quotes
                    if not in_quotes:
                        # End of quoted value, don't include quote
                        continue
                    elif current and current[-1] != ',':
                        # Start of quoted value
                        continue
                
                if char == ',' and not in_quotes:
                    parts.append(current.strip())
                    current = ""
                    continue
                
                current += char
            
            if current:
                parts.append(current.strip())
            
            if len(parts) >= 4:
                row_contentid = parts[2]
                if row_contentid == str(content_id):
                    tmplvarid = parts[1]
                    value = parts[3]
                    tv_values[tmplvarid] = value
                    print(f"  TV {tmplvarid}: {value[:100]}..." if len(value) > 100 else f"  TV {tmplvarid}: {value}")
    
    return tv_values

if __name__ == "__main__":
    dump_file = "/app/modx_dump.sql"
    
    # Get TV names
    tv_map = get_tv_names_map(dump_file)
    
    # Get TV values for person 350
    tv_values = get_tv_values_for_content(dump_file, 350)
    
    # Combine
    result = {}
    for tv_id, value in tv_values.items():
        tv_name = tv_map.get(tv_id, f"unknown_{tv_id}")
        result[tv_name] = value
    
    print("\n" + "="*80)
    print("РЕЗУЛЬТАТ: TV для person ID=350")
    print("="*80)
    
    for name, value in result.items():
        print(f"\n{name}:")
        print(f"  {value[:200]}..." if len(value) > 200 else f"  {value}")
    
    # Save to JSON
    with open('/app/migration/person_350_tv.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("\n✅ Сохранено в /app/migration/person_350_tv.json")
