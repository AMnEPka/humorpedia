"""Интеграция с отдельной временной MongoDB: PAGE_PACKAGE_INTEGRATION=1."""
from copy import deepcopy
import os
import uuid
from io import BytesIO

from PIL import Image
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles

from routes import page_packages as packages
from routes import content_people, content_teams, content_shows, memberships
from services.page_packages import pack_page, seed_page, image_info, MEDIA_FIELDS
from utils import database
from utils.auth import create_token


@pytest.fixture
def integration(monkeypatch, tmp_path):
    if os.environ.get('PAGE_PACKAGE_INTEGRATION') != '1':
        pytest.skip('Нужен отдельный запуск PAGE_PACKAGE_INTEGRATION=1 с локальной MongoDB')
    name = 'humorpedia_package_test_' + uuid.uuid4().hex
    monkeypatch.setenv('DB_NAME', name)
    monkeypatch.setenv('PAGE_PACKAGE_DIR', str(tmp_path / 'private'))
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path / 'uploads'))
    app = FastAPI()
    app.include_router(packages.media_router)
    for router in (packages.router, content_people.router, content_teams.router, content_shows.router, memberships.router):
        app.include_router(router, prefix='/api')
    (tmp_path / 'uploads').mkdir()
    app.mount('/uploads', StaticFiles(directory=tmp_path / 'uploads'))
    with TestClient(app) as client:
        async def setup():
            await database.close_db()
            db = await database.get_db()
            assert db.name == name and name.startswith('humorpedia_package_test_')
            await db.users.insert_one({'_id': 'editor', 'role': 'editor', 'username': 'Редактор'})
            await db.people.create_index('slug', unique=True)
            await db.shows.create_index('full_path', unique=True, sparse=True)
            await db.teams.create_index([('show_id', 1), ('slug', 1)], unique=True)
            return db
        db = client.portal.call(setup)
        token, _ = create_token('editor', 'editor')
        client.headers['Authorization'] = 'Bearer ' + token
        try:
            yield client, db, tmp_path
        finally:
            async def cleanup():
                assert db.name == name and name.startswith('humorpedia_package_test_')
                await db.client.drop_database(name)
                await database.close_db()
            client.portal.call(cleanup)


def package(kind):
    page = seed_page(kind, {'name': 'Проверка редактора'})
    page['aliases'] = ['Редакторская проверка']
    page['modules'].append({'id': 'bio', 'type': 'text_block', 'order': 4, 'visible': True,
                            'data': {'title': 'Биография', 'content': '<p>Исходный текст.</p>'}})
    image = BytesIO()
    Image.new('RGB', (15, 15)).save(image, 'PNG')
    raw = image.getvalue()
    page[MEDIA_FIELDS[kind]] = {'url': 'asset:photo', 'alt': 'Фото'}
    return {'id': str(uuid.uuid4()), 'kind': kind, 'revision': 1, 'page': page, 'materials': {},
            'relations': [], 'assets': [dict(image_info(raw, 'photo.png'), id='photo')]}, {'photo': raw}


@pytest.mark.parametrize('kind,path', [('person','people'), ('team','teams'), ('show','shows')])
def test_imported_page_is_fully_editable_through_normal_editor_api(integration, kind, path):
    client, db, _ = integration
    draft, assets = package(kind)
    data = pack_page(draft, assets)
    response = client.post('/api/page-packages/preview', files={'file': ('page.zip', data, 'application/zip')})
    assert response.status_code == 200, response.text
    preview = response.json()
    async def count():
        return await db[path].count_documents({})
    assert client.portal.call(count) == 0
    endpoint = f"/api/page-packages/{preview['id']}/apply"
    result = client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True})
    assert result.status_code == 200, result.text
    applied = result.json()
    target = applied['result']['id']
    assert target != draft['id']
    assert client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True}).json()['result']['id'] == target
    assert client.portal.call(count) == 1
    raw = client.get(f'/api/content/{path}/{target}?raw=true').json()
    assert raw['aliases'] == ['Редакторская проверка']
    assert raw[MEDIA_FIELDS[kind]]['url'].startswith('/uploads/page-packages/')
    changed_modules = deepcopy(raw['modules'])
    next(m for m in changed_modules if m['id'] == 'bio')['data']['content'] = '<p>Ручная редактура.</p>'
    update = {'title': 'Название редактора', 'modules': changed_modules, 'facts': {'Факт': 'Исправлен'},
              'facts_order': ['Факт'], 'seo': {'meta_title': 'Новый SEO заголовок'}, 'tags': ['Редактура']}
    response = client.put(f'/api/content/{path}/{target}', json=update)
    assert response.status_code == 200, response.text
    edited = client.get(f'/api/content/{path}/{target}?raw=true').json()
    assert edited['title'] == 'Название редактора'
    assert edited['facts']['Факт'] == 'Исправлен'
    assert next(m for m in edited['modules'] if m['id'] == 'bio')['data']['content'] == '<p>Ручная редактура.</p>'
    # Повтор старого импорта не отменяет новую ручную редактуру.
    client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True})
    assert client.get(f'/api/content/{path}/{target}?raw=true').json()['title'] == 'Название редактора'


def test_slug_conflict_does_not_replace_and_unauthorized_import_rejected(integration):
    client, db, _ = integration
    draft, assets = package('person')
    async def insert():
        await db.people.insert_one({'_id': 'existing', 'slug': draft['page']['slug'], 'title': 'Существующий'})
    client.portal.call(insert)
    preview = client.post('/api/page-packages/preview', files={'file': ('page.zip', pack_page(draft, assets))}).json()
    assert preview['conflicts']
    assert client.post(f"/api/page-packages/{preview['id']}/apply", json={'hash': preview['hash'], 'reviewed': True}).status_code == 409
    client.headers.clear()
    assert client.get(f"/api/page-packages/{preview['id']}").status_code == 401


def test_failed_team_import_is_private_and_retry_keeps_one_manual_roster(integration, monkeypatch):
    client, db, _ = integration
    draft, assets = package('team')
    draft['relations'] = [{'id': 'member-one', 'kind': 'membership', 'name': 'Иван Иванов', 'roles': ['капитан']}]
    preview = client.post('/api/page-packages/preview', files={'file': ('page.zip', pack_page(draft, assets))}).json()
    from services import page_package_import as service
    original = service.apply_relations
    async def failed(*args, **kwargs):
        await original(*args, **kwargs)
        raise ValueError('Имитированный сбой после записи состава')
    monkeypatch.setattr(service, 'apply_relations', failed)
    endpoint = f"/api/page-packages/{preview['id']}/apply"
    assert client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True}).status_code == 422
    auth = client.headers.pop('Authorization')
    assert client.get('/api/competitions/teams/' + draft['page']['slug'] + '/members').status_code == 404
    assert client.get('/api/content/teams/' + draft['page']['slug']).status_code == 404
    assert client.get('/api/content/teams/' + draft['page']['slug'] + '?raw=true').status_code == 404
    media_url = '/uploads/page-packages/' + draft['id'] + '/photo.png'
    assert client.get(media_url).status_code == 404
    assert client.get(media_url.replace('/uploads/', '/uploads//')).status_code == 404
    client.headers['Authorization'] = auth
    monkeypatch.setattr(service, 'apply_relations', original)
    response = client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True})
    assert response.status_code == 200, response.text
    result = response.json()['result']
    async def count():
        return await db.memberships.count_documents({'team_id': result['id']})
    assert client.portal.call(count) == 1
    roster = client.get('/api/competitions/teams/' + result['id'] + '/members').json()
    assert roster['current'][0]['source'] == 'manual'
    assert client.get(media_url).status_code == 200


def test_manual_change_to_interrupted_import_blocks_reapplication(integration, monkeypatch):
    client, db, _ = integration
    draft, assets = package('team')
    draft['relations'] = [{'id': 'member', 'kind': 'membership', 'name': 'Иван Иванов'}]
    preview = client.post('/api/page-packages/preview', files={'file': ('page.zip', pack_page(draft, assets))}).json()
    endpoint = f"/api/page-packages/{preview['id']}/apply"
    from services import page_package_import as service
    original = service.apply_relations
    async def failed(*args):
        await original(*args)
        raise ValueError('До публикации')
    monkeypatch.setattr(service, 'apply_relations', failed)
    assert client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True}).status_code == 422
    async def lookup():
        return await db.memberships.find_one({})
    row = client.portal.call(lookup)
    assert client.delete('/api/competitions/memberships/' + row['_id']).status_code == 200
    monkeypatch.setattr(service, 'apply_relations', original)
    assert client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True}).status_code == 409
    assert client.portal.call(lookup) is None


def test_recovery_after_publication_preserves_editor_archive_and_deleted_roster(integration, monkeypatch):
    client, db, _ = integration
    draft, assets = package('team')
    draft['relations'] = [{'id': 'member', 'kind': 'membership', 'name': 'Иван Иванов'}]
    preview = client.post('/api/page-packages/preview', files={'file': ('page.zip', pack_page(draft, assets))}).json()
    endpoint = f"/api/page-packages/{preview['id']}/apply"
    from services.cache import cache_service
    original = cache_service.invalidate_everywhere
    async def failed(*args):
        raise ValueError('Сбой после публикации')
    monkeypatch.setattr(cache_service, 'invalidate_everywhere', failed)
    assert client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True}).status_code == 422
    async def lookup():
        return await db.teams.find_one({'slug': draft['page']['slug']}), await db.memberships.find_one({})
    target, row = client.portal.call(lookup)
    monkeypatch.setattr(cache_service, 'invalidate_everywhere', original)
    assert client.put('/api/content/teams/' + target['_id'], json={'status': 'archived', 'title': 'Ручная правка'}).status_code == 200
    assert client.delete('/api/competitions/memberships/' + row['_id']).status_code == 200
    assert client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True}).status_code == 200
    after, row = client.portal.call(lookup)
    assert after['status'] == 'archived' and after['title'] == 'Ручная правка'
    assert row is None


def test_incomplete_show_is_private_on_all_read_routes(integration, monkeypatch):
    client, db, _ = integration
    draft, assets = package('show')
    preview = client.post('/api/page-packages/preview', files={'file': ('page.zip', pack_page(draft, assets))}).json()
    from services import page_package_import as service
    async def failed(*args):
        raise ValueError('До публикации')
    monkeypatch.setattr(service, 'apply_relations', failed)
    assert client.post(f"/api/page-packages/{preview['id']}/apply", json={'hash': preview['hash'], 'reviewed': True}).status_code == 422
    client.headers.clear()
    for suffix in (draft['page']['slug'], draft['page']['slug'] + '?raw=true', 'by-path/' + draft['page']['slug'], draft['page']['slug'] + '/children'):
        assert client.get('/api/content/shows/' + suffix).status_code == 404
    assert client.get('/api/content/shows-hierarchy').json()['total'] == 0


def test_portable_relations_resolve_target_ids_and_remain_editable(integration):
    client, db, _ = integration
    show = client.post('/api/content/shows', json={'title': 'Проект', 'name': 'Проект', 'slug': 'project', 'status': 'published'}).json()
    draft, assets = package('person')
    draft['relations'] = [{'id': 'show-one', 'kind': 'appearance', 'target': {'type': 'show', 'slug': 'project'}, 'achievement': 'finalist'}]
    preview = client.post('/api/page-packages/preview', files={'file': ('page.zip', pack_page(draft, assets))}).json()
    response = client.post(f"/api/page-packages/{preview['id']}/apply", json={'hash': preview['hash'], 'reviewed': True})
    assert response.status_code == 200, response.text
    person_id = response.json()['result']['id']
    async def related():
        from services.show_appearances import public_rows
        return await public_rows(db, person_id=person_id)
    rows = client.portal.call(related)
    assert len(rows) == 1 and 'Финалист' in rows[0]['caption']
    assert rows[0]['show_url'] == '/shows/project'
    # Show cards resolve portable slugs against this database rather than carrying source IDs.
    team_show, image = package('show')
    team_show['page']['slug'] = 'second-project'
    team_show['page']['modules'].append({'id': 'participants', 'type': 'participants', 'order': 5, 'visible': True,
        'data': {'items': [{'name': draft['page']['full_name'], 'person_slug': draft['page']['slug']}]}})
    preview2 = client.post('/api/page-packages/preview', files={'file': ('page.zip', pack_page(team_show, image))}).json()
    response2 = client.post(f"/api/page-packages/{preview2['id']}/apply", json={'hash': preview2['hash'], 'reviewed': True})
    assert response2.status_code == 200, response2.text
    imported = client.get('/api/content/shows/' + response2.json()['result']['id'] + '?raw=true').json()
    participant = next(m for m in imported['modules'] if m['type'] == 'participants')['data']['items'][0]
    assert participant['person_url'] == '/people/' + draft['page']['slug']
    assert 'person_id' not in participant


@pytest.mark.parametrize('kind,path', [('person', 'people'), ('team', 'teams'), ('show', 'shows')])
def test_direct_create_and_zip_import_keep_same_domain_fields(integration, kind, path):
    client, db, _ = integration
    draft, _assets = package(kind)
    draft['assets'] = []
    draft['page'][MEDIA_FIELDS[kind]] = None
    response = client.post('/api/content/' + path, json={**draft['page'], 'status': 'published'})
    assert response.status_code == 200, response.text
    direct_id = response.json()['id']

    async def read_then_remove_direct():
        assert db.name.startswith('humorpedia_package_test_')
        record = await db[path].find_one({'_id': direct_id})
        await db[path].delete_one({'_id': direct_id})
        return record
    direct = client.portal.call(read_then_remove_direct)
    response = client.post('/api/page-packages/preview', files={'file': ('page.zip', pack_page(draft, {}))})
    assert response.status_code == 200, response.text
    preview = response.json()
    response = client.post('/api/page-packages/' + preview['id'] + '/apply',
                           json={'hash': preview['hash'], 'reviewed': True})
    assert response.status_code == 200, response.text

    async def imported_record():
        return await db[path].find_one({'_id': response.json()['result']['id']})
    imported = client.portal.call(imported_record)

    def domain_fields(record):
        record = deepcopy(record)
        for key in list(record):
            if key in ('_id', 'created_at', 'updated_at', 'updated_by') or key.startswith('page_package_'):
                record.pop(key)
        # Сравниваем и новые UUID модулей, и ссылки roster_import на эти UUID.
        module_ids = {module['id']: index for index, module in enumerate(record.get('modules', []))}
        for module in record.get('modules', []):
            module['id'] = module_ids[module['id']]
        for roster in record.get('roster_import', []):
            roster['module_id'] = module_ids.get(roster['module_id'], roster['module_id'])
        return record

    assert domain_fields(imported) == domain_fields(direct)
