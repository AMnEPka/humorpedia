"""Конкурентный ZIP apply на отдельной Mongo: управляемый lease и барьер, без sleep."""
import asyncio
from types import SimpleNamespace

from fastapi import HTTPException

from test_page_package_import import integration, package
from services.page_packages import pack_page
from services import page_package_import as service
from services.tags import tag_service


def test_expired_lease_never_allows_stale_worker_to_write_tags(integration, monkeypatch):
    client, db, _ = integration
    draft, assets = package('person')
    response = client.post('/api/page-packages/preview', files={'file': ('page.zip', pack_page(draft, assets))})
    assert response.status_code == 200, response.text
    preview = response.json()
    data = SimpleNamespace(hash=preview['hash'], reviewed=True, omit_relations=[])
    original_sync = tag_service.sync_tags

    async def scenario():
        arrived, release = asyncio.Event(), asyncio.Event()

        async def pause_old_writer(tags, *, db=None):
            if asyncio.current_task().get_name() == 'stale-apply':
                arrived.set()
                await release.wait()
            await original_sync(tags, db=db)

        monkeypatch.setattr(tag_service, 'sync_tags', pause_old_writer)
        first = asyncio.create_task(service.apply(db, preview['id'], data, 'old-worker'), name='stale-apply')
        await asyncio.wait_for(arrived.wait(), timeout=10)
        second = None
        try:
            await db.page_package_imports.update_one({'_id': preview['id']},
                {'$set': {'lease_until': '2000-01-01T00:00:00+00:00'}})
            try:
                second = await service.apply(db, preview['id'], data, 'new-worker')
            except HTTPException as exc:
                second = exc
        finally:
            release.set()
            first_result, = await asyncio.gather(first, return_exceptions=True)
        after = {tag['name']: tag['usage_count'] async for tag in db.tags.find({})}
        assert isinstance(second, HTTPException) and second.status_code == 409
        assert not isinstance(first_result, Exception)
        assert after and all(count == 1 for count in after.values())
        assert (await service.get_import(db, preview['id']))['status'] == 'applied'

    client.portal.call(scenario)


def test_published_target_does_not_bypass_active_claim(integration, monkeypatch):
    client, db, _ = integration
    draft, assets = package('person')
    preview = client.post('/api/page-packages/preview',
        files={'file': ('page.zip', pack_page(draft, assets))}).json()
    data = SimpleNamespace(hash=preview['hash'], reviewed=True, omit_relations=[])
    original_finish = service.finish_import

    async def scenario():
        arrived, release = asyncio.Event(), asyncio.Event()

        async def pause_before_finish(*args, **kwargs):
            if asyncio.current_task().get_name() == 'active-apply':
                arrived.set()
                await release.wait()
            return await original_finish(*args, **kwargs)

        monkeypatch.setattr(service, 'finish_import', pause_before_finish)
        first = asyncio.create_task(service.apply(db, preview['id'], data, 'old-worker'), name='active-apply')
        try:
            await asyncio.wait_for(arrived.wait(), timeout=10)
            owned = await service.get_import(db, preview['id'])
            try:
                second = await service.apply(db, preview['id'], data, 'new-worker')
            except HTTPException as exc:
                second = exc
            still_owned = await service.get_import(db, preview['id'])
        finally:
            release.set()
            first_result, = await asyncio.gather(first, return_exceptions=True)

        assert isinstance(second, HTTPException) and second.status_code == 409
        assert still_owned['status'] == 'applying'
        assert still_owned['lease_token'] == owned['lease_token']
        assert not isinstance(first_result, Exception)
        final = await service.get_import(db, preview['id'])
        assert final['status'] == 'applied' and final['applied_by'] == 'old-worker'
        assert 'lease_token' not in final and 'lease_until' not in final

    client.portal.call(scenario)


def test_completion_and_error_cannot_overwrite_replaced_owner(integration, monkeypatch):
    client, db, _ = integration
    draft, assets = package('person')
    preview = client.post('/api/page-packages/preview',
        files={'file': ('page.zip', pack_page(draft, assets))}).json()
    data = SimpleNamespace(hash=preview['hash'], reviewed=True, omit_relations=[])
    original_finish = service.finish_import

    async def replace_owner_before_finish(database, doc, target, actor, warnings=()):
        await database.page_package_imports.update_one({'_id': doc['_id']},
            {'$set': {'lease_token': 'replacement-owner', 'status': 'applying'}})
        return await original_finish(database, doc, target, actor, warnings)

    monkeypatch.setattr(service, 'finish_import', replace_owner_before_finish)

    async def scenario():
        try:
            result = await service.apply(db, preview['id'], data, 'old-worker')
        except HTTPException as exc:
            result = exc
        stored = await service.get_import(db, preview['id'])
        assert isinstance(result, HTTPException) and result.status_code == 409
        assert stored['status'] == 'applying' and stored['lease_token'] == 'replacement-owner'
        assert not stored.get('result') and not stored.get('error')

    client.portal.call(scenario)
