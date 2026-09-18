"""Build quiz documents from the legacy MODX dump.

Legacy questions store their answer variants as nested MIGX JSON in the
``answers`` field.  The public/admin application expects two page modules:
``quiz_questions`` and ``quiz_results``.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from services.modx_content import LinkMapper, clean_html, image_url, plain_text
from services.modx_dump import ModxSite, json_list
from services.modx_people import _module, _timestamp


QUIZ_PARENT_ID = 31
QUIZ_TEMPLATE = 16
CITY_PARENT_ID = 34
CITY_TEMPLATE = 19
_IMAGE_FILE_RE = re.compile(r"\.(?:avif|gif|jpe?g|png|svg|webp)(?:[?#].*)?$", re.I)
_RANGE_RE = re.compile(r"^\s*(\d+)\s*[-–—]\s*(\d+)\s*$")


def quiz_resources(site: ModxSite, *, include_unpublished: bool = False) -> List[dict]:
    """Return non-deleted direct children of the legacy quiz section."""
    return [
        resource for resource in site.resources.values()
        if resource.get("parent") == QUIZ_PARENT_ID
        and resource.get("template") == QUIZ_TEMPLATE
        and not resource.get("deleted")
        and (include_unpublished or resource.get("published"))
    ]


def quiz_url_builder(site: ModxSite):
    """Return a LinkMapper builder for legacy quiz resources."""
    def build(resource: dict) -> Optional[str]:
        if resource.get("parent") != QUIZ_PARENT_ID or resource.get("template") != QUIZ_TEMPLATE:
            return None
        slug = str(resource.get("alias") or "").strip("/")
        return f"/quizzes/{slug}" if slug else None

    return build


def quiz_path_builder(site: ModxSite):
    """Map bare city links used inside legacy quiz explanations."""
    city_slugs = {
        str(resource.get("alias") or "").strip("/")
        for resource in site.resources.values()
        if resource.get("parent") == CITY_PARENT_ID and resource.get("template") == CITY_TEMPLATE
    }

    def build(path: str) -> Optional[str]:
        clean = str(path or "").strip("/")
        slug = clean[:-5] if clean.endswith(".html") else clean
        if "/" not in slug and slug in city_slugs:
            return f"/city/{slug}"
        return None

    return build


def _truthy(value) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y", "да"}


def _legacy_image(value: str, field: str, warnings: List[str]) -> Optional[str]:
    value = str(value or "").strip()
    if not value:
        return None
    if not _IMAGE_FILE_RE.search(value):
        warnings.append(f"поле {field} не похоже на путь к изображению: {value}")
        return None
    return image_url(value)


def _question_modules(site: ModxSite, resource_id: int, mapper: Optional[LinkMapper]) -> Tuple[List[dict], List[str]]:
    questions: List[dict] = []
    warnings: List[str] = []
    for index, raw in enumerate(json_list(site.tv(resource_id, "quiz_questions")), start=1):
        if not isinstance(raw, dict):
            warnings.append(f"вопрос {index}: запись имеет неверный формат")
            continue
        text = plain_text(raw.get("question") or raw.get("title") or "")
        answers = [answer for answer in json_list(raw.get("answers")) if isinstance(answer, dict)]
        options = []
        for answer_index, answer in enumerate(answers):
            answer_text = plain_text(answer.get("text") or answer.get("answer") or "")
            if not answer_text:
                continue
            options.append({
                "id": chr(97 + answer_index) if answer_index < 26 else str(answer_index + 1),
                "text": answer_text,
                "correct": _truthy(answer.get("right") or answer.get("correct")),
            })
        correct_count = sum(option["correct"] for option in options)
        if not text or len(options) < 2 or correct_count == 0:
            warnings.append(
                f"вопрос {index}: пропущен (текст={bool(text)}, вариантов={len(options)}, правильных={correct_count})"
            )
            continue

        question_image = _legacy_image(raw.get("image") or raw.get("img") or "", f"вопрос {index}.image", warnings)
        try:
            question_id = int(raw.get("MIGX_id") or index)
        except (TypeError, ValueError):
            question_id = index
        questions.append({
            "id": question_id,
            "type": "multiple" if correct_count > 1 else "single",
            "question": text,
            "image": question_image,
            "options": options,
            "explanation": None,
            "success_explanation": clean_html(raw.get("text_success") or "", mapper) or None,
            "error_explanation": clean_html(raw.get("text_error") or "", mapper) or None,
        })

    return questions, warnings


def _result_module(site: ModxSite, resource_id: int, question_count: int) -> Tuple[List[dict], List[str]]:
    warnings: List[str] = []
    raw_results = json_list(site.tv(resource_id, "quiz_final"))
    if not raw_results:
        raw_results = json_list(site.tv(QUIZ_PARENT_ID, "quiz_final"))

    results: List[dict] = []
    for index, raw in enumerate(raw_results, start=1):
        if not isinstance(raw, dict):
            warnings.append(f"результат {index}: запись имеет неверный формат")
            continue
        match = _RANGE_RE.match(str(raw.get("range") or ""))
        if not match:
            warnings.append(f"результат {index}: не распознан диапазон {raw.get('range')!r}")
            continue
        minimum, maximum = map(int, match.groups())
        if minimum > question_count:
            continue
        maximum = min(maximum, question_count)
        title = plain_text(raw.get("text") or raw.get("title") or "")
        if not title:
            warnings.append(f"результат {index}: пустой текст")
            continue
        results.append({
            "min_score": minimum,
            "max_score": maximum,
            "title": title,
            "description": "",
            "image": _legacy_image(raw.get("img") or raw.get("image") or "", f"результат {index}.image", warnings),
        })
    return results, warnings


def build_quiz(
    site: ModxSite,
    resource_id: int,
    mapper: Optional[LinkMapper] = None,
) -> Tuple[dict, dict, List[str]]:
    """Build a QuizCreate payload plus legacy-only fields."""
    resource = site.resources[resource_id]
    if resource.get("parent") != QUIZ_PARENT_ID or resource.get("template") != QUIZ_TEMPLATE:
        raise ValueError(f"Resource {resource_id} is not a legacy quiz")

    title = plain_text(resource.get("pagetitle") or "")
    slug = str(resource.get("alias") or "").strip("/")
    published = bool(resource.get("published")) and not resource.get("deleted")
    questions, warnings = _question_modules(site, resource_id, mapper)
    results, result_warnings = _result_module(site, resource_id, len(questions))
    warnings.extend(result_warnings)
    if not questions:
        warnings.append("в квизе нет пригодных вопросов")
    if not results:
        warnings.append("в квизе нет пригодных диапазонов результатов")

    cover_url = _legacy_image(site.tv(resource_id, "img"), "img", warnings)
    cover_image = None
    if cover_url:
        cover_image = {"url": cover_url, "alt": title, "caption": "", "thumbnail": cover_url}

    description = plain_text(resource.get("description") or resource.get("introtext") or "") or None
    payload = {
        "title": title,
        "slug": slug,
        "status": "published" if published else "draft",
        "description": description,
        "cover_image": cover_image,
        "modules": [
            _module("quiz_questions", 0, "Вопросы", {"questions": questions}),
            _module("quiz_results", 1, "Результаты", {"results": results}),
        ],
        "questions_count": len(questions),
        "tags": site.tags_of(resource_id),
        "seo": {
            "meta_title": plain_text(resource.get("longtitle") or "") or title,
            "meta_description": plain_text(resource.get("description") or "") or description,
            "keywords": [part.strip() for part in str(resource.get("keywords") or "").split(",") if part.strip()],
        },
    }

    votes = int(resource.get("votes") or 0)
    old_path = "/" + str(resource.get("uri") or f"quiz/{slug}.html").strip("/")
    extra = {
        "old_id": int(resource_id),
        "old_urls": [old_path],
        "rating": round(min(10.0, max(0.0, float(resource.get("rating") or 0))), 2),
        "votes_count": votes,
    }
    created_at = _timestamp(resource.get("createdon"))
    updated_at = _timestamp(resource.get("editedon"))
    published_at = (_timestamp(resource.get("publishedon")) or created_at) if published else None
    if created_at:
        extra["created_at"] = created_at
    if updated_at:
        extra["updated_at"] = updated_at
    if published_at:
        extra["published_at"] = published_at
    return payload, extra, warnings
