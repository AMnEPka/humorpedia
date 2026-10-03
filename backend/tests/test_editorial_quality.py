"""Regression coverage for candidate completeness and archived profile visibility."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import content_people
from services.editorial_quality import has_day_and_month, missing_candidate_requirements


def test_candidate_requires_real_date_biography_and_distinct_shows():
    biography = (
        "Артист начал выступать в родном городе и постепенно стал участвовать в разных проектах. "
        "Позднее он продолжил карьеру на сцене и выступил в телевизионной программе."
    )
    changes = [
        ({"field": "bio.birth_date"}, "29.02"),
        ({"field": "bio.birth_place"}, "Москва"),
        ({"field": "module.bio.content", "label": "Биография"}, biography),
        ({"field": "appearance.show-one"}, {"achievement": "participant"}),
        ({"field": "appearance.show-two"}, {"achievement": "participant"}),
    ]
    assert missing_candidate_requirements("Имя Фамилия", changes) == []
    assert not has_day_and_month("31.02")
    assert "дата рождения (ДД.ММ или ДД.ММ.ГГГГ)" in missing_candidate_requirements(
        "Имя Фамилия", [(changes[0][0], "31.02"), *changes[1:]])
    assert "участие минимум в двух разных проектах/шоу" in missing_candidate_requirements(
        "Имя Фамилия", changes[:-1])


def test_archived_person_is_hidden_from_anonymous_api_but_editor_can_open(monkeypatch):
    archived = {"_id": "archived-1", "title": "Архивный комик", "slug": "archivnyi-komik", "status": "archived"}
    observed_queries = []
    current_user = None

    async def fake_db():
        return object()

    async def fake_user(_request):
        return current_user

    async def fake_conditions(_db, **_kwargs):
        return []

    async def fake_options(_db, _query):
        return {}

    async def fake_list(_collection, _skip, _limit, query, _fields, **_kwargs):
        observed_queries.append(query)
        return {"items": [], "total": 0}

    async def fake_get(_collection, _identifier, _error):
        return archived.copy()

    monkeypatch.setattr(content_people, "get_db", fake_db)
    monkeypatch.setattr(content_people, "get_current_user", fake_user)
    monkeypatch.setattr(content_people, "person_conditions", fake_conditions, raising=False)
    monkeypatch.setattr(content_people, "people_filter_options", fake_options, raising=False)
    monkeypatch.setattr(content_people, "list_alphabetical_content", fake_list)
    monkeypatch.setattr(content_people, "get_by_id_or_slug", fake_get)
    app = FastAPI()
    app.include_router(content_people.router, prefix="/api")

    with TestClient(app) as client:
        assert client.get("/api/content/people").status_code == 200
        assert observed_queries[-1] == {"status": {"$ne": "archived"}}
        assert client.get("/api/content/people?status=archived").status_code == 404
        assert client.get("/api/content/people/archivnyi-komik?raw=true").status_code == 404

        current_user = {"role": "editor"}
        assert client.get("/api/content/people/archivnyi-komik?raw=true").json()["status"] == "archived"
