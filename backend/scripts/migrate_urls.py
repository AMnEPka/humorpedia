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
        Поддерживает как новые, так и старые форматы URL
        
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
        
        # Улучшенный паттерн для поиска ссылок (поддерживает разные форматы)
        url_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
        
        total_links_checked = 0
        total_docs_checked = 0
        total_modules_checked = 0
        
        # Также проверяем description и другие HTML поля
        html_fields_to_check = ['description']
        
        for collection_name, collection in collections:
            # Проверяем документы с модулями
            async for doc in collection.find({"modules": {"$exists": True}}):
                total_docs_checked += 1
                doc_id = str(doc.get('_id'))
                doc_title = doc.get('title') or doc.get('name') or doc.get('full_name') or 'N/A'
                doc_slug = doc.get('slug', 'N/A')
                
                # Проверяем модули
                for module in doc.get('modules', []):
                    if module.get('type') == 'text_block':
                        total_modules_checked += 1
                        content = module.get('data', {}).get('content', '')
                        if not content:
                            continue
                        
                        # Находим все ссылки
                        for match in url_pattern.finditer(content):
                            url = match.group(1)
                            total_links_checked += 1
                            
                            # Пропускаем внешние ссылки
                            if url.startswith('http://') or url.startswith('https://') or url.startswith('mailto:'):
                                continue
                            
                            # Пропускаем якоря
                            if url.startswith('#'):
                                continue
                            
                            # Парсим URL
                            parsed = urlparse(url)
                            path = parsed.path
                            
                            # Определяем тип контента по пути (поддерживаем старые и новые форматы)
                            # Новые форматы
                            if path.startswith('/people/'):
                                slug = path.replace('/people/', '').strip('/').split('/')[0]  # Берем только первый сегмент
                                # Очищаем slug от параметров запроса и якорей
                                slug = slug.split('?')[0].split('#')[0]
                                if slug and slug.strip() and slug not in existing_slugs['people']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'doc_slug': doc_slug,
                                        'url': url,
                                        'slug': slug,
                                        'type': 'person',
                                        'expected_path': '/people/'
                                    })
                            
                            # Старые форматы тоже проверяем
                            elif path.startswith('/person/'):
                                slug = path.replace('/person/', '').strip('/').split('/')[0]
                                slug = slug.split('?')[0].split('#')[0]
                                if slug and slug.strip() and slug not in existing_slugs['people']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'doc_slug': doc_slug,
                                        'url': url,
                                        'slug': slug,
                                        'type': 'person',
                                        'expected_path': '/people/',
                                        'old_format': True
                                    })
                            
                            elif path.startswith('/kvn/teams/') or path.startswith('/teams/'):
                                slug = path.replace('/kvn/teams/', '').replace('/teams/', '').strip('/').split('/')[0]
                                slug = slug.split('?')[0].split('#')[0]
                                if slug and slug.strip() and slug not in existing_slugs['teams']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'doc_slug': doc_slug,
                                        'url': url,
                                        'slug': slug,
                                        'type': 'team',
                                        'expected_path': '/kvn/teams/'
                                    })
                            
                            # Старый формат /team/
                            elif path.startswith('/team/'):
                                slug = path.replace('/team/', '').strip('/').split('/')[0]
                                slug = slug.split('?')[0].split('#')[0]
                                if slug and slug.strip() and slug not in existing_slugs['teams']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'doc_slug': doc_slug,
                                        'url': url,
                                        'slug': slug,
                                        'type': 'team',
                                        'expected_path': '/kvn/teams/',
                                        'old_format': True
                                    })
                            
                            elif path.startswith('/shows/'):
                                slug = path.replace('/shows/', '').strip('/').split('/')[0]
                                slug = slug.split('?')[0].split('#')[0]
                                if slug and slug.strip() and slug not in existing_slugs['shows']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'doc_slug': doc_slug,
                                        'url': url,
                                        'slug': slug,
                                        'type': 'show',
                                        'expected_path': '/shows/'
                                    })
                            
                            # Старый формат /show/
                            elif path.startswith('/show/'):
                                slug = path.replace('/show/', '').strip('/').split('/')[0]
                                slug = slug.split('?')[0].split('#')[0]
                                if slug and slug.strip() and slug not in existing_slugs['shows']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'doc_slug': doc_slug,
                                        'url': url,
                                        'slug': slug,
                                        'type': 'show',
                                        'expected_path': '/shows/',
                                        'old_format': True
                                    })
                            
                            elif path.startswith('/kvn/'):
                                # Для KVN может быть полный путь
                                path_part = path.replace('/kvn/', '').strip('/')
                                # Проверяем и полный путь, и только slug
                                slug_part = path_part.split('/')[0] if '/' in path_part else path_part
                                
                                # Проверяем полный путь
                                if path_part and path_part not in existing_slugs['kvn']:
                                    # Проверяем только slug
                                    if slug_part and slug_part not in existing_slugs['kvn']:
                                        broken_internal.append({
                                            'collection': collection_name,
                                            'doc_id': doc_id,
                                            'doc_title': doc_title,
                                            'doc_slug': doc_slug,
                                            'url': url,
                                            'slug': path_part,
                                            'type': 'kvn',
                                            'expected_path': '/kvn/'
                                        })
                
                # Также проверяем другие HTML поля
                for field_name in html_fields_to_check:
                    field_content = doc.get(field_name, '')
                    if field_content and isinstance(field_content, str):
                        for match in url_pattern.finditer(field_content):
                            url = match.group(1)
                            total_links_checked += 1
                            
                            # Пропускаем внешние ссылки
                            if url.startswith('http://') or url.startswith('https://') or url.startswith('mailto:'):
                                continue
                            
                            # Пропускаем якоря
                            if url.startswith('#'):
                                continue
                            
                            # Парсим URL
                            parsed = urlparse(url)
                            path = parsed.path
                            
                            # Проверяем битые ссылки (аналогично модулям)
                            if path.startswith('/people/') or path.startswith('/person/'):
                                slug = path.replace('/people/', '').replace('/person/', '').strip('/').split('/')[0]
                                slug = slug.split('?')[0].split('#')[0]
                                if slug and slug.strip() and slug not in existing_slugs['people']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'doc_slug': doc_slug,
                                        'url': url,
                                        'slug': slug,
                                        'type': 'person',
                                        'expected_path': '/people/',
                                        'field': field_name
                                    })
                            elif path.startswith('/kvn/teams/') or path.startswith('/teams/') or path.startswith('/team/'):
                                slug = path.replace('/kvn/teams/', '').replace('/teams/', '').replace('/team/', '').strip('/').split('/')[0]
                                slug = slug.split('?')[0].split('#')[0]
                                if slug and slug.strip() and slug not in existing_slugs['teams']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'doc_slug': doc_slug,
                                        'url': url,
                                        'slug': slug,
                                        'type': 'team',
                                        'expected_path': '/kvn/teams/',
                                        'field': field_name,
                                        'old_format': path.startswith('/team/')
                                    })
                            elif path.startswith('/shows/') or path.startswith('/show/'):
                                slug = path.replace('/shows/', '').replace('/show/', '').strip('/').split('/')[0]
                                slug = slug.split('?')[0].split('#')[0]
                                if slug and slug.strip() and slug not in existing_slugs['shows']:
                                    broken_internal.append({
                                        'collection': collection_name,
                                        'doc_id': doc_id,
                                        'doc_title': doc_title,
                                        'doc_slug': doc_slug,
                                        'url': url,
                                        'slug': slug,
                                        'type': 'show',
                                        'expected_path': '/shows/',
                                        'field': field_name,
                                        'old_format': path.startswith('/show/')
                                    })
        
        print(f"\nСтатистика проверки:")
        print(f"  Проверено документов: {total_docs_checked}")
        print(f"  Проверено модулей: {total_modules_checked}")
        print(f"  Проверено ссылок: {total_links_checked}")
        
        return {
            'broken_internal': broken_internal,
            'broken_external': [],
            'existing_slugs': existing_slugs,
            'total_checked': total_links_checked,
            'total_docs': total_docs_checked,
            'total_modules': total_modules_checked
        }
    
    @staticmethod
    async def migrate_urls(
        dry_run: bool = True,
        collection_name: str = None,
        doc_id: str = None
    ) -> Dict[str, any]:
        """
        Мигрирует старые URL на новый формат во всех документах
        
        Args:
            dry_run: Если True, только показывает что будет изменено
            collection_name: Имя коллекции для фильтрации (people, teams, shows, kvn, articles, news)
            doc_id: ID конкретного документа для обработки
        
        Returns:
            Dict с результатами миграции
        """
        db = await get_db()
        
        # Определяем коллекции для обработки
        all_collections_map = {
            'people': db.people,
            'teams': db.teams,
            'shows': db.shows,
            'kvn': db.kvn,
            'articles': db.articles,
            'news': db.news,
            'quizzes': db.quizzes,
            'wiki': db.wiki
        }
        
        if collection_name:
            if collection_name not in all_collections_map:
                print(f"Ошибка: неизвестная коллекция '{collection_name}'")
                print(f"Доступные: {', '.join(all_collections_map.keys())}")
                return {'total_updated': 0, 'total_replacements': 0, 'details': []}
            collections = [(collection_name, all_collections_map[collection_name])]
        else:
            collections = [(name, coll) for name, coll in all_collections_map.items()]
        
        total_updated = 0
        total_replacements = 0
        details = []  # Детальная информация о заменах
        
        for coll_name, collection in collections:
            print(f"\nОбработка коллекции: {coll_name}")
            
            # Формируем запрос
            query = {"modules": {"$exists": True}}
            if doc_id:
                try:
                    from bson import ObjectId
                    query["_id"] = ObjectId(doc_id)
                except:
                    query["_id"] = doc_id
            
            async for doc in collection.find(query):
                updated = False
                new_modules = []
                replacements_count = 0
                doc_replacements = []  # Детали замен для этого документа
                
                doc_title = doc.get('title') or doc.get('name') or doc.get('full_name') or 'N/A'
                doc_slug = doc.get('slug', 'N/A')
                
                for module in doc.get('modules', []):
                    if module.get('type') == 'text_block':
                        content = module.get('data', {}).get('content', '')
                        new_content = content
                        
                        # Применяем все паттерны замены
                        for old_pattern, new_pattern in URLMigrator.URL_PATTERNS:
                            # Находим все совпадения для детального вывода
                            matches = list(re.finditer(old_pattern, new_content))
                            if matches:
                                for match in matches:
                                    old_url = match.group(0)
                                    # Извлекаем slug из старого URL
                                    slug_match = re.search(old_pattern, old_url)
                                    if slug_match:
                                        slug = slug_match.group(1) if slug_match.groups() else 'unknown'
                                        new_url = re.sub(old_pattern, new_pattern, old_url)
                                        doc_replacements.append({
                                            'old': old_url,
                                            'new': new_url,
                                            'slug': slug
                                        })
                                
                                new_content = re.sub(old_pattern, new_pattern, new_content)
                                replacements_count += len(matches)
                        
                        if new_content != content:
                            module['data']['content'] = new_content
                            updated = True
                    
                    new_modules.append(module)
                
                if updated:
                    total_updated += 1
                    total_replacements += replacements_count
                    
                    detail = {
                        'collection': coll_name,
                        'doc_id': str(doc.get('_id')),
                        'title': doc_title,
                        'slug': doc_slug,
                        'replacements_count': replacements_count,
                        'replacements': doc_replacements
                    }
                    details.append(detail)
                    
                    if not dry_run:
                        await collection.update_one(
                            {"_id": doc["_id"]},
                            {"$set": {"modules": new_modules}}
                        )
                        print(f"  ✅ Обновлен: {doc_title} ({doc_slug}) - {replacements_count} замен")
                    else:
                        print(f"  [DRY-RUN] Обновлен: {doc_title} ({doc_slug}) - {replacements_count} замен")
                        # Показываем примеры замен
                        if doc_replacements:
                            for i, rep in enumerate(doc_replacements[:3]):  # Показываем первые 3
                                print(f"      {i+1}. {rep['old']} -> {rep['new']}")
                            if len(doc_replacements) > 3:
                                print(f"      ... и еще {len(doc_replacements) - 3} замен")
        
        return {
            'total_updated': total_updated,
            'total_replacements': total_replacements,
            'details': details
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
    parser.add_argument('--collection', type=str, help='Обработать только указанную коллекцию (people, teams, shows, kvn, articles, news)')
    parser.add_argument('--doc-id', type=str, help='Обработать только указанный документ (ID)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробный вывод')
    
    args = parser.parse_args()
    
    if args.migrate:
        print("=" * 80)
        print("МИГРАЦИЯ СТАРЫХ URL")
        print("=" * 80)
        if args.collection:
            print(f"Обработка коллекции: {args.collection}")
        if args.doc_id:
            print(f"Обработка документа: {args.doc_id}")
        print()
        
        result = await URLMigrator.migrate_urls(
            dry_run=not args.apply,
            collection_name=args.collection,
            doc_id=args.doc_id
        )
        
        print(f"\n{'=' * 80}")
        print("РЕЗУЛЬТАТЫ МИГРАЦИИ")
        print(f"{'=' * 80}")
        print(f"Обновлено документов: {result['total_updated']}")
        print(f"Всего замен: {result['total_replacements']}")
        
        if args.verbose and result['details']:
            print(f"\nДетальная информация:")
            for detail in result['details']:
                print(f"\n  📄 {detail['title']} ({detail['slug']})")
                print(f"     Коллекция: {detail['collection']}, ID: {detail['doc_id']}")
                print(f"     Замен: {detail['replacements_count']}")
                if detail['replacements']:
                    for i, rep in enumerate(detail['replacements'][:5], 1):
                        print(f"       {i}. {rep['old']} -> {rep['new']}")
                    if len(detail['replacements']) > 5:
                        print(f"       ... и еще {len(detail['replacements']) - 5} замен")
        
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
            # Группируем по типам
            by_type = {}
            for link in result['broken_internal']:
                link_type = link['type']
                if link_type not in by_type:
                    by_type[link_type] = []
                by_type[link_type].append(link)
            
            for link_type, links in by_type.items():
                print(f"\n  {link_type.upper()} ({len(links)} битых ссылок):")
                for link in links[:10]:
                    old_format = " [СТАРЫЙ ФОРМАТ]" if link.get('old_format') else ""
                    field_info = f" (поле: {link.get('field', 'text_block')})" if link.get('field') else ""
                    print(f"    • {link['doc_title']} ({link.get('doc_slug', 'N/A')}){field_info}")
                    print(f"      URL: {link['url']}")
                    print(f"      Slug: {link['slug']}{old_format}")
                if len(links) > 10:
                    print(f"    ... и еще {len(links) - 10} битых ссылок")
        else:
            print("\n✅ Битые ссылки не найдены!")
            print(f"   Проверено документов: {result.get('total_docs', 0)}")
            print(f"   Проверено модулей: {result.get('total_modules', 0)}")
            print(f"   Проверено ссылок: {result.get('total_checked', 0)}")
            
            # Диагностика: показываем примеры найденных ссылок
            if args.verbose:
                print("\nДиагностика: примеры найденных ссылок (первые 5):")
                db = await get_db()
                url_pattern_diag = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
                sample_count = 0
                for collection_name, collection in [
                    ('teams', db.teams),
                    ('people', db.people),
                    ('kvn', db.kvn),
                ]:
                    if sample_count >= 5:
                        break
                    async for doc in collection.find({"modules": {"$exists": True}}).limit(2):
                        if sample_count >= 5:
                            break
                        for module in doc.get('modules', []):
                            if module.get('type') == 'text_block':
                                content = module.get('data', {}).get('content', '')
                                if content:
                                    matches = list(url_pattern_diag.finditer(content))
                                    for match in matches[:2]:
                                        url = match.group(1)
                                        if not url.startswith('http') and not url.startswith('#'):
                                            print(f"    {collection_name}: {url}")
                                            sample_count += 1
                                            if sample_count >= 5:
                                                break
                                if sample_count >= 5:
                                    break
                        if sample_count >= 5:
                            break
    
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
