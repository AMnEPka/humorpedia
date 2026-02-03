"""
Скрипт для автоматического обновления старых URL на новый формат
и поиска/исправления битых ссылок
"""
import asyncio
import re
from typing import Dict, List, Tuple
from urllib.parse import urlparse
import sys
import os

# Добавляем путь к backend для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_db


class URLMigrator:
    """Миграция старых URL на новый формат и исправление битых ссылок"""
    
    # Маппинг старых паттернов на новые
    URL_PATTERNS = [
        # Старые форматы -> новые форматы
        (r'/team/([^/"\'>\s]+)', r'/kvn/teams/\1'),
        (r'/person/([^/"\'>\s]+)', r'/people/\1'),
        (r'/show/([^/"\'>\s]+)', r'/shows/\1'),
        (r'/article/([^/"\'>\s]+)', r'/articles/\1'),
        (r'/news/([^/"\'>\s]+)', r'/news/\1'),
        # Добавьте свои паттерны здесь
    ]
    
    @staticmethod
    async def find_broken_links(dry_run: bool = True) -> Dict[str, List[Dict]]:
        """
        Находит все битые ссылки (ссылки на несуществующие страницы)
        
        Returns:
            Dict с ключами: 'broken_internal', 'broken_external', 'fixed'
        """
        db = await get_db()
        
        # Получаем все существующие slug'и
        existing_slugs = {
            'people': set(),
            'teams': set(),
            'shows': set(),
            'kvn': set(),
            'articles': set(),
            'news': set(),
        }
        
        # Собираем все slug'и
        async for doc in db.people.find({}, {"slug": 1}):
            if doc.get('slug'):
                existing_slugs['people'].add(doc['slug'])
        
        async for doc in db.teams.find({}, {"slug": 1}):
            if doc.get('slug'):
                existing_slugs['teams'].add(doc['slug'])
        
        async for doc in db.shows.find({}, {"slug": 1}):
            if doc.get('slug'):
                existing_slugs['shows'].add(doc['slug'])
        
        async for doc in db.kvn.find({}, {"slug": 1, "full_path": 1}):
            if doc.get('slug'):
                existing_slugs['kvn'].add(doc['slug'])
            if doc.get('full_path'):
                existing_slugs['kvn'].add(doc['full_path'].lstrip('/'))
        
        async for doc in db.articles.find({}, {"slug": 1}):
            if doc.get('slug'):
                existing_slugs['articles'].add(doc['slug'])
        
        async for doc in db.news.find({}, {"slug": 1}):
            if doc.get('slug'):
                existing_slugs['news'].add(doc['slug'])
        
        print(f"Найдено существующих slug'ов:")
        for key, slugs in existing_slugs.items():
            print(f"  {key}: {len(slugs)}")
        
        # Ищем битые ссылки
        broken_internal = []  # Внутренние битые ссылки
        
        collections = [
            ('people', db.people),
            ('teams', db.teams),
            ('shows', db.shows),
            ('kvn', db.kvn),
            ('articles', db.articles),
            ('news', db.news),
        ]
        
        url_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
        
        for collection_name, collection in collections:
            async for doc in collection.find({"modules": {"$exists": True}}):
                doc_id = str(doc.get('_id'))
                doc_title = doc.get('title') or doc.get('name') or 'N/A'
                
                for module in doc.get('modules', []):
                    if module.get('type') == 'text_block':
                        content = module.get('data', {}).get('content', '')
                        if not content:
                            continue
                        
                        # Находим все ссылки
                        for match in url_pattern.finditer(content):
                            url = match.group(1)
                            
                            # Пропускаем внешние ссылки
                            if url.startswith('http://') or url.startswith('https://') or url.startswith('mailto:'):
                                continue
                            
                            # Пропускаем якоря
                            if url.startswith('#'):
                                continue
                            
                            # Парсим URL
                            parsed = urlparse(url)
                            path = parsed.path
                            
                            # Определяем тип контента по пути
                            if path.startswith('/people/'):
                                slug = path.replace('/people/', '').strip('/')
                                if slug not in existing_slugs['people']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'url': url,
                                        'slug': slug,
                                        'type': 'person',
                                        'expected_path': '/people/'
                                    })
                            
                            elif path.startswith('/kvn/teams/') or path.startswith('/teams/'):
                                slug = path.replace('/kvn/teams/', '').replace('/teams/', '').strip('/')
                                if slug not in existing_slugs['teams']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'url': url,
                                        'slug': slug,
                                        'type': 'team',
                                        'expected_path': '/kvn/teams/'
                                    })
                            
                            elif path.startswith('/shows/'):
                                slug = path.replace('/shows/', '').strip('/')
                                if slug not in existing_slugs['shows']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'url': url,
                                        'slug': slug,
                                        'type': 'show',
                                        'expected_path': '/shows/'
                                    })
                            
                            elif path.startswith('/kvn/'):
                                # Для KVN может быть полный путь
                                path_part = path.replace('/kvn/', '').strip('/')
                                if path_part not in existing_slugs['kvn']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'url': url,
                                        'slug': path_part,
                                        'type': 'kvn',
                                        'expected_path': '/kvn/'
                                    })
        
        return {
            'broken_internal': broken_internal,
            'broken_external': [],
            'existing_slugs': existing_slugs
        }
    
    @staticmethod
    async def migrate_urls(dry_run: bool = True) -> Dict[str, int]:
        """
        Мигрирует старые URL на новый формат во всех документах
        
        Returns:
            Dict с количеством обновленных документов
        """
        db = await get_db()
        
        collections = [
            db.people, db.teams, db.shows, db.kvn,
            db.articles, db.news, db.quizzes, db.wiki
        ]
        
        total_updated = 0
        total_replacements = 0
        
        for collection in collections:
            collection_name = collection.name
            print(f"\nОбработка коллекции: {collection_name}")
            
            async for doc in collection.find({"modules": {"$exists": True}}):
                updated = False
                new_modules = []
                replacements_count = 0
                
                for module in doc.get('modules', []):
                    if module.get('type') == 'text_block':
                        content = module.get('data', {}).get('content', '')
                        new_content = content
                        
                        # Применяем все паттерны замены
                        for old_pattern, new_pattern in URLMigrator.URL_PATTERNS:
                            matches = re.findall(old_pattern, new_content)
                            if matches:
                                new_content = re.sub(old_pattern, new_pattern, new_content)
                                replacements_count += len(matches)
                        
                        if new_content != content:
                            module['data']['content'] = new_content
                            updated = True
                    
                    new_modules.append(module)
                
                if updated:
                    total_updated += 1
                    total_replacements += replacements_count
                    
                    if not dry_run:
                        await collection.update_one(
                            {"_id": doc["_id"]},
                            {"$set": {"modules": new_modules}}
                        )
                    else:
                        print(f"  [DRY-RUN] Обновлен: {doc.get('title') or doc.get('name', 'N/A')} "
                              f"({replacements_count} замен)")
        
        return {
            'total_updated': total_updated,
            'total_replacements': total_replacements
        }
    
    @staticmethod
    async def fix_broken_links(
        broken_links: List[Dict],
        dry_run: bool = True,
        auto_fix: bool = False
    ) -> Dict[str, int]:
        """
        Исправляет битые ссылки
        
        Args:
            broken_links: Список битых ссылок из find_broken_links
            dry_run: Если True, только показывает что будет исправлено
            auto_fix: Если True, пытается автоматически найти правильный slug
        """
        db = await get_db()
        
        if not broken_links:
            print("Битые ссылки не найдены")
            return {'fixed': 0, 'removed': 0, 'not_found': 0}
        
        fixed = 0
        removed = 0
        not_found = 0
        
        # Группируем по документам
        by_doc = {}
        for link in broken_links:
            key = (link['collection'], link['doc_id'])
            if key not in by_doc:
                by_doc[key] = []
            by_doc[key].append(link)
        
        for (collection_name, doc_id), links in by_doc.items():
            collection = getattr(db, collection_name)
            doc = await collection.find_one({"_id": doc_id})
            
            if not doc:
                continue
            
            updated = False
            new_modules = []
            
            for module in doc.get('modules', []):
                if module.get('type') == 'text_block':
                    content = module.get('data', {}).get('content', '')
                    new_content = content
                    
                    for link in links:
                        old_url = link['url']
                        slug = link['slug']
                        link_type = link['type']
                        
                        if auto_fix:
                            # Пытаемся найти правильный slug
                            target_collection_map = {
                                'person': db.people,
                                'team': db.teams,
                                'show': db.shows,
                                'kvn': db.kvn,
                            }
                            
                            target_collection = target_collection_map.get(link_type)
                            if target_collection:
                                # Ищем по частичному совпадению slug
                                similar = await target_collection.find_one({
                                    "slug": {"$regex": slug, "$options": "i"}
                                })
                                
                                if similar:
                                    correct_slug = similar.get('slug')
                                    correct_url = link['expected_path'] + correct_slug
                                    new_content = new_content.replace(old_url, correct_url)
                                    fixed += 1
                                    print(f"  [FIX] {old_url} -> {correct_url}")
                                    updated = True
                                    continue
                        
                        # Если не удалось исправить, удаляем ссылку (оставляем только текст)
                        # Заменяем <a href="...">текст</a> на просто "текст"
                        pattern = f'<a[^>]*href=["\']{re.escape(old_url)}["\'][^>]*>(.*?)</a>'
                        new_content = re.sub(pattern, r'\1', new_content, flags=re.IGNORECASE)
                        removed += 1
                        print(f"  [REMOVE] Удалена битая ссылка: {old_url}")
                        updated = True
                    
                    module['data']['content'] = new_content
                
                new_modules.append(module)
            
            if updated:
                if not dry_run:
                    await collection.update_one(
                        {"_id": doc_id},
                        {"$set": {"modules": new_modules}}
                    )
        
        return {
            'fixed': fixed,
            'removed': removed,
            'not_found': not_found
        }


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Миграция URL и исправление битых ссылок')
    parser.add_argument('--migrate', action='store_true', help='Мигрировать старые URL')
    parser.add_argument('--find-broken', action='store_true', help='Найти битые ссылки')
    parser.add_argument('--fix-broken', action='store_true', help='Исправить битые ссылки')
    parser.add_argument('--auto-fix', action='store_true', help='Автоматически исправлять битые ссылки')
    parser.add_argument('--apply', action='store_true', help='Применить изменения (без этого - dry-run)')
    
    args = parser.parse_args()
    
    if args.migrate:
        print("=" * 80)
        print("МИГРАЦИЯ СТАРЫХ URL")
        print("=" * 80)
        result = await URLMigrator.migrate_urls(dry_run=not args.apply)
        print(f"\nРезультат:")
        print(f"  Обновлено документов: {result['total_updated']}")
        print(f"  Всего замен: {result['total_replacements']}")
        if not args.apply:
            print("\n[DRY-RUN] Для применения запустите с --apply")
    
    if args.find_broken:
        print("=" * 80)
        print("ПОИСК БИТЫХ ССЫЛОК")
        print("=" * 80)
        result = await URLMigrator.find_broken_links()
        print(f"\nНайдено битых внутренних ссылок: {len(result['broken_internal'])}")
        
        if result['broken_internal']:
            print("\nПримеры битых ссылок:")
            for link in result['broken_internal'][:10]:
                print(f"  {link['doc_title']}: {link['url']} (slug: {link['slug']})")
    
    if args.fix_broken:
        print("=" * 80)
        print("ИСПРАВЛЕНИЕ БИТЫХ ССЫЛОК")
        print("=" * 80)
        broken = await URLMigrator.find_broken_links()
        result = await URLMigrator.fix_broken_links(
            broken['broken_internal'],
            dry_run=not args.apply,
            auto_fix=args.auto_fix
        )
        print(f"\nРезультат:")
        print(f"  Исправлено: {result['fixed']}")
        print(f"  Удалено: {result['removed']}")
        if not args.apply:
            print("\n[DRY-RUN] Для применения запустите с --apply")


if __name__ == "__main__":
    asyncio.run(main())
