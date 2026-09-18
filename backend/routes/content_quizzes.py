"""Quiz routes — CRUD."""
from fastapi import APIRouter, Query, Depends
from utils.auth import require_editor_on_write
from typing import Optional

from models.base import ContentStatus
from models.content import Quiz, QuizCreate, QuizUpdate
from services.crud import (
    check_slug_unique, create_content, update_content,
    delete_content, get_by_id_or_slug, list_content, build_query,
)
from services.link_resolver import LinkResolver

router = APIRouter(prefix="/content", tags=["quizzes"], dependencies=[Depends(require_editor_on_write)])


def _questions_count(modules) -> int:
    for module in modules or []:
        if str(getattr(module, "type", "")) in ("quiz_questions", "ModuleType.QUIZ_QUESTIONS"):
            return len((module.data or {}).get("questions") or [])
    return 0


@router.post("/quizzes", response_model=dict)
async def create_quiz(data: QuizCreate):
    """Create a quiz."""
    await check_slug_unique("quizzes", data.slug)
    quiz = Quiz(
        title=data.title, slug=data.slug, description=data.description,
        cover_image=data.cover_image, modules=data.modules,
        tags=data.tags, seo=data.seo or {}, status=data.status,
        questions_count=_questions_count(data.modules)
    )
    return await create_content(
        "quizzes", quiz, data.tags, published_status=ContentStatus.PUBLISHED
    )


@router.get("/quizzes", response_model=dict)
async def list_quizzes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """List quizzes with pagination."""
    query = build_query(status, tag, search, ["title"])
    return await list_content("quizzes", skip, limit, query, sort_field="published_at")


@router.get("/quizzes/{id_or_slug}", response_model=dict)
async def get_quiz(id_or_slug: str):
    """Get quiz by ID or slug."""
    quiz = await get_by_id_or_slug("quizzes", id_or_slug, "Quiz not found")
    await LinkResolver.resolve_document(quiz)
    return quiz


@router.put("/quizzes/{id}", response_model=dict)
async def update_quiz(id: str, data: QuizUpdate):
    """Update quiz."""
    if data.modules is not None:
        data = data.model_copy(update={"questions_count": _questions_count(data.modules)})
    return await update_content(
        "quizzes", id, data, "Quiz not found", published_status=ContentStatus.PUBLISHED
    )


@router.delete("/quizzes/{id}")
async def delete_quiz(id: str):
    """Delete quiz."""
    return await delete_content("quizzes", id, "Quiz not found")
