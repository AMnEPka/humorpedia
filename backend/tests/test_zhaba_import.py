"""Telegram transport and resumable collection against disposable MongoDB."""
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from services.source_fetcher import SourceFetcher, canonical_url
from test_editorial_imports import integration


@pytest.mark.parametrize('url', [
    'https://t.me/zhabqua/123', 'https://t.me/s/zhabqua/123',
    'https://telegram.me/zhabqua/123?single#x',
])
def test_post_links_have_one_canonical_identity(url):
    assert canonical_url(url) == 'https://t.me/zhabqua/123'


@pytest.mark.parametrize('url', [
    'https://t.me/other_channel/123', 'https://t.me/c/123/456',
    'https://t.me/+private', 'https://t.me/s/zhabqua?after=100',
    'https://t.me/s/zhabqua?before=1&before=2', 'https://t.me/s/zhabqua?before=-1',
    'https://t.me/s/zhabqua?before=1&embed=1', 'https://t.me/s/other_channel?before=100',
])
def test_channel_and_feed_cursor_allowlist_is_strict(url):
    with pytest.raises(ValueError):
        canonical_url(url, resource=True)


@pytest.mark.parametrize('robots_status', [200, 404, 403, 429, 500])
def test_public_transport_uses_preview_and_respects_robots_failures(robots_status):
    requests = []
    def respond(request):
        requests.append(str(request.url))
        if request.url.path == '/robots.txt':
            return httpx.Response(robots_status, headers={'content-type': 'text/plain'}, text='User-agent: *\nAllow: /')
        return httpx.Response(200, headers={'content-type': 'text/html'}, text='post')
    async def run():
        async with SourceFetcher(transport=httpx.MockTransport(respond), delay=0) as fetcher:
            if robots_status in (200, 404):
                assert await fetcher.fetch('https://t.me/zhabqua/123') == 'post'
                assert await fetcher.fetch('https://t.me/s/zhabqua?before=123', resource=True) == 'post'
            else:
                with pytest.raises(httpx.HTTPStatusError):
                    await fetcher.fetch('https://t.me/zhabqua/123')
    asyncio.run(run())
    assert requests == (['https://t.me/robots.txt', 'https://t.me/s/zhabqua/123', 'https://t.me/s/zhabqua?before=123']
        if robots_status in (200, 404) else ['https://t.me/robots.txt'])


def test_robots_is_checked_against_the_actual_preview_path():
    def respond(request):
        assert request.url.path == '/robots.txt'
        return httpx.Response(200, headers={'content-type': 'text/plain'}, text='User-agent: *\nDisallow: /s/')
    async def run():
        async with SourceFetcher(transport=httpx.MockTransport(respond), delay=0) as fetcher:
            with pytest.raises(ValueError, match='robots'):
                await fetcher.fetch('https://t.me/zhabqua/123')
    asyncio.run(run())


def post(post_id, *, age=0, text=True):
    return {'post_id': post_id, 'kind': 'news', 'title': f'Пост канала {post_id}', 'full_name': None,
        'bio': {}, 'body_html': '<p>Новый юмористический проект.</p>' if text else '',
        'excerpt': 'Новый проект' if text else '', 'mentioned_names': [], 'modified_at': None,
        'published_at': (datetime.now(timezone.utc) - timedelta(days=age)).isoformat(),
        'canonical_url': f'https://t.me/zhabqua/{post_id}'}


def configure_feed(monkeypatch, pages, links, fail=None):
    from services import source_channel_import as channel
    from services import source_import_scheduler as scheduler
    class Fetcher:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def fetch(self, url, **_):
            if fail and fail(url): raise RuntimeError('temporary feed failure')
            assert url in pages, url
            return url
    monkeypatch.setattr(scheduler, 'SourceFetcher', Fetcher)
    monkeypatch.setattr(channel, 'parse_feed', lambda html: pages[html])
    monkeypatch.setattr(channel, 'current_page_url', lambda html: links[html][0])
    monkeypatch.setattr(channel, 'next_page_url', lambda html: links[html][1])


async def scan(db, limit=100):
    from services import source_import_scheduler as scheduler
    await scheduler.settings(db, 'zhaba')
    await db.site_settings.update_one({'_id': 'source_import_zhaba'}, {'$set': {'lease_token': 'test'}})
    return await scheduler.collect_news(db, 3, limit, 'editor', 'test', 'zhaba')


def test_channel_imports_all_text_without_catalog_matches_and_holds_until_approval(integration, monkeypatch):
    client, db = integration
    base, first, older = 'https://t.me/s/zhabqua', 'https://t.me/s/zhabqua?before=104', 'https://t.me/s/zhabqua?before=101'
    pages = {base: [post(103), post(102, text=False), post(101)], older: [post(100, age=9)]}
    configure_feed(monkeypatch, pages, {base: (first, older), older: (older, None)})
    result = client.portal.call(scan, db)
    assert result['created'] == 2 and result['without_text'] == 1 and not result['errors']
    async def check():
        assert await db.news.count_documents({}) == 0
        assert (await db.site_settings.find_one({'_id': 'source_import_zhaba'}))['last_post_id'] == 103
        return await db.editorial_imports.find_one({'source_id': 'zhaba'})
    item = client.portal.call(check)
    assert item['status'] == 'pending' and item['payload']['slug'].startswith('zhaba-')
    assert client.portal.call(scan, db)['created'] == 0
    payload = item['payload'] | {'title': 'Исправленный пост'}
    path = '/api/editorial-imports/' + item['_id']
    assert client.patch(path, json={'revision': 1, 'payload': payload}).status_code == 200
    assert client.post(path + '/approve', json={'revision': 2}).status_code == 200
    async def published():
        document = await db.news.find_one({})
        assert document['title'] == 'Исправленный пост'
        assert 'ЖАБА' in document['content'] and item['source']['url'] in document['content']
    client.portal.call(published)


def test_channel_cursor_resumes_partial_pages_and_recovers_posts_older_than_window(integration, monkeypatch):
    client, db = integration
    base, first, older = 'https://t.me/s/zhabqua', 'https://t.me/s/zhabqua?before=107', 'https://t.me/s/zhabqua?before=104'
    pages = {base: [post(i, age=10) for i in [106, 105, 104]], first: [post(i, age=10) for i in [106, 105, 104]],
        older: [post(i, age=10) for i in [103, 102, 101, 100]]}
    configure_feed(monkeypatch, pages, {base: (first, older), first: (first, older), older: (older, None)})
    async def run():
        from services import source_import_scheduler as scheduler
        await scheduler.settings(db, 'zhaba')
        await db.site_settings.update_one({'_id': 'source_import_zhaba'}, {'$set': {'last_post_id': 100}})
        first_result = await scan(db, 2)
        state = await db.site_settings.find_one({'_id': 'source_import_zhaba'})
        assert first_result['truncated'] and state['last_post_id'] == 100 and state['pending_page'] == first
        for _ in range(3):
            assert not (await scan(db, 2))['errors']
        state = await db.site_settings.find_one({'_id': 'source_import_zhaba'})
        assert state['last_post_id'] == 106 and 'pending_page' not in state
        assert await db.editorial_imports.count_documents({'source_id': 'zhaba'}) == 6
        assert await db.news.count_documents({}) == 0
    client.portal.call(run)


def test_feed_failure_keeps_cursor_and_resumes_from_saved_previous_link(integration, monkeypatch):
    client, db = integration
    base, first, older = 'https://t.me/s/zhabqua', 'https://t.me/s/zhabqua?before=104', 'https://t.me/s/zhabqua?before=102'
    pages = {base: [post(103), post(102)], older: [post(101), post(100, age=10)]}
    broken = [True]
    configure_feed(monkeypatch, pages, {base: (first, older), older: (older, None)}, lambda url: broken[0] and url == older)
    async def run():
        result = await scan(db)
        state = await db.site_settings.find_one({'_id': 'source_import_zhaba'})
        assert result['errors'] and not state.get('last_post_id') and state['pending_page'] == older
        broken[0] = False
        result = await scan(db)
        assert not result['errors']
        assert (await db.site_settings.find_one({'_id': 'source_import_zhaba'}))['last_post_id'] == 103
        assert await db.editorial_imports.count_documents({'source_id': 'zhaba'}) == 3
    client.portal.call(run)
