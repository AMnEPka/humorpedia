"""Resumable collection of the one configured public Telegram channel."""
from datetime import datetime, timedelta, timezone
import time
from urllib.parse import urlsplit

from fastapi import HTTPException

from services.editorial_imports import digest, enqueue_document, error_text, now_iso, plain
from services.source_adapters.zhaba import parse_feed, current_page_url, next_page_url
from services.source_registry import canonical_url, source_for_url

SETTING_ID = 'source_import_zhaba'
MAX_PAGES = 10


def feed_url(value):
    url = canonical_url(value, resource=True)
    if source_for_url(url, resource=True).id != 'zhaba' or urlsplit(url).path != '/s/zhabqua':
        raise ValueError('Продолжение должно указывать на публичную ленту ЖАБЫ')
    return url


def post_date(document):
    value = datetime.fromisoformat((document.get('published_at') or '').replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Не определён часовой пояс публикации поста')
    if value > datetime.now(timezone.utc) + timedelta(hours=1):
        raise ValueError('Дата поста находится в будущем')
    return value


async def checkpoint(db, token, result, updates=None, *, complete=False):
    values = {'lease_until': (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
              'last_result': result, **(updates or {})}
    change = {'$set': values}
    if complete:
        change['$unset'] = {'pending_page': '', 'pending_highwater': '', 'pending_since': ''}
    written = await db.site_settings.update_one({'_id': SETTING_ID, 'lease_token': token}, change)
    if not written.matched_count:
        raise HTTPException(409, 'Блокировка сбора постов перешла другому исполнителю')


async def collect_posts(db, fetcher, days, limit, actor, token, result, entities, started):
    state = await db.site_settings.find_one({'_id': SETTING_ID}) or {}
    cursor = int(state.get('last_post_id') or 0)
    highwater = int(state.get('pending_highwater') or cursor)
    since = datetime.fromisoformat(state['pending_since']) if state.get('pending_since') else datetime.now(timezone.utc) - timedelta(days=days)
    page = feed_url(state.get('pending_page') or 'https://t.me/s/zhabqua')
    visited = set()
    result.update(without_text=0, pages=0)
    for _ in range(MAX_PAGES):
        if result['checked'] >= limit or time.monotonic() - started > 600:
            result['truncated'] = True
            return
        if page in visited:
            raise ValueError('Лента повторяет уже просмотренную страницу')
        visited.add(page)
        await checkpoint(db, token, result)
        html = await fetcher.fetch(page, resource=True)
        records = parse_feed(html)
        if not records:
            raise ValueError('В ленте не найдены посты ЖАБЫ; позиция сбора сохранена')
        snapshot = current_page_url(html)
        if not snapshot:
            raise ValueError('В ленте отсутствует ссылка на текущую страницу; позиция не изменена')
        snapshot = feed_url(snapshot)
        previous = next_page_url(html)
        previous = feed_url(previous) if previous else None
        records = sorted(records, key=lambda record: int(record['post_id']), reverse=True)
        for record in records:
            url = canonical_url(record['canonical_url'])
            if source_for_url(url).id != 'zhaba' or int(url.rsplit('/', 1)[-1]) != int(record['post_id']):
                raise ValueError('Идентификатор поста не соответствует ссылке канала')
        highwater = max(highwater, *(int(record['post_id']) for record in records))
        result['pages'] += 1
        await checkpoint(db, token, result, {'pending_page': snapshot, 'pending_highwater': highwater, 'pending_since': since.isoformat()})
        for record in records:
            if int(record['post_id']) <= cursor:
                continue
            url = canonical_url(record['canonical_url'])
            seen = await db.source_import_seen.find_one({'_id': digest(url), 'channel_processed': True})
            if seen:
                continue
            if result['checked'] >= limit or time.monotonic() - started > 600:
                result['truncated'] = True
                return
            try:
                published = post_date(record)
                result['checked'] += 1
                if not cursor and published < since:
                    result['unrelated'] += 1
                elif not plain(record['body_html']):
                    result['without_text'] += 1
                else:
                    _, created = await enqueue_document(db, record, actor, entities)
                    result['created' if created else 'duplicates'] += 1
                await db.source_import_seen.update_one({'_id': digest(url)}, {'$set': {
                    'url': url, 'source_id': 'zhaba', 'channel_processed': True, 'checked_at': now_iso()}}, upsert=True)
                await checkpoint(db, token, result)
            except HTTPException as exc:
                if exc.status_code == 409:
                    raise
                result['errors'].append({'url': url, 'error': error_text(exc)})
                result['truncated'] = True
                return
            except Exception as exc:
                result['errors'].append({'url': url, 'error': error_text(exc)})
                result['truncated'] = True
                return
        # Only advance after reaching the previous cursor, the initial date boundary or the end.
        next_before = int(urlsplit(previous).query.split('=', 1)[1]) if previous and urlsplit(previous).query else None
        reached_cursor = bool(cursor and next_before is not None and next_before <= cursor)
        reached_date = not cursor and all(post_date(record) < since for record in records)
        if not previous or reached_cursor or reached_date:
            await checkpoint(db, token, result, {'last_post_id': highwater}, complete=True)
            return
        if previous == page or previous == snapshot:
            raise ValueError('Ссылка продолжения не ведёт к более старым постам')
        await checkpoint(db, token, result, {'pending_page': previous, 'pending_highwater': highwater, 'pending_since': since.isoformat()})
        page = previous
    result['truncated'] = True
