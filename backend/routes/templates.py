"""Page templates management routes"""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional, List
from datetime import datetime, timezone

from models.modules import PageTemplate, PageModule
from utils.database import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/templates", tags=["templates"])


@router.post("", response_model=dict)
async def create_template(data: PageTemplate, request: Request):
    """Create a new page template"""
    user = await get_current_user(request)
    if not user or user.get("role") not in ["admin", "editor"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    db = await get_db()
    
    # Check name uniqueness
    existing = await db.templates.find_one({"name": data.name})
    if existing:
        raise HTTPException(status_code=400, detail="Шаблон с таким именем уже существует")
    
    doc = data.model_dump()
    doc["_id"] = data.id
    doc["created_by"] = user["_id"]
    
    await db.templates.insert_one(doc)
    
    return {"id": doc["_id"], "name": data.name}


@router.get("", response_model=dict)
async def list_templates(
    content_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """List all templates"""
    db = await get_db()
    
    query = {}
    if content_type:
        query["content_type"] = content_type
    
    total = await db.templates.count_documents(query)
    cursor = db.templates.find(query).skip(skip).limit(limit).sort("name", 1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/default/{content_type}", response_model=dict)
async def get_default_template(content_type: str):
    """Get default template for content type"""
    db = await get_db()
    
    template = await db.templates.find_one({
        "content_type": content_type,
        "is_default": True
    })
    
    if not template:
        # Return empty template
        return {
            "id": None,
            "name": f"Стандартный {content_type}",
            "content_type": content_type,
            "modules": [],
            "is_default": True
        }
    
    return template


@router.get("/{template_id}", response_model=dict)
async def get_template(template_id: str):
    """Get template by ID"""
    db = await get_db()
    
    template = await db.templates.find_one({"_id": template_id})
    
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    return template


@router.put("/{template_id}", response_model=dict)
async def update_template(template_id: str, data: PageTemplate, request: Request):
    """Update template"""
    user = await get_current_user(request)
    if not user or user.get("role") not in ["admin", "editor"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    db = await get_db()
    
    update_data = data.model_dump(exclude={"id"})
    update_data["updated_by"] = user["_id"]
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.templates.update_one({"_id": template_id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    return {"id": template_id, "updated": True}


@router.post("/{template_id}/set-default", response_model=dict)
async def set_default_template(template_id: str, request: Request):
    """Set template as default for its content type"""
    user = await get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    
    db = await get_db()
    
    template = await db.templates.find_one({"_id": template_id})
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    # Remove default from other templates of same type
    await db.templates.update_many(
        {"content_type": template["content_type"]},
        {"$set": {"is_default": False}}
    )
    
    # Set this one as default
    await db.templates.update_one(
        {"_id": template_id},
        {"$set": {"is_default": True}}
    )
    
    return {"id": template_id, "is_default": True}


@router.delete("/{template_id}")
async def delete_template(template_id: str, request: Request):
    """Delete template"""
    user = await get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    
    db = await get_db()
    
    result = await db.templates.delete_one({"_id": template_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    return {"id": template_id, "deleted": True}


# === MODULE TYPES INFO ===

@router.get("/modules/types", response_model=list)
async def list_module_types():
    """Get all available module types with descriptions"""
    return [
        {
            "type": "hero_card",
            "name": "Карточка с фото",
            "description": "Фото с краткими фактами",
            "icon": "user",
            "for_types": ["person", "team", "show"]
        },
        {
            "type": "text_block",
            "name": "Текстовый блок",
            "description": "Блок текста с заголовком",
            "icon": "file-text",
            "for_types": ["all"]
        },
        {
            "type": "timeline",
            "name": "Хронология",
            "description": "Таймлайн событий",
            "icon": "clock",
            "for_types": ["person", "team", "show"]
        },
        {
            "type": "tags",
            "name": "Теги",
            "description": "Отображение тегов",
            "icon": "tag",
            "for_types": ["all"]
        },
        {
            "type": "table",
            "name": "Таблица",
            "description": "Таблица данных с сортировкой",
            "icon": "table",
            "for_types": ["all"]
        },
        {
            "type": "gallery",
            "name": "Галерея",
            "description": "Галерея изображений",
            "icon": "image",
            "for_types": ["all"]
        },
        {
            "type": "video",
            "name": "Видео",
            "description": "Встроенное видео",
            "icon": "play",
            "for_types": ["all"]
        },
        {
            "type": "quote",
            "name": "Цитата",
            "description": "Блок цитаты",
            "icon": "quote",
            "for_types": ["article", "news"]
        },
        {
            "type": "team_members",
            "name": "Состав команды",
            "description": "Список участников",
            "icon": "users",
            "for_types": ["team"]
        },
        {
            "type": "tv_appearances",
            "name": "ТВ эфиры",
            "description": "Таблица ТВ эфиров",
            "icon": "tv",
            "for_types": ["team"]
        },
        {
            "type": "games_list",
            "name": "Список игр",
            "description": "Список игр команды",
            "icon": "list",
            "for_types": ["team"]
        },
        {
            "type": "episodes_list",
            "name": "Список выпусков",
            "description": "Список эпизодов шоу",
            "icon": "film",
            "for_types": ["show"]
        },
        {
            "type": "participants",
            "name": "Участники",
            "description": "Список участников шоу",
            "icon": "users",
            "for_types": ["show"]
        },
        {
            "type": "quiz_questions",
            "name": "Вопросы квиза",
            "description": "Блок вопросов",
            "icon": "help-circle",
            "for_types": ["quiz"]
        },
        {
            "type": "quiz_results",
            "name": "Результаты квиза",
            "description": "Описание результатов",
            "icon": "award",
            "for_types": ["quiz"]
        },
        {
            "type": "best_articles",
            "name": "Лучшие статьи",
            "description": "Виджет лучших статей",
            "icon": "star",
            "for_types": ["page"]
        },
        {
            "type": "interesting",
            "name": "Интересное",
            "description": "Виджет интересного контента",
            "icon": "zap",
            "for_types": ["page"]
        },
        {
            "type": "random_page",
            "name": "Случайная страница",
            "description": "Ссылка на случайную страницу",
            "icon": "shuffle",
            "for_types": ["page"]
        },
        {
            "type": "table_of_contents",
            "name": "Оглавление",
            "description": "Навигация по странице (по timeline или секциям)",
            "icon": "list",
            "for_types": ["person", "team", "article", "wiki"]
        }
    ]
