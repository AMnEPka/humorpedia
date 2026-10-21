"""HTTP/Mongo season write contracts, isolated DB: SEASON_WRITE_INTEGRATION=1."""
from copy import deepcopy
import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import competitions, content_kvn
from services.competitions import sync_from_kvn_page
from utils import database
from utils.auth import create_token


@pytest.fixture
def season_api(monkeypatch):
    if os.environ.get('SEASON_WRITE_INTEGRATION') != '1':
        pytest.skip('Нужен SEASON_WRITE_INTEGRATION=1 с локальной MongoDB')
    name = 'humorpedia_season_test_' + uuid.uuid4().hex
    monkeypatch.setenv('DB_NAME', name)
    app = FastAPI()
    app.include_router(content_kvn.router, prefix='/api')
    app.include_router(competitions.router, prefix='/api')
    with TestClient(app) as client:
        async def setup():
            await database.close_db()
            db = await database.get_db()
            assert db.name == name and name.startswith('humorpedia_season_test_')
            await db.users.insert_one({'_id': 'editor', 'role': 'editor', 'username': 'Редактор'})
            await db.kvn.insert_one({'_id': 'league', 'title': 'Высшая лига', 'full_path': 'kvn/vl-kvn'})
            page = {
                '_id': 'page-1', 'id': 'page-1', 'title': 'Сезон 2000', 'slug': 'vl-2000',
                'full_path': 'kvn/vl-kvn/vl-2000', 'status': 'published',
                'updated_at': '2025-01-01T00:00:00+00:00',
                'season_data': {
                    'year': 2000, 'league_slug': 'vl-kvn', 'description': 'Исходный текст',
                    'stages': [{'name': 'Финал', 'games': [{'name': 'Игра', 'teams': [
                        {'person_id': 'person-42', 'team_name': 'Участник', 'place': 1},
                    ]}]}],
                },
            }
            await db.kvn.insert_one(page)
            season = await sync_from_kvn_page(db, page)
            return db, season['_id']
        db, season_id = client.portal.call(setup)
        token, _ = create_token('editor', 'editor')
        client.headers['Authorization'] = 'Bearer ' + token
        try:
            yield client, db, season_id
        finally:
            async def cleanup():
                assert db.name == name and name.startswith('humorpedia_season_test_')
                await db.client.drop_database(name)
                await database.close_db()
            client.portal.call(cleanup)


def snapshot(client, db):
    async def read():
        return {collection: await db[collection].find({}).sort('_id', 1).to_list(None)
                for collection in ('kvn', 'seasons', 'participations', 'tags')}
    return client.portal.call(read)


def test_season_versions_round_trip_through_both_http_apis(season_api):
    client, db, season_id = season_api
    page_url = '/api/content/kvn/page-1'
    season_url = '/api/competitions/seasons/' + season_id
    page = client.get(page_url + '?raw=true').json()
    season = client.get(season_url).json()
    before = snapshot(client, db)
    for payload in ({'description': 'Без версии'},
                    {'description': 'Старая версия', 'expected_updated_at': '2000-01-01T00:00:00Z'}):
        assert client.put(season_url, json=payload).status_code == 409
    assert client.put(page_url, json={'season_data': page['season_data'], 'tags': ['Не записывать']}).status_code == 409
    assert snapshot(client, db) == before

    response = client.put(season_url, json={
        'description': 'Каноническая правка', 'expected_updated_at': season['updated_at'],
    })
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['stages'][0]['games'][0]['results'][0]['person_id'] == 'person-42'
    assert saved['updated_at'] != season['updated_at']
    # A legacy form opened before the canonical write cannot overwrite it.
    before = snapshot(client, db)
    assert client.put(page_url, json={
        'season_data': page['season_data'], 'expected_updated_at': page['updated_at'],
    }).status_code == 409
    assert snapshot(client, db) == before

    reloaded = client.get(page_url + '?raw=true').json()
    assert reloaded['season_data']['description'] == 'Каноническая правка'
    changed = deepcopy(reloaded['season_data'])
    changed['description'] = 'Правка через старый редактор'
    response = client.put(page_url, json={
        'season_data': changed, 'expected_updated_at': reloaded['updated_at'],
    })
    assert response.status_code == 200, response.text
    assert response.json()['updated_at'] != reloaded['updated_at']
    current = client.get(season_url).json()
    assert current['description'] == changed['description']
    assert current['stages'][0]['games'][0]['results'][0]['person_id'] == 'person-42'
    before = snapshot(client, db)
    assert client.put(season_url, json={
        'description': 'Устаревшая правка', 'expected_updated_at': saved['updated_at'],
    }).status_code == 409
    assert snapshot(client, db) == before
    assert all('expected_updated_at' not in doc
               for docs in before.values() for doc in docs)


@pytest.mark.parametrize('collection', ['kvn', 'seasons'])
@pytest.mark.parametrize('stored_null', [False, True])
def test_explicit_null_only_initializes_unversioned_documents(season_api, collection, stored_null):
    client, db, season_id = season_api
    target_id = 'page-1' if collection == 'kvn' else season_id
    async def remove_version():
        update = {'$set': {'updated_at': None}} if stored_null else {'$unset': {'updated_at': ''}}
        await db[collection].update_one({'_id': target_id}, update)
    client.portal.call(remove_version)
    if collection == 'kvn':
        url = '/api/content/kvn/page-1'
        payload = {'season_data': client.get(url + '?raw=true').json()['season_data']}
    else:
        url = '/api/competitions/seasons/' + season_id
        payload = {'description': 'Первая версионированная правка'}
    assert client.put(url, json=payload).status_code == 409
    payload['expected_updated_at'] = None
    response = client.put(url, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()['updated_at']
    before = snapshot(client, db)
    assert client.put(url, json=payload).status_code == 409
    assert snapshot(client, db) == before
