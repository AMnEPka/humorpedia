import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from starlette.requests import Request

import routes.correction_suggestions as suggestion_routes
from models.correction_suggestion import CorrectionSuggestionCreate, CorrectionSuggestionReview


def _request():
    return Request({"type": "http", "method": "POST", "path": "/api/correction-suggestions", "headers": []})


def _payload(**overrides):
    data = {
        "page_title": "Александр Гудков",
        "page_path": "/people/aleksandr-gudkov",
        "section": "Биография / основной текст",
        "message": "Исправьте год участия в команде.",
    }
    data.update(overrides)
    return CorrectionSuggestionCreate(**data)


def test_suggestion_accepts_plain_text_and_optional_email(monkeypatch):
    collection = SimpleNamespace(insert_one=AsyncMock())
    monkeypatch.setattr(
        suggestion_routes,
        "get_db",
        AsyncMock(return_value=SimpleNamespace(correction_suggestions=collection)),
    )

    result = asyncio.run(suggestion_routes.create_correction_suggestion(
        _payload(email="reader@example.com", source="https://example.com/source"),
        _request(),
    ))

    assert result["accepted"] is True
    inserted = collection.insert_one.await_args.args[0]
    assert inserted["status"] == "new"
    assert inserted["email"] == "reader@example.com"
    assert inserted["message"] == "Исправьте год участия в команде."


def test_honeypot_is_accepted_without_storage(monkeypatch):
    collection = SimpleNamespace(insert_one=AsyncMock())
    monkeypatch.setattr(
        suggestion_routes,
        "get_db",
        AsyncMock(return_value=SimpleNamespace(correction_suggestions=collection)),
    )

    result = asyncio.run(suggestion_routes.create_correction_suggestion(
        _payload(website="spam.example"), _request()
    ))

    assert result == {"accepted": True}
    collection.insert_one.assert_not_awaited()


@pytest.mark.parametrize("page_path", ["https://evil.example/page", "//evil.example/page"])
def test_external_page_path_is_rejected(page_path):
    with pytest.raises(ValidationError):
        _payload(page_path=page_path)


def test_editor_can_mark_suggestion_fixed(monkeypatch):
    collection = SimpleNamespace(
        update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)),
        find_one=AsyncMock(),
    )
    monkeypatch.setattr(
        suggestion_routes,
        "get_db",
        AsyncMock(return_value=SimpleNamespace(correction_suggestions=collection)),
    )

    result = asyncio.run(suggestion_routes.review_correction_suggestion(
        "suggestion-1",
        CorrectionSuggestionReview(status="fixed", admin_comment="Исправлено в карточке."),
        user={"_id": "editor-1"},
    ))

    assert result == {"id": "suggestion-1", "status": "fixed"}
    changes = collection.update_one.await_args.args[1]["$set"]
    assert changes["reviewed_by"] == "editor-1"
    assert changes["admin_comment"] == "Исправлено в карточке."
