#!/usr/bin/env python3
"""
Скрипт для удаления дубликатов модулей у команд КВН.
Удаляет модули с одинаковой сигнатурой (type + title), оставляя только первый.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_db
from datetime import datetime, timezone


def _module_signature(m: dict) -> tuple:
    """
    Build a stable signature to match modules.
    For text_block with same title, include content hash to distinguish different content blocks.
    """
    m_type = (m.get("type") or "").strip()
    data = m.get("data") or {}

    if m_type == "text_block":
        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()
        # For text_block: if title is same but content is different, they're NOT duplicates
        # Use content hash (first 50 chars) as part of signature to distinguish them
        content_hash = content[:50] if content else ""
        return (m_type, title, content_hash)

    if m_type == "timeline":
        title = (data.get("title") or m.get("title") or "").strip()
        return (m_type, title)

    title = (m.get("title") or data.get("title") or "").strip()
    return (m_type, title)


def remove_duplicate_modules(modules: list) -> list:
    """
    Remove duplicate modules with same signature, keeping only first occurrence.
    For text_block: modules with same title but different content are NOT considered duplicates.
    """
    if not modules:
        return []
    
    seen_signatures = {}
    result = []
    
    for m in modules:
        if not isinstance(m, dict):
            continue
        
        sig = _module_signature(m)
        
        # If we've seen this exact signature before (including content for text_block), skip it
        if sig in seen_signatures:
            continue
        
        # First time seeing this signature - keep it
        seen_signatures[sig] = True
        result.append(m)
    
    return result


async def fix_duplicates(team_type="kvn", dry_run=False):
    """
    Удаляет дубликаты модулей у команд.
    
    Args:
        team_type: Тип команды (по умолчанию 'kvn')
        dry_run: Если True, только показывает что будет изменено, не сохраняет.
    """
    db = await get_db()
    
    query = {"team_type": team_type}
    cursor = db.teams.find(query)
    
    matched = 0
    modified = 0
    total_duplicates_removed = 0
    
    async for team in cursor:
        existing_modules = team.get("modules") or []
        if not existing_modules:
            continue
        
        matched += 1
        original_count = len(existing_modules)
        cleaned_modules = remove_duplicate_modules(existing_modules)
        new_count = len(cleaned_modules)
        duplicates_removed = original_count - new_count
        
        if duplicates_removed == 0:
            continue
        
        total_duplicates_removed += duplicates_removed
        
        team_name = team.get("name") or team.get("title", "Unknown")
        print(f"  {'[DRY RUN]' if dry_run else ''} {team_name}: удалено {duplicates_removed} дубликатов ({original_count} → {new_count})")
        
        if dry_run:
            continue
        
        # Update modules
        changes = {
            "modules": cleaned_modules,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        res = await db.teams.update_one({"_id": team["_id"]}, {"$set": changes})
        if res.modified_count:
            modified += 1
    
    print(f"\n📊 Результаты:")
    print(f"   Проверено команд: {matched}")
    print(f"   Обновлено команд: {modified}")
    print(f"   Всего удалено дубликатов: {total_duplicates_removed}")
    print(f"   Режим: {'DRY RUN (тест)' if dry_run else 'РЕАЛЬНОЕ ОБНОВЛЕНИЕ'}")
    
    return {
        "matched": matched,
        "modified": modified,
        "total_duplicates_removed": total_duplicates_removed,
        "dry_run": dry_run
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Удаление дубликатов модулей у команд")
    parser.add_argument("--team-type", type=str, default="kvn", help="Тип команды (по умолчанию 'kvn')")
    parser.add_argument("--dry-run", action="store_true", help="Только показать что будет изменено, не сохранять")
    
    args = parser.parse_args()
    
    print("🔄 Запуск удаления дубликатов модулей...")
    print(f"   Тип команды: {args.team_type}")
    if args.dry_run:
        print("   ⚠️  DRY RUN - изменения не будут сохранены")
    print()
    
    result = asyncio.run(fix_duplicates(
        team_type=args.team_type,
        dry_run=args.dry_run
    ))
    
    if not args.dry_run and result["modified"] > 0:
        print(f"\n✅ Исправлено {result['modified']} команд, удалено {result['total_duplicates_removed']} дубликатов!")
