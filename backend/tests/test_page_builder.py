import json
from copy import deepcopy
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from routes import page_builder as route
from tests.test_editorial_proposals import _Collection


@pytest.fixture
def builder(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCAL_PAGE_BUILDER_ENABLED', 'true')
    monkeypatch.setenv('ENVIRONMENT', 'development')
    monkeypatch.setenv('PAGE_BUILDER_DIR', str(tmp_path))
    db = SimpleNamespace(page_builder_drafts=_Collection())
    async def get_db():
        return db
    async def editor():
        return {'_id': 'editor', 'role': 'editor'}
    monkeypatch.setattr(route, 'get_db', get_db)
    app = FastAPI()
    app.include_router(route.router, prefix='/api')
    app.dependency_overrides[route.require_editor] = editor
    return TestClient(app), db, tmp_path


def test_builder_needs_auth_and_production_is_disabled(monkeypatch):
    app = FastAPI()
    app.include_router(route.router, prefix='/api')
    client = TestClient(app)
    assert client.get('/api/page-builder/drafts').status_code == 401
    monkeypatch.setenv('ENVIRONMENT', 'production')
    monkeypatch.setenv('LOCAL_PAGE_BUILDER_ENABLED', 'true')
    assert not route.enabled()


def test_draft_manual_edit_cas_and_no_public_document(builder):
    client, db, _ = builder
    draft = client.post('/api/page-builder/drafts', json={'kind': 'person', 'materials': {'name': 'Иван Иванов'}}).json()
    assert draft['page']['full_name'] == 'Иван Иванов'
    change = {key: deepcopy(draft[key]) for key in ('revision', 'materials', 'page', 'relations')}
    change['page']['title'] = 'Название редактора'
    changed = client.put(f"/api/page-builder/drafts/{draft['id']}", json=change)
    assert changed.status_code == 200
    assert changed.json()['page']['title'] == 'Название редактора'
    assert client.put(f"/api/page-builder/drafts/{draft['id']}", json=change).status_code == 409
    assert not hasattr(db, 'people')


def test_export_requires_manual_review(builder):
    client, _, _ = builder
    draft = client.post('/api/page-builder/drafts', json={'kind': 'team', 'materials': {'name': 'Команда'}}).json()
    assert client.get(f"/api/page-builder/drafts/{draft['id']}/export").status_code == 422
    response = client.get(f"/api/page-builder/drafts/{draft['id']}/export?reviewed=true")
    assert response.status_code == 200
    assert response.content.startswith(b'PK')


def test_generated_text_is_an_offer_and_stale_offer_cannot_overwrite(builder):
    client, db, root = builder
    draft = client.post('/api/page-builder/drafts', json={'kind': 'person', 'materials': {'name': 'Иван Иванов'}}).json()
    from services.page_builder import atomic_json, now
    change = {key: deepcopy(draft[key]) for key in ('revision', 'materials', 'page', 'relations')}
    change['materials']['birth_date'] = '1990'
    change['materials']['birth_place'] = 'Казань'
    change['page']['facts']['Место рождения'] = 'Ручной город'
    draft = client.put(f"/api/page-builder/drafts/{draft['id']}", json=change).json()
    atomic_json(root / 'worker.json', {'status': 'ready', 'updated_at': now()})
    generated = client.post(f"/api/page-builder/drafts/{draft['id']}/generate", json={'revision': draft['revision']})
    assert generated.status_code == 200, generated.text
    queued = generated.json()
    folder = root / 'jobs' / queued['job']['id']
    atomic_json(folder / 'result.json', {'sections': [{'heading': 'Биография', 'paragraphs': ['Иван Иванов.'], 'fact_ids': ['name']}], 'questions': [], 'warnings': []})
    atomic_json(folder / 'status.json', {'status': 'completed', 'updated_at': now()})
    loaded = client.get(f"/api/page-builder/drafts/{draft['id']}").json()
    assert loaded['page'] == draft['page']
    assert loaded['versions'][0]['page']['modules'][-1]['data']['content'] == '<p>Иван Иванов.</p>'
    assert loaded['versions'][0]['page']['bio']['birth_date'] == '1990'
    assert loaded['versions'][0]['page']['facts']['Место рождения'] == 'Ручной город'
    change = {key: deepcopy(loaded[key]) for key in ('revision', 'materials', 'page', 'relations')}
    change['page']['title'] = 'Ручное изменение'
    edited = client.put(f"/api/page-builder/drafts/{draft['id']}", json=change).json()
    response = client.post(f"/api/page-builder/drafts/{draft['id']}/accept", json={'revision': edited['revision'], 'version_id': loaded['versions'][0]['id']})
    assert response.status_code == 409
    assert db.page_builder_drafts.docs[draft['id']]['page']['title'] == 'Ручное изменение'
