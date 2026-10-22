import pytest

from scripts.profile_api import (
    _explain_summary,
    _rate_limit_override,
    _explainable_command,
    _command_metrics,
    _safe_query_shape,
    _content_hash,
    _p95,
    _validate_read_roles,
    validate_db_name,
    validate_plan,
)


def test_database_name_requires_isolated_per_run_database():
    assert validate_db_name('humorpedia_perf_0123456789abcdef0123456789abcdef')
    with pytest.raises(ValueError):
        validate_db_name('humorpedia')
    with pytest.raises(ValueError):
        validate_db_name('humorpedia_perf_not-a-uuid')


def test_read_role_must_be_the_only_authenticated_role_on_target_database():
    role = [{'role': 'read', 'db': 'humorpedia_perf_0123456789abcdef0123456789abcdef'}]
    _validate_read_roles(role, role[0]['db'])
    with pytest.raises(ValueError):
        _validate_read_roles(role + [{'role': 'readWrite', 'db': role[0]['db']}], role[0]['db'])
    with pytest.raises(ValueError):
        _validate_read_roles([{'role': 'read', 'db': 'humorpedia'}], role[0]['db'])


def test_plan_accepts_only_named_get_routes_and_rejects_hierarchy_and_absolute_urls():
    plan = validate_plan([
        {'name': 'search', 'path': '/api/content/search?q=final'},
        {'name': 'person-card', 'path': '/api/content/people/r8-person'},
        {'name': 'team-card', 'path': '/api/content/teams/r8-team'},
        {'name': 'season', 'path': '/api/content/kvn/by-path/kvn/vl-kvn/vl-2026'},
        {'name': 'recommendations', 'path': '/api/recommendations?content_type=article&content_id=sample'},
    ])
    assert [item['name'] for item in plan] == ['search', 'person-card', 'team-card', 'season', 'recommendations']
    for path in ('/api/content/kvn-hierarchy', '/api/../health', 'https://localhost/api/search'):
        with pytest.raises(ValueError):
            validate_plan([{'name': 'bad', 'path': path}])


def test_p95_uses_nearest_rank_for_small_sample_sets():
    assert _p95([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]) == 19
    assert _p95([]) is None


def test_explain_summary_uses_top_level_totals_without_double_counting_stages():
    explain = {
        'executionStats': {
            'nReturned': 4,
            'totalDocsExamined': 40,
            'totalKeysExamined': 12,
            'executionStages': {
                'stage': 'FETCH', 'nReturned': 4, 'docsExamined': 40,
                'inputStage': {'stage': 'IXSCAN', 'nReturned': 4, 'keysExamined': 12},
            },
        },
        'queryPlanner': {'winningPlan': {'stage': 'FETCH', 'inputStage': {'stage': 'IXSCAN', 'indexName': 'x_1'}}},
    }
    summary = _explain_summary(explain)
    assert summary['n_returned'] == 4
    assert summary['docs_examined'] == 40
    assert summary['keys_examined'] == 12
    assert summary['index_names'] == ['x_1']
    assert summary['statistics_scope'] == 'query'


def test_aggregate_explain_summary_reads_cursor_totals_and_plan():
    explain = {
        'stages': [{
            '$cursor': {
                'queryPlanner': {'winningPlan': {'stage': 'IXSCAN', 'indexName': 'status_1'}},
                'executionStats': {
                    'nReturned': 7, 'totalDocsExamined': 21, 'totalKeysExamined': 9,
                    'executionStages': {'nReturned': 7, 'docsExamined': 21},
                },
            },
        }, {'$group': {'nReturned': 1, 'internal': 'ignored'}}],
    }
    summary = _explain_summary(explain)
    assert summary['n_returned'] == 7
    assert summary['docs_examined'] == 21
    assert summary['keys_examined'] == 9
    assert summary['index_names'] == ['status_1']
    assert summary['statistics_scope'] == 'aggregate_cursor'


def test_rate_limit_override_restores_state_after_exception_and_is_noop_when_disabled():
    class Limiter:
        enabled = True

    limiter = Limiter()
    with pytest.raises(RuntimeError):
        with _rate_limit_override(limiter, True):
            assert limiter.enabled is False
            raise RuntimeError('profile failed')
    assert limiter.enabled is True

    limiter.enabled = False
    with _rate_limit_override(limiter, False):
        assert limiter.enabled is False
    assert limiter.enabled is False


def test_getmore_is_not_explained_and_volatile_command_fields_are_removed():
    assert _explainable_command({'getMore': 12, 'collection': 'kvn'}) is None
    command = _explainable_command({
        'find': 'kvn', 'filter': {'status': {'$eq': 'published', 'comment': 'user-filter-value'}}, '$db': 'humorpedia_perf_x',
        'lsid': {'id': 'secret'}, '$clusterTime': {'clusterTime': 'volatile'},
    })
    assert command == {'find': 'kvn', 'filter': {'status': {'$eq': 'published', 'comment': 'user-filter-value'}}}


def test_query_shape_is_safe_and_command_hash_is_attached_to_sample_metrics():
    command = {'find': 'kvn', 'filter': {'status': {'$ne': 'archived'}, 'season_data.year': 2026}}
    shape = _safe_query_shape(command)
    assert shape == {
        'command': 'find', 'collection': 'kvn',
        'fields': ['season_data.year', 'status'], 'operators': ['$ne'],
        'options': ['filter'],
    }
    assert 'archived' not in str(shape)
    metrics = _command_metrics([
        {'name': 'find', 'command': command, 'duration_ms': 3, 'docs_returned': 2},
    ])
    assert metrics['query_hashes'] == [metrics['explainable_commands'][0]['hash']]


def test_content_hash_ignores_only_root_kvn_team_data_version():
    path = '/api/content/kvn/by-path/kvn/vl-kvn/vl-2026'
    first = {
        'title': 'Season', 'team_data_version': '2026-10-21T10:00:00Z',
        'updated_at': 'same', 'nested': {'team_data_version': 'nested-a'},
    }
    root_stamp_changed = {**first, 'team_data_version': '2026-10-21T10:00:01Z'}
    assert _content_hash(path, first) == _content_hash(path, root_stamp_changed)

    updated_at_changed = {**first, 'updated_at': 'changed'}
    assert _content_hash(path, first) != _content_hash(path, updated_at_changed)

    nested_stamp_changed = {**first, 'nested': {'team_data_version': 'nested-b'}}
    assert _content_hash(path, first) != _content_hash(path, nested_stamp_changed)

    non_kvn_path = '/api/content/people/person-a'
    assert _content_hash(non_kvn_path, first) != _content_hash(non_kvn_path, root_stamp_changed)


def test_command_metrics_separate_logical_reads_from_getmore_and_dedupe_explains():
    command = {'find': 'kvn', 'filter': {'status': 'published'}}
    metrics = _command_metrics([
        {'name': 'find', 'command': command, 'duration_ms': 3, 'docs_returned': 2},
        {'name': 'getMore', 'command': {'getMore': 1, 'collection': 'kvn'}, 'duration_ms': 1, 'docs_returned': 1},
        {'name': 'find', 'command': command, 'duration_ms': 2, 'docs_returned': 0},
    ])
    assert metrics['logical_commands'] == {'find': 2}
    assert metrics['wire_commands'] == {'find': 2, 'getMore': 1}
    assert metrics['mongo_docs_returned'] == 3
    assert len(metrics['explainable_commands']) == 1
    assert metrics['query_hashes'] == [metrics['explainable_commands'][0]['hash']]
    assert metrics['mongo_duration_ms'] == 6

def test_timing_only_sample_never_attaches_command_listener_and_marks_query_metrics_unmeasured():
    import asyncio
    import json
    from types import SimpleNamespace
    from scripts.profile_api import _profile_request, _sample_summary

    class Client:
        async def get(self, path):
            return SimpleNamespace(status_code=200, content=json.dumps({"title": "same"}).encode())

    class Cache:
        calls = 0
        def flush_all(self):
            self.calls += 1

    cache = Cache()
    counter = SimpleNamespace(_buffer={"old": 1})
    sample = asyncio.run(_profile_request(
        Client(), None, {"name": "person", "path": "/api/content/people/person"},
        clear_cache=True, cache_service=cache, views_counter=counter,
    ))
    assert sample["duration_ms"] >= 0 and sample["cpu_ms"] >= 0
    assert sample["started_at_unix_ns"] > 0
    assert sample["logical_commands"] is None
    assert sample["wire_commands"] is None
    assert sample["mongo_duration_ms"] is None
    assert sample["mongo_docs_returned"] is None
    assert sample["explainable_commands"] == []
    assert cache.calls == 1 and counter._buffer == {}
    summary = _sample_summary([sample])
    assert summary["logical_command_count"] is None
    assert summary["wire_command_count"] is None
    assert summary["mongo_duration_ms"] is None
    assert summary["mongo_docs_returned"] is None
    assert summary["latency_ms"]["p95"] == sample["duration_ms"]

def test_timing_only_factory_does_not_register_mongo_listener(monkeypatch):
    from scripts import profile_api
    attached = []
    monkeypatch.setattr(profile_api, "register", attached.append)
    assert profile_api._make_listener(True) is None
    assert attached == []
    listener = profile_api._make_listener(False)
    assert attached == [listener]

@pytest.mark.parametrize('output_error', [False, True])
def test_full_timing_profile_restores_resources_on_success_and_output_error(monkeypatch, tmp_path, output_error):
    import asyncio
    import json
    import logging
    import os
    import sys
    from types import SimpleNamespace
    from fastapi import FastAPI
    from scripts import profile_api

    app = FastAPI()
    @app.get("/api/content/people/person")
    async def person():
        return {"title": "same"}

    limiter = SimpleNamespace(enabled=True)
    closed = []
    async def get_db():
        return None
    async def close_db():
        closed.append(True)

    monkeypatch.setitem(sys.modules, "server", SimpleNamespace(app=app, limiter=limiter))
    monkeypatch.setitem(sys.modules, "utils.database", SimpleNamespace(get_db=get_db, close_db=close_db))
    monkeypatch.setenv("DB_NAME", "original-test-name")
    logger = logging.getLogger("httpx")
    previous = logger.level
    output = tmp_path if output_error else tmp_path / "profile.json"
    def run():
        asyncio.run(profile_api._run_profile(
            "humorpedia_perf_0123456789abcdef0123456789abcdef",
            [{"name": "person", "path": "/api/content/people/person"}],
            2, "test", output, without_rate_limit=True, timing_only=True,
        ))
    if output_error:
        with pytest.raises(IsADirectoryError):
            run()
    else:
        run()
        report = json.loads(output.read_text())
        assert report["measurement_mode"] == "timing_only"
        assert report["query_metrics_collected"] is False
        assert report["explain"] == []
        assert report["scenarios"][0]["cold"]["summary"]["logical_command_count"] is None
    assert limiter.enabled is True
    assert closed == [True]
    assert os.environ["DB_NAME"] == "original-test-name"
    assert logger.level == previous
