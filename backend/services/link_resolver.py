"""
Батчевый резолвер ссылок в HTML-контенте.

Вместо N отдельных find_one запросов (по одному на каждую ссылку),
собирает все slug'и, делает 1 запрос ($in) на коллекцию, затем заменяет разом.

Было:  50 ссылок → 50 find_one → ~50 × 1ms = 50ms
Стало: 50 ссылок → 1 parse + max 6 find($in) → ~6 × 1ms = 6ms
"""

import re
from typing import Dict, List
from utils.database import get_db
from services.cache import cache_service

# Паттерн для поиска ссылок в HTML
_LINK_RE = re.compile(
    r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL
)


class LinkResolver:
    """Разрешает ссылки в HTML контенте, проверяя актуальность slug'ов."""

    @staticmethod
    async def resolve_links_in_html(html: str) -> str:
        """
        Обновляет ссылки в HTML, проверяя актуальность slug'ов.
        Результат кэшируется по хэшу исходного HTML.
        """
        if not html:
            return html

        # ─── Кэш ──────────────────────────────────────────────────────
        cached = cache_service.get_resolved_html(html)
        if cached is not None:
            return cached

        # ─── Фаза 1: Парсим все ссылки ────────────────────────────────
        matches = list(_LINK_RE.finditer(html))
        if not matches:
            cache_service.set_resolved_html(html, html)
            return html

        # Собираем уникальные slug'и и full_path'ы по коллекциям
        # {collection_name: set_of_slugs}
        slug_requests: Dict[str, set] = {}
        # {full_path: True} — для KVN ссылок с полным путём
        full_path_requests: set = set()

        parsed_links = []  # (match, url, url_parts, content_type, slug, is_full_path)

        for match in matches:
            url = match.group(1)

            # Пропускаем внешние, якоря, короткие
            if (url.startswith(('http://', 'https://', 'mailto:', '#'))
                    or not url.strip('/')):
                parsed_links.append((match, url, None, None, None, False))
                continue

            url_parts = url.strip('/').split('/')
            if len(url_parts) < 2:
                parsed_links.append((match, url, url_parts, None, None, False))
                continue

            content_type = url_parts[0]
            slug = url_parts[-1]

            # KVN full path (kvn/vl-kvn/vl-2025 и т.д.)
            if content_type == 'kvn' and len(url_parts) > 2:
                fp = '/'.join(url_parts).lstrip('/')
                full_path_requests.add(fp)
                parsed_links.append((match, url, url_parts, content_type, slug, True))
            elif content_type in ('people', 'kvn', 'teams', 'shows', 'articles', 'news'):
                slug_requests.setdefault(content_type, set()).add(slug)
                parsed_links.append((match, url, url_parts, content_type, slug, False))
            else:
                parsed_links.append((match, url, url_parts, None, None, False))

        # ─── Фаза 2: Батчевые запросы к БД ────────────────────────────
        db = await get_db()

        # Маппинг collection_name → (db_collection, url_prefix)
        collection_map = {
            'people':   (db.people,   '/people/'),
            'kvn':      (db.kvn,      '/kvn/'),
            'teams':    (db.teams,    '/kvn/teams/'),
            'shows':    (db.shows,    '/shows/'),
            'articles': (db.articles, '/articles/'),
            'news':     (db.news,     '/news/'),
        }

        # slug → doc  (по коллекциям)
        slug_lookup: Dict[str, Dict[str, dict]] = {}  # {content_type: {slug: doc}}

        for coll_name, slugs in slug_requests.items():
            if not slugs or coll_name not in collection_map:
                continue
            db_coll = collection_map[coll_name][0]
            docs = await db_coll.find(
                {"slug": {"$in": list(slugs)}},
                {"slug": 1, "full_path": 1, "_id": 0}
            ).to_list(len(slugs) + 10)
            slug_lookup[coll_name] = {doc["slug"]: doc for doc in docs}

        # full_path → doc  (для KVN)
        fp_lookup: Dict[str, dict] = {}
        if full_path_requests:
            fp_docs = await db.kvn.find(
                {"full_path": {"$in": list(full_path_requests)}},
                {"slug": 1, "full_path": 1, "_id": 0}
            ).to_list(len(full_path_requests) + 10)
            fp_lookup = {doc["full_path"]: doc for doc in fp_docs}

        # ─── Фаза 3: Замена ссылок ────────────────────────────────────
        replacements = []
        for (match, url, url_parts, content_type, slug, is_full_path) in parsed_links:
            full_tag = match.group(0)
            text = match.group(2)

            if content_type is None:
                # Ссылка не подлежит резолву
                replacements.append((match.start(), match.end(), full_tag))
                continue

            if is_full_path:
                fp = '/'.join(url_parts).lstrip('/')
                doc = fp_lookup.get(fp)
                if doc:
                    correct_url = f"/{doc.get('full_path', '').lstrip('/')}"
                    replacements.append((match.start(), match.end(),
                                         f'<a href="{correct_url}">{text}</a>'))
                else:
                    replacements.append((match.start(), match.end(), full_tag))
                continue

            coll_docs = slug_lookup.get(content_type, {})
            doc = coll_docs.get(slug)
            if doc:
                current_slug = doc.get('slug')
                if current_slug != slug:
                    # Slug изменился — обновляем
                    if content_type == 'kvn':
                        fp = doc.get('full_path') or current_slug
                        correct_url = f"/{fp.lstrip('/')}"
                    else:
                        correct_url = f"{collection_map[content_type][1]}{current_slug}"
                    replacements.append((match.start(), match.end(),
                                         f'<a href="{correct_url}">{text}</a>'))
                else:
                    replacements.append((match.start(), match.end(), full_tag))
            else:
                replacements.append((match.start(), match.end(), full_tag))

        # Применяем замены в обратном порядке
        result = html
        for start, end, replacement in reversed(replacements):
            result = result[:start] + replacement + result[end:]

        # ─── Кэш: сохраняем ──────────────────────────────────────────
        cache_service.set_resolved_html(html, result)

        return result

    @staticmethod
    async def resolve_links_in_modules(modules: List[Dict]) -> List[Dict]:
        """
        Разрешает ссылки во всех text_block модулях.
        """
        if not modules:
            return modules

        resolved_modules = []
        for module in modules:
            if module.get('type') == 'text_block':
                content = module.get('data', {}).get('content', '')
                if content:
                    resolved_content = await LinkResolver.resolve_links_in_html(content)
                    new_module = module.copy()
                    new_module['data'] = module['data'].copy()
                    new_module['data']['content'] = resolved_content
                    resolved_modules.append(new_module)
                else:
                    resolved_modules.append(module)
            else:
                resolved_modules.append(module)

        return resolved_modules
