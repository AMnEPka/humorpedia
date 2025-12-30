#!/usr/bin/env python3
"""Анализ структуры дочерних страниц к ресурсу с id=32 (КВН).

Этот скрипт анализирует всю иерархию дочерних страниц до 4 уровня вложенности.
"""

import argparse
import json
import re
import sys
import os
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Копируем необходимые функции, чтобы не зависеть от pymongo
def _unescape_sql_string(s: str) -> str:
    """Распаковывает SQL строку."""
    if not s or not isinstance(s, str):
        return ""
    s = s.strip()
    if s.startswith("'") and s.endswith("'"):
        s = s[1:-1]
    elif s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    s = s.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")
    s = s.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")
    return s


def _split_rows(values_str: str) -> list[str]:
    """Разбивает VALUES на отдельные строки."""
    rows = []
    current = []
    depth = 0
    in_string = False
    escape_next = False
    string_char = None
    
    for char in values_str:
        if escape_next:
            current.append(char)
            escape_next = False
            continue
        
        if char == '\\' and in_string:
            escape_next = True
            current.append(char)
            continue
        
        if char in ("'", '"') and not escape_next:
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
            current.append(char)
            continue
        
        if not in_string:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0 and current:
                    rows.append(''.join(current).strip())
                    current = []
                    continue
            elif char == ',' and depth == 1:
                if current:
                    rows.append(''.join(current).strip())
                    current = []
                continue
        
        current.append(char)
    
    if current:
        rows.append(''.join(current).strip())
    
    return rows


def _split_fields(row: str) -> list:
    """Разбивает строку на поля."""
    if not row or not row.strip():
        return []
    
    # Убираем скобки
    row = row.strip()
    if row.startswith('(') and row.endswith(')'):
        row = row[1:-1]
    
    fields = []
    current = []
    depth = 0
    in_string = False
    escape_next = False
    string_char = None
    
    for char in row:
        if escape_next:
            current.append(char)
            escape_next = False
            continue
        
        if char == '\\' and in_string:
            escape_next = True
            current.append(char)
            continue
        
        if char in ("'", '"') and not escape_next:
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
            current.append(char)
            continue
        
        if not in_string:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == ',' and depth == 0:
                fields.append(''.join(current).strip())
                current = []
                continue
        
        current.append(char)
    
    if current:
        fields.append(''.join(current).strip())
    
    return fields

SQL_FILE = "C:\\Users\\rdp6126443.gmail.com\\humorpedia\\migration\\humorbd.sql"


def get_resource_by_id(resource_id: int) -> dict:
    """Получает данные ресурса по ID из SQL."""
    in_sc = False
    buf = []
    
    with open(SQL_FILE, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if not in_sc:
                if line.startswith('INSERT INTO `modx_site_content`'):
                    in_sc = True
                    buf = [line]
                continue
            
            buf.append(line)
            if not line.strip().endswith(';'):
                continue
            
            blob = ''.join(buf)
            in_sc = False
            buf = []
            
            m = re.search(r'VALUES\s*(.*);\s*$', blob, flags=re.DOTALL)
            if not m:
                continue
            
            rows = _split_rows(m.group(1))
            for r in rows:
                parts = _split_fields(r)
                if not parts or parts[0] is None:
                    continue
                
                try:
                    # ID находится в первой позиции
                    rid_str = str(parts[0]).strip()
                    # Убираем кавычки и пробелы
                    rid_str = rid_str.strip("'\" ")
                    rid = int(rid_str)
                    
                    if rid == resource_id:
                        # pagetitle - индекс 3, alias - индекс 6, parent - индекс 12
                        title = _unescape_sql_string(parts[3]) if len(parts) > 3 and parts[3] else ''
                        slug = _unescape_sql_string(parts[6]) if len(parts) > 6 and parts[6] else ''
                        
                        parent = 0
                        if len(parts) > 12 and parts[12]:
                            parent_str = str(parts[12]).strip().strip("'\" ")
                            if parent_str and parent_str.upper() != 'NULL':
                                try:
                                    parent = int(parent_str)
                                except:
                                    parent = 0
                        
                        return {
                            'id': rid,
                            'title': title,
                            'slug': slug,
                            'parent': parent
                        }
                except Exception as ex:
                    continue
    
    return None


def get_children_recursive(parent_id: int, max_level: int = 4, current_level: int = 0) -> list[dict]:
    """Рекурсивно получает все дочерние страницы до указанного уровня."""
    if current_level >= max_level:
        return []
    
    children = []
    in_sc = False
    buf = []
    
    with open(SQL_FILE, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if not in_sc:
                if line.startswith('INSERT INTO `modx_site_content`'):
                    in_sc = True
                    buf = [line]
                continue
            
            buf.append(line)
            if not line.strip().endswith(';'):
                continue
            
            blob = ''.join(buf)
            in_sc = False
            buf = []
            
            m = re.search(r'VALUES\s*(.*);\s*$', blob, flags=re.DOTALL)
            if not m:
                continue
            
            rows = _split_rows(m.group(1))
            for r in rows:
                parts = _split_fields(r)
                if not parts or parts[0] is None:
                    continue
                
                if len(parts) <= 12:
                    continue
                
                try:
                    rid_str = str(parts[0]).strip().strip("'\" ")
                    rid = int(rid_str)
                    
                    parent = 0
                    if len(parts) > 12 and parts[12]:
                        parent_str = str(parts[12]).strip().strip("'\" ")
                        if parent_str and parent_str.upper() != 'NULL':
                            try:
                                parent = int(parent_str)
                            except:
                                parent = 0
                    
                    if parent == parent_id:
                        child = {
                            'id': rid,
                            'title': _unescape_sql_string(parts[3]) if len(parts) > 3 and parts[3] else '',
                            'slug': _unescape_sql_string(parts[6]) if len(parts) > 6 and parts[6] else '',
                            'parent': parent,
                            'level': current_level + 1
                        }
                        
                        # Рекурсивно получаем дочерние
                        child['children'] = get_children_recursive(rid, max_level, current_level + 1)
                        children.append(child)
                except Exception as ex:
                    continue
    
    return children


def print_tree(items: list[dict], indent: int = 0):
    """Выводит дерево в консоль."""
    for item in items:
        prefix = '  ' * indent + ('└─ ' if indent > 0 else '')
        print(f"{prefix}ID: {item['id']}, Title: {item['title']}, Slug: {item['slug']}, Level: {item['level']}")
        if item.get('children'):
            print_tree(item['children'], indent + 1)


def main():
    parser = argparse.ArgumentParser(description="Анализ структуры КВН (id=32)")
    parser.add_argument("--root-id", type=int, default=32, help="ID корневого ресурса")
    parser.add_argument("--max-level", type=int, default=4, help="Максимальный уровень вложенности")
    parser.add_argument("--output", help="Путь к JSON файлу для сохранения структуры")
    args = parser.parse_args()
    
    print(f"Анализ структуры ресурса с ID={args.root_id}")
    print(f"Максимальный уровень вложенности: {args.max_level}")
    print("=" * 60)
    
    # Получаем корневой ресурс
    root = get_resource_by_id(args.root_id)
    if not root:
        print(f"❌ Ресурс с ID {args.root_id} не найден")
        return
    
    print(f"\nКорневой ресурс:")
    print(f"  ID: {root['id']}")
    print(f"  Title: {root['title']}")
    print(f"  Slug: {root['slug']}")
    print(f"  Parent: {root['parent']}")
    print()
    
    # Получаем дочерние страницы
    children = get_children_recursive(args.root_id, args.max_level, 0)
    
    print(f"Найдено дочерних страниц: {len(children)}")
    print()
    print("Структура дерева:")
    print("=" * 60)
    print(f"ID: {root['id']}, Title: {root['title']}, Slug: {root['slug']}, Level: 0")
    print_tree(children)
    
    # Подсчитываем статистику
    def count_items(items, level=0):
        count = len(items)
        for item in items:
            if item.get('children'):
                count += count_items(item['children'], level + 1)
        return count
    
    total_count = count_items(children)
    print()
    print("=" * 60)
    print(f"Статистика:")
    print(f"  Всего дочерних страниц (включая вложенные): {total_count}")
    print(f"  Прямых дочерних: {len(children)}")
    
    # Группируем по уровням
    level_counts = defaultdict(int)
    def count_by_level(items, level=1):
        for item in items:
            level_counts[level] += 1
            if item.get('children'):
                count_by_level(item['children'], level + 1)
    
    count_by_level(children)
    print(f"  Распределение по уровням:")
    for level in sorted(level_counts.keys()):
        print(f"    Уровень {level}: {level_counts[level]} страниц")
    
    # Сохраняем в JSON если указан путь
    if args.output:
        structure = {
            'root': root,
            'children': children,
            'statistics': {
                'total_children': total_count,
                'direct_children': len(children),
                'by_level': dict(level_counts)
            }
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(structure, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Структура сохранена в {args.output}")


if __name__ == "__main__":
    main()

