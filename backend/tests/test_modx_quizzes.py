"""Legacy MODX quiz conversion without database access."""
import json

from models.content import QuizCreate, QuizUpdate
from routes.redirects import _try_pattern_redirect
from services.modx_content import LinkMapper
from services.modx_dump import ModxSite
from services.modx_quizzes import build_quiz, quiz_path_builder, quiz_resources, quiz_url_builder


def quiz_site():
    site = ModxSite()
    site.resources = {
        31: {"id": 31, "uri": "quiz/"},
        77: {"id": 77, "template": 20, "alias": "guest", "uri": "people/guest.html"},
        78: {"id": 78, "parent": 34, "template": 19, "alias": "tyumen", "uri": "city/tyumen.html"},
        100: {
            "id": 100, "parent": 31, "template": 16, "pagetitle": "Квиз",
            "longtitle": "Большой квиз", "alias": "quiz-one", "uri": "quiz/quiz-one.html",
            "published": 1, "deleted": 0, "createdon": 1716367575, "publishedon": 1716367560,
            "editedon": 1716459683, "description": "Описание", "introtext": "", "keywords": "КВН, юмор",
            "rating": 8.75, "votes": 4,
        },
        101: {
            "id": 101, "parent": 31, "template": 16, "pagetitle": "Черновик",
            "alias": "draft", "uri": "quiz/draft.html", "published": 0, "deleted": 0,
        },
    }
    site.by_uri = {
        resource["uri"].strip("/"): resource_id
        for resource_id, resource in site.resources.items() if resource.get("uri")
    }
    site.tv_values[31] = {
        "quiz_final": json.dumps([
            {"range": "0-1", "text": "Надо ещё попробовать", "img": ""},
            {"range": "2-4", "text": "Отлично", "img": "images/quiz/result.jpg"},
            {"range": "5-8", "text": "Недостижимый результат", "img": ""},
        ])
    }
    site.tv_values[100] = {
        "img": "images/quiz/cover.jpg",
        "tags": "5",
        "quiz_questions": json.dumps([
            {
                "MIGX_id": "1", "question": "Кто был гостем?",
                "answers": json.dumps([
                    {"text": "Первый", "right": "1"},
                    {"text": "Второй"},
                ]),
                "text_success": '<p>Верно: <a href="people/guest.html">гость</a> из <a href="tyumen.html">Тюмени</a>.</p>',
                "text_error": "Нет, правильный ответ — первый.",
            },
            {
                "MIGX_id": "2", "question": "Выберите оба",
                "answers": json.dumps([
                    {"text": "A", "right": "1"},
                    {"text": "B", "right": "true"},
                    {"text": "C"},
                ]),
            },
            {
                "MIGX_id": "3", "question": "Некорректный",
                "answers": json.dumps([{"text": "Без правильного"}, {"text": "Тоже"}]),
            },
        ]),
    }
    site.tags = {5: "КВН"}
    return site


def test_build_quiz_parses_nested_answers_explanations_and_shared_results():
    site = quiz_site()
    mapper = LinkMapper(
        site,
        _try_pattern_redirect,
        url_builders=[quiz_url_builder(site)],
        path_builders=[quiz_path_builder(site)],
    )

    payload, extra, warnings = build_quiz(site, 100, mapper)

    QuizCreate(**payload)
    QuizUpdate(**payload)
    assert payload["questions_count"] == 2
    questions = payload["modules"][0]["data"]["questions"]
    assert questions[0]["type"] == "single"
    assert [option["correct"] for option in questions[0]["options"]] == [True, False]
    assert questions[0]["success_explanation"] == (
        '<p>Верно: <a href="/people/guest">гость</a> из <a href="/city/tyumen">Тюмени</a>.</p>'
    )
    assert questions[0]["error_explanation"] == "Нет, правильный ответ — первый."
    assert questions[1]["type"] == "multiple"
    assert [result["max_score"] for result in payload["modules"][1]["data"]["results"]] == [1, 2]
    assert payload["cover_image"]["url"] == "/media/imported/images/quiz/cover.jpg"
    assert payload["tags"] == ["КВН"]
    assert extra["old_id"] == 100 and extra["old_urls"] == ["/quiz/quiz-one.html"]
    assert extra["rating"] == 8.75 and extra["votes_count"] == 4
    assert any("вопрос 3: пропущен" in warning for warning in warnings)


def test_quiz_selection_url_builder_and_redirect():
    site = quiz_site()

    assert [resource["id"] for resource in quiz_resources(site)] == [100]
    assert [resource["id"] for resource in quiz_resources(site, include_unpublished=True)] == [100, 101]
    assert quiz_url_builder(site)(site.resources[100]) == "/quizzes/quiz-one"
    assert _try_pattern_redirect("/quiz/quiz-one.html") == "/quizzes/quiz-one"
