"""
In-memory TTL-кэш для API ответов.

Контент сайта меняется редко (раз в неделю), а читается миллионы раз.
TTL-кэш с инвалидацией при записи — оптимальная стратегия.

Использование:
    from services.cache import cache_service
    
    # Чтение
    cached = cache_service.get_kvn("kvn/vl-kvn")
    
    # Запись
    cache_service.set_kvn("kvn/vl-kvn", data)
    
    # Инвалидация
    cache_service.invalidate_kvn("kvn/vl-kvn")
    cache_service.invalidate_kvn_children("parent-uuid")
"""

import hashlib
import logging
from cachetools import TTLCache

logger = logging.getLogger("cache")


class CacheService:
    """Централизованный in-memory кэш с TTL и инвалидацией."""

    def __init__(self):
        # Страницы KVN (full_path → response dict)
        # maxsize=500: покрывает все страницы КВН + сезоны (≈140 сейчас)
        # TTL=300s (5 мин): баланс между свежестью и нагрузкой
        self.kvn_pages = TTLCache(maxsize=500, ttl=300)

        # Дети KVN-страниц (parent_id → children list)
        self.kvn_children = TTLCache(maxsize=100, ttl=300)

        # Страницы команд (slug → response dict)
        self.teams = TTLCache(maxsize=500, ttl=300)

        # Список команд (cache_key → response dict)
        self.team_lists = TTLCache(maxsize=50, ttl=120)

        # Redirect lookups (old_path → redirect result)
        self.redirects = TTLCache(maxsize=2000, ttl=1800)

        # Поисковые запросы (query_hash → results)
        self.search = TTLCache(maxsize=200, ttl=60)

        # Резолвер ссылок (content_hash → resolved_html)
        self.resolved_links = TTLCache(maxsize=500, ttl=600)

        # Breadcrumbs (page_id → breadcrumbs list)
        self.breadcrumbs = TTLCache(maxsize=200, ttl=300)

        self._stats = {"hits": 0, "misses": 0}

    # ─── KVN pages ─────────────────────────────────────────────────────

    def get_kvn(self, full_path: str):
        val = self.kvn_pages.get(full_path)
        if val is not None:
            self._stats["hits"] += 1
            return val
        self._stats["misses"] += 1
        return None

    def set_kvn(self, full_path: str, data: dict):
        self.kvn_pages[full_path] = data

    def invalidate_kvn(self, full_path: str = None):
        """Инвалидация конкретной страницы или всех KVN-страниц."""
        if full_path:
            self.kvn_pages.pop(full_path, None)
        else:
            self.kvn_pages.clear()

    # ─── KVN children ──────────────────────────────────────────────────

    def get_kvn_children(self, parent_id: str):
        val = self.kvn_children.get(parent_id)
        if val is not None:
            self._stats["hits"] += 1
            return val
        self._stats["misses"] += 1
        return None

    def set_kvn_children(self, parent_id: str, data):
        self.kvn_children[parent_id] = data

    def invalidate_kvn_children(self, parent_id: str = None):
        if parent_id:
            self.kvn_children.pop(parent_id, None)
        else:
            self.kvn_children.clear()

    # ─── Teams ─────────────────────────────────────────────────────────

    def get_team(self, slug: str):
        val = self.teams.get(slug)
        if val is not None:
            self._stats["hits"] += 1
            return val
        self._stats["misses"] += 1
        return None

    def set_team(self, slug: str, data: dict):
        self.teams[slug] = data

    def invalidate_team(self, slug: str = None):
        if slug:
            self.teams.pop(slug, None)
        else:
            self.teams.clear()

    # ─── Team lists ────────────────────────────────────────────────────

    def get_team_list(self, cache_key: str):
        val = self.team_lists.get(cache_key)
        if val is not None:
            self._stats["hits"] += 1
            return val
        self._stats["misses"] += 1
        return None

    def set_team_list(self, cache_key: str, data: dict):
        self.team_lists[cache_key] = data

    def invalidate_team_lists(self):
        self.team_lists.clear()

    # ─── Redirects ─────────────────────────────────────────────────────

    def get_redirect(self, path: str):
        val = self.redirects.get(path)
        if val is not None:
            self._stats["hits"] += 1
            return val
        self._stats["misses"] += 1
        return None

    def set_redirect(self, path: str, data: dict):
        self.redirects[path] = data

    def invalidate_redirects(self):
        self.redirects.clear()

    # ─── Search ────────────────────────────────────────────────────────

    def get_search(self, query_key: str):
        val = self.search.get(query_key)
        if val is not None:
            self._stats["hits"] += 1
            return val
        self._stats["misses"] += 1
        return None

    def set_search(self, query_key: str, data):
        self.search[query_key] = data

    # ─── Link resolver ─────────────────────────────────────────────────

    def get_resolved_html(self, html: str) -> str | None:
        key = hashlib.md5(html.encode()).hexdigest()
        val = self.resolved_links.get(key)
        if val is not None:
            self._stats["hits"] += 1
            return val
        self._stats["misses"] += 1
        return None

    def set_resolved_html(self, html: str, resolved: str):
        key = hashlib.md5(html.encode()).hexdigest()
        self.resolved_links[key] = resolved

    # ─── Breadcrumbs ───────────────────────────────────────────────────

    def get_breadcrumbs(self, page_id: str):
        val = self.breadcrumbs.get(page_id)
        if val is not None:
            self._stats["hits"] += 1
            return val
        self._stats["misses"] += 1
        return None

    def set_breadcrumbs(self, page_id: str, data: list):
        self.breadcrumbs[page_id] = data

    # ─── Общее ─────────────────────────────────────────────────────────

    def flush_all(self):
        """Полный сброс всех кэшей."""
        self.kvn_pages.clear()
        self.kvn_children.clear()
        self.teams.clear()
        self.team_lists.clear()
        self.redirects.clear()
        self.search.clear()
        self.resolved_links.clear()
        self.breadcrumbs.clear()
        self._stats = {"hits": 0, "misses": 0}
        logger.info("All caches flushed")

    def stats(self) -> dict:
        """Статистика кэша."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": f"{hit_rate:.1f}%",
            "sizes": {
                "kvn_pages": len(self.kvn_pages),
                "kvn_children": len(self.kvn_children),
                "teams": len(self.teams),
                "team_lists": len(self.team_lists),
                "redirects": len(self.redirects),
                "search": len(self.search),
                "resolved_links": len(self.resolved_links),
                "breadcrumbs": len(self.breadcrumbs),
            },
        }


# Singleton: один экземпляр на весь процесс
cache_service = CacheService()
