"""Повтор после сбоев на границах ZIP: отдельная Mongo, deterministic IDs, без sleep."""
import pytest
from test_page_package_import import integration, package
from services import page_package_import as service
from services.page_packages import pack_page


@pytest.mark.parametrize('phase,kind,path', [
    ('assets', 'person', 'people'), ('document', 'person', 'people'),
    ('memberships', 'team', 'teams'), ('appearances', 'person', 'people'),
    ('publication', 'team', 'teams'), ('completion', 'team', 'teams'),
])
def test_retry_after_each_import_boundary_preserves_unique_records_and_manual_edits(integration, monkeypatch, phase, kind, path):
    client, db, _ = integration
    draft, assets = package(kind)
    if kind == 'person':
        created = client.post('/api/content/shows', json={'title': 'Проект R7', 'name': 'Проект R7',
                              'slug': 'r7-project', 'status': 'published'})
        assert created.status_code == 200, created.text
        draft['relations'] = [{'id': 'r7-show', 'kind': 'appearance',
                               'target': {'type': 'show', 'slug': 'r7-project'}}]
    else:
        draft['relations'] = [{'id': 'r7-member', 'kind': 'membership', 'name': 'Иван Иванов'}]
    response = client.post('/api/page-packages/preview', files={'file': ('page.zip', pack_page(draft, assets))})
    assert response.status_code == 200, response.text
    preview = response.json()
    endpoint = '/api/page-packages/' + preview['id'] + '/apply'
    hook = {'assets': 'copy_assets', 'document': 'create_document', 'memberships': 'apply_relations',
            'appearances': 'apply_relations', 'publication': 'finish_import', 'completion': 'finish_import'}[phase]
    original = getattr(service, hook)

    async def fail_at_boundary(*args, **kwargs):
        if phase != 'publication':
            await original(*args, **kwargs)
        raise ValueError('Контролируемый сбой R7: ' + phase)

    monkeypatch.setattr(service, hook, fail_at_boundary)
    response = client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True})
    assert response.status_code == 422, response.text

    async def read_target():
        document = await db.page_package_imports.find_one({'_id': preview['id']})
        return await db[path].find_one({'_id': document['target_id']})
    target = client.portal.call(read_target)
    async def read_journal():
        return await db.page_package_imports.find_one({'_id': preview['id']})
    journal = client.portal.call(read_journal)
    assert journal['status'] == ('applied' if phase == 'completion' else 'error')
    assert 'lease_token' not in journal and 'lease_until' not in journal
    committed = phase in ('publication', 'completion')
    if committed:
        assert target['page_package_state'] == 'published'
        response = client.put('/api/content/' + path + '/' + target['_id'],
                              json={'title': 'Ручная правка после публикации', 'status': 'archived'})
        assert response.status_code == 200, response.text
        async def membership_id():
            return (await db.memberships.find_one({'team_id': target['_id']}))['_id']
        assert client.delete('/api/competitions/memberships/' + client.portal.call(membership_id)).status_code == 200
    else:
        auth = client.headers.pop('Authorization')
        try:
            assert client.get('/api/content/' + path + '/' + draft['page']['slug']).status_code == 404
            assert client.get('/uploads/page-packages/' + draft['id'] + '/photo.png').status_code == 404
        finally:
            client.headers['Authorization'] = auth
    monkeypatch.setattr(service, hook, original)
    response = client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True})
    assert response.status_code == 200, response.text
    final = client.portal.call(read_target)

    async def counts():
        relation = db.memberships if kind == 'team' else db.show_appearances
        key = 'team_id' if kind == 'team' else 'person_id'
        return (await db[path].count_documents({}), await db.media.count_documents({}),
                await relation.count_documents({key: final['_id']}))
    assert client.portal.call(counts) == (1, 1, 0 if committed else 1)
    assert final['status'] == ('archived' if committed else 'published')
    if committed:
        assert final['title'] == 'Ручная правка после публикации'
    assert client.post(endpoint, json={'hash': preview['hash'], 'reviewed': True}).status_code == 200
    assert client.portal.call(counts) == (1, 1, 0 if committed else 1)
