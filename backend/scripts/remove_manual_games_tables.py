#!/usr/bin/env python3
"""
Remove manually created "Список игр команды" modules from all KVN team pages.
The automatic module will be created/updated on next page load via self-healing.
"""
import asyncio
import argparse
import os
import sys
from datetime import datetime, timezone

# Add parent directory to path to import modules from backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.database import get_db

async def remove_manual_games_tables(dry_run=True, team_type="kvn", remove_all=False):
    """
    Remove "Список игр команды" modules from all KVN team pages.
    If remove_all=True, removes ALL such modules (they will be auto-regenerated).
    If remove_all=False, only removes manually created ones (with tables but not auto-generated structure).
    """
    mode = "всех модулей" if remove_all else "ручных таблиц"
    print(f"🔄 Запуск удаления {mode} 'Список игр команды'...")
    print(f"   Тип команды: {team_type}")
    if dry_run:
        print("   ⚠️  DRY RUN - изменения не будут сохранены")

    db = await get_db()

    query = {"team_type": team_type}
    cursor = db.teams.find(query)
    
    checked_teams = 0
    updated_teams = 0
    removed_modules = 0
    
    # Keywords to identify the games table
    table_headers = ["Год", "Лига", "Стадия", "Результат"]
    
    async for team in cursor:
        checked_teams += 1
        modules = team.get("modules") or []
        if not modules:
            continue
        
        updated_modules = []
        removed_count = 0
        
        for module in modules:
            if not isinstance(module, dict):
                updated_modules.append(module)
                continue
            
            m_type = module.get("type")
            data = module.get("data") or {}
            title = (data.get("title") or "").strip()
            content = (data.get("content") or "").strip()
            
            # Check if this is "Список игр команды" module
            # Match by title OR by content structure (table with headers)
            is_games_module = False
            if m_type == "text_block":
                # Check by title (exact or partial match)
                if title and ("Список игр команды" in title or title == "Список игр команды"):
                    is_games_module = True
                # Check by content structure - table with required headers
                elif content:
                    content_lower = content.lower()
                    has_table = "<table" in content_lower or "<th" in content_lower
                    if has_table:
                        # Check if all required headers are present
                        has_all_headers = all(header in content for header in table_headers)
                        if has_all_headers:
                            is_games_module = True
            
            if is_games_module:
                if remove_all:
                    # Remove ALL "Список игр команды" modules - they will be auto-regenerated
                    removed_count += 1
                    if dry_run:
                        print(f"  [DRY RUN] Would remove module from: {team.get('name') or team.get('title')} (slug: {team.get('slug')})")
                    continue  # Skip this module
                else:
                    # Original logic: only remove manually created ones
                    # Check if it contains a table with our headers
                    has_table = False
                    has_all_headers = True
                    
                    # Check if content contains table tags
                    if "<table" in content.lower() or "<th" in content.lower():
                        has_table = True
                        # Check if all headers are present
                        for header in table_headers:
                            if header not in content:
                                has_all_headers = False
                                break
                    
                    # If it's a table with our headers, it's likely a manual one (we'll regenerate automatically)
                    # But we need to be careful: our auto-generated table also has these headers
                    # Distinguish by checking for specific patterns in our auto-generated table
                    is_auto_generated = data.get("auto_generated") == True or data.get("source") == "vl-kvn"
                    
                    if has_table and has_all_headers and not is_auto_generated:
                        # This is a manual table - remove it
                        removed_count += 1
                        if dry_run:
                            print(f"  [DRY RUN] Would remove manual table from: {team.get('name') or team.get('title')} (slug: {team.get('slug')})")
                        continue  # Skip this module
                    elif is_auto_generated:
                        # Keep our auto-generated table
                        updated_modules.append(module)
                    else:
                        # Keep module if it doesn't have table or doesn't match our criteria
                        updated_modules.append(module)
            else:
                # Keep all other modules
                updated_modules.append(module)
        
        if removed_count > 0:
            removed_modules += removed_count
            if not dry_run:
                # Normalize orders
                for i, m in enumerate(updated_modules):
                    if isinstance(m, dict):
                        m["order"] = i
                
                changes = {
                    "modules": updated_modules,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                res = await db.teams.update_one({"_id": team["_id"]}, {"$set": changes})
                if res.modified_count:
                    updated_teams += 1
                    print(f"  ✅ Removed {removed_count} manual table(s) from: {team.get('name') or team.get('title')} (slug: {team.get('slug')})")
            else:
                updated_teams += 1  # Count for dry run report
    
    print("\n📊 Результаты:")
    print(f"   Проверено команд: {checked_teams}")
    print(f"   Обновлено команд: {updated_teams}")
    print(f"   Всего удалено модулей: {removed_modules}")
    print(f"   Режим: {'DRY RUN (тест)' if dry_run else 'РЕАЛЬНОЕ УДАЛЕНИЕ'}")

    if not dry_run:
        print(f"\n✅ Удалено {removed_modules} ручных таблиц из {updated_teams} команд!")
        print("   Автоматические таблицы будут созданы при следующем открытии страниц команд.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove 'Список игр команды' modules from KVN team pages.")
    parser.add_argument("--dry-run", action="store_true", help="Only report changes, do not save to DB.")
    parser.add_argument("--team-type", type=str, default="kvn", help="Filter by team_type (e.g. 'kvn').")
    parser.add_argument("--all", action="store_true", help="Remove ALL 'Список игр команды' modules (they will be auto-regenerated).")
    
    args = parser.parse_args()

    asyncio.run(remove_manual_games_tables(dry_run=args.dry_run, team_type=args.team_type, remove_all=args.all))
