#!/usr/bin/env python3
"""
Более умный парсер TV с правильным извлечением полей
"""
import re
import json

def extract_tv_definitions(dump_file):
    """Extract TV definitions with ID and name"""
    print("Парсинг TV definitions...\n")
    
    # Read the file
    with open(dump_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    tv_defs = {}
    in_tmplvars = False
    
    for i, line in enumerate(lines):
        if 'INSERT INTO `modx_site_tmplvars`' in line:
            in_tmplvars = True
            continue
        
        if in_tmplvars and line.strip().startswith('('):
            # Parse TV row
            # Format: (id, source, property_preprocess, type, name, caption, ...)
            match = re.match(r"^\((\d+),\s*\d+,\s*\d+,\s*'[^']*',\s*'([^']*)'", line)
            if match:
                tv_id = match.group(1)
                tv_name = match.group(2)
                tv_defs[tv_id] = tv_name
                print(f"  {tv_id}: {tv_name}")
        
        if in_tmplvars and line.strip().endswith(');'):
            in_tmplvars = False
    
    return tv_defs

def extract_tv_values(dump_file, content_id):
    """Extract TV values for specific content"""
    print(f"\nПарсинг TV values для content {content_id}...\n")
    
    with open(dump_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    tv_values = {}
    in_values = False
    
    for line in lines:
        if 'INSERT INTO `modx_site_tmplvar_contentvalues`' in line:
            in_values = True
            continue
        
        if in_values and line.strip().startswith('('):
            # Format: (id, tmplvarid, contentid, value)
            # Need to carefully extract contentid
            match = re.match(r"^\((\d+),\s*(\d+),\s*(\d+),\s*'(.*?)'(?:\)|,)", line)
            if match:
                row_contentid = match.group(3)
                if row_contentid == str(content_id):
                    tmplvarid = match.group(2)
                    value = match.group(4)
                    # Unescape
                    value = value.replace("\\'", "'").replace("\\\\", "\\")
                    tv_values[tmplvarid] = value
                    print(f"  TV {tmplvarid}: {value[:80]}...")
        
        if in_values and line.strip().endswith(');'):
            in_values = False
    
    return tv_values

if __name__ == "__main__":
    dump_file = "/app/modx_dump.sql"
    
    tv_defs = extract_tv_definitions(dump_file)
    tv_values = extract_tv_values(dump_file, 350)
    
    # Map values to names
    mapped = {}
    for tv_id, value in tv_values.items():
        name = tv_defs.get(tv_id, f"unknown_{tv_id}")
        mapped[name] = value
    
    print("\n" + "="*80)
    print("MAPPED TV:")
    print("="*80)
    for name in sorted(mapped.keys()):
        value = mapped[name]
        print(f"\n{name}:")
        if len(value) > 200:
            print(f"  {value[:200]}...")
        else:
            print(f"  {value}")
    
    with open('/app/migration/person_350_tv_mapped.json', 'w', encoding='utf-8') as f:
        json.dump(mapped, f, ensure_ascii=False, indent=2)
    
    print("\n✅ Saved to /app/migration/person_350_tv_mapped.json")
