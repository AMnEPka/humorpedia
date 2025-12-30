#!/usr/bin/env python3
"""Build list of KVN pages from humorbd.sql.

KVN pages are MODX resources with parent = 32.
We output a json list with fields needed for incremental import.
"""

import argparse
import json
import re
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Копируем функции парсинга, чтобы не зависеть от pymongo
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", default="C:\\Users\\rdp6126443.gmail.com\\humorpedia\\migration\\humorbd.sql")
    parser.add_argument("--out", default="C:\\Users\\rdp6126443.gmail.com\\humorpedia\\migration\\kvn\\kvn_list.json")
    parser.add_argument("--parent", type=int, default=32)
    args = parser.parse_args()

    parent_id = str(args.parent)

    in_sc = False
    buf = []
    results = []

    with open(args.sql, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not in_sc:
                if line.startswith("INSERT INTO `modx_site_content`"):
                    in_sc = True
                    buf = [line]
                continue

            buf.append(line)
            if not line.strip().endswith(";"):
                continue

            blob = "".join(buf)
            in_sc = False
            buf = []

            m = re.search(r"VALUES\s*(.*);\s*$", blob, flags=re.DOTALL)
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
                    rid = int(str(parts[0]).strip().strip("'\" "))
                except Exception:
                    continue
                
                # parent is at index 12
                parent_val = 0
                if parts[12] is not None:
                    parent_str = str(parts[12]).strip().strip("'\" ")
                    if parent_str and parent_str.upper() != 'NULL':
                        try:
                            parent_val = int(parent_str)
                        except:
                            parent_val = 0
                
                if parent_val != args.parent:
                    continue

                def s(idx: int) -> str:
                    v = parts[idx] if idx < len(parts) else ""
                    return _unescape_sql_string(v) if isinstance(v, str) else ""

                results.append(
                    {
                        "id": rid,
                        "title": s(3),
                        "slug": s(6),  # alias is at index 6
                        "status": "pending",
                    }
                )

    results.sort(key=lambda x: x["id"])

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(results)} KVN pages to {args.out}")


if __name__ == "__main__":
    main()

