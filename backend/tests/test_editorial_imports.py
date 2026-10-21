"""Source matching plus API integration against an isolated disposable MongoDB."""
import os
import uuid
import asyncio
from copy import deepcopy

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from services.source_fetcher import canonical_url, SourceFetcher
from services.editorial_imports import match_entities, next_run
from routes import editorial_imports as route


@pytest.mark.parametrize('url', [
    'http://24smi.org/news/1-test.html', 'https://24smi.org.evil.test/news/1-a.html',
    'https://user@24smi.org/news/1-a.html', 'https://24smi.org:444/news/1-a.html',
    'https://127.0.0.1/news/1-a.html', 'https://24smi.org/celebrity/search/',
    'https://24smi.org/news/%2e%2e/admin',
])
def test_fetcher_rejects_untrusted_urls(url):
    with pytest.raises(ValueError):
        canonical_url(url)


def test_source_identity_ignores_tracking_parameters():
    assert canonical_url('https://www.24smi.org/news/123-test.html?utm_source=x#x') == 'https://24smi.org/news/123-test.html'


@pytest.mark.parametrize('url,expected', [
    ('https://vokrug.tv/person/show/viktor_komarov/?utm_source=x', 'https://www.vokrug.tv/person/show/viktor_komarov/'),
    ('https://www.vokrug.tv/article/show/123-test/', 'https://www.vokrug.tv/article/show/123-test/'),
    ('https://www.gostandup.ru/comedians/kostya_pushkin#bio', 'https://gostandup.ru/comedians/kostya_pushkin'),
    ('https://gostandup.ru/articles/test_article/', 'https://gostandup.ru/articles/test_article'),
])
def test_multiple_source_canonical_urls(url, expected):
    assert canonical_url(url) == expected


@pytest.mark.parametrize('url', [
    'https://www.vokrug.tv.evil.test/person/show/person/',
    'https://gostandup.ru@127.0.0.1/comedians/person',
    'https://gostandup.ru/events/concert', 'https://www.vokrug.tv/person/',
    'https://gostandup.ru/articles/test%2fsecret',
])
def test_new_sources_reject_other_hosts_and_non_content_paths(url):
    with pytest.raises(ValueError):
        canonical_url(url)


def test_fetcher_uses_separate_robots_for_each_source_and_rejects_cross_source_redirect():
    requests = []
    def respond(request):
        requests.append((request.url.host, request.url.path))
        if request.url.path == '/robots.txt':
            return httpx.Response(200, headers={'content-type': 'text/plain'}, text='User-agent: *\nAllow: /')
        if request.url.host == 'www.vokrug.tv':
            return httpx.Response(302, headers={'location': 'https://gostandup.ru/articles/test'})
        return httpx.Response(200, headers={'content-type': 'text/html'}, text='<p>Text</p>')
    async def run():
        async with SourceFetcher(transport=httpx.MockTransport(respond), delay=0) as fetcher:
            assert await fetcher.fetch('https://gostandup.ru/comedians/kostya_pushkin') == '<p>Text</p>'
            with pytest.raises(ValueError, match='источник'):
                await fetcher.fetch('https://www.vokrug.tv/article/show/123-test/')
    asyncio.run(run())
    assert requests == [('gostandup.ru', '/robots.txt'), ('gostandup.ru', '/comedians/kostya_pushkin'),
        ('www.vokrug.tv', '/robots.txt'), ('www.vokrug.tv', '/article/show/123-test/')]


def test_matching_handles_names_but_not_surname_or_generic_show_alone():
    people = [{'_id': 'p', 'title': 'Михаил Галустян', 'aliases': []}]
    shows = [{'_id': 's', 'title': 'Звёзды'}]
    assert match_entities('Концерт Михаила Галустяна', [], people, shows)['related_person_ids'] == ['p']
    assert match_entities('Галустян и звёзды на небе', [], people, shows) == {'related_person_ids': [], 'related_show_ids': []}
    assert match_entities('Участник шоу «Звёзды»', [], people, shows)['related_show_ids'] == ['s']


def test_schedule_uses_moscow_time():
    from datetime import datetime, timezone
    now = datetime(2026, 10, 21, 6, 59, tzinfo=timezone.utc)
    assert next_run(now, 10) == '2026-10-21T07:00:00+00:00'
    assert next_run(now.replace(hour=7), 10) == '2026-10-22T07:00:00+00:00'


def test_calendar_publication_dates_use_moscow_day_without_invented_time():
    from datetime import datetime, timedelta, timezone
    from services.source_import_scheduler import publication_is_recent
    now = datetime(2026, 10, 21, 22, tzinfo=timezone.utc)  # already Oct 22 in Moscow
    since = now - timedelta(days=3)
    assert publication_is_recent('2026-10-22', since, now)
    assert not publication_is_recent('2026-10-23', since, now)
    assert not publication_is_recent('2026-10-01', since, now)
    with pytest.raises(ValueError, match='пояс'):
        publication_is_recent('2026-10-22T00:00:00', since, now)


def test_all_import_routes_require_editor():
    app = FastAPI()
    app.include_router(route.router, prefix='/api')
    with TestClient(app) as client:
        assert client.get('/api/editorial-imports').status_code == 401
        assert client.get('/api/editorial-imports/settings').status_code == 401
        assert client.post('/api/editorial-imports/import', json={'urls': []}).status_code == 401
        assert client.post('/api/editorial-imports/x/approve', json={'revision': 1}).status_code == 401


@pytest.fixture
def integration(monkeypatch):
    if os.environ.get('SOURCE_IMPORT_INTEGRATION') != '1':
        pytest.skip('SOURCE_IMPORT_INTEGRATION=1 uses a separate temporary local MongoDB')
    from utils import database
    from utils.auth import create_token
    name = 'humorpedia_source_test_' + uuid.uuid4().hex
    monkeypatch.setenv('DB_NAME', name)
    app = FastAPI()
    app.include_router(route.router, prefix='/api')
    with TestClient(app) as client:
        async def setup():
            await database.close_db()
            db = await database.get_db()
            assert db.name == name
            await db.users.insert_one({'_id': 'editor', 'role': 'editor'})
            await db.news.create_index('slug', unique=True)
            await db.people.create_index('slug', unique=True)
            return db
        db = client.portal.call(setup)
        token, _ = create_token('editor', 'editor')
        client.headers['Authorization'] = 'Bearer ' + token
        try:
            yield client, db
        finally:
            async def cleanup():
                assert db.name.startswith('humorpedia_source_test_') and db.name == name
                await db.client.drop_database(name)
                await database.close_db()
            client.portal.call(cleanup)


def parsed(kind='news'):
    return {'kind': kind, 'canonical_url': f'https://24smi.org/{"news" if kind == "news" else "celebrity"}/123-test.html',
            'title': 'Михаил Галустян выпустил шоу', 'full_name': 'Михаил Галустян',
            'body_html': '<p>Комик представил зрителям новую программу и рассказал о её участниках. В ней будут выступать известные артисты и молодые исполнители.</p>',
            'excerpt': 'Новая программа комика', 'bio': {'birth_date': '25.10.1979', 'birth_place': 'Сочи'},
            'published_at': '2026-10-21T09:00:00+03:00', 'modified_at': None, 'mentioned_names': []}


def enqueue(client, db, kind='news'):
    from services.editorial_imports import enqueue_document
    return client.portal.call(enqueue_document, db, parsed(kind), 'editor')[0]


def test_import_is_private_idempotent_and_publish_retry_safe(integration):
    client, db = integration
    item = enqueue(client, db)
    repeated = enqueue(client, db)
    assert repeated['_id'] == item['_id']
    async def counts():
        return await db.news.count_documents({}), await db.editorial_imports.count_documents({})
    assert client.portal.call(counts) == (0, 1)
    path = '/api/editorial-imports/' + item['_id']
    payload = deepcopy(item['payload'])
    payload['title'] = 'Отредактированная новость'
    payload['content'] += '<script>alert(1)</script><img src="https://example.test/x">'
    saved = client.patch(path, json={'revision': item['revision'], 'payload': payload, 'target_id': None})
    assert saved.status_code == 200, saved.text
    rev = saved.json()['revision']
    approved = client.post(path + '/approve', json={'revision': rev})
    assert approved.status_code == 200, approved.text
    again = client.post(path + '/approve', json={'revision': rev})
    assert again.status_code == 200, again.text
    assert client.portal.call(counts) == (1, 1)
    async def read():
        return await db.news.find_one({})
    news = client.portal.call(read)
    assert news['title'] == 'Отредактированная новость'
    assert news['status'] == 'published'
    assert '<script' not in news['content'] and '<img' not in news['content']
    assert parsed()['canonical_url'] in news['content']


def test_rejection_and_stale_revision_do_not_publish(integration):
    client, db = integration
    item = enqueue(client, db)
    path = '/api/editorial-imports/' + item['_id']
    assert client.post(path + '/approve', json={'revision': 999}).status_code == 409
    assert client.post(path + '/reject', json={'revision': 1}).status_code == 200
    assert client.post(path + '/approve', json={'revision': 1}).status_code == 409
    async def count():
        return await db.news.count_documents({})
    assert client.portal.call(count) == 0


def test_biography_detects_target_edits_and_preserves_other_modules(integration):
    client, db = integration
    async def seed():
        await db.people.insert_one({'_id': 'p1', 'title': 'Михаил Галустян', 'full_name': 'Михаил Галустян',
            'slug': 'galustyan', 'bio': {}, 'modules': [{'id': 'keep', 'type': 'text_block', 'order': 0,
            'data': {'title': 'Другой раздел', 'content': '<p>Сохранить.</p>'}}], 'updated_at': 'before', 'status': 'published'})
    client.portal.call(seed)
    item = enqueue(client, db, 'biography')
    assert item['target_id'] == 'p1'
    async def edit():
        await db.people.update_one({'_id': 'p1'}, {'$set': {'updated_at': 'changed'}})
    client.portal.call(edit)
    response = client.post('/api/editorial-imports/' + item['_id'] + '/approve', json={'revision': 1})
    assert response.status_code == 409
    async def read():
        return await db.people.find_one({'_id': 'p1'})
    assert client.portal.call(read)['modules'][0]['data']['content'] == '<p>Сохранить.</p>'
    rebased = client.patch('/api/editorial-imports/' + item['_id'], json={
        'revision': 1, 'payload': item['payload'], 'target_id': 'p1', 'refresh_target': True})
    assert rebased.status_code == 200, rebased.text
    assert rebased.json()['base_updated_at'] == 'changed'
    assert client.post('/api/editorial-imports/' + item['_id'] + '/approve', json={'revision': 2}).status_code == 200
    assert client.portal.call(read)['modules'][0]['data']['content'] == '<p>Сохранить.</p>'


def test_new_person_requires_complete_editorial_profile(integration):
    client, db = integration
    item = enqueue(client, db, 'biography')
    response = client.post('/api/editorial-imports/' + item['_id'] + '/approve', json={'revision': 1})
    assert response.status_code == 422, response.text
    assert 'проект' in response.text or 'шоу' in response.text


@pytest.mark.parametrize('source_id,url,label', [
    ('vokrugtv', 'https://www.vokrug.tv/article/show/12345/', 'Вокруг ТВ'),
    ('gostandup', 'https://gostandup.ru/articles/test_article', 'GoStandup'),
])
def test_new_source_is_private_filterable_editable_and_attributed(integration, source_id, url, label):
    from services.editorial_imports import enqueue_document
    client, db = integration
    document = parsed()
    document['canonical_url'] = url
    item = client.portal.call(enqueue_document, db, document, 'editor')[0]
    assert item['source_id'] == source_id
    assert item['payload']['slug']
    assert client.get('/api/editorial-imports', params={'source_id': source_id}).json()['total'] == 1
    assert client.get('/api/editorial-imports', params={'source_id': '24smi'}).json()['total'] == 0
    duplicate = client.portal.call(enqueue_document, db, document, 'editor')[0]
    assert duplicate['_id'] == item['_id']
    async def counts():
        return await db.news.count_documents({})
    assert client.portal.call(counts) == 0
    payload = deepcopy(item['payload'])
    payload['title'] = 'Отредактированная новость'
    path = '/api/editorial-imports/' + item['_id']
    assert client.patch(path, json={'revision': 1, 'payload': payload}).status_code == 200
    approved = client.post(path + '/approve', json={'revision': 2})
    assert approved.status_code == 200, approved.text
    async def read():
        return await db.news.find_one({})
    news = client.portal.call(read)
    assert news['title'] == payload['title']
    assert url in news['content'] and f'>{label}</a>' in news['content']
    assert '>24СМИ</a>' not in news['content']


def test_daily_settings_and_leases_are_separate_for_each_source(integration, monkeypatch):
    from services import source_import_scheduler as scheduler
    client, db = integration
    response = client.put('/api/editorial-imports/settings', json={'source_id': 'gostandup', 'enabled': True})
    assert response.status_code == 200, response.text
    assert response.json()['source_id'] == 'gostandup'
    assert client.get('/api/editorial-imports/settings', params={'source_id': '24smi'}).json()['enabled'] is False
    assert client.get('/api/editorial-imports/settings', params={'source_id': 'gostandup'}).json()['enabled'] is True
    assert client.get('/api/editorial-imports/settings', params={'source_id': 'bad'}).status_code == 422
    async def run():
        gate = asyncio.Event()
        async def collect(*args):
            await gate.wait()
        monkeypatch.setattr(scheduler, 'collect_news', collect)
        assert await scheduler.start_scan(db, source_id='gostandup')
        assert await scheduler.start_scan(db, source_id='vokrugtv')
        with pytest.raises(HTTPException) as exc:
            await scheduler.start_scan(db, source_id='gostandup')
        assert exc.value.status_code == 409
        gate.set()
        await asyncio.gather(*list(scheduler._tasks))
    client.portal.call(run)


@pytest.mark.parametrize('failure', ['redirect', 'robots', 'size'])
def test_fetcher_stops_before_forbidden_destination_or_oversized_body(failure):
    requests = []
    def respond(request):
        requests.append(str(request.url))
        if request.url.path == '/robots.txt':
            return httpx.Response(200, headers={'content-type': 'text/plain'},
                text='User-agent: *\nDisallow: /news/' if failure == 'robots' else 'User-agent: *\nAllow: /')
        if failure == 'redirect':
            return httpx.Response(302, headers={'location': 'https://127.0.0.1/admin'})
        return httpx.Response(200, headers={'content-type': 'text/html'}, content=b'x' * 2_000_001)
    async def run():
        async with SourceFetcher(transport=httpx.MockTransport(respond), delay=0) as fetcher:
            with pytest.raises(ValueError):
                await fetcher.fetch('https://24smi.org/news/123-test.html')
    asyncio.run(run())
    assert all(url.startswith('https://24smi.org/') for url in requests)
    assert len(requests) == (1 if failure == 'robots' else 2)


def test_new_biography_publishes_confirmed_shows_and_existing_updates_keep_facts(integration):
    client, db = integration
    async def seed():
        for show_id in ['show1', 'show2']:
            await db.shows.insert_one({'_id': show_id, 'title': show_id, 'status': 'published'})
    client.portal.call(seed)
    item = enqueue(client, db, 'biography')
    payload = deepcopy(item['payload'])
    payload['related_show_ids'] = ['show1', 'show2']
    path = '/api/editorial-imports/' + item['_id']
    assert client.patch(path, json={'revision': 1, 'payload': payload}).status_code == 200
    response = client.post(path + '/approve', json={'revision': 2})
    assert response.status_code == 200, response.text
    person_id = response.json()['published']['id']
    async def modify():
        person = await db.people.find_one({'_id': person_id})
        assert await db.show_appearances.count_documents({'person_id': person_id}) == 2
        person['modules'].append({'id': 'other', 'type': 'text_block', 'order': 9, 'data': {'title': 'Дополнительно', 'content': 'Сохранить'}})
        await db.people.update_one({'_id': person_id}, {'$set': {'modules': person['modules'], 'facts.Рост': '163 см'}})
        from services.editorial_imports import enqueue_document
        document = parsed('biography')
        document['bio']['birth_place'] = 'Сочи, Краснодарский край'
        return (await enqueue_document(db, document, 'editor'))[0]
    updated = client.portal.call(modify)
    response = client.post('/api/editorial-imports/' + updated['_id'] + '/approve', json={'revision': 1})
    assert response.status_code == 200, response.text
    async def verify():
        person = await db.people.find_one({'_id': person_id})
        assert person['facts']['Место рождения'] == person['bio']['birth_place'] == 'Сочи, Краснодарский край'
        assert person['facts']['Рост'] == '163 см'
        assert any(m['id'] == 'other' for m in person['modules'])
        assert await db.show_appearances.count_documents({'person_id': person_id}) == 2
    client.portal.call(verify)


def test_approval_recovers_after_write_before_cache_failure(integration, monkeypatch):
    from services import editorial_imports as service
    client, db = integration
    item = enqueue(client, db)
    original = service.cache_service.invalidate_everywhere
    async def fail_once(db):
        monkeypatch.setattr(service.cache_service, 'invalidate_everywhere', original)
        raise RuntimeError('simulated post-write failure')
    monkeypatch.setattr(service.cache_service, 'invalidate_everywhere', fail_once)
    with pytest.raises(RuntimeError, match='post-write'):
        client.post('/api/editorial-imports/' + item['_id'] + '/approve', json={'revision': 1})
    assert client.patch('/api/editorial-imports/' + item['_id'], json={'revision': 1, 'payload': item['payload']}).status_code == 409
    assert client.post('/api/editorial-imports/' + item['_id'] + '/reject', json={'revision': 1}).status_code == 409
    response = client.post('/api/editorial-imports/' + item['_id'] + '/approve', json={'revision': 1})
    assert response.status_code == 200, response.text
    async def count():
        return await db.news.count_documents({})
    assert client.portal.call(count) == 1


def test_scan_lease_prevents_parallel_workers_and_runs_when_due(integration, monkeypatch):
    from services import source_import_scheduler as scheduler
    client, db = integration
    async def run():
        gate = asyncio.Event()
        calls = []
        async def collect(*args):
            calls.append(args)
            await gate.wait()
        monkeypatch.setattr(scheduler, 'collect_news', collect)
        assert await scheduler.start_scan(db, scheduled=True) is False  # disabled by default
        await db.site_settings.update_one({'_id': scheduler.SETTING_ID}, {'$set': {'enabled': True, 'next_run_at': '2000-01-01'}})
        results = await asyncio.gather(scheduler.start_scan(db, scheduled=True), scheduler.start_scan(db), return_exceptions=True)
        assert results[0] is True
        assert isinstance(results[1], HTTPException) and results[1].status_code == 409
        gate.set()
        await asyncio.gather(*list(scheduler._tasks))
        assert len(calls) == 1
    client.portal.call(run)


@pytest.mark.parametrize('source_id', ['24smi', 'gostandup'])
def test_news_scan_filters_catalog_deduplicates_and_reports(integration, monkeypatch, source_id):
    from datetime import datetime, timezone
    from services import source_import_scheduler as scheduler
    client, db = integration
    urls = ['https://24smi.org/news/123-test.html', 'https://24smi.org/news/124-other.html']
    if source_id == 'gostandup':
        urls = ['https://gostandup.ru/articles/test', 'https://gostandup.ru/articles/other']
    class Fetcher:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def fetch(self, url, **_): return url
    def parse(_, url):
        document = parsed()
        document['canonical_url'] = url
        document['published_at'] = datetime.now(timezone.utc).isoformat()
        if source_id == 'gostandup':
            document['published_at'] = datetime.now(timezone.utc).date().isoformat()
        if url == urls[1]:
            document.update(title='Погода в Москве', body_html='<p>Сегодня солнечно.</p>')
        return document
    monkeypatch.setattr(scheduler, 'SourceFetcher', Fetcher)
    monkeypatch.setattr(scheduler, 'discover_news', lambda *args, **kwargs: urls)
    monkeypatch.setattr(scheduler, 'parse_document', parse)
    async def run():
        await db.people.insert_one({'_id': 'person', 'title': 'Михаил Галустян'})
        await scheduler.settings(db, source_id)
        for attempt in range(2):
            await db.site_settings.update_one({'_id': 'source_import_' + source_id}, {'$set': {'lease_token': 'test'}})
            result = await scheduler.collect_news(db, 3, 100, 'editor', 'test', source_id)
            assert result['errors'] == []
            assert result['checked'] == (2 if attempt == 0 else 0)
            assert result['created'] == (1 if attempt == 0 else 0)
        assert await db.news.count_documents({}) == 0
        assert await db.editorial_imports.count_documents({}) == 1
        assert (await scheduler.settings(db, source_id))['running'] is False
    client.portal.call(run)
