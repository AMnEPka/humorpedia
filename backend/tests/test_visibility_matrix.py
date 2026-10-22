"""Exercise public visibility through real routers and CRUD, without a live DB."""
from copy import deepcopy
import asyncio
import re
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import (cities, sections, content_articles, content_news, content_wiki,
                    content_quizzes, content_people, content_shows, content_teams, content_kvn, content_search)
from services import crud
from services.cache import cache_service
from services.link_resolver import LinkResolver
from services.views_counter import views_counter

find_adjacent_seasons = content_kvn.find_adjacent_seasons


def matches(doc, query):
    for key, value in query.items():
        actual = doc
        for part in key.split("."):
            actual = actual.get(part) if isinstance(actual, dict) else None
        if key == "$and":
            if not all(matches(doc, part) for part in value):
                return False
        elif key == "$or":
            if not any(matches(doc, part) for part in value):
                return False
        elif isinstance(value, dict):
            if "$ne" in value and actual == value["$ne"]:
                return False
            if "$in" in value and actual not in value["$in"]:
                return False
            if "$regex" in value and (not isinstance(actual, str) or not re.search(value["$regex"], actual)):
                return False
        elif actual != value:
            return False
    return True


class Cursor:
    def __init__(self, docs):
        self.docs = deepcopy(docs)

    def sort(self, *_args):
        return self

    def skip(self, count):
        self.docs = self.docs[count:]
        return self

    def limit(self, count):
        self.docs = self.docs[:count]
        return self

    async def to_list(self, length=None):
        return deepcopy(self.docs if length is None else self.docs[:length])

    def __aiter__(self):
        self.iterator = iter(self.docs)
        return self

    async def __anext__(self):
        try:
            return deepcopy(next(self.iterator))
        except StopIteration:
            raise StopAsyncIteration


class Collection:
    def __init__(self, docs=()):
        self.docs = deepcopy(list(docs))

    def find(self, query, projection=None):
        docs = [doc for doc in self.docs if matches(doc, query)]
        if projection:
            if any(projection.values()):
                keys = {key for key, include in projection.items() if include}
                if projection.get("_id", 1):
                    keys.add("_id")
                docs = [{key: value for key, value in doc.items() if key in keys} for doc in docs]
            else:
                docs = [{key: value for key, value in doc.items() if key not in projection} for doc in docs]
        return Cursor(docs)

    async def find_one(self, query, projection=None):
        docs = await self.find(query, projection).to_list(1)
        return docs[0] if docs else None

    async def count_documents(self, query):
        return len([doc for doc in self.docs if matches(doc, query)])


class Database:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, Collection())

    def __getattr__(self, name):
        return self[name]


def document(kind, status):
    return {"_id": f"{kind}-{status}", "id": f"{kind}-{status}", "title": status,
            "name": status, "slug": status, "full_path": f"probe/{status}",
            "status": status, "parent_id": None, "level": 0, "modules": [], "facts": {}}


@pytest.fixture
def visibility(monkeypatch):
    db = Database()
    modules = (cities, sections, content_articles, content_news, content_wiki,
               content_quizzes, content_people, content_shows, content_teams, content_kvn, content_search)
    for kind in ("cities", "sections", "articles", "news", "wiki", "quizzes", "people", "shows", "teams", "kvn"):
        db[kind].docs = [document(kind, status) for status in ("draft", "published", "archived")]

    async def get_db():
        return db

    async def current_user(request):
        role = request.headers.get("X-Test-Role") if request else None
        return {"_id": "test-user", "role": role} if role else None

    async def no_decoration(*_args, **_kwargs):
        return None

    async def no_adjacent_seasons(*_args, **_kwargs):
        return "", ""

    app = FastAPI()
    monkeypatch.setattr(crud, "get_db", get_db)
    monkeypatch.setattr(LinkResolver, "resolve_document", no_decoration)
    monkeypatch.setattr(content_shows, "link_participant_cards", no_decoration)
    monkeypatch.setattr(content_kvn, "find_adjacent_seasons", no_adjacent_seasons)
    for module in modules:
        monkeypatch.setattr(module, "get_db", get_db, raising=False)
        monkeypatch.setattr(module, "get_current_user", current_user, raising=False)
        if hasattr(module, "decorate_document"):
            monkeypatch.setattr(module, "decorate_document", no_decoration)
        app.include_router(module.router, prefix="/api")
    for name in ("teams", "team_lists", "kvn_pages", "kvn_children", "breadcrumbs"):
        monkeypatch.setattr(cache_service, name, {})
    views = []
    monkeypatch.setattr(views_counter, "increment", lambda *args: views.append(args))
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, db=db, views=views)


def headers(role):
    return {"X-Test-Role": role} if role else {}


@pytest.mark.parametrize("kind", ["articles", "news", "wiki", "quizzes", "people", "shows", "teams", "kvn", "cities", "sections"])
@pytest.mark.parametrize("role", [None, "user", "moderator", "editor", "admin"])
@pytest.mark.parametrize("status", ["draft", "published", "archived"])
@pytest.mark.parametrize("raw", [False, True])
def test_detail_visibility_is_role_based_and_raw_does_not_bypass_it(visibility, kind, role, status, raw):
    prefix = "/api" if kind in ("cities", "sections") else "/api/content"
    response = visibility.client.get(f"{prefix}/{kind}/{status}", params={"raw": str(raw).lower()}, headers=headers(role))
    allowed = status != "archived" or role in ("editor", "admin")
    assert response.status_code == (200 if allowed else 404), response.text
    if allowed:
        assert response.json()["status"] == status
    else:
        assert visibility.views == [], "Rejected archive reads must not increment views"


@pytest.mark.parametrize("path", ["/api/content/articles", "/api/content/news", "/api/content/wiki", "/api/content/quizzes",
                                  "/api/content/kvn", "/api/cities?sort_by=views", "/api/sections"])
@pytest.mark.parametrize("role", [None, "user", "moderator", "editor", "admin"])
def test_lists_filter_before_pagination_and_count(visibility, path, role):
    response = visibility.client.get(path, headers=headers(role))
    assert response.status_code == 200, response.text
    body = response.json()
    expected = {"draft", "published", "archived"} if role in ("editor", "admin") else {"draft", "published"}
    assert {item["status"] for item in body["items"]} == expected
    assert body["total"] == len(expected)


@pytest.mark.parametrize("path", ["/api/content/kvn/by-path/probe/archived", "/api/sections/path/probe/archived",
                                  "/api/content/kvn/archived/children", "/api/sections/sections-archived/children",
                                  "/api/cities/cities-archived/related-people", "/api/cities/cities-archived/related-teams"])
def test_nested_archive_reads_remain_private_after_editor_reads(visibility, path):
    for role in ("editor", None, "admin", "moderator", None):
        response = visibility.client.get(path, headers=headers(role))
        assert response.status_code == (200 if role in ("editor", "admin") else 404), response.text


@pytest.mark.parametrize("first_role", [None, "editor"])
@pytest.mark.parametrize("raw", [False, True])
def test_archived_show_summary_is_not_leaked_through_team_or_shared_cache(visibility, first_role, raw):
    team = visibility.db.teams.docs[1]
    team.update(show_id="shows-archived", full_path="probe/archived/teams/published")
    related = visibility.db.teams.docs[0]
    related.update(show_id="shows-archived", full_path="probe/archived/teams/draft")
    team["related_team_ids"] = [related["_id"]]
    path = f"/api/content/teams/{team['_id']}?raw={str(raw).lower()}"
    for role in (first_role, "editor", None, "admin", "user"):
        response = visibility.client.get(path, headers=headers(role))
        assert response.status_code == 200, response.text
        body = response.json()
        if role in ("editor", "admin"):
            assert body["show"]["title"] == "archived"
        else:
            assert body.get("show") is None
            assert body.get("breadcrumbs", []) == []
            assert all(item.get("show") is None for item in body["related_teams"])


def test_city_relations_hide_archived_targets_and_archived_parent_show(visibility):
    city = visibility.db.cities.docs[1]
    city["related_person_ids"] = [item["_id"] for item in visibility.db.people.docs]
    city["related_team_ids"] = [item["_id"] for item in visibility.db.teams.docs]
    visibility.db.teams.docs[1].update(show_id="shows-archived", full_path="probe/archived/teams/published")
    for relation in ("people", "teams"):
        response = visibility.client.get(f"/api/cities/{city['_id']}/related-{relation}")
        assert response.status_code == 200, response.text
        assert {item["status"] for item in response.json()["items"]} == {"draft", "published"}
        assert all(item.get("show") is None for item in response.json()["items"])


@pytest.mark.parametrize("role", [None, "editor"])
def test_jury_statistics_exclude_archived_seasons_and_teams(visibility, role):
    for season in visibility.db.kvn.docs:
        season["season_data"] = {"league_slug": "probe", "year": 2026, "stages": [{"games": [{
            "name": season["title"], "jury": [season["title"]],
            "teams": [{"team_slug": team["slug"]} for team in visibility.db.teams.docs],
        }]}]}
    response = visibility.client.get("/api/content/kvn/jury-stats?league_slug=probe", headers=headers(role))
    assert response.status_code == 200, response.text
    expected = {"draft", "published", "archived"} if role else {"draft", "published"}
    assert {member["name"] for member in response.json()["jury_members"]} == expected
    assert set(response.json()["all_teams"]) == expected


@pytest.mark.parametrize("kind", ["person", "team", "show", "kvn"])
def test_link_lookup_cannot_reveal_archive_title_or_url(visibility, kind):
    for role in ("editor", None, "moderator"):
        response = visibility.client.get(f"/api/content/{kind}/archived/resolve-link", headers=headers(role))
        assert response.status_code == (200 if role == "editor" else 404), response.text


def test_adjacent_season_search_skips_archives_even_in_fallback_queries(visibility):
    current = {"slug": "2026", "parent_id": "league", "season_data": {"year": 2026, "league_slug": "probe"}}
    visibility.db.kvn.docs = [
        {"_id": "previous", "slug": "2025", "full_path": "kvn/probe/2025", "parent_id": "league", "status": "archived",
         "season_data": {"year": 2025, "league_slug": "probe"}},
        {"_id": "next", "slug": "2027", "full_path": "kvn/probe/2027", "parent_id": "league", "status": "draft",
         "season_data": {"year": 2027, "league_slug": "probe"}},
    ]
    assert asyncio.run(find_adjacent_seasons(visibility.db, current)) == ("", "2027")
    assert asyncio.run(find_adjacent_seasons(visibility.db, current, editor=True)) == ("2025", "2027")


def test_stored_adjacent_season_links_are_filtered_without_changing_saved_data(visibility):
    current = visibility.db.kvn.docs[1]
    current["season_data"] = {"prev_season": "archived", "next_season": "draft"}
    for role in ("editor", None, "admin", None):
        response = visibility.client.get("/api/content/kvn/by-path/probe/published", headers=headers(role))
        assert response.status_code == 200, response.text
        data = response.json()["season_data"]
        assert data["prev_season"] == ("archived" if role in ("editor", "admin") else "")
        assert data["next_season"] == "draft"
    assert current["season_data"]["prev_season"] == "archived"


class CountedSeasonCollection(Collection):
    def __init__(self, docs=()):
        super().__init__(docs)
        self.queries = []

    def find(self, query, projection=None):
        self.queries.append(deepcopy(query))
        return super().find(query, projection)


def _adjacent_probe(docs, parent=None):
    collection = CountedSeasonCollection(docs)
    current = {'slug': '2026', 'season_data': {'year': 2026, 'league_slug': 'probe'}}
    if parent:
        current['parent_id'] = parent
    result = asyncio.run(find_adjacent_seasons(SimpleNamespace(kvn=collection), current))
    return result, collection.queries


def test_adjacent_empty_legacy_results_do_not_repeat_twelve_proven_empty_path_searches():
    result, queries = _adjacent_probe([])
    assert result == ('', '')
    assert len(queries) == 4  # Two exact and two legacy superset reads.


def test_adjacent_empty_path_proof_keeps_parent_map_for_manual_metadata_only_seasons():
    result, queries = _adjacent_probe([{
        'slug': 'manual-previous', 'full_path': 'kvn/probe/manual',
        'parent_id': 'league', 'season_data': {'year': 2025},
    }], parent='league')
    assert result == ('manual-previous', '')
    assert len(queries) == 5


def test_adjacent_truncated_legacy_list_keeps_original_patterns_and_leading_slash_candidate():
    unrelated = [{'slug': f'other-{n}-2025', 'full_path': f'kvn/other/other-{n}-2025'} for n in range(20)]
    previous = {'slug': 'previous', 'full_path': '/kvn/probe/final-2025', 'season_data': {'year': 2025}}
    result, queries = _adjacent_probe([*unrelated, previous])
    assert result == ('previous', '')
    final_queries = [query.get('$and', [query])[0] for query in queries]
    assert any(set(query) == {'full_path'} for query in final_queries)


def test_adjacent_missing_path_is_unknown_and_keeps_the_six_legacy_queries():
    result, queries = _adjacent_probe([{'slug': 'other-2025'}])
    assert result == ('', '')
    final_queries = [query.get('$and', [query])[0] for query in queries]
    assert sum(set(query) == {'full_path'} for query in final_queries) == 6


def test_adjacent_existing_paths_keep_original_duplicate_selection_priority():
    current = {'slug': '2026', 'season_data': {'year': 2026, 'league_slug': 'probe'}}
    duplicates = [
        {'slug': 'chosen', 'full_path': 'kvn/probe/chosen-2025', 'season_data': {'year': 2025, 'league_slug': 'probe'}},
        {'slug': 'second', 'full_path': 'kvn/probe/second-2025', 'season_data': {'year': 2025, 'league_slug': 'probe'}},
    ]
    assert asyncio.run(find_adjacent_seasons(SimpleNamespace(kvn=CountedSeasonCollection(duplicates)), current)) == ('chosen', '')
