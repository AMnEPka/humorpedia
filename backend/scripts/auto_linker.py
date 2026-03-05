"""
Автоматическое проставление ссылок по текстовым совпадениям
Находит упоминания "Флэш рояль" и добавляет ссылку на страницу команды
"""
import asyncio
import re
from typing import Dict, List, Tuple
import sys
import os

# Добавляем путь к backend для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_db


class AutoLinker:
    """Автоматически находит упоминания и добавляет ссылки"""
    
    @staticmethod
    async def create_link_index() -> Dict[str, Dict]:
        """Создает индекс всех имен/названий для быстрого поиска"""
        db = await get_db()
        
        index = {
            'teams': {},
            'people': {},
            'shows': {},
            'kvn': {}
        }
        
        # Индексируем команды
        async for team in db.teams.find({}):
            name = team.get('name') or team.get('title', '')
            slug = team.get('slug')
            team_id = str(team.get('_id'))
            
            if name and slug:
                index['teams'][name.lower()] = {
                    'id': team_id,
                    'slug': slug,
                    'url': f'/kvn/teams/{slug}',
                    'name': name
                }
                # Также добавляем алиасы
                for alias in team.get('aliases', []):
                    if alias:
                        index['teams'][alias.lower()] = index['teams'][name.lower()]
        
        # Индексируем людей
        async for person in db.people.find({}):
            name = person.get('full_name') or person.get('title', '')
            slug = person.get('slug')
            person_id = str(person.get('_id'))
            
            if name and slug:
                index['people'][name.lower()] = {
                    'id': person_id,
                    'slug': slug,
                    'url': f'/people/{slug}',
                    'name': name
                }
        
        # Индексируем шоу
        async for show in db.shows.find({}):
            name = show.get('name') or show.get('title', '')
            slug = show.get('slug')
            show_id = str(show.get('_id'))
            
            if name and slug:
                index['shows'][name.lower()] = {
                    'id': show_id,
                    'slug': slug,
                    'url': f'/shows/{slug}',
                    'name': name
                }
        
        return index
    
    @staticmethod
    async def auto_link_in_html(
        html: str,
        link_index: Dict,
        skip_existing_links: bool = True
    ) -> Tuple[str, List[Dict]]:
        """
        Автоматически добавляет ссылки в HTML текст
        
        Args:
            html: HTML контент
            link_index: Индекс имен и ссылок
            skip_existing_links: Пропускать текст, который уже является ссылкой
        
        Returns:
            Tuple[updated_html, list_of_added_links]
        """
        if not html:
            return html, []
        
        added_links = []
        
        # Сортируем по длине (сначала длинные названия, чтобы избежать частичных совпадений)
        all_entities = []
        for entity_type, entities in link_index.items():
            for name, data in entities.items():
                if len(name) >= 3:  # Минимум 3 символа
                    all_entities.append((name, entity_type, data))
        
        all_entities.sort(key=lambda x: len(x[0]), reverse=True)
        
        # Обрабатываем каждое упоминание
        for name, entity_type, data in all_entities:
            # Создаем паттерн для поиска (исключаем уже существующие ссылки)
            if skip_existing_links:
                # Ищем упоминания, которые НЕ являются частью ссылки
                pattern = re.compile(
                    r'(?<!<a[^>]*>)(?<!\[)' +  # Не внутри <a> тега
                    r'(?<![а-яА-Яa-zA-Z])' +  # Не часть другого слова
                    re.escape(name) +
                    r'(?![а-яА-Яa-zA-Z])' +  # Не часть другого слова
                    r'(?!\])(?![^<]*</a>)',  # Не внутри ссылки
                    re.IGNORECASE
                )
            else:
                pattern = re.compile(
                    r'(?<![а-яА-Яa-zA-Z])' + re.escape(name) + r'(?![а-яА-Яa-zA-Z])',
                    re.IGNORECASE
                )
            
            def replace_with_link(match):
                matched_text = match.group(0)
                # Проверяем, что это не часть HTML тега
                if '<' in matched_text or '>' in matched_text:
                    return matched_text
                
                # Создаем ссылку
                link_html = f'<a href="{data["url"]}">{matched_text}</a>'
                added_links.append({
                    'type': entity_type,
                    'name': data['name'],
                    'url': data['url'],
                    'matched_text': matched_text
                })
                return link_html
            
            new_html = pattern.sub(replace_with_link, html)
            if new_html != html:
                html = new_html
        
        return html, added_links
    
    @staticmethod
    async def auto_link_all_pages(
        content_types: List[str] = None,
        dry_run: bool = True
    ):
        """Автоматически проставляет ссылки на всех страницах"""
        db = await get_db()
        
        if content_types is None:
            content_types = ['person', 'team', 'show', 'kvn', 'article', 'news']
        
        print("Создание индекса ссылок...")
        link_index = await AutoLinker.create_link_index()
        print(f"Индекс создан: {len(link_index['teams'])} команд, "
              f"{len(link_index['people'])} людей, "
              f"{len(link_index['shows'])} шоу")
        
        collection_map = {
            'person': db.people,
            'team': db.teams,
            'show': db.shows,
            'kvn': db.kvn,
            'article': db.articles,
            'news': db.news
        }
        
        total_updated = 0
        total_links_added = 0
        
        for content_type in content_types:
            if content_type not in collection_map:
                continue
            
            collection = collection_map[content_type]
            print(f"\nОбработка {content_type}...")
            
            async for doc in collection.find({"modules": {"$exists": True}}):
                updated = False
                new_modules = []
                all_added_links = []
                
                for module in doc.get('modules', []):
                    if module.get('type') == 'text_block':
                        content = module.get('data', {}).get('content', '')
                        new_content, added_links = await AutoLinker.auto_link_in_html(
                            content, link_index
                        )
                        
                        if new_content != content:
                            module['data']['content'] = new_content
                            updated = True
                            all_added_links.extend(added_links)
                    
                    new_modules.append(module)
                
                if updated:
                    total_updated += 1
                    total_links_added += len(all_added_links)
                    
                    if not dry_run:
                        await collection.update_one(
                            {"_id": doc["_id"]},
                            {"$set": {"modules": new_modules}}
                        )
                    else:
                        doc_title = doc.get('title') or doc.get('name') or 'N/A'
                        print(f"  [DRY-RUN] Обновлен: {doc_title} "
                              f"({len(all_added_links)} ссылок)")
        
        print(f"\nИтого:")
        print(f"  Обновлено документов: {total_updated}")
        print(f"  Добавлено ссылок: {total_links_added}")
        
        return {
            'total_updated': total_updated,
            'total_links_added': total_links_added
        }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Автоматическое проставление ссылок')
    parser.add_argument('--apply', action='store_true', help='Применить изменения')
    parser.add_argument('--types', type=str, help='Типы контента через запятую (person,team,show)')
    
    args = parser.parse_args()
    
    content_types = None
    if args.types:
        content_types = [t.strip() for t in args.types.split(',')]
    
    result = asyncio.run(AutoLinker.auto_link_all_pages(
        content_types=content_types,
        dry_run=not args.apply
    ))
    
    if not args.apply:
        print("\n[DRY-RUN] Для применения запустите с --apply")
