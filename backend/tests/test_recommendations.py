import asyncio

import pytest
from pydantic import ValidationError

from models.recommendation import DEFAULT_RECOMMENDATION_TYPES, RecommendationSettings
from services.recommendations import (
    get_recommendation_settings,
    public_item,
    rank_candidates,
    recommendations_for,
    save_recommendation_settings,
)


def _matches(document, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(document, clause) for clause in expected):
                return False
            continue
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$in" in expected:
                actual_values = actual if isinstance(actual, list) else [actual]
                if not any(value in expected["$in"] for value in actual_values):
                    return False
            if "$nin" in expected and actual in expected["$nin"]:
                return False
        elif isinstance(actual, list) and expected not in actual:
            return False
        elif not isinstance(actual, list) and actual != expected:
            return False
    return True


class _Cursor:
    def __init__(self, items):
        self.items = items

    async def to_list(self, _limit):
        items = self.items if _limit is None else self.items[:_limit]
        return [dict(item) for item in items]

    def sort(self, _fields):
        return self

    def limit(self, limit):
        self.items = self.items[:limit]
        return self


class _Collection:
    def __init__(self, docs=None):
        self.docs = [dict(item) for item in (docs or [])]

    async def find_one(self, query, *_args, **_kwargs):
        return next((dict(doc) for doc in self.docs if _matches(doc, query)), None)

    def find(self, query, _projection=None):
        return _Cursor([doc for doc in self.docs if _matches(doc, query)])

    async def update_one(self, query, update, upsert=False):
        document = next((doc for doc in self.docs if _matches(doc, query)), None)
        if document is None and upsert:
            document = dict(query)
            self.docs.append(document)
        if document is not None:
            document.update(update.get("$set", {}))


class _Db:
    def __init__(self, **collections):
        names = [
            "site_settings", "articles", "news", "people", "teams", "shows",
            "cities", "kvn", "sections", "quizzes",
        ]
        for name in names:
            setattr(self, name, _Collection(collections.get(name)))

    def __getitem__(self, key):
        return getattr(self, key)


def test_settings_defaults_and_validation():
    settings = RecommendationSettings()
    assert settings.max_items == 3
    assert settings.result_types == DEFAULT_RECOMMENDATION_TYPES
    assert "news" not in settings.result_types
    assert settings.apply_to.kvn_teams is True

    assert RecommendationSettings(result_types=["article", "article", "person"]).result_types == ["article", "person"]
    with pytest.raises(ValidationError):
        RecommendationSettings(result_types=[])
    with pytest.raises(ValidationError):
        RecommendationSettings(max_items=13)


def test_settings_are_saved_and_read_from_site_settings():
    db = _Db()
    saved = asyncio.run(save_recommendation_settings(
        db,
        RecommendationSettings(max_items=6, result_types=["person", "news"]),
    ))
    loaded = asyncio.run(get_recommendation_settings(db))

    assert saved["max_items"] == 6
    assert loaded.max_items == 6
    assert loaded.result_types == ["person", "news"]
    assert db.site_settings.docs[0]["_id"] == "recommendations"
    assert db.site_settings.docs[0]["updated_at"]


def test_rank_mixed_content_prefers_direct_relation_then_tags():
    source = {"_id": "person-1", "tags": ["КВН"]}
    candidates = [
        {"_id": "team-tag", "_recommendation_type": "kvn_team", "tags": ["КВН"], "views": 50},
        {"_id": "article-direct", "_recommendation_type": "article", "related_person_ids": ["person-1"]},
        {"_id": "article-tag", "_recommendation_type": "article", "tags": ["КВН"], "views": 100},
    ]
    assert [item["_id"] for item in rank_candidates(source, "person", candidates, ["article", "kvn_team"])] == [
        "article-direct", "article-tag", "team-tag",
    ]


def test_manual_articles_keep_priority_then_mixed_automatic_results():
    db = _Db(
        site_settings=[{
            "_id": "recommendations", "max_items": 3, "result_types": ["article", "person"],
        }],
        articles=[
            {"_id": "current", "slug": "current", "title": "Текущая", "status": "published", "tags": ["КВН"],
             "related_article_ids": ["manual", "archived", "missing", "manual"]},
            {"_id": "manual", "slug": "manual", "title": "Ручная", "status": "draft"},
            {"_id": "archived", "slug": "archived", "title": "Архив", "status": "archived"},
            {"_id": "automatic", "slug": "automatic", "title": "Автоматическая", "status": "published", "tags": ["КВН"]},
        ],
        people=[
            {"_id": "person", "slug": "person", "title": "Связанный человек", "status": "draft", "article_ids": ["current"]},
        ],
    )

    result = asyncio.run(recommendations_for(db, "article", "current"))

    assert result["enabled"] is True
    assert [(item["id"], item["type"], item["manual"]) for item in result["items"]] == [
        ("manual", "article", True),
        ("person", "person", False),
        ("automatic", "article", False),
    ]


def test_disabled_target_hides_block_without_loading_candidates():
    db = _Db(
        site_settings=[{
            "_id": "recommendations", "result_types": ["article"],
            "apply_to": {"people": False},
        }],
        people=[{"_id": "person", "slug": "person", "title": "Человек", "status": "published"}],
        articles=[{"_id": "article", "slug": "article", "title": "Статья", "status": "published"}],
    )
    result = asyncio.run(recommendations_for(db, "person", "person"))
    assert result == {"enabled": False, "items": [], "max_items": 3}


def test_team_targets_are_selected_by_team_subtype():
    db = _Db(
        site_settings=[{
            "_id": "recommendations", "result_types": ["article"],
            "apply_to": {"kvn_teams": False, "show_teams": True},
        }],
        teams=[
            {"_id": "kvn-team", "slug": "kvn-team", "title": "Команда КВН", "status": "published"},
            {"_id": "show-team", "slug": "show-team", "title": "Команда шоу", "status": "published",
             "show_id": "show"},
        ],
        articles=[{"_id": "article", "slug": "article", "title": "Статья", "status": "published"}],
    )

    kvn_result = asyncio.run(recommendations_for(db, "team", "kvn-team"))
    show_result = asyncio.run(recommendations_for(db, "team", "show-team"))

    assert kvn_result["enabled"] is False
    assert show_result["enabled"] is True
    assert [item["id"] for item in show_result["items"]] == ["article"]


def test_kvn_source_falls_back_to_sections_collection():
    db = _Db(
        site_settings=[{"_id": "recommendations", "result_types": ["article"]}],
        sections=[{
            "_id": "section", "slug": "special", "full_path": "kvn/special",
            "title": "Раздел КВН", "status": "published", "article_ids": ["article"],
        }],
        articles=[{"_id": "article", "slug": "article", "title": "Статья", "status": "published"}],
    )

    result = asyncio.run(recommendations_for(db, "kvn", "kvn/special"))

    assert result["enabled"] is True
    assert [item["id"] for item in result["items"]] == ["article"]


def test_cards_build_public_urls_and_type_labels():
    kvn_team = public_item({"_id": "t1", "slug": "soyuz", "title": "Союз"}, "kvn_team")
    show_team = public_item(
        {"_id": "t2", "slug": "soyuz", "title": "Союз", "show_id": "s1", "full_path": "show/teams/soyuz"},
        "show_team",
    )
    kvn_page = public_item({"_id": "k1", "slug": "season", "full_path": "kvn/vl-kvn/season", "title": "Сезон"}, "kvn")
    assert kvn_team["url"] == "/kvn/teams/soyuz"
    assert show_team["url"] == "/shows/show/teams/soyuz"
    assert kvn_page["url"] == "/kvn/vl-kvn/season"
    assert kvn_team["type_label"] == "Команда КВН"
