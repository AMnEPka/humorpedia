"""Daily source collection with a Mongo lease shared by all backend workers."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import re
import time
import uuid

from fastapi import HTTPException
from pymongo import ReturnDocument

from services.editorial_imports import (catalog, digest, enqueue_document, error_text,
    match_entities, next_run, now_iso, plain)
from services.source_registry import SOURCES, get_source, discover_news, parse_document
from services.source_fetcher import SourceFetcher

logger = logging.getLogger(__name__)
SETTING_ID = 'source_import_24smi'
_tasks = set()


def publication_is_recent(value, since, now=None):
    now = now or datetime.now(timezone.utc)
    published = datetime.fromisoformat((value or '').replace('Z', '+00:00'))
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value or ''):
        # GoStandup publishes a calendar date. Compare that precision without inventing a time.
        moscow = timezone(timedelta(hours=3))
        return since.astimezone(moscow).date() <= published.date() <= now.astimezone(moscow).date()
    if published.tzinfo is None:
        raise ValueError('Не определён часовой пояс даты публикации')
    return since <= published <= now + timedelta(hours=1)


async def settings(db, source_id='24smi'):
    source = get_source(source_id)
    setting_id = 'source_import_' + source.id
    await db.site_settings.update_one({'_id': setting_id}, {'$setOnInsert': {
        'enabled': False, 'hour_moscow': 10, 'next_run_at': next_run(), 'last_result': None}}, upsert=True)
    state = await db.site_settings.find_one({'_id': setting_id})
    return {key: value for key, value in state.items() if key not in ('lease_token', 'lease_until', '_id')} | {
        'source_id': source.id, 'running': bool(state.get('lease_until') and state['lease_until'] > now_iso())}


async def save_settings(db, command):
    await settings(db, command.source_id)
    await db.site_settings.update_one({'_id': 'source_import_' + command.source_id}, {'$set': {
        'enabled': command.enabled, 'hour_moscow': command.hour_moscow,
        'next_run_at': next_run(hour=command.hour_moscow)}})
    return await settings(db, command.source_id)


async def collect_news(db, days, limit, actor, token, source_id='24smi'):
    source = get_source(source_id)
    setting_id = 'source_import_' + source.id
    result = {'checked': 0, 'created': 0, 'duplicates': 0, 'unrelated': 0, 'errors': [], 'truncated': False}
    since = datetime.now(timezone.utc) - timedelta(days=days)
    started = time.monotonic()
    try:
        entities = await catalog(db)
        catalog_hash = digest(entities)
        async with SourceFetcher() as fetcher:
            if source.id == 'zhaba':
                from services.source_channel_import import collect_posts
                await collect_posts(db, fetcher, days, limit, actor, token, result, entities, started)
                return result
            index = await fetcher.fetch(source.discovery_url, resource=True)
            candidates = discover_news(index, since, limit=1000, source_id=source.id)
            for url in candidates:
                seen = await db.source_import_seen.find_one({'_id': digest(url)})
                if seen and seen.get('catalog_hash') == catalog_hash:
                    continue
                if result['checked'] >= limit or time.monotonic() - started > 600:
                    result['truncated'] = True
                    break
                lease = await db.site_settings.update_one({'_id': setting_id, 'lease_token': token},
                    {'$set': {'lease_until': (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}})
                if not lease.matched_count:
                    raise RuntimeError('Блокировка сбора перешла другому исполнителю')
                result['checked'] += 1
                try:
                    document = parse_document(await fetcher.fetch(url), url)
                    if document['kind'] != 'news':
                        raise ValueError('Лента указала материал другого типа')
                    recent = publication_is_recent(document.get('published_at'), since)
                    related = match_entities(document['title'] + ' ' + plain(document['body_html']),
                        document.get('mentioned_names', []), *entities)
                    if not recent or not any(related.values()):
                        result['unrelated'] += 1
                    else:
                        _, created = await enqueue_document(db, document, actor, entities)
                        result['created' if created else 'duplicates'] += 1
                    await db.source_import_seen.update_one({'_id': digest(url)}, {'$set': {
                        'url': url, 'source_id': source.id, 'catalog_hash': catalog_hash, 'checked_at': now_iso()}}, upsert=True)
                except Exception as exc:
                    result['errors'].append({'url': url, 'error': error_text(exc)})
                await db.site_settings.update_one({'_id': setting_id, 'lease_token': token}, {'$set': {'last_result': result}})
    except asyncio.CancelledError:
        result['errors'].append({'url': '', 'error': 'Сбор прерван остановкой backend; возможен повторный запуск.'})
        raise
    except Exception as exc:
        result['errors'].append({'url': '', 'error': error_text(exc)})
    finally:
        state = await db.site_settings.find_one({'_id': setting_id})
        await db.site_settings.update_one({'_id': setting_id, 'lease_token': token}, {
            '$set': {'last_result': result, 'last_finished_at': now_iso(),
                     'next_run_at': next_run(hour=(state or {}).get('hour_moscow', 10))},
            '$unset': {'lease_token': '', 'lease_until': ''}})
    return result


async def start_scan(db, days=3, limit=100, actor='scheduler', *, scheduled=False, source_id='24smi'):
    source = get_source(source_id)
    await settings(db, source.id)
    now = now_iso()
    query = {'_id': 'source_import_' + source.id, '$or': [{'lease_until': {'$exists': False}}, {'lease_until': {'$lte': now}}]}
    if scheduled:
        query.update(enabled=True, next_run_at={'$lte': now})
    token = uuid.uuid4().hex
    claimed = await db.site_settings.find_one_and_update(query, {'$set': {
        'lease_token': token, 'lease_until': (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        'last_run_at': now, 'last_result': None}}, return_document=ReturnDocument.AFTER)
    if not claimed:
        if scheduled:
            return False
        raise HTTPException(409, 'Сбор уже выполняется. Дождитесь отчёта.')
    task = asyncio.create_task(collect_news(db, days, limit, actor, token, source.id), name=source.id + '-news-import')
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return True


async def scheduler_loop(db):
    while True:
        try:
            for source_id in SOURCES:
                await start_scan(db, scheduled=True, source_id=source_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Source import scheduler check failed')
        await asyncio.sleep(60)


async def stop_tasks():
    tasks = list(_tasks)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
