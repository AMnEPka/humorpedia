"""Повторяемое создание обычной страницы из предварительно проверенного пакета."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
from pathlib import Path
import uuid

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from models.content import PersonCreate, TeamCreate, ShowCreate
from models.user import Media
from services.page_builder import now, identifier
from services.page_packages import (COLLECTIONS, json_bytes, page_warnings, unpack_page, remap_assets)


def storage():
    return Path(os.environ.get('PAGE_PACKAGE_DIR', '/app/private/page-packages'))


async def get_import(db, package_id):
    doc = await db.page_package_imports.find_one({'_id': identifier(package_id)})
    if not doc:
        raise HTTPException(404, 'Пакет не найден')
    return doc


def wire(doc):
    keys = ('hash', 'kind', 'page', 'relations', 'assets', 'warnings', 'conflicts', 'status', 'result', 'error')
    return {'id': doc['_id'], **{k: doc[k] for k in keys if k in doc}}


async def analyze(db, doc, omitted=()):
    page, kind = doc['page'], doc['kind']
    conflicts, warnings, resolved = [], page_warnings(kind, page), []
    collection = db[COLLECTIONS[kind]]
    query = {'slug': page['slug']}
    if kind == 'team':
        query['show_id'] = {'$in': [None, '']}
    elif kind == 'show':
        query = {'$or': [{'full_path': page['slug']}, {'slug': page['slug'], 'parent_id': {'$in': [None, '']}}]}
    existing = await collection.find_one(query)
    if existing and existing['_id'] != doc['target_id']:
        conflicts.append('Адрес страницы уже занят: ' + page['slug'])
    if kind == 'show' and await db.teams.find_one({'full_path': page['slug']}):
        conflicts.append('Этот адрес занят командой шоу')
    tag = page.get('primary_tag') or (page.get('name') if kind == 'team' else None)
    if tag and kind in ('person', 'team'):
        same_tag = await collection.find_one({'primary_tag': tag})
        if same_tag and same_tag['_id'] != doc['target_id']:
            conflicts.append('Основной тег уже принадлежит другой странице: ' + tag)
    name_field = 'full_name' if kind == 'person' else 'name'
    same_name = await collection.find_one({name_field: page.get(name_field)})
    if same_name and same_name['_id'] != doc['target_id']:
        warnings.append('Уже есть страница с таким именем/названием; проверьте, что это другая сущность')
    for row in doc['relations']:
        if row['id'] in omitted:
            continue
        target = row.get('target')
        found = None
        if target:
            table = db[COLLECTIONS[target['type']]]
            query = {'slug': target['slug'], 'status': {'$ne': 'archived'}}
            if target['type'] == 'show':
                query = {'full_path': target.get('path') or target['slug'], 'status': {'$ne': 'archived'}}
            found = await table.find_one(query)
            if not found:
                warnings.append(f"Связь {row['id']}: не найдена страница {target['slug']}; исключите связь или создайте целевую страницу")
        resolved.append((row, found))
    return conflicts, warnings, resolved


async def receive(db, raw, actor):
    package = unpack_page(raw)
    manifest = package['manifest']
    package_id = manifest['package_id']
    digest = sha256(json_bytes(manifest)).hexdigest()
    old = await db.page_package_imports.find_one({'_id': package_id})
    if old:
        if old['hash'] != digest:
            raise HTTPException(409, 'Идентификатор пакета уже используется другим содержимым')
    target_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'humorpedia:page-package:' + manifest['entity_key']))
    folder = storage() / package_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'package.zip').write_bytes(raw)
    for aid, content in package['asset_bytes'].items():
        (folder / aid).write_bytes(content)
    if old:
        return old
    doc = {'_id': package_id, 'hash': digest, 'entity_key': manifest['entity_key'], 'target_id': target_id,
           'kind': package['kind'], 'page': package['page'], 'relations': package['relations'],
           'assets': package['assets'], 'status': 'preview', 'created_by': actor, 'created_at': now(),
           'editorial': package['editorial'], 'warnings': [], 'conflicts': []}
    doc['conflicts'], doc['warnings'], _ = await analyze(db, doc)
    try:
        await db.page_package_imports.insert_one(doc)
    except DuplicateKeyError:
        old = await get_import(db, package_id)
        if old['hash'] != digest:
            raise HTTPException(409, 'Конфликт содержимого пакета')
        return old
    return doc


async def copy_assets(db, doc, actor):
    mapping = {}
    for info in doc['assets']:
        relative = f"page-packages/{doc['entity_key']}/{info['id']}.{info['ext']}"
        # Outside StaticFiles: normalization of a URL must not bypass the publication guard.
        path = storage() / 'published' / doc['entity_key'] / f"{info['id']}.{info['ext']}"
        raw = (storage() / doc['_id'] / info['id']).read_bytes()
        if sha256(raw).hexdigest() != info['sha256']:
            raise ValueError('Изображение изменилось после проверки')
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and sha256(path.read_bytes()).hexdigest() != info['sha256']:
            raise HTTPException(409, 'Файл изображения уже изменён; автоматическая замена запрещена')
        if not path.exists():
            temp = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
            temp.write_bytes(raw)
            os.replace(temp, path)
        url = '/uploads/' + relative
        media_id = str(uuid.uuid5(uuid.UUID(doc['entity_key']), 'media:' + info['id']))
        model = Media(id=media_id, filename=path.name, original_name=info['filename'], path=str(path),
                      url=url, mime_type=info['mime'], file_size=info['size'], width=info['width'], height=info['height'], uploaded_by=actor)
        await db.media.update_one({'_id': media_id}, {'$setOnInsert': model.model_dump(mode='json', by_alias=True)}, upsert=True)
        mapping[info['id']] = url
    return mapping


async def create_document(doc, page):
    payload = {**page, 'status': 'archived'}
    if doc['kind'] == 'person':
        from routes.content_people import create_person_record
        return await create_person_record(PersonCreate.model_validate(payload), document_id=doc['target_id'], defer_links=True, page_package_id=doc['_id'])
    if doc['kind'] == 'team':
        from routes.content_teams import create_team_record
        return await create_team_record(TeamCreate.model_validate(payload), document_id=doc['target_id'], defer_links=True, page_package_id=doc['_id'])
    from routes.content_shows import create_show_record
    return await create_show_record(ShowCreate.model_validate(payload), document_id=doc['target_id'], page_package_id=doc['_id'])


async def finish_import(db, doc, target, actor, warnings=()):
    """A published document is the commit point; recovery never rewrites it."""
    prefix = {'person': '/people/', 'team': '/kvn/teams/', 'show': '/shows/'}[doc['kind']]
    result = {'id': doc['target_id'], 'url': prefix + (target.get('full_path') or target['slug']),
              'edit_url': f"/admin/{COLLECTIONS[doc['kind']]}/{doc['target_id']}"}
    from services.cache import cache_service
    await cache_service.invalidate_everywhere(db)
    await db.page_package_imports.update_one({'_id': doc['_id']}, {'$set': {
        'status': 'applied', 'result': result, 'applied_at': now(), 'applied_by': actor,
        'error': '', 'warnings': list(warnings), 'conflicts': []}})
    return await get_import(db, doc['_id'])


async def apply_relations(db, doc, resolved, actor):
    from services.memberships import name_key
    for order, (row, target) in enumerate(resolved):
        row_id = str(uuid.uuid5(uuid.UUID(doc['entity_key']), 'relation:' + row['id']))
        common = {'_id': row_id, 'created_at': now(), 'updated_at': now(), 'created_by': actor,
                  'page_package_id': doc['_id']}
        if row['kind'] == 'appearance':
            existing = await db.show_appearances.find_one({'person_id': doc['target_id'], 'show_id': target['_id']})
            if existing and existing['_id'] != row_id:
                raise HTTPException(409, 'Участие в шоу уже существует; требуется сравнение редактором')
            record = {**common, 'person_id': doc['target_id'], 'person_name': doc['page']['full_name'],
                'person_slug': doc['page']['slug'], 'show_id': target['_id'], 'show_path': target.get('full_path') or target['slug'],
                'source_page_id': target['_id'], 'source_path': target.get('full_path') or target['slug'],
                'source': 'editorial', 'source_title': 'Материалы редактора', 'team_id': None,
                'achievement': row.get('achievement', 'participant'), 'appearances': 0, 'group_name': '', 'group_kind': ''}
            await db.show_appearances.update_one({'_id': row_id}, {'$setOnInsert': record}, upsert=True)
        else:
            record = {**common, 'team_id': doc['target_id'], 'person_id': target['_id'] if target else None,
                'person_name': row['name'], 'name_key': name_key(row['name']), 'person_slug': target['slug'] if target else None,
                'roles': row.get('roles', []), 'from_year': row.get('from_year') or None, 'to_year': row.get('to_year') or None,
                'status': 'former' if row.get('to_year') else 'current', 'season_ids': [], 'note': '', 'order': order,
                'source': 'manual', 'source_ref': doc['_id'], 'link_review_status': 'confirmed' if target else None,
                'matched_by': 'manual' if target else None}
            await db.memberships.update_one({'_id': row_id}, {'$setOnInsert': record}, upsert=True)


async def apply(db, package_id, data, actor):
    doc = await get_import(db, package_id)
    if not data.reviewed:
        raise ValueError('Подтвердите проверку страницы редактором')
    if data.hash != doc['hash']:
        raise HTTPException(409, 'Пакет изменился после предпросмотра')
    if doc['status'] == 'applied':
        return doc
    collection = db[COLLECTIONS[doc['kind']]]
    target = await collection.find_one({'_id': doc['target_id']})
    if target and target.get('page_package_id') == doc['_id'] and target.get('page_package_state') == 'published':
        return await finish_import(db, doc, target, actor, doc.get('warnings', []))
    omitted = set(data.omit_relations)
    if omitted - {r['id'] for r in doc['relations']}:
        raise ValueError('Неизвестная исключаемая связь')
    conflicts, warnings, resolved = await analyze(db, doc, omitted)
    if conflicts:
        raise HTTPException(409, '; '.join(conflicts))
    if any(row.get('target') and not target for row, target in resolved):
        raise HTTPException(409, 'Не все связи сопоставлены. Исключите отсутствующие связи или добавьте целевые страницы.')
    # Атомарное владение заданием. После аварии повтор возможен по истечении lease.
    token = str(uuid.uuid4())
    stamp = now()
    claimed = await db.page_package_imports.find_one_and_update({'_id': doc['_id'], '$or': [
        {'status': {'$in': ['preview', 'error']}}, {'status': 'applying', 'lease_until': {'$lt': stamp}}]},
        {'$set': {'status': 'applying', 'lease_token': token,
                  'lease_until': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}}, return_document=ReturnDocument.AFTER)
    if not claimed:
        latest = await get_import(db, package_id)
        if latest['status'] == 'applied':
            return latest
        raise HTTPException(409, 'Этот импорт уже выполняется. Дождитесь результата.')
    try:
        reservation = {'_id': doc['entity_key'], 'package_id': doc['_id'], 'target_id': doc['target_id'], 'omit_relations': sorted(omitted)}
        await db.page_package_entities.update_one({'_id': doc['entity_key']}, {'$setOnInsert': reservation}, upsert=True)
        owner = await db.page_package_entities.find_one({'_id': doc['entity_key']})
        if owner['package_id'] != doc['_id']:
            raise HTTPException(409, 'Эта заготовка уже импортировалась. Изменяйте страницу обычным редактором.')
        if owner['omit_relations'] != sorted(omitted):
            raise HTTPException(409, 'При восстановлении используйте ранее выбранный набор связей')
        # Повторная проверка исходного файла ловит изменение временного хранилища.
        package = unpack_page((storage() / doc['_id'] / 'package.zip').read_bytes())
        if sha256(json_bytes(package['manifest'])).hexdigest() != doc['hash']:
            raise ValueError('Файл пакета изменился после проверки')
        mapping = await copy_assets(db, doc, actor)
        page = remap_assets(doc['page'], mapping)
        collection = db[COLLECTIONS[doc['kind']]]
        target = await collection.find_one({'_id': doc['target_id']})
        if not target:
            await create_document(doc, page)
            target = await collection.find_one({'_id': doc['target_id']})
        elif (target.get('page_package_id') != doc['_id'] or target.get('page_package_state') != 'preparing'
              or target.get('status') != 'archived' or target.get('page_package_manual_change')
              or target.get('updated_at') != target.get('page_package_initial_updated_at')):
            raise HTTPException(409, 'Состояние созданной страницы изменено редактором')
        await apply_relations(db, doc, resolved, actor)
        # Согласование состава не должно задублировать ручные записи.
        if doc['kind'] == 'team':
            from services.memberships import import_team_rosters
            await import_team_rosters(db, await collection.find_one({'_id': doc['target_id']}))
        elif doc['kind'] == 'person':
            from routes.content_people import _link_person_everywhere
            await _link_person_everywhere(doc['target_id'])
        elif doc['kind'] == 'show':
            from services.show_appearances import link_participant_cards
            linked = await link_participant_cards(db, await collection.find_one({'_id': doc['target_id']}))
            await collection.update_one({'_id': doc['target_id'], 'status': 'archived'}, {'$set': {'modules': linked['modules']}})
        published = await collection.find_one_and_update({
            '_id': doc['target_id'], 'status': 'archived', 'page_package_state': 'preparing',
            'updated_at': target['updated_at'], 'page_package_manual_change': {'$ne': True}}, {'$set': {
            'status': 'published', 'updated_at': now(), 'updated_by': actor, 'page_package_state': 'published'}},
            return_document=ReturnDocument.AFTER)
        if not published:
            raise HTTPException(409, 'Страница изменена редактором во время импорта')
        await finish_import(db, doc, published, actor, warnings)
    except Exception as exc:
        message = str(exc.detail) if isinstance(exc, HTTPException) else 'Импорт прерван; исправьте причину и повторите применение'
        await db.page_package_imports.update_one({'_id': doc['_id'], 'lease_token': token}, {'$set': {'status': 'error', 'error': message}})
        raise
    return await get_import(db, package_id)
