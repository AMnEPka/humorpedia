from services.modx_dump import ModxSite
from services.modx_polls import audit_polls, poll_definitions


def _site():
    return ModxSite(
        resources={
            29: {"id": 29, "parent": 0, "template": 1, "published": 1, "deleted": 0, "pagetitle": "Статьи"},
            100: {"id": 100, "parent": 29, "template": 13, "published": 1, "deleted": 0, "pagetitle": "Материал"},
            200: {"id": 200, "parent": 0, "template": 16, "published": 1, "deleted": 0, "pagetitle": "Лучший ответ?"},
            201: {"id": 201, "parent": 0, "template": 16, "published": 1, "deleted": 0, "pagetitle": "Без блока"},
        },
        tv_values={
            100: {"config": '[{"MIGX_formname":"voting","vote":"200"},{"MIGX_formname":"voting","vote":"999"}]'},
            200: {"vote_answers": '[{"MIGX_id":"1","answer":"Да","votes":"4"},{"MIGX_id":"2","answer":"Нет","votes":"1"}]'},
            201: {"vote_answers": '[{"MIGX_id":"1","answer":"A","votes":"0"},{"MIGX_id":"2","answer":"B","votes":"0"}]'},
        },
    )


def test_legacy_aggregates_do_not_store_user_ids():
    definitions, warnings = poll_definitions(_site(), [{"rid": 200, "answer_id": 1, "user_id": 77}])
    assert warnings == []
    assert definitions[0]["options"][0]["historical_votes"] == 4
    assert "user_id" not in str(definitions)


def test_audit_reports_missing_orphan_and_aggregate_mismatches():
    report = audit_polls(_site(), [
        {"rid": 200, "answer_id": 1, "user_id": 77},
        {"rid": 777, "answer_id": 1, "user_id": 88},
    ])
    assert report["missing_definitions"] == [999]
    assert report["orphan_vote_polls"] == [777]
    assert report["unplaced_definitions"] == [201]
    assert any(item["old_poll_id"] == 200 for item in report["aggregate_mismatches"])
