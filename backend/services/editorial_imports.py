"""Private, versioned source material and explicit editor-approved publication."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from html import escape, unescape
import hashlib
import json
import re
import uuid

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from models.editorial_import import ImportPayload
from models.content import Person, PersonUpdate, News, NewsUpdate
from models.base import ContentStatus
from services.crud import create_content, update_content, check_slug_unique
from services.editorial_quality import missing_candidate_requirements
from services.source_html import sanitize
from services.cache import cache_service
from services.source_fetcher import canonical_url, SourceFetcher
from services.source_registry import parse_document, source_for_url


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def plain(value):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', value or '')).split())


def name_key(value):
    return ' '.join(re.findall(r'[a-zа-я0-9]+', (value or '').casefold().replace('ё', 'е')))


@lru_cache(maxsize=8192)
def name_pattern(value):
    tokens = name_key(value).split()
    parts = []
    for token in tokens:
        if len(token) > 4 and token.endswith(('ий', 'ый')):
            parts.append(re.escape(token[:-2]) + r'(?:ий|ый|ия|ию|ием|его|ому|ым|ом)')
        elif len(token) >= 4 and not token.endswith(('а', 'я', 'ь', 'е', 'и', 'о', 'у', 'ы')):
            parts.append(re.escape(token) + r'(?:а|у|ом|е|ы|и)?')
        else:
            parts.append(re.escape(token))
    return re.compile(r'(?<!\w)' + r'\s+'.join(parts) + r'(?!\w)')


def match_entities(text, mentioned_names, people, shows):
    normalized = (text or '').casefold().replace('ё', 'е')
    linked = {name_key(name) for name in mentioned_names}
    result = {'related_person_ids': [], 'related_show_ids': []}
    for person in people:
        names = [person.get('title'), person.get('full_name'), *(person.get('aliases') or [])]
        if any(name and len(name_key(name).split()) >= 2 and
               (name_key(name) in linked or name_pattern(name).search(normalized)) for name in names):
            result['related_person_ids'].append(str(person['_id']))
    for show in shows:
        names = [show.get('title'), *(show.get('aliases') or [])]
        for name in names:
            key = name_key(name)
            if not key:
                continue
            multiword = len(key.split()) >= 2
            quoted = re.search(r'[«"“]\s*' + re.escape((name or '').casefold().replace('ё', 'е')) + r'\s*[»"”]', normalized)
            if key in linked or quoted or (multiword and name_pattern(name).search(normalized)):
                result['related_show_ids'].append(str(show['_id']))
                break
    return result


def next_run(now=None, hour=10):
    now = now or datetime.now(timezone.utc)
    moscow = timezone(timedelta(hours=3))
    local = now.astimezone(moscow)
    target = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc).isoformat()


async def catalog(db):
    people = await db.people.find({'status': {'$ne': 'archived'}},
        {'title': 1, 'full_name': 1, 'aliases': 1}).to_list(None)
    shows = await db.shows.find({'status': {'$ne': 'archived'}}, {'title': 1, 'aliases': 1}).to_list(None)
    return people, shows


async def enqueue_document(db, document, actor, entities=None):
    source_url = canonical_url(document['canonical_url'])
    source = source_for_url(source_url)
    kind = document['kind']
    source_hash = digest({key: document.get(key) for key in ('kind', 'title', 'full_name', 'bio', 'body_html')})
    item_id = digest([source_url, source_hash])
    existing = await db.editorial_imports.find_one({'_id': item_id})
    if existing:
        return existing, False
    people, shows = entities if entities is not None else await catalog(db)
    relations = match_entities(document['title'] + ' ' + plain(document['body_html']),
        document.get('mentioned_names', []), people, shows)
    matches = []
    target = None
    if kind == 'biography':
        keys = {name_key(document.get('title')), name_key(document.get('full_name'))} - {''}
        matches = [{'id': str(p['_id']), 'title': p.get('title', '')} for p in people
                   if keys.intersection({name_key(v) for v in [p.get('title'), p.get('full_name'), *(p.get('aliases') or [])]})]
        if len(matches) == 1:
            target = await db.people.find_one({'_id': matches[0]['id']})
    else:
        target = await db.news.find_one({'import_source_url': source_url})
    payload = ImportPayload(
        title=document['title'], slug=('zhaba-' if source.id == 'zhaba' else '') + source_url.rstrip('/').rsplit('/', 1)[-1].removesuffix('.html'),
        full_name=document.get('full_name') or (document['title'] if kind == 'biography' else ''),
        content=sanitize(document['body_html']), excerpt=(document.get('excerpt') or '')[:2000],
        bio=document.get('bio') or {},
        related_person_ids=relations['related_person_ids'] if kind == 'news' else [],
        related_show_ids=relations['related_show_ids'] if kind == 'news' else [],
    ).model_dump(mode='json')
    if target:
        payload['slug'] = target['slug']
        if kind == 'biography':
            payload['title'] = target.get('title') or payload['title']
            payload['full_name'] = target.get('full_name') or payload['full_name']
            payload['bio'] = {**(target.get('bio') or {}), **{k: v for k, v in payload['bio'].items() if v}}
    warnings = ['Проверьте факты и соответствие выбранным людям и шоу. Фотографии не импортированы.']
    if kind == 'biography' and not target:
        warnings.append('Для новой страницы заполните дату и город рождения и подтвердите участие минимум в двух шоу.')
    if len(matches) > 1:
        warnings.append('Найдено несколько совпадений имени: выберите нужную страницу вручную.')
    timestamp = now_iso()
    item = {'_id': item_id, 'source_id': source.id, 'source_hash': source_hash, 'kind': kind,
        'source': {'url': source_url, 'title': document['title'], 'published_at': document.get('published_at'),
                   'modified_at': document.get('modified_at'), 'checked_at': timestamp},
        'payload': payload, 'status': 'pending', 'revision': 1, 'created_at': timestamp, 'updated_at': timestamp,
        'created_by': actor, 'target_id': str(target['_id']) if target else None,
        'target_title': target.get('title') if target else None,
        'base_updated_at': target.get('updated_at') if target else None,
        'matches': matches, 'warnings': warnings,
        'audit': [{'action': 'imported', 'actor': actor, 'at': timestamp}]}
    try:
        await db.editorial_imports.insert_one(item)
        return item, True
    except DuplicateKeyError:
        return await db.editorial_imports.find_one({'_id': item_id}), False


async def import_urls(db, urls, actor):
    # Validate the entire command before making any network requests.
    urls = list(dict.fromkeys(canonical_url(url) for url in urls))
    results = []
    async with SourceFetcher() as fetcher:
        for url in urls:
            try:
                document = parse_document(await fetcher.fetch(url), url)
                item, created = await enqueue_document(db, document, actor)
                results.append({'url': url, 'id': item['_id'], 'status': 'created' if created else 'duplicate'})
            except Exception as exc:
                results.append({'url': url, 'status': 'error', 'error': error_text(exc)})
    return {'results': results}


def error_text(exc):
    if isinstance(exc, HTTPException):
        return str(exc.detail)[:500]
    return str(exc)[:500] or type(exc).__name__


async def get_item(db, item_id):
    item = await db.editorial_imports.find_one({'_id': item_id})
    if not item:
        raise HTTPException(404, 'Материал не найден')
    return item


async def ensure_not_partially_published(db, item):
    collection = db.people if item['kind'] == 'biography' else db.news
    target_id = item.get('target_id') or str(uuid.uuid5(uuid.NAMESPACE_URL, item['source']['url']))
    if await collection.find_one({'_id': target_id, 'editorial_import_id': item['_id'], 'editorial_import_revision': item['revision']}):
        raise HTTPException(409, 'Материал уже записан на сайт. Повторите утверждение без изменения карточки, чтобы завершить публикацию.')


async def edit_item(db, item_id, command, actor):
    item = await get_item(db, item_id)
    if item['status'] not in ('pending', 'conflict') or item['revision'] != command.revision:
        raise HTTPException(409, 'Материал уже изменён или решение принято. Обновите очередь.')
    await ensure_not_partially_published(db, item)
    target_id = command.target_id
    if item['kind'] == 'news' and target_id != item.get('target_id'):
        raise HTTPException(422, 'Целевую новость определяет ссылка источника')
    updates = {'payload': command.payload.model_dump(mode='json'), 'updated_at': now_iso()}
    updates['payload']['content'] = sanitize(updates['payload']['content'])
    if target_id != item.get('target_id') or command.refresh_target:
        collection = db.people if item['kind'] == 'biography' else db.news
        target = await collection.find_one({'_id': target_id}) if target_id else None
        if target_id and not target:
            raise HTTPException(404, 'Выбранная страница человека не найдена')
        updates.update(target_id=target_id, target_title=target.get('title') if target else None,
                       base_updated_at=target.get('updated_at') if target else None)
    # Keeping the original base version makes a stale edit fail even after saving the imported text.
    updates['status'] = 'pending'
    updated = await db.editorial_imports.find_one_and_update(
        {'_id': item_id, 'revision': command.revision, 'status': item['status']},
        {'$set': updates, '$inc': {'revision': 1}, '$push': {'audit': {'action': 'edited', 'actor': actor, 'at': now_iso()}}},
        return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(409, 'Материал изменён другим редактором')
    return updated


async def reject_item(db, item_id, revision, actor):
    item = await get_item(db, item_id)
    if item['status'] == 'rejected' and item['revision'] == revision:
        return item
    if item['status'] in ('pending', 'conflict'):
        await ensure_not_partially_published(db, item)
    updated = await db.editorial_imports.find_one_and_update(
        {'_id': item_id, 'revision': revision, 'status': {'$in': ['pending', 'conflict']}},
        {'$set': {'status': 'rejected', 'updated_at': now_iso()},
         '$push': {'audit': {'action': 'rejected', 'actor': actor, 'at': now_iso()}}}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(409, 'Материал уже изменён или решение принято')
    return updated


def attributed_html(item):
    body = sanitize(item['payload']['content'])
    url = canonical_url(item['source']['url'])
    name = source_for_url(url).name
    return body + f'<p>Источник: <a href="{escape(url, quote=True)}" rel="noopener noreferrer">{escape(name)}</a>.</p>'


async def validate_relations(db, payload):
    for field, collection in [('related_person_ids', db.people), ('related_show_ids', db.shows)]:
        for entity_id in payload.get(field, []):
            if not await collection.find_one({'_id': entity_id, 'status': {'$ne': 'archived'}}):
                raise HTTPException(422, 'Связанная страница отсутствует или архивирована: ' + entity_id)


class ImportedPerson(Person):
    import_source_url: str
    editorial_import_id: str
    editorial_import_revision: int


class ImportedNews(News):
    import_source_url: str
    editorial_import_id: str
    editorial_import_revision: int


class ImportedPersonUpdate(PersonUpdate):
    import_source_url: str
    editorial_import_id: str
    editorial_import_revision: int


class ImportedNewsUpdate(NewsUpdate):
    import_source_url: str
    editorial_import_id: str
    editorial_import_revision: int


async def _publish(db, item, actor):
    payload = item['payload']
    if not plain(sanitize(payload['content'])):
        raise HTTPException(422, 'Заполните текст материала')
    await validate_relations(db, payload)
    biography = item['kind'] == 'biography'
    collection_name = 'people' if biography else 'news'
    collection = db[collection_name]
    target_id = item.get('target_id') or str(uuid.uuid5(uuid.NAMESPACE_URL, item['source']['url']))
    target = await collection.find_one({'_id': target_id})
    already_applied = bool(target and target.get('editorial_import_id') == item['_id']
                           and target.get('editorial_import_revision') == item['revision'])
    marker = {'import_source_url': item['source']['url'], 'editorial_import_id': item['_id'],
              'editorial_import_revision': item['revision']}
    content = attributed_html(item)
    if not already_applied:
        if target and target.get('status') == 'archived':
            raise HTTPException(409, 'Целевая страница архивирована. Сначала восстановите её в редакторе страницы.')
        if item.get('target_id') and (not target or target.get('updated_at') != item.get('base_updated_at')):
            raise HTTPException(409, 'Страница изменилась после импорта. Сверьте изменения и выберите её заново.')
        if target and not item.get('target_id'):
            raise HTTPException(409, 'Этот источник уже опубликован другой версией. Импортируйте актуальную страницу заново.')
        await check_slug_unique(collection_name, payload['slug'], exclude_id=target_id if target else None)
        if biography:
            if not target:
                names = await db.people.find({}, {'title': 1, 'full_name': 1, 'aliases': 1}).to_list(None)
                candidate_keys = {name_key(payload['title']), name_key(payload['full_name'])} - {''}
                if any(candidate_keys.intersection({name_key(v) for v in [p.get('title'), p.get('full_name'), *(p.get('aliases') or [])]}) for p in names):
                    raise HTTPException(409, 'Такой человек уже есть. Выберите существующую страницу.')
                changes = [({'field': 'bio.' + key}, value) for key, value in payload['bio'].items()]
                changes += [({'field': 'module.biography.content', 'label': 'Биография'}, content)]
                changes += [({'field': 'appearance.' + show_id}, {}) for show_id in payload['related_show_ids']]
                missing = missing_candidate_requirements(payload['full_name'], changes)
                if missing:
                    raise HTTPException(422, 'Новая страница не готова: ' + '; '.join(missing))
            modules = deepcopy((target or {}).get('modules') or [])
            bio_module = next((m for m in modules if m.get('type') == 'text_block' and
                'биограф' in str(m.get('title') or (m.get('data') or {}).get('title') or '').casefold()), None)
            if bio_module:
                bio_module.setdefault('data', {})['content'] = content
            else:
                modules.append({'id': 'import-biography', 'type': 'text_block', 'title': 'Биография',
                                'order': len(modules), 'visible': True, 'data': {'title': 'Биография', 'content': content}})
            facts = deepcopy((target or {}).get('facts') or {})
            facts_order = list((target or {}).get('facts_order') or facts)
            for field, label in [('birth_date', 'Дата рождения'), ('birth_place', 'Место рождения'), ('death_date', 'Дата смерти')]:
                if payload['bio'].get(field):
                    facts[label] = payload['bio'][field]
                    if label not in facts_order:
                        facts_order.append(label)
            values = {'title': payload['title'], 'full_name': payload['full_name'], 'slug': payload['slug'],
                      'bio': payload['bio'], 'facts': facts, 'facts_order': facts_order, 'modules': modules, **marker}
            if target:
                await update_content('people', target_id, ImportedPersonUpdate(**values), 'Человек не найден',
                                     expected_updated_at=item.get('base_updated_at'))
            else:
                modules.append({'id': 'facts', 'type': 'facts_table', 'order': len(modules), 'visible': True, 'data': {}})
                await create_content('people', ImportedPerson(id=target_id, **values,
                    status=ContentStatus.PUBLISHED), published_status=ContentStatus.PUBLISHED)
        else:
            values = {'title': payload['title'], 'slug': payload['slug'], 'content': content,
                      'excerpt': payload['excerpt'], 'related_person_ids': payload['related_person_ids'],
                      'related_show_ids': payload['related_show_ids'], **marker}
            if target:
                await update_content('news', target_id, ImportedNewsUpdate(**values), 'Новость не найдена',
                                     expected_updated_at=item.get('base_updated_at'))
            else:
                await create_content('news', ImportedNews(id=target_id, **values, status=ContentStatus.PUBLISHED),
                                     published_status=ContentStatus.PUBLISHED)
    if biography:
        for show_id in payload['related_show_ids']:
            exists = await db.show_appearances.find_one({'person_id': target_id, 'show_id': show_id})
            if not exists:
                await db.show_appearances.update_one({'_id': digest(['source-import', target_id, show_id])},
                    {'$setOnInsert': {'person_id': target_id, 'show_id': show_id, 'source': 'editorial',
                        'source_page_id': show_id, 'source_url': item['source']['url'], 'achievement': 'participant',
                        'created_at': now_iso(), 'updated_at': now_iso()}}, upsert=True)
        from routes.content_people import _link_person_everywhere
        await _link_person_everywhere(target_id)
    await cache_service.invalidate_everywhere(db)
    return {'id': target_id, 'slug': payload['slug'], 'content_type': 'person' if biography else 'news'}


async def approve_item(db, item_id, revision, actor):
    item = await get_item(db, item_id)
    if item['status'] == 'accepted' and item['revision'] == revision:
        return item
    now = now_iso()
    token = uuid.uuid4().hex
    claimed = await db.editorial_imports.find_one_and_update(
        {'_id': item_id, 'revision': revision, '$or': [{'status': 'pending'},
            {'status': 'publishing', 'lease_until': {'$lt': now}}]},
        {'$set': {'status': 'publishing', 'lease_token': token,
                  'lease_until': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}},
        return_document=ReturnDocument.AFTER)
    if not claimed:
        raise HTTPException(409, 'Материал изменён, отклонён или уже утверждается. Обновите очередь.')
    try:
        published = await _publish(db, claimed, actor)
        result = await db.editorial_imports.find_one_and_update({'_id': item_id, 'lease_token': token},
            {'$set': {'status': 'accepted', 'published': published, 'updated_at': now_iso()},
             '$unset': {'lease_token': '', 'lease_until': ''},
             '$push': {'audit': {'action': 'approved', 'actor': actor, 'at': now_iso()}}}, return_document=ReturnDocument.AFTER)
        if not result:
            raise HTTPException(409, 'Блокировка утверждения изменилась')
        return result
    except Exception as exc:
        status = 'conflict' if isinstance(exc, HTTPException) and exc.status_code == 409 else 'pending'
        await db.editorial_imports.update_one({'_id': item_id, 'lease_token': token},
            {'$set': {'status': status, 'last_error': error_text(exc), 'updated_at': now_iso()},
             '$unset': {'lease_token': '', 'lease_until': ''}})
        raise
