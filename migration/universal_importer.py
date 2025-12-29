#!/usr/bin/env python3
"""
Универсальный модульный импортер для Humorpedia.

Позволяет создавать импорт-скрипты для разных типов контента,
указывая лишь последовательность модулей.

Пример использования:
    
    from universal_importer import UniversalImporter, ModuleConfig
    
    # Создаём импортер для шоу
    importer = UniversalImporter(
        content_type='shows',
        collection='shows',
        modules=[
            ModuleConfig('poster_photo'),
            ModuleConfig('facts_table', title='Информация'),
            ModuleConfig('rating_widget'),
            ModuleConfig('tags_cloud'),
            ModuleConfig('social_links'),
            ModuleConfig('text_block', title='Описание', migx_section='info', migx_field='subtitle'),
        ]
    )
    
    # Импортируем один ресурс
    doc = importer.import_resource(resource_id=1234, apply=True)
"""

from __future__ import annotations

import os
import sys
import re
import json
import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Type
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parsers import (
    BaseParser,
    ParseContext,
    PhotoParser,
    FactsParser,
    TagsParser,
    SocialLinksParser,
    TextBlockParser,
    TimelineParser,
    TeamMembersParser,
    GalleryParser,
    RatingParser,
)

# Маппинг типов модулей на парсеры
PARSER_MAP: Dict[str, Type[BaseParser]] = {
    'poster_photo': PhotoParser,
    'facts_table': FactsParser,
    'tags_cloud': TagsParser,
    'social_links': SocialLinksParser,
    'text_block': TextBlockParser,
    'timeline': TimelineParser,
    'team_members': TeamMembersParser,
    'image_gallery': GalleryParser,
    'rating_widget': RatingParser,
}


@dataclass
class ModuleConfig:
    """Конфигурация модуля для импорта."""
    type: str  # poster_photo, facts_table, text_block, etc.
    title: str = ""  # Заголовок модуля
    visible: bool = True  # Видимость модуля
    # Дополнительные параметры передаются в парсер
    tv_field: str = ""
    migx_section: str = ""
    migx_field: str = ""
    html_selector: str = ""
    style: str = ""
    delimiter: str = "||"
    max_items: int = 0
    strip_first_heading: bool = False
    all_sections: bool = False
    all_text_sections: bool = False  # Для text_block - парсить все text секции
    exclude_keys: List[str] = field(default_factory=list)
    fallback_tv_fields: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Конвертирует в словарь для парсера."""
        d = {
            'title': self.title,
            'visible': self.visible,
        }
        if self.tv_field:
            d['tv_field'] = self.tv_field
        if self.migx_section:
            d['migx_section'] = self.migx_section
        if self.migx_field:
            d['migx_field'] = self.migx_field
        if self.html_selector:
            d['html_selector'] = self.html_selector
        if self.style:
            d['style'] = self.style
        if self.delimiter:
            d['delimiter'] = self.delimiter
        if self.max_items:
            d['max_tags'] = self.max_items
            d['max_images'] = self.max_items
        if self.strip_first_heading:
            d['strip_first_heading'] = self.strip_first_heading
        if self.all_sections:
            d['all_sections'] = self.all_sections
        if self.all_text_sections:
            d['all_text_sections'] = self.all_text_sections
        if self.exclude_keys:
            d['exclude_keys'] = self.exclude_keys
        if self.fallback_tv_fields:
            d['fallback_tv_fields'] = self.fallback_tv_fields
        return d


# Transliteration map for cyrillic -> latin slugs
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def transliterate_slug(text: str) -> str:
    """Convert cyrillic text to latin slug."""
    slug = text.lower().replace(" ", "-").replace(".", "").replace(",", "")
    slug = ''.join(TRANSLIT_MAP.get(char, char) for char in slug)
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


class UniversalImporter:
    """Универсальный импортер контента."""
    
    def __init__(
        self,
        content_type: str,
        collection: str,
        modules: List[ModuleConfig],
        sql_file: str = None,
        tag_map_file: str = None,
        image_map_file: str = None,
        tv_map_file: str = None,
    ):
        """
        Инициализация импортера.
        
        Args:
            content_type: Тип контента (people, shows, teams, articles, etc.)
            collection: Название MongoDB коллекции
            modules: Список конфигураций модулей в порядке отображения
            sql_file: Путь к SQL дампу (по умолчанию: humorbd.sql в директории скрипта)
            tag_map_file: Путь к маппингу тегов (по умолчанию: tag_mapping.json в директории скрипта)
            image_map_file: Путь к маппингу изображений (по умолчанию: image_mapping.json в директории скрипта)
            tv_map_file: Путь к маппингу TV переменных (по умолчанию: tv_map.json в директории скрипта)
        """
        # Определяем базовую директорию (где находится скрипт)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.content_type = content_type
        self.collection = collection
        self.module_configs = modules
        
        # Устанавливаем пути по умолчанию относительно директории скрипта
        if sql_file is None:
            # Сначала пробуем в той же директории, потом в родительской
            sql_file = os.path.join(script_dir, "humorbd.sql")
            if not os.path.exists(sql_file):
                sql_file = os.path.join(os.path.dirname(script_dir), "humorbd.sql")
        self.sql_file = sql_file
        
        if tag_map_file is None:
            tag_map_file = os.path.join(script_dir, "tag_mapping.json")
        if image_map_file is None:
            image_map_file = os.path.join(script_dir, "image_mapping.json")
        if tv_map_file is None:
            tv_map_file = os.path.join(script_dir, "tv_map.json")
        
        # Загружаем маппинги
        print(f"📂 Загрузка маппингов...")
        print(f"   SQL файл: {self.sql_file}")
        self.tag_map = self._load_json(tag_map_file)
        self.image_map = self._load_json(image_map_file)
        self.tv_map = self._load_json(tv_map_file)
        
        # MongoDB
        self.mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        self.db_name = os.environ.get('DB_NAME', 'humorpedia')
    
    def _load_json(self, path: str) -> dict:
        """Загружает JSON файл."""
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"   ✅ {os.path.basename(path)}: {len(data)} записей")
                    return data
            except Exception as e:
                print(f"   ⚠️ Ошибка загрузки {os.path.basename(path)}: {e}")
                return {}
        else:
            print(f"   ⚠️ Файл не найден: {os.path.basename(path)}")
            return {}
    
    def extract_resource(self, resource_id: int) -> Optional[dict]:
        """Извлекает данные ресурса из SQL."""
        # Используем существующую функцию парсинга SQL из import_people_from_sql
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        import import_people_from_sql
        
        # Временно устанавливаем правильный путь к SQL файлу
        original_sql_file = getattr(import_people_from_sql, 'SQL_FILE', None)
        import_people_from_sql.SQL_FILE = self.sql_file
        
        try:
            from import_people_from_sql import _extract_for_ids
            
            # Функция возвращает (site_content_dict, tv_values_dict)
            site_content, tv_values = _extract_for_ids({resource_id})
            
            if resource_id not in site_content:
                return None
            
            return {
                'sc': site_content[resource_id],
                'tv': tv_values.get(resource_id, {})
            }
        finally:
            # Восстанавливаем оригинальный путь
            if original_sql_file is not None:
                import_people_from_sql.SQL_FILE = original_sql_file
    
    def build_document(
        self,
        resource_data: dict,
        parent_id: str = None,
        parent_path: str = None,
        level: int = 0,
    ) -> dict:
        """
        Строит документ MongoDB из данных ресурса.
        
        Args:
            resource_data: Данные из SQL (site_content + TV)
            parent_id: MongoDB ID родительского документа
            parent_path: Путь родителя для иерархии
            level: Уровень вложенности
            
        Returns:
            Готовый документ для MongoDB
        """
        # Извлекаем базовые поля
        sc = resource_data['sc']  # site_content
        tv_by_id = resource_data.get('tv', {})  # TV переменные по ID
        
        # Конвертируем TV ID в имена
        tv_data = {}
        unmapped_tv_count = 0
        for tv_id, val in tv_by_id.items():
            tv_name = self.tv_map.get(tv_id)
            if tv_name:
                tv_data[tv_name] = val
            else:
                unmapped_tv_count += 1
        
        if unmapped_tv_count > 0:
            print(f"  ⚠️ {unmapped_tv_count} TV переменных не найдено в маппинге (используется {len(tv_data)} из {len(tv_by_id)})")
        
        # Создаём контекст для парсеров
        # SiteContentRow не имеет content, используем description для HTML
        ctx = ParseContext(
            html=sc.description or "",
            title=sc.pagetitle or "",
            resource_id=int(sc.id),
            tv_data=tv_data,
            tag_map=self.tag_map,
            image_map=self.image_map,
            sql_file=self.sql_file,
            rating=float(sc.rating) if sc.rating else 0.0,
            votes=int(sc.votes) if sc.votes else 0,
        )
        
        # Собираем модули
        modules = []
        order = 1
        
        # Дополнительные поля для документа
        extra_fields = {}
        
        for config in self.module_configs:
            parser_class = PARSER_MAP.get(config.type)
            if not parser_class:
                print(f"  ⚠️ Неизвестный тип модуля: {config.type}")
                continue
            
            parser = parser_class(config.to_dict())
            
            # Специальная обработка для text_block с all_text_sections
            if config.type == 'text_block' and config.to_dict().get('all_text_sections'):
                from parsers.text import TextBlockParser
                text_parser = TextBlockParser(config.to_dict())
                text_sections = text_parser.parse_all_text_sections(ctx)
                
                for text_data in text_sections:
                    module = {
                        'id': str(uuid4()),
                        'type': 'text_block',
                        'order': order,
                        'title': text_data.get('title', ''),
                        'visible': True,
                        'data': text_data
                    }
                    modules.append(module)
                    order += 1
            # Специальная обработка для "личной жизни" из MIGX info секции
            elif config.type == 'text_block' and config.to_dict().get('migx_section') == 'info' and config.to_dict().get('migx_field') == 'subtitle':
                # Парсим биографию (subtitle) и личную жизнь (content) из одной секции
                from parsers.text import TextBlockParser
                from parsers.base import BaseParser
                
                config_dict = config.to_dict()
                bio_parser = TextBlockParser(config_dict)
                bio_data = bio_parser.parse(ctx)
                
                if bio_data:
                    # Добавляем биографию
                    bio_module = {
                        'id': str(uuid4()),
                        'type': 'text_block',
                        'order': order,
                        'title': bio_data.get('title', 'Биография'),
                        'visible': True,
                        'data': bio_data
                    }
                    modules.append(bio_module)
                    order += 1
                    
                    # Парсим "личную жизнь" из info.content (если есть и отличается от subtitle)
                    # Логика как в старом коде: если есть и subtitle, и content, и они разные,
                    # то content становится "личной жизнью"
                    config_personal = ctx.tv_data.get('config', '')
                    if config_personal:
                        sections = BaseParser.parse_migx_config(config_personal)
                        for sec in sections:
                            if sec.get('MIGX_formname') == 'info':
                                subtitle_raw = sec.get('subtitle', '') or ''
                                content_raw = sec.get('content', '') or ''
                                
                                # Нормализуем как в старом коде
                                subtitle_html = BaseParser.normalize_html(subtitle_raw)
                                content_html = BaseParser.normalize_html(content_raw)
                                
                                # Если есть и subtitle, и content, и они разные - content это "личная жизнь"
                                if subtitle_html and content_html and content_html != subtitle_html:
                                    personal_module = {
                                        'id': str(uuid4()),
                                        'type': 'text_block',
                                        'order': order,
                                        'title': 'Личная жизнь',
                                        'visible': True,
                                        'data': {
                                            'title': 'Личная жизнь',
                                            'content': content_html
                                        }
                                    }
                                    modules.append(personal_module)
                                    order += 1
                                break
            else:
                # Парсим данные напрямую для извлечения в extra_fields
                # (даже если модуль не создастся, данные могут быть нужны)
                parsed_data = parser.parse(ctx)
                
                module = parser.build_module(ctx, order)
                
                if module:
                    modules.append(module)
                    order += 1
                    
                    # Извлекаем данные для основных полей документа
                    data = module.get('data', {})
                    
                    if config.type == 'tags_cloud' and 'tags' in data:
                        extra_fields['tags'] = data['tags']
                    elif config.type == 'rating_widget' and 'rating' in data:
                        extra_fields['rating'] = data['rating']
                    elif config.type == 'social_links' and 'links' in data:
                        extra_fields['social_links'] = data['links']
                    elif config.type == 'facts_table' and 'facts' in data:
                        extra_fields['facts'] = data['facts']
                    elif config.type == 'poster_photo' and data.get('url'):
                        extra_fields['image'] = data['url']
                        extra_fields['poster'] = data['url']
                else:
                    # Модуль не создан, но данные могут быть нужны для extra_fields
                    # (например, рейтинг и теги должны быть всегда)
                    if parsed_data:
                        if config.type == 'tags_cloud' and 'tags' in parsed_data:
                            extra_fields['tags'] = parsed_data['tags']
                        elif config.type == 'rating_widget' and 'rating' in parsed_data:
                            extra_fields['rating'] = parsed_data['rating']
                        elif config.type == 'poster_photo' and parsed_data.get('url'):
                            extra_fields['image'] = parsed_data['url']
                            extra_fields['poster'] = parsed_data['url']
                    print(f"  ⚠️ Модуль {config.type} не создан (данные не найдены)")
        
        # Строим slug
        slug = sc.alias or transliterate_slug(sc.pagetitle)
        full_path = f"{parent_path}/{slug}" if parent_path else slug
        
        # Базовый документ
        doc = {
            'id': str(uuid4()),
            'content_type': self.content_type,
            'title': sc.pagetitle,
            'slug': slug,
            'full_path': full_path,
            'status': 'published',
            'description': BaseParser.normalize_html(sc.description or "")[:500] if sc.description else "",
            'modules': modules,
            'tags': extra_fields.get('tags', []),
            'rating': extra_fields.get('rating', {'average': 0.0, 'count': 0}),
            'social_links': extra_fields.get('social_links', {}),
            'facts': extra_fields.get('facts', {}),
            'image': extra_fields.get('image', ''),
            'poster': extra_fields.get('poster', ''),
            'views_count': 0,
            'views': 0,
            'featured': False,
            'level': level,
            'parent_id': parent_id,
            'old_id': int(sc.id),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'seo': {
                'meta_title': sc.pagetitle,
                'meta_description': sc.description or ""
            }
        }
        
        return doc
    
    def import_resource(
        self,
        resource_id: int,
        apply: bool = False,
        parent_id: str = None,
        parent_path: str = None,
        level: int = 0,
    ) -> Optional[dict]:
        """
        Импортирует один ресурс.
        
        Args:
            resource_id: ID ресурса в MODX
            apply: Если True - записывает в MongoDB
            parent_id: MongoDB ID родителя
            parent_path: Путь родителя
            level: Уровень вложенности
            
        Returns:
            Документ или None при ошибке
        """
        print(f"\n📥 Извлечение ресурса ID={resource_id}...")
        
        resource_data = self.extract_resource(resource_id)
        if not resource_data:
            print(f"  ❌ Ресурс не найден в SQL")
            return None
        
        sc = resource_data['sc']
        print(f"  📄 Найден: {sc.pagetitle}")
        
        doc = self.build_document(resource_data, parent_id, parent_path, level)
        
        print(f"  📦 Модулей: {len(doc['modules'])}")
        print(f"  🏷️  Тегов: {len(doc['tags'])}")
        print(f"  ⭐ Рейтинг: {doc['rating']['average']:.1f} ({doc['rating']['count']} голосов)")
        
        if apply:
            import pymongo
            client = pymongo.MongoClient(self.mongo_url)
            db = client[self.db_name]
            
            # Проверяем существует ли (по old_id или slug)
            existing = db[self.collection].find_one({
                '$or': [
                    {'old_id': int(sc.id)},
                    {'slug': doc['slug']}
                ]
            })
            
            if existing:
                # Обновляем
                doc['id'] = existing.get('id', doc['id'])
                db[self.collection].update_one(
                    {'_id': existing['_id']},
                    {'$set': doc}
                )
                print(f"  ✅ Обновлён: {doc['slug']}")
            else:
                # Создаём
                db[self.collection].insert_one({'_id': doc['id'], **doc})
                print(f"  ✅ Создан: {doc['slug']}")
            
            # Синхронизируем теги
            self._sync_tags(db, doc['tags'])
            
            client.close()
        else:
            print(f"  🔍 Dry-run: документ не сохранён")
            print(f"     Используйте --apply для записи в БД")
        
        return doc
    
    def _sync_tags(self, db, tags: List[str]) -> None:
        """Синхронизирует теги с коллекцией tags."""
        for tag_name in tags:
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            
            existing = db.tags.find_one({
                "name": {"$regex": f"^{re.escape(tag_name)}$", "$options": "i"}
            })
            
            if not existing:
                tag_doc = {
                    "_id": str(uuid4()),
                    "name": tag_name,
                    "slug": transliterate_slug(tag_name),
                    "old_id": None,
                    "usage_count": 1,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                try:
                    db.tags.insert_one(tag_doc)
                except Exception:
                    pass
            else:
                db.tags.update_one(
                    {"_id": existing["_id"]},
                    {"$inc": {"usage_count": 1}}
                )
    
    def print_document(self, doc: dict, verbose: bool = False) -> None:
        """Красиво выводит документ."""
        print(f"\n{'='*60}")
        print(f"📄 {doc['title']}")
        print(f"   slug: {doc['slug']}")
        print(f"   path: {doc['full_path']}")
        print(f"{'='*60}")
        
        print("\n📦 Модули:")
        for m in doc['modules']:
            status = "✅" if m['visible'] else "❌"
            print(f"   {status} {m['order']}. {m['type']}: {m.get('title', '-')}")
            
            if verbose:
                data = m.get('data', {})
                for k, v in data.items():
                    if k in ('content', 'description'):
                        v = (v[:100] + '...') if len(str(v)) > 100 else v
                    print(f"      {k}: {v}")
        
        if doc.get('tags'):
            print(f"\n🏷️  Теги: {', '.join(doc['tags'][:10])}")
            if len(doc['tags']) > 10:
                print(f"      ... и ещё {len(doc['tags']) - 10}")
        
        if doc.get('facts'):
            print(f"\n📊 Факты:")
            for k, v in list(doc['facts'].items())[:5]:
                print(f"   {k}: {v[:50]}..." if len(str(v)) > 50 else f"   {k}: {v}")


# ============================================================================
# Пример создания импортера для конкретного типа контента
# ============================================================================

def create_show_importer() -> UniversalImporter:
    """Создаёт импортер для шоу."""
    return UniversalImporter(
        content_type='show',
        collection='shows',
        modules=[
            ModuleConfig('poster_photo'),
            ModuleConfig('facts_table', title='Информация', style='card'),
            ModuleConfig('rating_widget', title='Оценка', style='smileys'),
            ModuleConfig('tags_cloud', style='badges'),
            ModuleConfig('social_links', title='Ссылки', style='list'),
            ModuleConfig('text_block', title='', migx_section='info', migx_field='subtitle', strip_first_heading=True),
            ModuleConfig('text_block', title='', all_sections=True),
        ]
    )


def create_person_importer() -> UniversalImporter:
    """Создаёт импортер для людей."""
    return UniversalImporter(
        content_type='person',
        collection='people',
        modules=[
            ModuleConfig('poster_photo'),
            ModuleConfig('facts_table', title='Информация', style='card'),
            ModuleConfig('rating_widget', title='Оценка', style='smileys'),
            ModuleConfig('tags_cloud', style='badges'),
            ModuleConfig('social_links', title='Ссылки', style='icons'),
            ModuleConfig('text_block', title='Биография', migx_section='info', migx_field='subtitle'),
            ModuleConfig('timeline', title='Хронология'),
        ]
    )


def create_team_importer() -> UniversalImporter:
    """Создаёт импортер для команд."""
    return UniversalImporter(
        content_type='team',
        collection='teams',
        modules=[
            ModuleConfig('poster_photo', tv_field='img'),
            ModuleConfig('facts_table', title='Информация', style='card'),
            ModuleConfig('rating_widget', title='Оценка', style='smileys'),
            ModuleConfig('tags_cloud', style='badges'),
            ModuleConfig('social_links', title='Ссылки', style='list'),
            ModuleConfig('text_block', title='', migx_section='info', migx_field='subtitle'),
            ModuleConfig('timeline', title='Хронология'),
            ModuleConfig('text_block', all_text_sections=True),  # Все text секции как отдельные модули
        ]
    )


# ============================================================================
# CLI
# ============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Универсальный импортер Humorpedia',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Импорт человека
  python universal_importer.py --type person --ids 350 --apply

  # Импорт шоу
  python universal_importer.py --type show --ids 1656 --apply

  # Импорт сезона как дочерней страницы шоу (по slug родителя)
  python universal_importer.py --type show --ids 1700 --parent-slug comedy-battle --apply

  # Импорт сезона как дочерней страницы (по old_id родителя из MODX)  
  python universal_importer.py --type show --ids 1700 --parent-old-id 1629 --apply

  # Импорт в произвольную коллекцию
  python universal_importer.py --type show --collection articles --ids 500 --apply
        """
    )
    parser.add_argument('--type', choices=['show', 'person', 'team'], required=True,
                        help='Тип шаблона для импорта (определяет набор модулей)')
    parser.add_argument('--collection', type=str, default=None,
                        help='Коллекция MongoDB (по умолчанию: shows/people/teams)')
    parser.add_argument('--ids', type=str, required=True,
                        help='ID ресурсов MODX через запятую')
    parser.add_argument('--parent-slug', type=str, default=None,
                        help='Slug родительской страницы для иерархии')
    parser.add_argument('--parent-old-id', type=int, default=None,
                        help='MODX ID родительской страницы для иерархии')
    parser.add_argument('--apply', action='store_true',
                        help='Записать в MongoDB (без этого флага - dry-run)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Подробный вывод')
    
    args = parser.parse_args()
    
    # Создаём импортер
    if args.type == 'show':
        importer = create_show_importer()
    elif args.type == 'person':
        importer = create_person_importer()
    elif args.type == 'team':
        importer = create_team_importer()
    
    # Переопределяем коллекцию если указана
    if args.collection:
        importer.collection = args.collection
        print(f"📁 Используется коллекция: {args.collection}")
    
    # Определяем родителя если указан
    parent_id = None
    parent_path = None
    parent_level = 0
    
    if args.parent_slug or args.parent_old_id:
        import pymongo
        client = pymongo.MongoClient(importer.mongo_url)
        db = client[importer.db_name]
        
        # Ищем родителя
        if args.parent_slug:
            parent_doc = db[importer.collection].find_one({'slug': args.parent_slug})
        else:
            parent_doc = db[importer.collection].find_one({'old_id': args.parent_old_id})
        
        if parent_doc:
            parent_id = parent_doc.get('id')
            parent_path = parent_doc.get('full_path', parent_doc.get('slug'))
            parent_level = parent_doc.get('level', 0)
            print(f"📂 Родитель найден: {parent_doc.get('title')} (level={parent_level})")
            print(f"   path: {parent_path}")
        else:
            print(f"⚠️  Родитель не найден! Импорт будет на верхнем уровне.")
        
        client.close()
    
    # Импортируем
    ids = [int(x.strip()) for x in args.ids.split(',')]
    
    for rid in ids:
        doc = importer.import_resource(
            rid, 
            apply=args.apply,
            parent_id=parent_id,
            parent_path=parent_path,
            level=parent_level + 1 if parent_id else 0
        )
        if doc and args.verbose:
            importer.print_document(doc, verbose=True)
    else:
        print("Укажите --ids для импорта")
