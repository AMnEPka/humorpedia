"""Legacy quiz hrefs resolve by stored aliases without guessing a same-slug page."""
import asyncio
from copy import deepcopy

import pytest

from services.link_resolver import collect_keys, replace_links, resolve_targets


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def __aiter__(self):
        async def iterate():
            for row in self.rows:
                yield deepcopy(row)
        return iterate()


class Collection:
    def __init__(self, rows):
        self.rows = rows

    def find(self, query, projection=None):
        def matches(row):
            for field, expected in query.items():
                value = row.get(field)
                if isinstance(expected, dict):
                    if "$ne" in expected and value == expected["$ne"]:
                        return False
                    if "$in" in expected:
                        values = value if isinstance(value, list) else [value]
                        if not any(item in expected["$in"] for item in values):
                            return False
                elif isinstance(value, list):
                    if expected not in value:
                        return False
                elif value != expected:
                    return False
            return True
        return Cursor([row for row in self.rows if matches(row)])


class Database:
    def __init__(self, **collections):
        self.collections = collections

    def __getitem__(self, kind):
        return Collection(self.collections.get(kind, []))


def quiz_database(status="published", **extra):
    records = {
        "quizzes": [{"_id": "quiz", "slug": "bolshoe-shou", "status": status,
                     "old_urls": ["/quiz/big-show.html"]}],
        "shows": [{"_id": "show", "slug": "big-show", "full_path": "big-show",
                   "status": "published", "old_urls": ["/show/big-show.html"]}],
        "news": [{"_id": "news", "slug": "big-show", "status": "published",
                  "old_urls": ["/novosti/big-show.html"]}],
    }
    records.update(extra)
    return Database(**records)


@pytest.mark.parametrize("href", ["/quiz/big-show", "/quiz/big-show.html"])
def test_legacy_quiz_alias_keeps_label_attributes_and_suffix(href):
    source = (f'<p><a href="{href}?from=old&amp;page=2#rules" target="_blank" '
              'rel="noopener"><b>15 вопросов</b></a></p>')
    resolved = asyncio.run(resolve_targets(quiz_database(), collect_keys(source)))
    assert replace_links(source, resolved) == (
        '<p><a href="/quizzes/bolshoe-shou?from=old&amp;page=2#rules" target="_blank" '
        'rel="noopener"><b>15 вопросов</b></a></p>'
    )


@pytest.mark.parametrize("status", ["archived", None])
def test_quiz_archive_filter_matches_existing_content_contract(status):
    resolved = asyncio.run(resolve_targets(quiz_database(status), {"quiz/big-show"}))
    expected = None if status == "archived" else "/quizzes/bolshoe-shou"
    assert resolved == {"quiz/big-show": expected}
    if status == "archived":
        assert replace_links('<a href="/quiz/big-show"><b>Квиз</b></a>', resolved) == '<b>Квиз</b>'


def test_missing_quiz_does_not_link_to_same_slug_show_or_news():
    assert asyncio.run(resolve_targets(quiz_database(quizzes=[]), {"quiz/big-show"})) == {
        "quiz/big-show": None,
    }


def test_existing_old_url_priority_is_preserved():
    news = [{"_id": "news", "slug": "existing", "status": "published",
             "old_urls": ["/quiz/big-show.html"]}]
    assert asyncio.run(resolve_targets(quiz_database(news=news), {"quiz/big-show"})) == {
        "quiz/big-show": "/news/existing",
    }


def test_direct_canonical_path_takes_priority_over_legacy_quiz_alias():
    quizzes = [{"_id": "quiz", "slug": "quiz", "status": "published",
                "old_urls": ["/news/big-show.html"]}]
    assert asyncio.run(resolve_targets(quiz_database(quizzes=quizzes), {"news/big-show"})) == {
        "news/big-show": "/news/big-show",
    }
