"""HTTP contract checks for selectable modules without a MongoDB connection."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from models.module_contract import MODULE_CONTRACT
from models.modules import ModuleType
from routes import content_articles, templates


SELECTABLE = [entry for entry in MODULE_CONTRACT if entry.get("for_types")]


class FakeTemplates:
    def __init__(self):
        self.documents = {}

    async def find_one(self, query):
        return next((deepcopy(document) for document in self.documents.values()
                     if all(document.get(key) == value for key, value in query.items())), None)

    async def insert_one(self, document):
        self.documents[document["_id"]] = deepcopy(document)
        return SimpleNamespace(inserted_id=document["_id"])

    async def update_one(self, query, update):
        document = await self.find_one(query)
        if document is None:
            return SimpleNamespace(matched_count=0)
        document.update(deepcopy(update["$set"]))
        self.documents[document["_id"]] = document
        return SimpleNamespace(matched_count=1)


@pytest.fixture
def template_client(monkeypatch):
    database = SimpleNamespace(templates=FakeTemplates())

    async def fake_db():
        return database

    async def editor_user(*_args, **_kwargs):
        return {"_id": "contract-editor", "role": "editor"}

    monkeypatch.setattr(templates, "get_db", fake_db)
    monkeypatch.setattr(templates, "get_current_user", editor_user)
    application = FastAPI()
    application.include_router(templates.router, prefix="/api")
    application.dependency_overrides[templates.require_editor] = lambda: {"role": "editor"}
    with TestClient(application) as client:
        yield client


def test_registry_matches_enum_and_declares_working_editors_and_owners():
    names = [entry["type"] for entry in MODULE_CONTRACT]
    assert len(names) == len(set(names)) == 35
    assert set(names) == {member.value for member in ModuleType}
    assert SELECTABLE
    for entry in SELECTABLE:
        assert entry.get("editor") and entry["editor"].lower() != "json", entry["type"]
        assert entry.get("owners") and all(entry["owners"]), entry["type"]
        assert entry.get("schema") == "PageModule", entry["type"]


def test_module_types_endpoint_uses_the_same_registry(template_client):
    response = template_client.get("/api/templates/modules/types")
    assert response.status_code == 200
    api_entries = response.json()
    assert {entry["type"] for entry in api_entries} == {entry["type"] for entry in MODULE_CONTRACT}
    for api_entry, entry in zip(api_entries, MODULE_CONTRACT):
        assert all(api_entry[key] == value for key, value in entry.items())


MODULE_DATA = {
    "gallery": {"title": "Фото", "images": [{"url": "/photo.jpg", "caption": "Сцена"}]},
    "video": {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "title": "Видео"},
    "timeline": {"events": [{"year": "2007-2013", "title": "Период", "description": "<b>Карьера</b>"}]},
    "table": {"headers": ["Команда", "Баллы"], "rows": [["А", "42"]], "hasHeaders": True, "sortable": True},
    "table_of_contents": {"mode": "auto", "position": "sidebar"},
    "participants": {"items": [{"name": "Участник", "person_slug": "person", "facts": [{"title": "Роль", "value": "Ведущий"}]}]},
    "quiz_questions": {"questions": [{"id": 1, "type": "text", "question": "Кто?", "correct_answer": "Участник"}]},
    "quiz_results": {"results": [{"min_score": 0, "max_score": 1, "title": "Итог", "description": "Ответы"}]},
    "text_block": {"content": "<p>Текст</p>", "collapsed": True, "anchor_id": "intro"},
    "quote": {"text": "Цитата", "author": "Автор"},
    "image": {"url": "/photo.jpg", "caption": "Фото"},
    "poll": {"poll_id": "contract-poll"},
}


def test_recommendation_filter_excludes_archived_before_pagination(article_client):
    client, calls = article_client
    response = client.get('/api/content/articles', params={'exclude_archived': True, 'limit': 3, 'sort': '-rating'})
    assert response.status_code == 200
    assert calls[0]['query']['$and'][-1] == {'status': {'$ne': 'archived'}}
    assert calls[0]['sort_field'] == 'rating'


@pytest.mark.parametrize("entry", SELECTABLE, ids=lambda entry: entry["type"])
def test_selectable_module_roundtrips_through_template_create_read_update(template_client, entry):
    module_type = entry["type"]
    module_data = deepcopy(MODULE_DATA.get(module_type, {}))
    module_data["import_metadata"] = {"legacy_id": 42, "notes": ["сохранить", {"enabled": False}]}
    module = {
        "id": f"module-{module_type}", "type": module_type, "title": "Переопределённый заголовок",
        "order": 7, "visible": False, "data": module_data,
    }
    payload = {"name": f"Шаблон {module_type}", "content_type": entry["for_types"][0], "modules": [module]}
    created = template_client.post("/api/templates", json=payload)
    assert created.status_code == 200, created.text
    template_id = created.json()["id"]
    url = f"/api/templates/{template_id}"
    loaded = template_client.get(url)
    assert loaded.status_code == 200
    assert loaded.json()["modules"] == [module]
    assert loaded.json()["created_by"] == "contract-editor"

    updated_module = deepcopy(module)
    updated_module.update(title="Новый заголовок", order=11, visible=True)
    updated_module["data"]["editor_metadata"] = {"nested": [1, "дополнительное поле"]}
    updated = template_client.put(url, json={**payload, "id": template_id, "modules": [updated_module]})
    assert updated.status_code == 200, updated.text
    reloaded = template_client.get(url)
    assert reloaded.status_code == 200
    assert reloaded.json()["modules"] == [updated_module]
    assert reloaded.json()["updated_by"] == "contract-editor"


@pytest.mark.parametrize("module_type", ["image_gallery", "video_embed", "unknown_module"])
def test_template_api_rejects_aliases_and_unknown_types_on_create_and_update(template_client, module_type):
    valid = {"name": "Проверка валидации", "content_type": "page", "modules": []}
    created = template_client.post("/api/templates", json=valid)
    assert created.status_code == 200
    template_id = created.json()["id"]
    invalid = {**valid, "modules": [{"type": module_type, "data": {"content": "Не сохранять"}}]}
    for response in [
        template_client.post("/api/templates", json={**invalid, "name": "Невалидный шаблон"}),
        template_client.put(f"/api/templates/{template_id}", json=invalid),
    ]:
        assert response.status_code == 422, response.text
        assert any(error["loc"][-1] == "type" for error in response.json()["detail"])
    assert template_client.get(f"/api/templates/{template_id}").json()["modules"] == []


@pytest.fixture
def article_client(monkeypatch):
    calls = []

    async def fake_list_content(collection, skip, limit, query, **kwargs):
        calls.append({"collection": collection, "skip": skip, "limit": limit, "query": query, **kwargs})
        return {"items": [], "total": 0, "skip": skip, "limit": limit}

    monkeypatch.setattr(content_articles, "list_content", fake_list_content)
    application = FastAPI()
    application.include_router(content_articles.router, prefix="/api")
    application.dependency_overrides[content_articles.require_editor_on_write] = lambda: None
    with TestClient(application) as client:
        yield client, calls


@pytest.mark.parametrize(
    "params,sort_field",
    [
        ({}, "created_at"),
        ({"sort": "-created_at"}, "created_at"),
        ({"sort": "-published_at"}, "published_at"),
        ({"sort": "-rating"}, "rating"),
    ],
)
@pytest.mark.parametrize("featured", [None, True, False])
def test_article_recommendation_sort_and_featured_filter_reach_query(article_client, params, sort_field, featured):
    client, calls = article_client
    params = {**params, "skip": 2, "limit": 3, "status": "published"}
    if featured is not None:
        params["featured"] = str(featured).lower()
    response = client.get("/api/content/articles", params=params)
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    call = calls[0]
    assert call["collection"] == "articles"
    assert (call["skip"], call["limit"], call["sort_field"]) == (2, 3, sort_field)
    assert call["query"]["status"] == "published"
    if featured is None:
        assert "featured" not in call["query"]
    else:
        assert call["query"]["featured"] is featured


@pytest.mark.parametrize("sort", ["rating", "-unknown", "title"])
def test_article_api_rejects_unsupported_sort_fields(article_client, sort):
    client, calls = article_client
    assert client.get("/api/content/articles", params={"sort": sort}).status_code == 422
    assert calls == []


@pytest.mark.parametrize("content_type,collection_name", [("team", "teams"), ("show", "shows"), ("city", "cities")])
@pytest.mark.parametrize("exclude_slug", [None, "current"])
def test_random_page_api_retains_navigation_fields(monkeypatch, tmp_path, content_type, collection_name, exclude_slug):
    # Register the actual endpoint without the production app lifespan or its database startup.
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    import server

    document = {
        "_id": "target-id", "name": "Карточка", "slug": "target", "content_type": content_type,
        "full_path": "shows/improv/target", "show_id": "parent-show", "url": "/shows/improv/target",
        "status": "published", "private_field": "must not be returned",
    }
    pipelines = {}

    class AggregateCollection:
        def __init__(self, name):
            self.name = name

        def aggregate(self, pipeline):
            pipelines[self.name] = deepcopy(pipeline)
            projection = next(stage["$project"] for stage in pipeline if "$project" in stage)

            async def to_list(limit):
                assert limit == 1
                return [{key: value for key, value in document.items() if projection.get(key) == 1}]

            return SimpleNamespace(to_list=to_list)

    database = SimpleNamespace(**{
        name: AggregateCollection(name)
        for name in ["people", "teams", "shows", "articles", "news", "quizzes", "wiki", "cities"]
    })

    async def fake_db():
        return database

    monkeypatch.setattr(server, "get_db", fake_db)
    application = FastAPI()
    application.add_api_route("/api/random/{content_type}", server.get_random_content, methods=["GET"])
    with TestClient(application) as client:
        response = client.get(f"/api/random/{content_type}", params={"exclude_slug": exclude_slug} if exclude_slug else {})
    assert response.status_code == 200, response.text
    assert set(pipelines) == {collection_name}
    match = {"status": {"$ne": "archived"}}
    if exclude_slug:
        match['slug'] = {'$ne': exclude_slug}
    assert pipelines[collection_name][0] == {"$match": match}
    assert pipelines[collection_name][1] == {"$sample": {"size": 1}}
    for field in ["_id", "slug", "full_path", "show_id", "url"]:
        assert response.json()[field] == document[field]
    assert "private_field" not in response.json()
