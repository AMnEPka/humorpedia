#!/usr/bin/env python3
"""
Скрипт для восстановления логотипов команд из старых полей image/poster.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_db
from routes.content import _pick_team_logo, _is_placeholder_logo
from datetime import datetime, timezone


async def restore_logos(team_type=None, only_if_placeholder=True, dry_run=False):
    """
    Восстанавливает логотипы команд из legacy полей image/poster.
    
    Args:
        team_type: Фильтр по типу команды (например 'kvn'). Если None - все команды.
        only_if_placeholder: Восстанавливать только если logo отсутствует или плейсхолдер.
        dry_run: Если True, только показывает что будет изменено, не сохраняет.
    """
    db = await get_db()
    
    query = {}
    if team_type:
        query["team_type"] = team_type
    
    cursor = db.teams.find(query)
    matched = 0
    modified = 0
    restored_from_image = 0
    restored_from_poster = 0
    skipped_no_source = 0
    
    async for team in cursor:
        current_logo = team.get("logo")
        
        # Check if we should restore this team's logo
        should_restore = False
        if only_if_placeholder:
            # Only restore if logo is missing or is placeholder
            if not current_logo or _is_placeholder_logo(current_logo):
                should_restore = True
        else:
            # Restore all teams (even if they have a logo, try to improve from legacy fields)
            should_restore = True
        
        if not should_restore:
            continue
        
        matched += 1
        
        # Try to restore from legacy fields
        picked_logo = _pick_team_logo(team)
        
        # Check if we actually found a source (not just placeholder)
        if _is_placeholder_logo(picked_logo):
            skipped_no_source += 1
            continue
        
        # Determine source for reporting
        if team.get("image") and not _is_placeholder_logo(team.get("image")):
            restored_from_image += 1
        elif team.get("poster") and not _is_placeholder_logo(team.get("poster")):
            restored_from_poster += 1
        
        if dry_run:
            print(f"  [DRY RUN] Would restore logo for team: {team.get('name') or team.get('title', 'Unknown')}")
            continue
        
        # Update logo
        changes = {
            "logo": picked_logo,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        res = await db.teams.update_one({"_id": team["_id"]}, {"$set": changes})
        if res.modified_count:
            modified += 1
            print(f"  ✅ Restored logo for: {team.get('name') or team.get('title', 'Unknown')}")
    
    print(f"\n📊 Результаты:")
    print(f"   Найдено команд для проверки: {matched}")
    print(f"   Обновлено: {modified}")
    print(f"   Восстановлено из поля 'image': {restored_from_image}")
    print(f"   Восстановлено из поля 'poster': {restored_from_poster}")
    print(f"   Пропущено (нет источника): {skipped_no_source}")
    print(f"   Режим: {'DRY RUN (тест)' if dry_run else 'РЕАЛЬНОЕ ОБНОВЛЕНИЕ'}")
    
    return {
        "matched": matched,
        "modified": modified,
        "restored_from_image": restored_from_image,
        "restored_from_poster": restored_from_poster,
        "skipped_no_source": skipped_no_source,
        "dry_run": dry_run,
        "team_type": team_type
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Восстановление логотипов команд")
    parser.add_argument("--team-type", type=str, default=None, help="Фильтр по типу команды (например 'kvn')")
    parser.add_argument("--all", action="store_true", help="Восстанавливать все команды, даже если у них уже есть логотип")
    parser.add_argument("--dry-run", action="store_true", help="Только показать что будет изменено, не сохранять")
    
    args = parser.parse_args()
    
    only_if_placeholder = not args.all
    
    print("🔄 Запуск восстановления логотипов команд...")
    if args.team_type:
        print(f"   Фильтр по типу: {args.team_type}")
    if only_if_placeholder:
        print("   Режим: только команды без логотипа или с плейсхолдером")
    else:
        print("   Режим: все команды")
    if args.dry_run:
        print("   ⚠️  DRY RUN - изменения не будут сохранены")
    print()
    
    result = asyncio.run(restore_logos(
        team_type=args.team_type,
        only_if_placeholder=only_if_placeholder,
        dry_run=args.dry_run
    ))
    
    if not args.dry_run and result["modified"] > 0:
        print(f"\n✅ Восстановлено {result['modified']} логотипов!")
