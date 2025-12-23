#!/usr/bin/env python3
"""
Анализ MySQL дампа для понимания структуры данных
"""
import re
import sys

def parse_insert_line(line):
    """Parse single INSERT statement line"""
    # Find VALUES part
    match = re.search(r'VALUES\s*\((.*)\);?$', line, re.DOTALL)
    if not match:
        return []
    
    values_str = match.group(1)
    
    # Split by ),( to get individual rows
    rows = re.split(r'\),\s*\(', values_str)
    
    return rows

def analyze_templates(dump_file):
    """Analyze templates in dump"""
    print("=== АНАЛИЗ ШАБЛОНОВ ===\n")
    
    with open(dump_file, 'r', encoding='utf-8') as f:
        in_templates = False
        templates = []
        
        for line in f:
            if 'INSERT INTO `modx_site_templates`' in line:
                in_templates = True
                # Get the rest of the INSERT
                insert_data = line
                continue
            
            if in_templates:
                insert_data += line
                if line.strip().endswith(';'):
                    # Parse templates
                    rows = parse_insert_line(insert_data)
                    for i, row in enumerate(rows[:5]):  # First 5 templates
                        # Extract basic info (id, templatename)
                        parts = row.split(',', 4)
                        if len(parts) >= 4:
                            template_id = parts[0].strip()
                            template_name = parts[3].strip().strip("'")
                            print(f"Template {template_id}: {template_name}")
                    break
    
    print()

def analyze_content_by_template(dump_file, template_id=None):
    """Analyze content grouped by template"""
    print(f"=== АНАЛИЗ КОНТЕНТА (template={template_id or 'all'}) ===\n")
    
    with open(dump_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all INSERT INTO modx_site_content
    pattern = r"INSERT INTO `modx_site_content`.*?VALUES\s*\((.*?)\);?"
    
    # Find the INSERT statements
    matches = re.finditer(r"INSERT INTO `modx_site_content`[^;]*;", content, re.DOTALL)
    
    items_by_template = {}
    total_count = 0
    
    for match in matches:
        insert_stmt = match.group(0)
        
        # Extract rows
        rows_match = re.search(r'VALUES\s*\((.*)\);?$', insert_stmt, re.DOTALL)
        if not rows_match:
            continue
        
        values_str = rows_match.group(1)
        
        # Simple split by ),( - may not be perfect but good enough for analysis
        rows = re.split(r'\),\s*\(', values_str)
        
        for row in rows:
            total_count += 1
            
            # Parse row - format: id, type, contentType, pagetitle, longtitle, description, alias...
            # Field 17 (0-indexed) is template
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
            parts.append(current.strip().strip("'"))
            
            if len(parts) > 17:
                item_id = parts[0]
                pagetitle = parts[3]
                alias = parts[6]
                template = parts[17]
                
                if template not in items_by_template:
                    items_by_template[template] = []
                
                items_by_template[template].append({
                    'id': item_id,
                    'title': pagetitle,
                    'alias': alias
                })
    
    print(f"Всего записей в site_content: {total_count}\n")
    print("Группировка по template_id:")
    
    for tmpl_id in sorted(items_by_template.keys(), key=lambda x: len(items_by_template[x]), reverse=True):
        items = items_by_template[tmpl_id]
        print(f"\nTemplate {tmpl_id}: {len(items)} записей")
        
        # Show first 3 examples
        for item in items[:3]:
            print(f"  - [{item['id']}] {item['title'][:50]} (alias: {item['alias'][:30]})")
        
        if len(items) > 3:
            print(f"  ... и ещё {len(items) - 3}")

if __name__ == "__main__":
    dump_file = "/app/modx_dump.sql"
    
    print("АНАЛИЗ ДАМПА MySQL\n")
    print("=" * 60)
    print()
    
    analyze_templates(dump_file)
    analyze_content_by_template(dump_file)
