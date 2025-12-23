#!/usr/bin/env python3
"""
Извлечение одной записи человека из MySQL дампа для проверки
"""
import re
import json
import sys

def extract_person(dump_file, person_id=350):
    """Extract one person record with all fields"""
    print(f"Извлечение записи person ID={person_id}...\n")
    
    with open(dump_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all INSERT INTO modx_site_content
    matches = re.finditer(r"INSERT INTO `modx_site_content`[^;]*;", content, re.DOTALL)
    
    for match in matches:
        insert_stmt = match.group(0)
        
        # Extract rows
        rows_match = re.search(r'VALUES\s*\((.*)\);?$', insert_stmt, re.DOTALL)
        if not rows_match:
            continue
        
        values_str = rows_match.group(1)
        
        # Split by ),( carefully
        rows = []
        current_row = ""
        paren_depth = 0
        in_quotes = False
        escape_next = False
        
        for char in values_str:
            if escape_next:
                current_row += char
                escape_next = False
                continue
            
            if char == '\\':
                current_row += char
                escape_next = True
                continue
            
            if char == "'" and not escape_next:
                in_quotes = not in_quotes
            elif char == '(' and not in_quotes:
                paren_depth += 1
            elif char == ')' and not in_quotes:
                paren_depth -= 1
                if paren_depth == -1:
                    # End of this row
                    rows.append(current_row)
                    current_row = ""
                    paren_depth = 0
                    continue
            
            if char == ',' and paren_depth == 0 and not in_quotes and current_row:
                # Start of new row
                rows.append(current_row)
                current_row = ""
                continue
            
            current_row += char
        
        if current_row:
            rows.append(current_row)
        
        # Now parse each row
        for row in rows:
            # Parse fields
            fields = []
            current_field = ""
            in_quotes = False
            escape_next = False
            
            for char in row:
                if escape_next:
                    current_field += char
                    escape_next = False
                    continue
                
                if char == '\\':
                    current_field += char
                    escape_next = True
                    continue
                
                if char == "'" and not escape_next:
                    if in_quotes:
                        # End of quoted string
                        in_quotes = False
                        continue
                    else:
                        # Start of quoted string
                        in_quotes = True
                        continue
                elif char == ',' and not in_quotes:
                    fields.append(current_field)
                    current_field = ""
                    continue
                
                current_field += char
            
            if current_field:
                fields.append(current_field)
            
            # Check if this is our person
            if len(fields) > 0 and fields[0].strip() == str(person_id):
                # Found it!
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
                
                person = {}
                for i, field_name in enumerate(field_names):
                    if i < len(fields):
                        value = fields[i].strip()
                        # Handle NULL
                        if value.upper() == 'NULL':
                            value = None
                        person[field_name] = value
                
                return person
    
    return None

def get_template_vars(dump_file, resource_id):
    """Get template variables for a resource"""
    print(f"Извлечение TV (Template Variables) для resource {resource_id}...\n")
    
    with open(dump_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find INSERT INTO modx_site_tmplvar_contentvalues
    pattern = r"INSERT INTO `modx_site_tmplvar_contentvalues`[^;]*;"
    matches = re.finditer(pattern, content, re.DOTALL)
    
    tv_values = {}
    
    for match in matches:
        insert_stmt = match.group(0)
        
        # Extract rows - format: (id, tmplvarid, contentid, value)
        rows_match = re.search(r'VALUES\s*\((.*)\);?$', insert_stmt, re.DOTALL)
        if not rows_match:
            continue
        
        values_str = rows_match.group(1)
        
        # Simple parse
        rows = re.split(r'\),\s*\(', values_str)
        
        for row in rows:
            parts = row.split(',', 3)
            if len(parts) >= 4:
                contentid = parts[2].strip().strip("'")
                if contentid == str(resource_id):
                    tmplvarid = parts[1].strip()
                    value = parts[3].strip().strip("'")
                    tv_values[tmplvarid] = value
    
    return tv_values

if __name__ == "__main__":
    dump_file = "/app/modx_dump.sql"
    
    # Extract Ирина Чеснокова
    person = extract_person(dump_file, person_id=350)
    
    if person:
        print("=" * 80)
        print("НАЙДЕНА ЗАПИСЬ:")
        print("=" * 80)
        print()
        
        # Main fields
        print(f"ID: {person['id']}")
        print(f"Название (pagetitle): {person['pagetitle']}")
        print(f"Алиас: {person['alias']}")
        print(f"URI: {person['uri']}")
        print(f"Опубликовано: {person['published']}")
        print(f"Template: {person['template']}")
        print()
        
        print("ОПИСАНИЕ (introtext):")
        print("-" * 80)
        print(person['introtext'][:500] if person['introtext'] else "(пусто)")
        print()
        
        print("КОНТЕНТ (content):")
        print("-" * 80)
        content = person['content'] if person['content'] else ""
        print(content[:1000] if content else "(пусто)")
        if len(content) > 1000:
            print(f"\n... (всего {len(content)} символов)")
        print()
        
        # Get TV values
        tv_values = get_template_vars(dump_file, person['id'])
        if tv_values:
            print("TEMPLATE VARIABLES (TV):")
            print("-" * 80)
            for tv_id, value in tv_values.items():
                print(f"TV_{tv_id}: {value[:100]}")
                if len(value) > 100:
                    print(f"  ... (всего {len(value)} символов)")
            print()
        
        # Save to JSON
        output = {
            'main': person,
            'tv_values': tv_values
        }
        
        with open('/app/migration/person_350_raw.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print("✅ Данные сохранены в /app/migration/person_350_raw.json")
    else:
        print("❌ Запись не найдена")
