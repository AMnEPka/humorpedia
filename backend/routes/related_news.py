"""Public contextual news feed and admin settings."""

from fastapi import APIRouter, Depends

from models.related_news import RelatedNewsEntityType, RelatedNewsSettings
from services.related_news import (
    get_related_news_settings,
    related_news_for,
    save_related_news_settings,
)
from utils.auth import require_admin
from utils.database import get_db


router = APIRouter(prefix="/related-news", tags=["related-news"])


@router.get("/settings", dependencies=[Depends(require_admin)])
async def get_settings():
    return (await get_related_news_settings(await get_db())).model_dump()


@router.put("/settings", dependencies=[Depends(require_admin)])
async def update_settings(settings: RelatedNewsSettings):
    return await save_related_news_settings(await get_db(), settings)


@router.get("/{entity_type}/{entity_id}")
async def get_related_news(entity_type: RelatedNewsEntityType, entity_id: str):
    return await related_news_for(await get_db(), entity_type, entity_id)
