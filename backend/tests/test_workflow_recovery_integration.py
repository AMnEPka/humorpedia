"""Восстановление claims и повтор через API на одноразовой MongoDB."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from test_page_package_import import integration, package
from scripts.recover_workflow_claim import recover_claim
from services import page_package_import as importer
from services import editorial_decisions
from routes import editorial_proposals
from services.page_packages import pack_page


@pytest.mark.parametrize('phase', ['assets', 'publication'])
def test_stopped_zip_worker_requires_operator_recovery_then_safe_retry(integration, monkeypatch, phase):
    client, db, _ = integration
    draft, assets = package('person')
    response = client.post('/api/page-packages/preview',
        files={'file': ('page.zip', pack_page(draft, assets))})
    assert response.status_code == 200, response.text
    preview = response.json()
    endpoint = '/api/page-packages/' + preview['id'] + '/apply'
    data = SimpleNamespace(hash=preview['hash'], reviewed=True, omit_relations=[])
    hook = 'copy_assets' if phase == 'assets' else 'finish_import'
    original = getattr(importer, hook)

    async def interrupted(*args, **kwargs):
        if phase == 'assets':
            await original(*args, **kwargs)
        # Аналог необработанной остановки запроса: обработчик Exception не срабатывает.
        raise asyncio.CancelledError()

    monkeypatch.setattr(importer, hook, interrupted)

    async def stop_attempt():
        with pytest.raises(asyncio.CancelledError):
            await importer.apply(db, preview['id'], data, 'stopped-worker')
        document = await importer.get_import(db, preview['id'])
        assert document['status'] == 'applying'
        await db.page_package_imports.update_one({'_id': preview['id']},
            {'$set': {'lease_until': '2000-01-01T00:00:00+00:00'}})
        return await importer.get_import(db, preview['id'])

    stopped = client.portal.call(stop_attempt)
    token = stopped['lease_token']
    assert client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True}).status_code == 409

    async def release():
        before = await importer.get_import(db, preview['id'])
        report = await recover_claim(db, 'page-package', preview['id'])
        assert report['token'] == token and report['applied'] is False
        assert await importer.get_import(db, preview['id']) == before
        recovered = await recover_claim(db, 'page-package', preview['id'],
            expected_token=token, worker_stopped=True, apply=True,
            actor='operator-test', reason='Прежний запрос остановлен')
        assert recovered['applied'] is True and recovered['status'] == 'error'
        document = await importer.get_import(db, preview['id'])
        assert document['claim_recovery_audit'][0]['previous_token'] == token
        assert document['claim_recovery_audit'][0]['actor'] == 'operator-test'
        assert 'lease_token' not in document and 'lease_until' not in document
        return document

    recovered = client.portal.call(release)
    if phase == 'publication':
        response = client.put('/api/content/people/' + recovered['target_id'],
            json={'title': 'Ручная правка после публикации', 'status': 'archived'})
        assert response.status_code == 200, response.text
    monkeypatch.setattr(importer, hook, original)
    response = client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'applied'

    async def inspect_result():
        target = await db.people.find_one({'_id': recovered['target_id']})
        assert target['status'] == ('archived' if phase == 'publication' else 'published')
        if phase == 'publication':
            assert target['title'] == 'Ручная правка после публикации'
        assert await db.people.count_documents({}) == 1
        assert await db.media.count_documents({}) == 1
        tag_counts = [row['usage_count'] async for row in db.tags.find({})]
        assert tag_counts and all(count == 1 for count in tag_counts)
        document = await importer.get_import(db, preview['id'])
        assert len(document['claim_recovery_audit']) == 1
        assert 'lease_token' not in document
        return deepcopy(target)

    final = client.portal.call(inspect_result)
    assert client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True}).status_code == 200
    assert client.portal.call(inspect_result) == final


def test_editorial_operator_recovery_invalidates_old_revision_and_preserves_manual_edit(integration):
    client, db, _ = integration
    client.app.include_router(editorial_proposals.router, prefix='/api')
    created = client.post('/api/content/people', json={
        'title': 'Проверка редакции', 'full_name': 'Проверка редакции', 'slug': 'editorial-r7',
        'facts': {'show': 'старое'}, 'status': 'published'})
    assert created.status_code == 200, created.text
    person_id = created.json()['id']
    response = client.post('/api/editorial-proposals', json={
        'kind': 'update_person', 'person_id': person_id, 'reason': 'Проверка R7',
        'changes': [{'id': 'c1', 'field': 'facts.show', 'old_value': 'старое', 'proposed_value': 'A',
                     'sources': [{'url': 'https://example.com/r7', 'title': 'Проверка'}]}]})
    assert response.status_code == 200, response.text
    proposal = response.json()
    endpoint = '/api/editorial-proposals/' + proposal['id'] + '/decide'

    async def interrupted_request():
        doc = await db.editorial_proposals.find_one({'_id': proposal['id']})
        claim = await editorial_decisions.claim_decision(db, doc, 'stopped-editor', 0)
        doc['revision'], doc['decision_claim'] = 0, claim
        assert await editorial_proposals._apply_person_value(db, doc, doc['changes'][0], 'A', 'stopped-editor')
        return claim['token']

    token = client.portal.call(interrupted_request)
    assert client.post(endpoint, json={'expected_revision': 0,
        'decisions': [{'change_id': 'c1', 'decision': 'accept', 'edited_value': 'A'}]}).status_code == 409
    response = client.put('/api/content/people/' + person_id, json={'facts': {'show': 'C'}})
    assert response.status_code == 200, response.text

    async def release():
        before = await db.people.find_one({'_id': person_id})
        report = await recover_claim(db, 'editorial', proposal['id'])
        assert report['token'] == token and report['revision'] == 0
        recovered = await recover_claim(db, 'editorial', proposal['id'],
            expected_token=token, worker_stopped=True, apply=True,
            actor='operator-test', reason='Редакционный worker остановлен')
        assert recovered['revision'] == 1 and recovered['applied'] is True
        assert await db.people.find_one({'_id': person_id}) == before
    client.portal.call(release)
    assert client.post(endpoint, json={'expected_revision': 0,
        'decisions': [{'change_id': 'c1', 'decision': 'accept', 'edited_value': 'A'}]}).status_code == 409
    response = client.post(endpoint, json={'expected_revision': 1,
        'decisions': [{'change_id': 'c1', 'decision': 'accept', 'edited_value': 'A'}]})
    assert response.status_code == 200, response.text
    assert response.json()['changes'][0]['status'] == 'accepted'
    assert 'decision_claim' not in response.json()

    async def inspect_result():
        target = await db.people.find_one({'_id': person_id})
        assert target['facts']['show'] == 'C' and len(target['editorial_audit']) == 1
        document = await db.editorial_proposals.find_one({'_id': proposal['id']})
        assert 'decision_claim' not in document
        assert document['revision'] == response.json()['revision'] > 1
        assert document['claim_recovery_audit'][0]['previous_token'] == token
    client.portal.call(inspect_result)
