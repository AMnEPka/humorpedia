"""Public "Читайте также" recommendations."""
from fastapi import APIRouter, Query

from services.recommendations import recommendations_for
from utils.database import get_db

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("")
@router.get("/")
async def get_recommendations(
    content_type: str,
    content_id: str,
    limit: int | None = Query(None, ge=1, le=6),
):
    return await recommendations_for(await get_db(), content_type, content_id, limit)
