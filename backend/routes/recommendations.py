"""Public recommendations and administrator-managed global settings."""
from fastapi import APIRouter, Depends, Query, Response

from models.recommendation import RecommendationSettings
from services.recommendations import (
    get_recommendation_settings,
    recommendations_for,
    save_recommendation_settings,
)
from utils.auth import require_admin
from utils.database import get_db

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/settings", dependencies=[Depends(require_admin)])
async def get_settings(response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return (await get_recommendation_settings(await get_db())).model_dump()


@router.put("/settings", dependencies=[Depends(require_admin)])
async def update_settings(settings: RecommendationSettings, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return await save_recommendation_settings(await get_db(), settings)


@router.get("")
@router.get("/")
async def get_recommendations(
    content_type: str,
    content_id: str,
    limit: int | None = Query(None, ge=1, le=12),
):
    return await recommendations_for(await get_db(), content_type, content_id, limit)
