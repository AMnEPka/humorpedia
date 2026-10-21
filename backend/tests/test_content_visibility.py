"""Archived team and show pages are editor-only across public GET routes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import content_shows, content_teams


def _contains(query, expected):
    if query == expected:
        return True
    if isinstance(query, dict):
        return any(_contains(value, expected) for value in query.values())
    if isinstance(query, list):
        return any(_contains(value, expected) for value in query)
    return False


def _client(monkeypatch, *, shows=None, teams=None):
    user = None

    async def current_user(_request):
        return user

    monkeypatch.setattr(content_shows, "get_current_user", current_user, raising=False)
    monkeypatch.setattr(content_teams, "get_current_user", current_user)
    app = FastAPI()
    app.include_router(content_shows.router, prefix="/api")
    app.include_router(content_teams.router, prefix="/api")

    class Client:
        def __enter__(self):
            self.client = TestClient(app)
            self.client.__enter__()
            return self

        def __exit__(self, *args):
            self.client.__exit__(*args)

        def get(self, *args, **kwargs):
            return self.client.get(*args, **kwargs)

        def editor(self):
            nonlocal user
            user = {"role": "editor"}

    return Client()


def test_lists_exclude_archived_for_public_and_keep_them_for_editors(monkeypatch):
    team_queries = []
    show_queries = []

    async def fake_db():
        return object()

    async def fake_team_conditions(*_args, **_kwargs):
        return []

    async def fake_show_list(_collection, _skip, _limit, query, _fields, **_kwargs):
        show_queries.append(query)
        return {"items": [], "total": 0}

    async def fake_team_list(_collection, _skip, _limit, query, _fields, **_kwargs):
        team_queries.append(query)
        return {"items": [], "total": 0}

    async def fake_filters(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(content_teams, "get_db", fake_db)
    monkeypatch.setattr(content_shows, "get_db", fake_db)
    monkeypatch.setattr(content_teams, "team_conditions", fake_team_conditions)
    monkeypatch.setattr(content_teams, "teams_filter_options", fake_filters)
    monkeypatch.setattr(content_teams, "list_alphabetical_content", fake_team_list)
    monkeypatch.setattr(content_shows, "list_alphabetical_content", fake_show_list)
    monkeypatch.setattr(content_teams, "attach_show_info", lambda *_args: None)

    # Team details attachment is async, unlike the small sync replacement above.
    async def attach_team_info(*_args, **_kwargs):
        return None

    monkeypatch.setattr(content_teams, "attach_show_info", attach_team_info)
    client = _client(monkeypatch)
    with client as c:
        assert c.get("/api/content/teams?search=private-visibility").status_code == 200
        assert c.get("/api/content/shows?search=private-visibility").status_code == 200
        assert {"status": {"$ne": "archived"}} in team_queries[-1]["$and"]
        assert _contains(show_queries[-1], {"status": {"$ne": "archived"}})

        assert c.get("/api/content/teams?status=archived&search=private-visibility").status_code == 404
        assert c.get("/api/content/shows?status=archived&search=private-visibility").status_code == 404

        c.editor()
        assert c.get("/api/content/teams?search=private-visibility").status_code == 200
        assert c.get("/api/content/shows?search=private-visibility").status_code == 200
        assert {"status": {"$ne": "archived"}} not in team_queries[-1]["$and"]
        assert not _contains(show_queries[-1], {"status": {"$ne": "archived"}})


def test_archived_detail_routes_require_editor_including_raw_and_cached_team(monkeypatch):
    archived = {"_id": "archived-team", "slug": "archived-team", "full_path": "show/teams/archived-team", "status": "archived"}

    async def fake_team(*_args, **_kwargs):
        return archived.copy()

    async def fake_show(*_args, **_kwargs):
        return {"_id": "archived-show", "slug": "archived-show", "full_path": "archived-show", "status": "archived"}

    class ShowCollection:
        async def find_one(self, _query, *_args):
            return {"_id": "archived-show", "slug": "archived-show", "full_path": "archived-show", "status": "archived"}

    async def fake_db():
        return type("DB", (), {"shows": ShowCollection()})()

    monkeypatch.setattr(content_teams, "get_db", fake_db)
    monkeypatch.setattr(content_teams, "_find_team", fake_team)
    monkeypatch.setattr(content_teams.cache_service, "get_team", lambda _key: archived.copy())
    async def no_op(*_args, **_kwargs):
        return None

    monkeypatch.setattr(content_teams, "attach_show_info", no_op)
    monkeypatch.setattr(content_teams, "attach_related_teams", no_op)
    monkeypatch.setattr(content_shows, "get_db", fake_db)
    monkeypatch.setattr(content_shows, "get_by_id_or_slug", fake_show)

    client = _client(monkeypatch)
    with client as c:
        for url in (
            "/api/content/teams/archived-team?raw=true",
            "/api/content/teams/archived-team",
            "/api/content/teams/by-path/show/teams/archived-team",
            "/api/content/shows/by-path/archived-show",
            "/api/content/shows/archived-show?raw=true",
            "/api/content/shows/archived-show",
        ):
            assert c.get(url).status_code == 404, url

        c.editor()
        assert c.get("/api/content/teams/archived-team?raw=true").status_code == 200
        assert c.get("/api/content/shows/archived-show?raw=true").status_code == 200


def test_show_hierarchy_and_children_do_not_include_archived_for_public(monkeypatch):
    queries = []

    class Cursor:
        def sort(self, *_args):
            return self

        async def to_list(self, _limit):
            return []

    class Shows:
        def find(self, query, *_args):
            queries.append(query)
            return Cursor()

        async def find_one(self, query, *_args):
            queries.append(query)
            return {"_id": "parent", "title": "Parent", "status": "archived"}

    async def fake_db():
        return type("DB", (), {"shows": Shows()})()

    monkeypatch.setattr(content_shows, "get_db", fake_db)
    client = _client(monkeypatch)
    with client as c:
        assert c.get("/api/content/shows-hierarchy").status_code == 200
        assert c.get("/api/content/shows/parent/children").status_code == 404
        assert queries[0] == {"status": {"$ne": "archived"}}
        c.editor()
        assert c.get("/api/content/shows-hierarchy").status_code == 200
        assert queries[-1] == {}
