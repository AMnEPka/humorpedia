"""Content API routes - CRUD for all content types"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone
import logging
import re

logger = logging.getLogger(__name__)

from models.base import ContentType, ContentStatus
from models.content import (
    Person, PersonCreate, PersonUpdate,
    Team, TeamCreate, TeamUpdate,
    Show, ShowCreate, ShowUpdate,
    Article, ArticleCreate, ArticleUpdate,
    News, NewsCreate, NewsUpdate,
    Quiz, QuizCreate, QuizUpdate,
    Wiki, WikiCreate, WikiUpdate,
    KVN, KVNCreate, KVNUpdate
)
from utils.database import get_db
from services.tags import tag_service
from services.linking import linking_service

router = APIRouter(prefix="/content", tags=["content"])


# === HELPER FUNCTIONS ===

def get_league_slug_from_parent(parent_doc):
    """Определяет league_slug из родительского документа KVN"""
    if not parent_doc:
        return None
    
    parent_slug = parent_doc.get("slug", "")
    parent_full_path = parent_doc.get("full_path", "")
    
    # Проверяем slug родителя
    if parent_slug == "vl-kvn":
        return "vl-kvn"
    elif parent_slug == "premier-liga":
        return "premier-liga"
    elif parent_slug == "1l-kvn":
        return "1l-kvn"
    elif parent_slug == "ml-kvn":
        return "ml-kvn"
    elif parent_slug == "vul":
        return "vul"
    
    # Проверяем full_path
    if "/vl-kvn" in parent_full_path or parent_full_path.startswith("kvn/vl-kvn"):
        return "vl-kvn"
    elif "/premier-liga" in parent_full_path:
        return "premier-liga"
    elif "/1l-kvn" in parent_full_path:
        return "1l-kvn"
    elif "/ml-kvn" in parent_full_path:
        return "ml-kvn"
    elif "/vul" in parent_full_path:
        return "vul"
    
    return None


async def check_slug_unique(collection_name: str, slug: str, exclude_id: str = None):
    """Check if slug is unique in collection"""
    db = await get_db()
    collection = getattr(db, collection_name)
    query = {"slug": slug}
    if exclude_id:
        # For KVN, exclude by 'id' field (UUID) or _id
        if collection_name == "kvn":
            # Try to find the document to get its _id
            doc = await collection.find_one({"id": exclude_id})
            if not doc:
                doc = await collection.find_one({"_id": exclude_id})
            if doc:
                query["_id"] = {"$ne": doc["_id"]}
        else:
            query["_id"] = {"$ne": exclude_id}
    existing = await collection.find_one(query)
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")


async def generate_unique_slug(collection_name: str, base_slug: str, parent_path: str = None) -> str:
    """
    Generate unique slug by appending _1, _2, etc. if needed.
    For hierarchical content (KVN, sections), also checks full_path uniqueness.
    """
    db = await get_db()
    collection = getattr(db, collection_name)
    
    # Helper to check if slug is unique
    async def is_slug_unique(slug_to_check: str, expected_full_path: str = None) -> bool:
        # Check by slug field
        existing_by_slug = await collection.find_one({"slug": slug_to_check})
        if existing_by_slug:
            return False
        
        # For hierarchical content, also check full_path
        if expected_full_path:
            existing_by_path = await collection.find_one({"full_path": expected_full_path})
            if existing_by_path:
                return False
        
        return True
    
    # Try base slug first
    expected_full_path = f"{parent_path}/{base_slug}" if parent_path else base_slug
    if await is_slug_unique(base_slug, expected_full_path):
        return base_slug
    
    # Try with _1, _2, etc.
    counter = 1
    while True:
        new_slug = f"{base_slug}_{counter}"
        expected_full_path = f"{parent_path}/{new_slug}" if parent_path else new_slug
        if await is_slug_unique(new_slug, expected_full_path):
            return new_slug
        counter += 1
        if counter > 1000:  # Safety limit
            raise HTTPException(status_code=500, detail="Could not generate unique slug")


async def sync_primary_tag_to_tags(doc: dict) -> dict:
    """
    Автоматически добавляет primary_tag в массив tags, если его там нет (case-insensitive).
    Модифицирует doc напрямую и возвращает обновленный список tags.
    
    Args:
        doc: Словарь документа с полями primary_tag и tags
        
    Returns:
        Обновленный список tags
    """
    primary_tag = doc.get("primary_tag")
    if not primary_tag:
        return doc.get("tags", [])
    
    tags = doc.get("tags", [])
    
    # Проверяем, есть ли primary_tag в tags (case-insensitive)
    tag_exists = any(tag.lower() == primary_tag.lower() for tag in tags)
    
    if not tag_exists:
        tags.append(primary_tag)
        doc["tags"] = tags
    
    return tags


async def check_primary_tag_duplicate(
    collection_name: str, 
    primary_tag: Optional[str], 
    exclude_id: str = None
) -> None:
    """
    Проверяет, не используется ли primary_tag другим человеком/командой (case-insensitive).
    Если найден дубликат, возвращает ошибку с информацией о существующей записи.
    
    Args:
        collection_name: Имя коллекции ("people" или "teams")
        primary_tag: Базовый тег для проверки
        exclude_id: ID документа, который нужно исключить из проверки (для обновлений)
        
    Raises:
        HTTPException: Если найден дубликат primary_tag
    """
    if not primary_tag:
        return  # Пустой тег не проверяем
    
    # Проверяем только для людей и команд
    if collection_name not in ["people", "teams"]:
        return
    
    db = await get_db()
    collection = getattr(db, collection_name)
    
    # Ищем документы с таким же primary_tag (case-insensitive)
    query = {
        "primary_tag": {"$regex": f"^{re.escape(primary_tag)}$", "$options": "i"}
    }
    
    # Исключаем текущий документ при обновлении
    if exclude_id:
        query["_id"] = {"$ne": exclude_id}
    
    existing = await collection.find_one(query)
    
    if existing:
        # Формируем информативное сообщение об ошибке
        item_name = existing.get("full_name") or existing.get("name") or existing.get("title", "Неизвестно")
        item_type = "человека" if collection_name == "people" else "команды"
        
        raise HTTPException(
            status_code=400,
            detail=f"Базовый тег '{primary_tag}' уже используется {item_type} '{item_name}'. "
                   f"Пожалуйста, выберите уникальный тег (например, '{primary_tag} (команда X)')."
        )


async def create_content(collection_name: str, model_instance, tags: list = None):
    """Universal create handler"""
    db = await get_db()
    collection = getattr(db, collection_name)
    
    doc = model_instance.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    # For KVN, generate a separate UUID 'id' field (not just _id)
    # This is needed for hierarchy references (parent_id uses this field)
    if collection_name == "kvn":
        import uuid
        if "id" not in doc or not doc.get("id"):
            doc["id"] = str(uuid.uuid4())
    
    # Проверка на дубликаты primary_tag для людей и команд
    primary_tag = doc.get("primary_tag")
    if primary_tag and collection_name in ["people", "teams"]:
        await check_primary_tag_duplicate(collection_name, primary_tag)
    
    # Синхронизация primary_tag в tags для людей и команд
    # Используем tags из doc, а не из параметра, так как они уже должны совпадать
    if collection_name in ["people", "teams"]:
        updated_tags = await sync_primary_tag_to_tags(doc)
        # Обновляем tags в doc, если они изменились
        if updated_tags != doc.get("tags", []):
            doc["tags"] = updated_tags
    
    # Sync tags (используем tags из doc, так как они уже синхронизированы с primary_tag)
    final_tags = doc.get("tags", [])
    if final_tags:
        await tag_service.sync_tags(final_tags)
    
    await collection.insert_one(doc)
    
    # For KVN, return the UUID 'id' field instead of _id
    if collection_name == "kvn":
        return {"id": doc.get("id"), "slug": doc.get("slug")}
    
    return {"id": doc["_id"], "slug": doc.get("slug")}


async def update_tags_everywhere(
    db, old_primary_tag: Optional[str], new_primary_tag: Optional[str]
):
    """
    Универсальная функция для обновления тегов во всех коллекциях при изменении primary_tag.
    Заменяет старый тег на новый во всех документах, где он встречается в поле tags.
    Если new_primary_tag пустой, просто удаляет старый тег.
    
    Args:
        db: База данных MongoDB
        old_primary_tag: Старый базовый тег
        new_primary_tag: Новый базовый тег (может быть None для удаления)
    """
    if old_primary_tag == new_primary_tag:
        return  # Тег не изменился
    
    if not old_primary_tag:
        # Если старого тега не было, значит он еще нигде не использовался
        # Обновлять нечего
        return
    
    # Список всех коллекций, где могут быть теги
    collections_with_tags = [
        "people", "teams", "shows", "articles", "news", 
        "quizzes", "wiki", "kvn"
    ]
    
    total_updated = 0
    
    for collection_name in collections_with_tags:
        collection = getattr(db, collection_name)
        
        # Находим все документы, где есть старый тег
        # Используем case-insensitive поиск для надежности
        documents = await collection.find({
            "tags": {"$regex": f"^{re.escape(old_primary_tag)}$", "$options": "i"}
        }).to_list(None)
        
        updated_in_collection = 0
        
        for doc in documents:
            doc_id = doc.get("_id")
            tags = doc.get("tags", [])
            
            # Заменяем старый тег на новый (case-insensitive)
            updated_tags = []
            tag_updated = False
            
            for tag in tags:
                # Удаляем старый тег (case-insensitive сравнение)
                if tag.lower() == old_primary_tag.lower():
                    tag_updated = True
                    # Добавляем новый тег, если он задан и его еще нет
                    if new_primary_tag:
                        # Проверяем, нет ли уже нового тега (case-insensitive)
                        tag_exists = any(t.lower() == new_primary_tag.lower() for t in updated_tags)
                        if not tag_exists:
                            updated_tags.append(new_primary_tag)
                    continue
                updated_tags.append(tag)
            
            # Если тег был удален, но новый не добавлен (new_primary_tag пустой),
            # то просто удаляем старый тег
            if tag_updated:
                # Для сезонов КВН сохраняем специальную сортировку
                if collection_name == "kvn":
                    sorted_tags = sorted(updated_tags, key=lambda x: (
                        0 if x == "КВН" else 1,
                        x.lower()
                    ))
                else:
                    sorted_tags = updated_tags
                
                await collection.update_one(
                    {"_id": doc_id},
                    {"$set": {"tags": sorted_tags, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                
                # Синхронизируем теги в коллекции tags
                await tag_service.sync_tags(sorted_tags)
                updated_in_collection += 1
        
        if updated_in_collection > 0:
            logger.info(f"Обновлено {updated_in_collection} документов в коллекции {collection_name}")
            total_updated += updated_in_collection
    
    if total_updated > 0:
        logger.info(f"Всего обновлено {total_updated} документов при замене тега '{old_primary_tag}' на '{new_primary_tag}'")


async def update_content(collection_name: str, item_id: str, data, not_found_msg: str):
    """Universal update handler"""
    db = await get_db()
    collection = getattr(db, collection_name)
    
    # Получаем текущий документ для проверки изменений primary_tag
    current_item = await collection.find_one({"_id": item_id})
    if not current_item:
        raise HTTPException(status_code=404, detail=not_found_msg)
    
    old_primary_tag = current_item.get("primary_tag")
    
    # Use model_dump with exclude_unset=True to only include fields that were explicitly set
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Если primary_tag не задан в обновлении, но его нет в текущем документе, устанавливаем по умолчанию
    if hasattr(data, 'primary_tag') and 'primary_tag' not in update_data:
        if not old_primary_tag:
            if collection_name == "teams":
                default_tag = current_item.get("name") or current_item.get("title")
            elif collection_name == "people":
                # Преобразуем "Фамилия Имя" в "Имя Фамилия"
                def swap_name_order(name):
                    if not name:
                        return name
                    parts = name.strip().split()
                    if len(parts) == 2:
                        return f"{parts[1]} {parts[0]}"
                    return name
                title = current_item.get("title") or current_item.get("full_name")
                default_tag = swap_name_order(title)
            else:
                default_tag = None
            if default_tag:
                update_data["primary_tag"] = default_tag
                old_primary_tag = None  # Будет обновление с null -> default_tag
    
    # Проверка на дубликаты primary_tag для людей и команд
    new_primary_tag = update_data.get("primary_tag")
    if new_primary_tag and collection_name in ["people", "teams"]:
        # Проверяем только если primary_tag изменился
        if new_primary_tag != old_primary_tag:
            await check_primary_tag_duplicate(collection_name, new_primary_tag, exclude_id=item_id)
    
    # Синхронизация primary_tag в tags для людей и команд
    if collection_name in ["people", "teams"]:
        # Объединяем текущие данные с обновлениями для синхронизации
        merged_item = {**current_item, **update_data}
        # Если tags обновляются, используем новые tags, иначе текущие
        if hasattr(data, 'tags') and data.tags is not None:
            merged_item["tags"] = data.tags
        else:
            merged_item["tags"] = current_item.get("tags", [])
        
        # Синхронизируем primary_tag в tags
        updated_tags = await sync_primary_tag_to_tags(merged_item)
        if updated_tags != merged_item.get("tags", []):
            update_data["tags"] = updated_tags
    
    # Sync tags if present
    if hasattr(data, 'tags') and data.tags:
        await tag_service.sync_tags(data.tags)
    elif "tags" in update_data:
        # Синхронизируем обновленные tags (включая добавленный primary_tag)
        await tag_service.sync_tags(update_data["tags"])
    
    result = await collection.update_one({"_id": item_id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=not_found_msg)
    
    # Если изменился primary_tag для команды или человека, обновляем теги в сезонах
    # Определяем финальный new_primary_tag (может быть из update_data или остаться старым)
    final_new_primary_tag = update_data.get("primary_tag") or old_primary_tag
    if hasattr(data, 'primary_tag') and final_new_primary_tag != old_primary_tag:
        # Обновляем теги везде, где они используются
        await update_tags_everywhere(db, old_primary_tag, final_new_primary_tag)
    
    return {"id": item_id, "updated": True}


async def delete_content(collection_name: str, item_id: str, not_found_msg: str):
    """Universal delete handler"""
    db = await get_db()
    collection = getattr(db, collection_name)
    result = await collection.delete_one({"_id": item_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=not_found_msg)
    
    return {"id": item_id, "deleted": True}


def convert_objectids_to_strings(obj):
    """Recursively convert ObjectId to string for JSON serialization"""
    try:
        from bson import ObjectId
    except ImportError:
        ObjectId = None
    
    if ObjectId and isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: convert_objectids_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectids_to_strings(item) for item in obj]
    # Also handle ObjectId-like objects by checking string representation
    elif hasattr(obj, '__class__') and 'ObjectId' in str(type(obj)):
        return str(obj)
    return obj


async def get_by_id_or_slug(collection_name: str, id_or_slug: str, not_found_msg: str, increment_views: bool = True):
    """Universal get by ID or slug handler"""
    db = await get_db()
    collection = getattr(db, collection_name)

    # For KVN, also check the 'id' field (UUID)
    if collection_name == "kvn":
        query = {"$or": [{"_id": id_or_slug}, {"id": id_or_slug}, {"slug": id_or_slug}]}
    else:
        query = {"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}
    
    item = await collection.find_one(query)

    if not item:
        raise HTTPException(status_code=404, detail=not_found_msg)

    if increment_views:
        await collection.update_one({"_id": item["_id"]}, {"$inc": {"views": 1}})

    # Convert all ObjectId instances to strings for JSON serialization
    item = convert_objectids_to_strings(item)
    
    # Remove _id field if present (it's already converted to string if needed)
    # But keep it as string for reference if needed
    if "_id" in item:
        item["_id"] = str(item["_id"])
    
    return item


async def list_content(
    collection_name: str,
    skip: int,
    limit: int,
    query: dict = None,
    sort_field: str = "created_at",
    sort_order: int = -1,
    exclude_modules: bool = True
):
    """Universal list handler"""
    db = await get_db()
    collection = getattr(db, collection_name)
    
    query = query or {}
    projection = {"modules": 0} if exclude_modules else None
    
    total = await collection.count_documents(query)
    cursor = collection.find(query, projection).skip(skip).limit(limit).sort(sort_field, sort_order)
    items = await cursor.to_list(limit)
    
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def build_query(
    status: ContentStatus = None,
    tag: str = None,
    search: str = None,
    search_fields: list = None,
    letter: str = None,
    letter_field: str = "title",
    extra: dict = None
) -> dict:
    """Build MongoDB query from common filters"""
    query = {}
    
    if status:
        query["status"] = status.value
    if tag:
        query["tags"] = tag
    if search and search_fields:
        query["$or"] = [{f: {"$regex": search, "$options": "i"}} for f in search_fields]
    if letter:
        query[letter_field] = {"$regex": f"^{letter}", "$options": "i"}
    if extra:
        query.update(extra)
    
    return query


# === PERSON ROUTES ===

@router.post("/people", response_model=dict)
async def create_person(data: PersonCreate):
    """Create a new person"""
    await check_slug_unique("people", data.slug)
    
    # Функция для преобразования "Фамилия Имя" в "Имя Фамилия"
    def swap_name_order(name):
        if not name:
            return name
        parts = name.strip().split()
        if len(parts) == 2:
            return f"{parts[1]} {parts[0]}"
        return name
    
    # Устанавливаем primary_tag по умолчанию в формате "Имя Фамилия"
    primary_tag = data.primary_tag
    if not primary_tag:
        primary_tag = swap_name_order(data.title) or swap_name_order(data.full_name)
    
    person = Person(
        title=data.title, slug=data.slug, full_name=data.full_name,
        photo=data.photo, bio=data.bio or {}, social_links=data.social_links or {},
        facts=data.facts or {}, primary_tag=primary_tag,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status
    )
    return await create_content("people", person, data.tags)


@router.get("/people", response_model=dict)
async def list_people(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    letter: Optional[str] = None
):
    """List people with pagination and filters"""
    query = build_query(status, tag, search, ["title", "full_name"], letter)
    return await list_content("people", skip, limit, query, "title", 1)


@router.get("/people/search", response_model=list)
async def search_people(q: str = Query(..., min_length=2), limit: int = Query(10, ge=1, le=50)):
    """Search people by name for editor assistance"""
    db = await get_db()
    query = {
        "$or": [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"title": {"$regex": q, "$options": "i"}}
        ]
    }
    cursor = db.people.find(query, {"_id": 1, "full_name": 1, "title": 1, "slug": 1}).limit(limit)
    people = await cursor.to_list(limit)
    return [{"id": p["_id"], "name": p.get("full_name") or p.get("title", ""), "slug": p.get("slug")} for p in people]


@router.get("/people/{id_or_slug}/linked-content", response_model=dict)
async def get_person_linked_content(
    id_or_slug: str,
    types: Optional[str] = Query(None, description="Comma-separated content types: news,article,show"),
    limit: int = Query(20, ge=1, le=100)
):
    """Get content linked to a person (for humor_chronicles module)"""
    db = await get_db()
    
    # Find person by ID or slug
    person = await db.people.find_one({
        "$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person_id = person["_id"]
    content_types = types.split(",") if types else None
    
    result = await linking_service.get_linked_content(person_id, content_types, limit)
    return result


@router.get("/people/{id_or_slug}", response_model=dict)
async def get_person(id_or_slug: str):
    """Get person by ID or slug"""
    return await get_by_id_or_slug("people", id_or_slug, "Person not found")


@router.put("/people/{id}", response_model=dict)
async def update_person(id: str, data: PersonUpdate):
    """Update person"""
    return await update_content("people", id, data, "Person not found")


@router.delete("/people/{id}")
async def delete_person(id: str):
    """Delete person"""
    return await delete_content("people", id, "Person not found")


# === TEAM ROUTES ===

@router.post("/teams", response_model=dict)
async def create_team(data: TeamCreate):
    """Create a new team"""
    await check_slug_unique("teams", data.slug)
    
    # Устанавливаем primary_tag по умолчанию, если не задан
    primary_tag = data.primary_tag or data.name or data.title
    
    team = Team(
        title=data.title, slug=data.slug, name=data.name, team_type=data.team_type,
        logo=data.logo, facts=data.facts or {}, social_links=data.social_links or {},
        primary_tag=primary_tag,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status
    )
    return await create_content("teams", team, data.tags)


@router.get("/teams", response_model=dict)
async def list_teams(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    team_type: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    letter: Optional[str] = None
):
    """List teams with pagination and filters"""
    db = await get_db()
    query = {}
    
    if status:
        query["status"] = status.value
    if tag:
        query["tags"] = tag
    if team_type:
        query["team_type"] = team_type
    
    # Улучшенный поиск для команд: ищем по name, title, slug и aliases
    if search:
        # Экранируем специальные символы regex для безопасности
        # re.escape экранирует только специальные символы (., *, +, ?, ^, $, [, ], {, }, |, \, (, )),
        # обычные буквы и цифры остаются без изменений
        search_term = search.strip()
        search_escaped = re.escape(search_term)
        
        # Для массива строк MongoDB автоматически применяет regex к каждому элементу
        # Используем частичное совпадение - ищем подстроку в любом месте поля
        # MongoDB regex с опцией "i" (case-insensitive) ищет подстроки, так что "бай" должно находить "Байкал"
        search_conditions = [
            {"name": {"$regex": search_escaped, "$options": "i"}},
            {"title": {"$regex": search_escaped, "$options": "i"}},
            {"slug": {"$regex": search_escaped, "$options": "i"}},
            {"aliases": {"$regex": search_escaped, "$options": "i"}}
        ]
        query["$or"] = search_conditions
    
    # Фильтр по первой букве (применяется дополнительно к поиску, если указан)
    if letter:
        letter_condition = {"name": {"$regex": f"^{re.escape(letter)}", "$options": "i"}}
        if "$or" in query:
            # Если есть поиск, добавляем фильтр по букве через $and
            query = {"$and": [{"$or": query["$or"]}, letter_condition]}
        else:
            query.update(letter_condition)
    
    total = await db.teams.count_documents(query)
    cursor = db.teams.find(query, {"modules": 0}).skip(skip).limit(limit).sort("name", 1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/teams/{id_or_slug}", response_model=dict)
async def get_team(id_or_slug: str):
    """Get team by ID or slug"""
    return await get_by_id_or_slug("teams", id_or_slug, "Team not found")


@router.put("/teams/{id}", response_model=dict)
async def update_team(id: str, data: TeamUpdate):
    """Update team"""
    return await update_content("teams", id, data, "Team not found")


@router.delete("/teams/{id}")
async def delete_team(id: str):
    """Delete team"""
    return await delete_content("teams", id, "Team not found")


# === SHOW ROUTES ===

@router.post("/shows", response_model=dict)
async def create_show(data: ShowCreate):
    """Create a new show"""
    await check_slug_unique("shows", data.slug)
    
    # Handle ShowFacts - convert dict to ShowFacts if needed
    from models.content import ShowFacts
    facts_data = data.facts
    if facts_data is None:
        facts_data = ShowFacts()
    elif isinstance(facts_data, dict):
        # Convert dict to ShowFacts object
        try:
            facts_data = ShowFacts(**facts_data)
        except Exception:
            # If conversion fails, use empty ShowFacts
            facts_data = ShowFacts()
    
    show = Show(
        title=data.title, slug=data.slug, name=data.name, poster=data.poster,
        facts=facts_data, description=data.description,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status,
        related_person_ids=data.related_person_ids or []
    )
    result = await create_content("shows", show, data.tags)
    
    # Update person links
    if data.related_person_ids:
        await linking_service.update_person_links("show", result["id"], data.related_person_ids)
    
    return result


@router.get("/shows", response_model=dict)
async def list_shows(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    include_children: bool = Query(False, description="Include child shows")
):
    """List shows with pagination (excludes child shows by default)"""
    query = build_query(status, tag, search, ["title", "name"])
    
    # По умолчанию показываем только корневые шоу (level = 0 или отсутствует)
    if not include_children:
        query["$or"] = [{"level": 0}, {"level": {"$exists": False}}]
    
    return await list_content("shows", skip, limit, query, "name", 1)


@router.get("/shows/by-path/{path:path}", response_model=dict)
async def get_show_by_path(path: str):
    """Get show by full path (e.g., comedy-battle/season1)"""
    db = await get_db()
    show = await db.shows.find_one({"full_path": path}, {"_id": 0})
    if not show:
        # Попробуем найти по slug (для обратной совместимости)
        show = await db.shows.find_one({"slug": path}, {"_id": 0})
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    return show


@router.get("/shows/{parent_slug}/children", response_model=dict)
async def get_show_children(parent_slug: str):
    """Get children of a show"""
    db = await get_db()
    parent = await db.shows.find_one({"slug": parent_slug})
    if not parent:
        raise HTTPException(status_code=404, detail="Parent show not found")
    
    # Use parent's 'id' field (string UUID), not MongoDB's '_id'
    parent_id = parent.get("id")
    children = await db.shows.find(
        {"parent_id": parent_id},
        {"_id": 0}
    ).sort("title", 1).to_list(100)
    
    return {"items": children, "total": len(children), "parent": parent.get("title")}


@router.get("/shows/{id_or_slug}", response_model=dict)
async def get_show(id_or_slug: str):
    """Get show by ID or slug"""
    return await get_by_id_or_slug("shows", id_or_slug, "Show not found")


@router.get("/shows-hierarchy", response_model=dict)
async def get_shows_hierarchy(
    status: Optional[ContentStatus] = None
):
    """Get all shows with hierarchy for admin panel"""
    db = await get_db()
    
    query = {}
    if status:
        query["status"] = status.value
    
    # Получаем все шоу
    all_shows = await db.shows.find(query, {"_id": 0}).sort([("level", 1), ("title", 1)]).to_list(1000)
    
    # Строим дерево - индексируем по 'id' (UUID), т.к. parent_id ссылается на него
    shows_by_id = {}
    for s in all_shows:
        shows_by_id[s.get('id')] = s
    
    root_shows = []
    
    for show in all_shows:
        show['children'] = []
        parent_id = show.get('parent_id')
        
        if not parent_id:
            root_shows.append(show)
        else:
            parent = shows_by_id.get(parent_id)
            if parent:
                if 'children' not in parent:
                    parent['children'] = []
                parent['children'].append(show)
    
    return {"items": root_shows, "total": len(all_shows)}


@router.put("/shows/{id}", response_model=dict)
async def update_show(id: str, data: ShowUpdate):
    """Update show"""
    # Log the received data for debugging
    try:
        logger.info(f"Update show {id}, received data: {data.model_dump(exclude_unset=True)}")
    except Exception as e:
        logger.error(f"Error logging data: {e}")
    
    db = await get_db()
    
    # Build update data manually to handle ShowFacts and other complex types properly
    update_data = {}
    
    if data.title is not None:
        update_data["title"] = data.title
    if data.slug is not None:
        update_data["slug"] = data.slug
    if data.name is not None:
        update_data["name"] = data.name
    if data.poster is not None:
        # Handle null poster (to clear it)
        if data.poster is None or (isinstance(data.poster, dict) and not data.poster.get('url')):
            update_data["poster"] = None
        else:
            update_data["poster"] = data.poster.model_dump() if hasattr(data.poster, 'model_dump') else data.poster
    if data.facts is not None:
        # Convert dict to ShowFacts, then to dict for MongoDB
        from models.content import ShowFacts
        try:
            # If facts is a dict, convert it to ShowFacts object first
            if isinstance(data.facts, dict):
                facts_obj = ShowFacts(**data.facts)
                update_data["facts"] = facts_obj.model_dump()
            else:
                # If it's already a ShowFacts object
                update_data["facts"] = data.facts.model_dump() if hasattr(data.facts, 'model_dump') else data.facts
        except Exception as e:
            # If conversion fails, just use the dict as is
            update_data["facts"] = data.facts if isinstance(data.facts, dict) else {}
    if data.description is not None:
        update_data["description"] = data.description
    if data.parent_id is not None:
        update_data["parent_id"] = data.parent_id
    if data.modules is not None:
        # Convert modules to dict format
        try:
            update_data["modules"] = [
                m.model_dump() if hasattr(m, 'model_dump') else (m if isinstance(m, dict) else {})
                for m in data.modules
            ]
        except Exception as e:
            logger.error(f"Error processing modules: {e}")
            # If conversion fails, try to use as is
            update_data["modules"] = data.modules if isinstance(data.modules, list) else []
    if data.tags is not None:
        update_data["tags"] = data.tags
        await tag_service.sync_tags(data.tags)
    if data.seo is not None:
        update_data["seo"] = data.seo.model_dump() if hasattr(data.seo, 'model_dump') else data.seo
    if data.status is not None:
        update_data["status"] = data.status.value if hasattr(data.status, 'value') else data.status
    if data.participant_ids is not None:
        update_data["participant_ids"] = data.participant_ids
    if data.team_ids is not None:
        update_data["team_ids"] = data.team_ids
    if data.related_person_ids is not None:
        # Allow empty list to be set (to clear relations)
        update_data["related_person_ids"] = data.related_person_ids
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    try:
        logger.info(f"Updating show {id} with data: {update_data}")
        result = await db.shows.update_one({"_id": id}, {"$set": update_data})
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Show not found")
        
        # Update person links if related_person_ids changed
        if data.related_person_ids is not None:
            try:
                await linking_service.update_person_links("show", id, data.related_person_ids)
            except Exception as e:
                logger.error(f"Error updating person links: {e}")
                # Don't fail the update if linking fails
        
        return {"id": id, "updated": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating show {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating show: {str(e)}")


@router.delete("/shows/{id}")
async def delete_show(id: str):
    """Delete show"""
    return await delete_content("shows", id, "Show not found")


# === KVN ROUTES ===

@router.post("/kvn", response_model=dict)
async def create_kvn(data: KVNCreate):
    """Create a new KVN page"""
    await check_slug_unique("kvn", data.slug)
    
    db = await get_db()
    
    # Calculate level and full_path based on parent
    level = 0
    full_path = data.slug
    parent = None
    if data.parent_id:
        # For KVN, parent_id is a UUID string, not _id
        # Try to find by 'id' field first, then fallback to _id
        parent = await db.kvn.find_one({"id": data.parent_id})
        if not parent:
            parent = await db.kvn.find_one({"_id": data.parent_id})
        if not parent:
            raise HTTPException(status_code=404, detail="Parent KVN page not found")
        
        parent_level = parent.get("level", 0)
        if parent_level >= 4:
            raise HTTPException(status_code=400, detail="Maximum hierarchy level (4) reached")
        
        level = parent_level + 1
        parent_path = parent.get("full_path", parent.get("slug"))
        full_path = f"{parent_path}/{data.slug}"
    
    kvn = KVN(
        title=data.title,
        slug=data.slug,
        name=data.name,
        poster=data.poster,
        description=data.description,
        parent_id=data.parent_id,
        level=level,
        full_path=full_path,
        facts=data.facts or {},
        social_links=data.social_links or {},
        modules=data.modules,
        tags=data.tags,
        seo=data.seo or {},
        status=data.status,
        team_ids=data.team_ids or [],
        person_ids=data.person_ids or []
    )
    
    result = await create_content("kvn", kvn, data.tags)
    
    # Автоматически добавляем league_slug в season_data, если создается дочерняя страница с родителем "Высшая лига КВН"
    if parent:
        league_slug = get_league_slug_from_parent(parent)
        if league_slug:
            # Проверяем, есть ли уже season_data в документе
            created_doc = await db.kvn.find_one({"id": result["id"]})
            if created_doc:
                season_data = created_doc.get("season_data", {})
                # Если season_data существует, но нет league_slug - добавляем
                if season_data and not season_data.get("league_slug"):
                    season_data["league_slug"] = league_slug
                    await db.kvn.update_one(
                        {"_id": created_doc["_id"]},
                        {"$set": {"season_data": season_data}}
                    )
                    logger.info(f"Автоматически добавлен league_slug '{league_slug}' в season_data для нового документа KVN")
                # Если season_data не существует, но это сезон (определяем по full_path или slug, содержащему год)
                elif not season_data:
                    # Проверяем, является ли это сезоном (slug или full_path содержит год)
                    import re
                    year_match = re.search(r'\b(19|20)\d{2}\b', full_path)
                    if year_match:
                        # Создаем базовую структуру season_data с league_slug
                        year = int(year_match.group())
                        season_data = {
                            "league_slug": league_slug,
                            "year": year
                        }
                        await db.kvn.update_one(
                            {"_id": created_doc["_id"]},
                            {"$set": {"season_data": season_data}}
                        )
                        logger.info(f"Автоматически создан season_data с league_slug '{league_slug}' для нового сезона {year}")
    
    # Update parent's child_kvn_ids if parent exists
    if data.parent_id:
        # Find parent by 'id' field (UUID) for KVN
        parent_doc = await db.kvn.find_one({"id": data.parent_id})
        if not parent_doc:
            # Fallback to _id if not found by id
            parent_doc = await db.kvn.find_one({"_id": data.parent_id})
        if parent_doc:
            await db.kvn.update_one(
                {"_id": parent_doc["_id"]},
                {"$addToSet": {"child_kvn_ids": result["id"]}}
            )
    
    # Update person and team links
    if data.person_ids:
        await linking_service.update_person_links("kvn", result["id"], data.person_ids)
    if data.team_ids:
        await linking_service.update_team_links("kvn", result["id"], data.team_ids)
    
    return result


@router.get("/kvn", response_model=dict)
async def list_kvn(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[ContentStatus] = None,
    include_children: bool = False
):
    """List KVN pages"""
    db = await get_db()
    query = {}
    
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
            {"slug": {"$regex": search, "$options": "i"}}
        ]
    
    if status:
        query["status"] = status.value
    
    if not include_children:
        query["parent_id"] = None  # Only root pages
    
    count = await db.kvn.count_documents(query)
    cursor = db.kvn.find(query, {"_id": 0}).sort("title", 1).skip(skip).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"items": items, "total": count, "skip": skip, "limit": limit}


def extract_year_from_slug(slug: str) -> int:
    """Извлекает год из slug сезона."""
    # Ищем 4-значное число
    match = re.search(r'(\d{4})', slug)
    if match:
        return int(match.group(1))
    
    # Ищем 2-значное число (для старых сезонов)
    match = re.search(r'-(\d{2})(?:$|[^0-9])', slug)
    if match:
        year = int(match.group(1))
        return 1900 + year if year > 50 else 2000 + year
    
    return 0


async def find_adjacent_seasons(db, current_season: dict) -> tuple[str, str]:
    """
    Находит соседние сезоны для текущего сезона.
    
    Returns:
        Tuple (prev_season_slug, next_season_slug)
    """
    season_data = current_season.get("season_data", {})
    year = season_data.get("year", 0)
    league_slug = season_data.get("league_slug", "")
    
    # Если нет года или лиги, пытаемся извлечь из slug или full_path
    if not year:
        slug = current_season.get("slug", "")
        full_path = current_season.get("full_path", "")
        year = extract_year_from_slug(slug) or extract_year_from_slug(full_path)
    
    if not league_slug:
        # Пытаемся извлечь из full_path (формат: kvn/league-slug/season-slug)
        full_path = current_season.get("full_path", "")
        path_parts = full_path.split("/")
        if len(path_parts) >= 2 and path_parts[0] == "kvn":
            league_slug = path_parts[1]
    
    if not year or not league_slug:
        return "", ""
    
    prev_season_slug = ""
    next_season_slug = ""
    
    # Ищем предыдущий сезон (year - 1)
    prev_year = year - 1
    # Ищем следующий сезон (year + 1)
    next_year = year + 1
    
    # Ищем сезоны в той же лиге
    # Вариант 1 (самый надежный): ищем по season_data.year напрямую
    if not prev_season_slug:
        prev_season = await db.kvn.find_one({
            "season_data.year": prev_year,
            "season_data.league_slug": league_slug
        }, {"slug": 1})
        if prev_season:
            prev_season_slug = prev_season.get("slug", "")
    
    if not next_season_slug:
        next_season = await db.kvn.find_one({
            "season_data.year": next_year,
            "season_data.league_slug": league_slug
        }, {"slug": 1})
        if next_season:
            next_season_slug = next_season.get("slug", "")
    
    # Вариант 2: по parent_id (если сезоны - дочерние страницы лиги)
    if not prev_season_slug or not next_season_slug:
        parent_id = current_season.get("parent_id")
        if parent_id:
            # Ищем все сезоны той же лиги
            all_seasons = await db.kvn.find(
                {"parent_id": parent_id},
                {"slug": 1, "season_data": 1, "full_path": 1}
            ).to_list(1000)
            
            # Сортируем по году
            seasons_by_year = {}
            for season in all_seasons:
                s_year = season.get("season_data", {}).get("year", 0)
                if not s_year:
                    s_year = extract_year_from_slug(season.get("slug", ""))
                if s_year:
                    seasons_by_year[s_year] = season.get("slug", "")
            
            if not prev_season_slug and prev_year in seasons_by_year:
                prev_season_slug = seasons_by_year[prev_year]
            if not next_season_slug and next_year in seasons_by_year:
                next_season_slug = seasons_by_year[next_year]
    
    # Вариант 3: по full_path с regex (если не нашли предыдущими способами)
    if not prev_season_slug or not next_season_slug:
        # Ищем сезоны по full_path с годом
        for target_year in [prev_year, next_year]:
            if target_year == prev_year and prev_season_slug:
                continue
            if target_year == next_year and next_season_slug:
                continue
            
            # Ищем сезон с нужным годом в той же лиге
            # Варианты full_path: kvn/vl-kvn/vl-2009, kvn/vl-kvn/2009 и т.д.
            # Ищем по regex, который ищет год как отдельное число (не часть другого числа)
            # Используем границы слова или начало/конец строки для точного совпадения года
            escaped_league = re.escape(league_slug)
            patterns = [
                f"^kvn/{escaped_league}/.*-{target_year}$",  # kvn/vl-kvn/vl-2009
                f"^kvn/{escaped_league}/{target_year}$",      # kvn/vl-kvn/2009
                f"^kvn/{escaped_league}/.*{target_year}$",     # любой вариант с годом в конце
                f"kvn/{escaped_league}/.*-{target_year}$",     # без ^ в начале (на случай если путь без начального слэша)
                f"kvn/{escaped_league}/{target_year}$",
                f"kvn/{escaped_league}/.*{target_year}$",
            ]
            
            for pattern in patterns:
                seasons = await db.kvn.find({
                    "full_path": {"$regex": pattern}
                }, {"slug": 1, "season_data": 1}).to_list(10)
                
                # Проверяем каждый найденный сезон, чтобы убедиться, что год совпадает
                for season in seasons:
                    # Проверяем год в season_data
                    s_year = season.get("season_data", {}).get("year", 0)
                    if not s_year:
                        # Если нет в season_data, извлекаем из slug
                        s_year = extract_year_from_slug(season.get("slug", ""))
                    
                    # Если год совпадает - это наш сезон
                    if s_year == target_year:
                        found_slug = season.get("slug", "")
                        if target_year == prev_year:
                            prev_season_slug = found_slug
                        else:
                            next_season_slug = found_slug
                        break
                
                if (target_year == prev_year and prev_season_slug) or (target_year == next_year and next_season_slug):
                    break
    
    return prev_season_slug, next_season_slug


@router.get("/kvn/jury-stats", response_model=dict)
async def get_kvn_jury_stats(
    league_slug: str = "vl-kvn",
    min_year: Optional[int] = None,
    max_year: Optional[int] = None
):
    """
    Get jury statistics for KVN seasons.
    Returns aggregated data about all jury members with their game counts and details.
    """
    db = await get_db()
    
    # Get all teams from teams collection (without filtering by team_type)
    all_teams_from_db = await db.teams.find({}, {"slug": 1, "name": 1, "title": 1}).to_list(1000)
    team_slug_to_name = {}
    all_team_slugs = set()
    for team in all_teams_from_db:
        slug = team.get("slug", "")
        name = team.get("name") or team.get("title", "")
        if slug:
            all_team_slugs.add(slug)
            team_slug_to_name[slug] = name
    
    # Build query for seasons
    query = {
        "season_data.league_slug": league_slug
    }
    
    # Build year filter
    year_filter = {}
    if min_year is not None:
        year_filter["$gte"] = min_year
    if max_year is not None:
        year_filter["$lte"] = max_year
    
    if year_filter:
        query["season_data.year"] = year_filter
    
    # Get all seasons for the league
    seasons = await db.kvn.find(query).to_list(1000)
    
    # Aggregate jury statistics
    jury_stats = {}  # jury_name -> { games_count, games: [...], years: set(), teams: set() }
    all_years = set()
    
    for season in seasons:
        season_data = season.get("season_data", {})
        year = season_data.get("year", 0)
        season_slug = season.get("slug", "")
        season_name = season.get("name") or season.get("title", "")
        all_years.add(year)
        
        stages = season_data.get("stages", [])
        for stage in stages:
            games = stage.get("games", [])
            for game in games:
                jury = game.get("jury", [])
                game_name = game.get("name", "")
                game_date = game.get("date", "")
                stage_name = stage.get("name", "")
                
                # Get teams from this game
                teams = game.get("teams", [])
                team_slugs = []
                for team in teams:
                    team_slug = team.get("team_slug", "")
                    if team_slug and team_slug in all_team_slugs:
                        team_slugs.append(team_slug)
                
                # Process each jury member
                for jury_member in jury:
                    if not jury_member:
                        continue
                    
                    if jury_member not in jury_stats:
                        jury_stats[jury_member] = {
                            "games_count": 0,
                            "games": [],
                            "years": set(),
                            "teams": set()
                        }
                    
                    jury_stats[jury_member]["games_count"] += 1
                    jury_stats[jury_member]["years"].add(year)
                    for team_slug in team_slugs:
                        jury_stats[jury_member]["teams"].add(team_slug)
                    
                    # Add game details
                    jury_stats[jury_member]["games"].append({
                        "year": year,
                        "season_slug": season_slug,
                        "season_name": season_name,
                        "stage_name": stage_name,
                        "game_name": game_name,
                        "game_date": game_date,
                        "teams": team_slugs
                    })
    
    # Function to get last name (last word) for sorting
    def get_last_name_for_sort(name):
        """Get last name (last word) from full name for sorting"""
        if not name:
            return ""
        parts = name.strip().split()
        if len(parts) > 0:
            return parts[-1].lower()  # Return last word in lowercase for sorting
        return name.lower()
    
    # Convert sets to lists for JSON serialization
    result = {
        "jury_members": [],
        "all_years": sorted(list(all_years)),
        "all_teams": sorted(list(all_team_slugs)),
        "team_names": team_slug_to_name,
        "total_games": sum(stats["games_count"] for stats in jury_stats.values())
    }
    
    for jury_name, stats in jury_stats.items():
        result["jury_members"].append({
            "name": jury_name,
            "games_count": stats["games_count"],
            "years": sorted(list(stats["years"])),
            "teams": sorted(list(stats["teams"])),
            "games": stats["games"]
        })
    
    # Sort jury members by last name (alphabetically)
    result["jury_members"].sort(key=lambda x: get_last_name_for_sort(x["name"]))
    
    return result


@router.get("/kvn/by-path/{path:path}", response_model=dict)
async def get_kvn_by_path(path: str):
    """Get KVN page by full path with children and breadcrumbs"""
    db = await get_db()
    
    # Try both with and without leading slash
    path_clean = path.lstrip("/")
    
    kvn = await db.kvn.find_one({"full_path": path_clean})
    if not kvn:
        kvn = await db.kvn.find_one({"full_path": f"/{path_clean}"})
    if not kvn:
        kvn = await db.kvn.find_one({"slug": path_clean})
    if not kvn:
        raise HTTPException(status_code=404, detail="KVN page not found")
    
    # Increment views
    await db.kvn.update_one({"_id": kvn["_id"]}, {"$inc": {"views": 1}})
    
    # Get children
    section_id = kvn.get("id")
    if section_id:
        children = await db.kvn.find(
            {"parent_id": section_id},
            {"_id": 0}
        ).sort("title", 1).to_list(100)
        kvn["children"] = children
    else:
        kvn["children"] = []
    
    # Get breadcrumbs
    breadcrumbs = []
    if kvn.get("parent_id"):
        current_parent_id = kvn["parent_id"]
        while current_parent_id:
            parent = await db.kvn.find_one({"id": current_parent_id})
            if parent:
                breadcrumbs.insert(0, {
                    "id": parent.get("id"),
                    "title": parent.get("name") or parent.get("title"),
                    "full_path": parent.get("full_path") or parent.get("slug")
                })
                current_parent_id = parent.get("parent_id")
            else:
                break
    
    kvn["breadcrumbs"] = breadcrumbs
    
    # Автоматически определяем соседние сезоны
    # Пытаемся найти соседние сезоны, даже если season_data отсутствует
    # (можем извлечь год и лигу из slug или full_path)
    prev_season_slug, next_season_slug = await find_adjacent_seasons(db, kvn)
    
    # Обновляем season_data с найденными соседними сезонами
    if kvn.get("season_data"):
        # Всегда обновляем, чтобы исправить неправильные значения и добавить отсутствующие
        if prev_season_slug:
            kvn["season_data"]["prev_season"] = prev_season_slug
        elif not kvn["season_data"].get("prev_season"):
            kvn["season_data"]["prev_season"] = ""
        
        if next_season_slug:
            kvn["season_data"]["next_season"] = next_season_slug
        elif not kvn["season_data"].get("next_season"):
            kvn["season_data"]["next_season"] = ""
    elif prev_season_slug or next_season_slug:
        # Если season_data отсутствует, но мы нашли соседние сезоны, создаем season_data
        kvn["season_data"] = {
            "prev_season": prev_season_slug or "",
            "next_season": next_season_slug or ""
        }
    
    # Remove MongoDB _id from response
    if "_id" in kvn:
        del kvn["_id"]
    
    return kvn


@router.get("/kvn/{parent_slug}/children", response_model=dict)
async def get_kvn_children(parent_slug: str):
    """Get children of a KVN page"""
    db = await get_db()
    parent = await db.kvn.find_one({"slug": parent_slug})
    if not parent:
        raise HTTPException(status_code=404, detail="Parent KVN page not found")
    
    parent_id = parent.get("id")
    children = await db.kvn.find(
        {"parent_id": parent_id},
        {"_id": 0}
    ).sort("title", 1).to_list(100)
    
    return {"items": children, "total": len(children), "parent": parent.get("title")}


@router.get("/kvn/{id_or_slug}", response_model=dict)
async def get_kvn(id_or_slug: str):
    """Get KVN page by ID or slug"""
    return await get_by_id_or_slug("kvn", id_or_slug, "KVN page not found")


@router.get("/kvn-hierarchy", response_model=dict)
async def get_kvn_hierarchy(
    status: Optional[ContentStatus] = None
):
    """Get all KVN pages with hierarchy for admin panel"""
    db = await get_db()
    
    query = {}
    if status:
        query["status"] = status.value
    
    # We need _id to update records without 'id' field, so don't exclude it
    all_kvn = await db.kvn.find(query).sort([("level", 1), ("title", 1)]).to_list(1000)
    
    # Generate 'id' field for records that don't have it (for backward compatibility)
    import uuid
    records_to_update = []
    for k in all_kvn:
        if not k.get('id'):
            # Generate UUID and save it to database
            new_id = str(uuid.uuid4())
            k["id"] = new_id
            records_to_update.append((k["_id"], new_id))
    
    # Batch update records without 'id' field
    if records_to_update:
        from pymongo import UpdateMany
        bulk_ops = [UpdateMany({"_id": doc_id}, {"$set": {"id": new_id}}) for doc_id, new_id in records_to_update]
        if bulk_ops:
            await db.kvn.bulk_write(bulk_ops)
    
    # Remove _id from response (keep only 'id' field)
    for k in all_kvn:
        if "_id" in k:
            del k["_id"]
    
    kvn_by_id = {}
    for k in all_kvn:
        kvn_id = k.get('id')
        if kvn_id:  # Only add to dict if id exists
            kvn_by_id[kvn_id] = k
    
    root_kvn = []
    
    for kvn in all_kvn:
        kvn['children'] = []
        parent_id = kvn.get('parent_id')
        
        if not parent_id:
            root_kvn.append(kvn)
        else:
            parent = kvn_by_id.get(parent_id)
            if parent:
                if 'children' not in parent:
                    parent['children'] = []
                parent['children'].append(kvn)
    
    return {"items": root_kvn, "total": len(all_kvn)}


@router.put("/kvn/{id}", response_model=dict)
async def update_kvn(id: str, data: KVNUpdate):
    """Update KVN page"""
    db = await get_db()
    
    # For KVN, try to find by 'id' field (UUID) first, then by _id
    kvn = await db.kvn.find_one({"id": id})
    if not kvn:
        kvn = await db.kvn.find_one({"_id": id})
    
    if not kvn:
        raise HTTPException(status_code=404, detail="KVN page not found")
    
    # Get the actual _id for update operations
    kvn_id = kvn["_id"]
    
    update_data = {}
    
    if data.title is not None:
        update_data["title"] = data.title
    if data.slug is not None:
        await check_slug_unique("kvn", data.slug, exclude_id=id)
        update_data["slug"] = data.slug
    if data.name is not None:
        update_data["name"] = data.name
    if data.poster is not None:
        if isinstance(data.poster, dict) and not data.poster.get('url'):
            update_data["poster"] = None
        else:
            update_data["poster"] = data.poster.model_dump() if hasattr(data.poster, 'model_dump') else data.poster
    if data.description is not None:
        update_data["description"] = data.description
    if data.parent_id is not None:
        update_data["parent_id"] = data.parent_id
        if data.parent_id:
            # Find parent by 'id' field (UUID) first, then by _id
            parent = await db.kvn.find_one({"id": data.parent_id})
            if not parent:
                parent = await db.kvn.find_one({"_id": data.parent_id})
            if parent:
                parent_level = parent.get("level", 0)
                if parent_level >= 4:
                    raise HTTPException(status_code=400, detail="Maximum hierarchy level (4) reached")
                update_data["level"] = parent_level + 1
                parent_path = parent.get("full_path", parent.get("slug"))
                current_slug = data.slug or kvn.get("slug")
                update_data["full_path"] = f"{parent_path}/{current_slug}"
        else:
            current_slug = data.slug or kvn.get("slug")
            update_data["level"] = 0
            update_data["full_path"] = current_slug
    if data.facts is not None:
        update_data["facts"] = data.facts
    if data.social_links is not None:
        update_data["social_links"] = data.social_links.model_dump() if hasattr(data.social_links, 'model_dump') else data.social_links
    if data.modules is not None:
        update_data["modules"] = [
            m.model_dump() if hasattr(m, 'model_dump') else (m if isinstance(m, dict) else {})
            for m in data.modules
        ]
    if data.tags is not None:
        update_data["tags"] = data.tags
        await tag_service.sync_tags(data.tags)
    if data.seo is not None:
        update_data["seo"] = data.seo.model_dump() if hasattr(data.seo, 'model_dump') else data.seo
    if data.status is not None:
        update_data["status"] = data.status.value if hasattr(data.status, 'value') else data.status
    if data.team_ids is not None:
        update_data["team_ids"] = data.team_ids
    if data.person_ids is not None:
        update_data["person_ids"] = data.person_ids
    if data.related_kvn_ids is not None:
        update_data["related_kvn_ids"] = data.related_kvn_ids
    if data.jury_cards is not None:
        update_data["jury_cards"] = data.jury_cards
    if data.season_data is not None:
        # Валидируем и очищаем season_data перед сохранением
        # Убеждаемся, что все вложенные структуры сериализуемы
        try:
            import json
            from bson import ObjectId
            from datetime import datetime as dt, date
            
            # Преобразуем Pydantic модель в dict, если нужно
            season_data_dict = data.season_data
            if hasattr(season_data_dict, 'model_dump'):
                season_data_dict = season_data_dict.model_dump()
            elif hasattr(season_data_dict, 'dict'):
                season_data_dict = season_data_dict.dict()
            
            # Рекурсивно очищаем данные от несериализуемых объектов
            def clean_data(obj, depth=0, max_depth=15):
                if depth > max_depth:
                    logger.warning(f"Max depth reached in clean_data, converting to string")
                    return str(obj)
                
                # Обрабатываем специальные типы BSON и Python
                if isinstance(obj, ObjectId):
                    return str(obj)
                elif isinstance(obj, (dt, date)):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: clean_data(v, depth+1, max_depth) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_data(item, depth+1, max_depth) for item in obj]
                elif isinstance(obj, (str, int, float, bool, type(None))):
                    return obj
                elif hasattr(obj, 'model_dump'):
                    # Pydantic модель
                    return clean_data(obj.model_dump(), depth+1, max_depth)
                elif hasattr(obj, '__dict__'):
                    # Объект с атрибутами - преобразуем в словарь
                    return clean_data(obj.__dict__, depth+1, max_depth)
                else:
                    # Преобразуем в строку если не сериализуемо
                    return str(obj)
            
            cleaned_data = clean_data(season_data_dict)
            
            # Автоматически добавляем league_slug, если его нет и есть родитель "Высшая лига КВН"
            if not cleaned_data.get("league_slug"):
                parent_id = kvn.get("parent_id")
                if parent_id:
                    # Находим родителя
                    parent = await db.kvn.find_one({"id": parent_id})
                    if not parent:
                        parent = await db.kvn.find_one({"_id": parent_id})
                    
                    if parent:
                        # Определяем league_slug из родителя
                        league_slug = get_league_slug_from_parent(parent)
                        
                        if league_slug:
                            cleaned_data["league_slug"] = league_slug
                            logger.info(f"Автоматически добавлен league_slug '{league_slug}' в season_data при обновлении")
            
            # Пробуем сериализовать для проверки
            json_str = json.dumps(cleaned_data, default=str, ensure_ascii=False)
            logger.info(f"Season data serialized successfully, size: {len(json_str)} bytes")
            # Если данные слишком большие - логируем предупреждение, но сохраняем
            if len(json_str) > 1000000:  # 1MB
                logger.warning(f"Season data is large: {len(json_str)} bytes")
            update_data["season_data"] = cleaned_data
        except Exception as e:
            logger.error(f"Error processing season_data: {e}", exc_info=True)
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Пробуем сохранить хотя бы структуру без проблемных данных
            try:
                # Упрощаем данные - убираем сложные вложенные структуры
                season_data_dict = data.season_data
                if hasattr(season_data_dict, 'model_dump'):
                    season_data_dict = season_data_dict.model_dump()
                elif hasattr(season_data_dict, 'dict'):
                    season_data_dict = season_data_dict.dict()
                simplified = json.loads(json.dumps(season_data_dict, default=str, ensure_ascii=False))
                update_data["season_data"] = simplified
                logger.warning("Used simplified season_data after serialization error")
            except Exception as e2:
                logger.error(f"Failed to simplify season_data: {e2}", exc_info=True)
                # В крайнем случае - не сохраняем season_data, но не падаем
                logger.error("Skipping season_data update due to serialization errors")
                # Не добавляем season_data в update_data
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Логируем размер данных для отладки
    try:
        import json
        update_data_size = len(json.dumps(update_data, default=str, ensure_ascii=False))
        logger.info(f"Updating KVN {id}, data size: {update_data_size} bytes")
        if 'season_data' in update_data:
            season_data_size = len(json.dumps(update_data['season_data'], default=str, ensure_ascii=False))
            logger.info(f"Season data size: {season_data_size} bytes")
    except Exception as e:
        logger.warning(f"Could not calculate data size: {e}")
    
    try:
        result = await db.kvn.update_one({"_id": kvn_id}, {"$set": update_data})
    except Exception as e:
        logger.error(f"Error updating KVN {id}: {e}", exc_info=True)
        # Логируем детали ошибки
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Проверяем, не связана ли ошибка с сериализацией
        if 'ObjectId' in str(e) or 'serialize' in str(e).lower() or 'bson' in str(e).lower():
            logger.error("Error appears to be related to BSON serialization")
            # Пробуем преобразовать ObjectId в строки
            try:
                def convert_objectid(obj):
                    if isinstance(obj, dict):
                        return {k: convert_objectid(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_objectid(item) for item in obj]
                    elif hasattr(obj, '__class__') and 'ObjectId' in str(type(obj)):
                        return str(obj)
                    return obj
                
                cleaned_update_data = convert_objectid(update_data)
                result = await db.kvn.update_one({"_id": kvn_id}, {"$set": cleaned_update_data})
                logger.info("Successfully updated after ObjectId conversion")
            except Exception as e2:
                logger.error(f"Error after ObjectId conversion: {e2}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Failed to update KVN after ObjectId conversion: {str(e2)}")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to update KVN: {str(e)}")
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="KVN page not found")
    
    # Update person links if provided (team_ids are already saved in update_data above)
    if data.person_ids is not None:
        # Use UUID for linking service
        kvn_uuid = kvn.get("id") or str(kvn_id)
        await linking_service.update_person_links("kvn", kvn_uuid, data.person_ids)
    # Note: team_ids are already saved in the document via update_data, no additional linking needed
    
    # Return updated document, converting ObjectIds to strings
    updated = await db.kvn.find_one({"_id": kvn_id}, {"_id": 0})
    if updated:
        updated = convert_objectids_to_strings(updated)
    return updated


@router.delete("/kvn/{id}")
async def delete_kvn(id: str):
    """Delete KVN page"""
    db = await get_db()

    # For KVN, try to find by 'id' field (UUID) first, then by _id
    kvn = await db.kvn.find_one({"id": id})
    if not kvn:
        kvn = await db.kvn.find_one({"_id": id})
    
    if not kvn:
        raise HTTPException(status_code=404, detail="KVN page not found")

    # Get the actual _id for deletion
    kvn_id = kvn["_id"]
    kvn_uuid = kvn.get("id")  # UUID field

    if kvn.get("child_kvn_ids"):
        raise HTTPException(status_code=400, detail="Cannot delete KVN page with children. Delete children first.")

    # Update parent's child_kvn_ids if parent exists
    if kvn.get("parent_id"):
        parent_id = kvn["parent_id"]
        # Find parent by 'id' field (UUID) first, then by _id
        parent = await db.kvn.find_one({"id": parent_id})
        if not parent:
            parent = await db.kvn.find_one({"_id": parent_id})
        
        if parent:
            # Use the UUID for removing from child_kvn_ids
            child_id_to_remove = kvn_uuid if kvn_uuid else str(kvn_id)
            await db.kvn.update_one(
                {"_id": parent["_id"]},
                {"$pull": {"child_kvn_ids": child_id_to_remove}}
            )
    
    # Delete using the actual _id from the found document
    # Note: person_ids and team_ids are stored in the document itself,
    # so they will be deleted automatically when the document is deleted
    result = await db.kvn.delete_one({"_id": kvn_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="KVN page not found")
    
    return {"success": True}


# === ARTICLE ROUTES ===

@router.post("/articles", response_model=dict)
async def create_article(data: ArticleCreate):
    """Create a new article"""
    await check_slug_unique("articles", data.slug)
    
    article = Article(
        title=data.title, slug=data.slug, excerpt=data.excerpt, cover_image=data.cover_image,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status,
        featured=data.featured, related_person_ids=data.related_person_ids or []
    )
    
    doc = article.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    if data.status == ContentStatus.PUBLISHED:
        doc["published_at"] = datetime.now(timezone.utc).isoformat()
    
    if data.tags:
        await tag_service.sync_tags(data.tags)
    
    db = await get_db()
    await db.articles.insert_one(doc)
    
    # Update person links
    if data.related_person_ids:
        await linking_service.update_person_links("article", doc["_id"], data.related_person_ids)
    
    return {"id": doc["_id"], "slug": doc["slug"]}


@router.get("/articles", response_model=dict)
async def list_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    featured: Optional[bool] = None
):
    """List articles with pagination"""
    extra = {"featured": featured} if featured is not None else None
    query = build_query(status, tag, search, ["title"], extra=extra)
    return await list_content("articles", skip, limit, query)


@router.get("/articles/{id_or_slug}", response_model=dict)
async def get_article(id_or_slug: str):
    """Get article by ID or slug"""
    return await get_by_id_or_slug("articles", id_or_slug, "Article not found")


@router.put("/articles/{id}", response_model=dict)
async def update_article(id: str, data: ArticleUpdate):
    """Update article"""
    db = await get_db()
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    if data.tags:
        await tag_service.sync_tags(data.tags)
    
    # Set published_at if status changed to published
    if data.status == ContentStatus.PUBLISHED:
        article = await db.articles.find_one({"_id": id})
        if article and not article.get("published_at"):
            update_data["published_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.articles.update_one({"_id": id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Update person links if related_person_ids changed
    if data.related_person_ids is not None:
        await linking_service.update_person_links("article", id, data.related_person_ids)
    
    return {"id": id, "updated": True}


@router.delete("/articles/{id}")
async def delete_article(id: str):
    """Delete article"""
    return await delete_content("articles", id, "Article not found")


# === NEWS ROUTES ===

@router.post("/news", response_model=dict)
async def create_news(data: NewsCreate):
    """Create news item"""
    await check_slug_unique("news", data.slug)
    
    news = News(
        title=data.title, slug=data.slug, excerpt=data.excerpt,
        cover_image=data.cover_image, content=data.content, important=data.important,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status,
        related_person_ids=data.related_person_ids or []
    )
    
    doc = news.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    if data.status == ContentStatus.PUBLISHED:
        doc["published_at"] = datetime.now(timezone.utc).isoformat()
    
    if data.tags:
        await tag_service.sync_tags(data.tags)
    
    db = await get_db()
    await db.news.insert_one(doc)
    
    # Update person links
    if data.related_person_ids:
        await linking_service.update_person_links("news", doc["_id"], data.related_person_ids)
    
    return {"id": doc["_id"], "slug": doc["slug"]}


@router.get("/news", response_model=dict)
async def list_news(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """List news with pagination"""
    query = build_query(status, tag, search, ["title"])
    return await list_content("news", skip, limit, query)


@router.get("/news/{id_or_slug}", response_model=dict)
async def get_news_item(id_or_slug: str):
    """Get news by ID or slug"""
    return await get_by_id_or_slug("news", id_or_slug, "News not found")


@router.put("/news/{id}", response_model=dict)
async def update_news(id: str, data: NewsUpdate):
    """Update news"""
    result = await update_content("news", id, data, "News not found")
    
    # Update person links if related_person_ids changed
    if data.related_person_ids is not None:
        await linking_service.update_person_links("news", id, data.related_person_ids)
    
    return result


@router.delete("/news/{id}")
async def delete_news(id: str):
    """Delete news"""
    return await delete_content("news", id, "News not found")


# === QUIZ ROUTES ===

@router.post("/quizzes", response_model=dict)
async def create_quiz(data: QuizCreate):
    """Create a quiz"""
    await check_slug_unique("quizzes", data.slug)
    
    quiz = Quiz(
        title=data.title, slug=data.slug, description=data.description,
        cover_image=data.cover_image, modules=data.modules,
        tags=data.tags, seo=data.seo or {}, status=data.status
    )
    return await create_content("quizzes", quiz, data.tags)


@router.get("/quizzes", response_model=dict)
async def list_quizzes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """List quizzes with pagination"""
    query = build_query(status, tag, search, ["title"])
    return await list_content("quizzes", skip, limit, query)


@router.get("/quizzes/{id_or_slug}", response_model=dict)
async def get_quiz(id_or_slug: str):
    """Get quiz by ID or slug"""
    return await get_by_id_or_slug("quizzes", id_or_slug, "Quiz not found")


@router.put("/quizzes/{id}", response_model=dict)
async def update_quiz(id: str, data: QuizUpdate):
    """Update quiz"""
    return await update_content("quizzes", id, data, "Quiz not found")


@router.delete("/quizzes/{id}")
async def delete_quiz(id: str):
    """Delete quiz"""
    return await delete_content("quizzes", id, "Quiz not found")


# === WIKI ROUTES ===

@router.post("/wiki", response_model=dict)
async def create_wiki(data: WikiCreate):
    """Create wiki page"""
    await check_slug_unique("wiki", data.slug)
    
    content_type = ContentType.WIKI_HEADER if data.has_header else ContentType.WIKI
    
    wiki = Wiki(
        title=data.title, slug=data.slug, content_type=content_type,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status
    )
    return await create_content("wiki", wiki, data.tags)


@router.get("/wiki", response_model=dict)
async def list_wiki(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """List wiki pages with pagination"""
    query = build_query(status, tag, search, ["title"])
    return await list_content("wiki", skip, limit, query, "title", 1)


@router.get("/wiki/{id_or_slug}", response_model=dict)
async def get_wiki(id_or_slug: str):
    """Get wiki page by ID or slug"""
    return await get_by_id_or_slug("wiki", id_or_slug, "Wiki page not found")


@router.put("/wiki/{id}", response_model=dict)
async def update_wiki(id: str, data: WikiUpdate):
    """Update wiki page"""
    return await update_content("wiki", id, data, "Wiki page not found")


@router.delete("/wiki/{id}")
async def delete_wiki(id: str):
    """Delete wiki page"""
    return await delete_content("wiki", id, "Wiki page not found")


# === UNIVERSAL SEARCH ===

@router.get("/search", response_model=dict)
async def search_all(
    q: str = Query(..., min_length=2),
    types: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
):
    """Search across all content types"""
    db = await get_db()
    
    search_types = types.split(",") if types else ["person", "team", "show", "article", "news", "wiki", "section"]
    
    results = {}
    collection_map = {
        "person": ("people", ["title", "full_name"]),
        "team": ("teams", ["title", "name"]),
        "show": ("shows", ["title", "name"]),
        "article": ("articles", ["title"]),
        "news": ("news", ["title"]),
        "wiki": ("wiki", ["title"]),
        "section": ("sections", ["title", "description"]),
    }
    
    for content_type in search_types:
        if content_type not in collection_map:
            continue
        
        coll_name, fields = collection_map[content_type]
        collection = getattr(db, coll_name)
        
        query = {
            "$and": [
                {"status": "published"},
                {"$or": [{f: {"$regex": q, "$options": "i"}} for f in fields]}
            ]
        }
        cursor = collection.find(query, {"modules": 0}).limit(limit)
        items = await cursor.to_list(limit)
        
        if items:
            results[content_type] = items
    
    return results


@router.get("/search/autocomplete", response_model=list)
async def search_autocomplete(
    q: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=20)
):
    """Fast autocomplete search across all content"""
    db = await get_db()
    
    suggestions = []
    
    # Search in different collections
    collections_config = [
        ("people", "full_name", "person"),
        ("teams", "name", "team"),
        ("shows", "name", "show"),
        ("articles", "title", "article"),
        ("news", "title", "news"),
        ("sections", "title", "section"),
    ]
    
    for coll_name, field, content_type in collections_config:
        collection = getattr(db, coll_name)
        query = {
            "status": "published",
            field: {"$regex": q, "$options": "i"}
        }
        
        cursor = collection.find(query, {"_id": 1, field: 1, "slug": 1, "full_path": 1}).limit(limit)
        items = await cursor.to_list(limit)
        
        for item in items:
            suggestions.append({
                "id": item["_id"],
                "title": item.get(field, item.get("title", "")),
                "type": content_type,
                "slug": item.get("slug"),
                "path": item.get("full_path") if content_type == "section" else f"/{content_type}s/{item.get('slug', item['_id'])}"
            })
        
        if len(suggestions) >= limit:
            break
    
    return suggestions[:limit]


@router.get("/search/by-tag/{tag}", response_model=dict)
async def search_by_tag(
    tag: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """Search all content by tag"""
    db = await get_db()
    
    results = {}
    total_count = 0
    
    collection_map = {
        "people": "person",
        "teams": "team",
        "shows": "show",
        "articles": "article",
        "news": "news",
        "wiki": "wiki",
        "quizzes": "quiz",
        "sections": "section",
    }
    
    for coll_name, content_type in collection_map.items():
        collection = getattr(db, coll_name)
        
        query = {
            "status": "published",
            "tags": tag
        }
        
        count = await collection.count_documents(query)
        total_count += count
        
        if count > 0:
            cursor = collection.find(query, {"modules": 0}).sort("created_at", -1).limit(limit)
            items = await cursor.to_list(limit)
            results[content_type] = {
                "count": count,
                "items": items
            }
    
    return {
        "tag": tag,
        "total": total_count,
        "results": results,
        "skip": skip,
        "limit": limit
    }


# === DUPLICATE CONTENT ===

# Collection name mapping for content types
COLLECTION_MAP = {
    "person": "people",
    "people": "people",
    "team": "teams",
    "teams": "teams",
    "show": "shows",
    "shows": "shows",
    "article": "articles",
    "articles": "articles",
    "news": "news",
    "quiz": "quizzes",
    "quizzes": "quizzes",
    "wiki": "wiki",
    "kvn": "kvn",
    "section": "sections",
    "sections": "sections"
}


@router.post("/{content_type}/{id}/duplicate", response_model=dict)
async def duplicate_content(content_type: str, id: str):
    """
    Create a copy of a content page.
    The new page will have the same parent_id, but a new slug (slug_1, slug_2, etc.)
    """
    try:
        db = await get_db()
        
        # Get collection name
        collection_name = COLLECTION_MAP.get(content_type)
        if not collection_name:
            raise HTTPException(status_code=400, detail=f"Unknown content type: {content_type}")
        
        collection = getattr(db, collection_name)
        
        # Find original content
        # For KVN, try to find by 'id' field first, then by _id
        if content_type == "kvn":
            original = await collection.find_one({"id": id})
            if not original:
                original = await collection.find_one({"_id": id})
        else:
            original = await collection.find_one({"_id": id})
        
        if not original:
            raise HTTPException(status_code=404, detail="Content not found")
        
        # Create copy - use deep copy to avoid modifying original
        import copy as copy_module
        copy_data = copy_module.deepcopy(dict(original))
        
        # Remove MongoDB-specific fields
        copy_data.pop("_id", None)
        copy_data.pop("created_at", None)
        copy_data.pop("updated_at", None)
        copy_data.pop("views", None)
        
        # Convert any remaining ObjectId instances to strings in nested structures
        # This is important for fields like person_ids, team_ids, etc. that may contain ObjectIds
        copy_data = convert_objectids_to_strings(copy_data)
        
        # For hierarchical content (KVN, sections), we'll recalculate full_path
        # So we keep it for now but will update it after insertion
        
        # Generate unique slug
        base_slug = copy_data.get("slug", "")
        if not base_slug:
            raise HTTPException(status_code=400, detail="Original content has no slug")
        
        # For hierarchical content, get parent path to check full_path uniqueness
        parent_path_for_slug = None
        if content_type in ["kvn", "section", "sections"]:
            parent_id = copy_data.get("parent_id")
            if parent_id:
                if content_type == "kvn":
                    parent_doc = await db.kvn.find_one({"id": parent_id})
                    if not parent_doc:
                        parent_doc = await db.kvn.find_one({"_id": parent_id})
                else:
                    parent_doc = await db.sections.find_one({"_id": parent_id})
                if parent_doc:
                    parent_path_for_slug = parent_doc.get("full_path", parent_doc.get("slug", ""))
        
        new_slug = await generate_unique_slug(collection_name, base_slug, parent_path_for_slug)
        copy_data["slug"] = new_slug
        
        # Update title to indicate it's a copy (optional, can be removed if not needed)
        # copy_data["title"] = f"{copy_data.get('title', '')} (копия)"
        
        # Set timestamps
        now = datetime.now(timezone.utc).isoformat()
        copy_data["created_at"] = now
        copy_data["updated_at"] = now
        
        # Reset views
        copy_data["views"] = 0
        
        # For KVN pages, also need to handle 'id' field (not just _id)
        if content_type == "kvn":
            # Generate new UUID for 'id' field
            import uuid
            copy_data["id"] = str(uuid.uuid4())
            # Clear child_kvn_ids as children are not copied automatically
            copy_data["child_kvn_ids"] = []
        
        # Insert the copy
        result = await collection.insert_one(copy_data)
        
        # For sections, update full_path after insertion
        if content_type in ["section", "sections"]:
            # Import here to avoid circular dependency
            from routes.sections import build_full_path
            parent_id = copy_data.get("parent_id")
            new_full_path, new_level = await build_full_path(parent_id, new_slug, db)
            await collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {"full_path": new_full_path, "level": new_level}}
            )
        
        # For KVN pages, update full_path and level after insertion
        if content_type == "kvn":
            parent_id = copy_data.get("parent_id")
            level = 0
            full_path = new_slug
            
            if parent_id:
                # Find parent by 'id' field (not _id) for KVN
                parent = await db.kvn.find_one({"id": parent_id})
                if not parent:
                    # Fallback to _id if not found by id
                    parent = await db.kvn.find_one({"_id": parent_id})
                
                if parent:
                    parent_level = parent.get("level", 0)
                    if parent_level >= 4:
                        # If max level reached, set to root
                        level = 0
                        full_path = new_slug
                    else:
                        level = parent_level + 1
                        parent_path = parent.get("full_path", parent.get("slug", ""))
                        full_path = f"{parent_path}/{new_slug}"
            
            await collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {"full_path": full_path, "level": level}}
            )
            
            # Update parent's child_kvn_ids if parent exists
            if parent_id:
                # Use the new 'id' field from copy_data
                new_id = copy_data.get("id")
                if new_id:
                    # Find parent by 'id' field first (KVN uses 'id' for parent_id references)
                    parent_doc = await db.kvn.find_one({"id": parent_id})
                    if not parent_doc:
                        # Fallback to _id if not found by id
                        parent_doc = await db.kvn.find_one({"_id": parent_id})
                    if parent_doc:
                        await db.kvn.update_one(
                            {"_id": parent_doc["_id"]},
                            {"$addToSet": {"child_kvn_ids": new_id}}
                        )
        
        # Sync tags if present
        if "tags" in copy_data and copy_data["tags"]:
            await tag_service.sync_tags(copy_data["tags"])
        
        # Convert ObjectId to string for JSON serialization
        inserted_id_str = str(result.inserted_id)
        
        # For KVN, also return the 'id' field (UUID) instead of _id
        if content_type == "kvn":
            kvn_id = copy_data.get("id")
            return {
                "id": kvn_id or inserted_id_str,
                "_id": inserted_id_str,
                "slug": new_slug,
                "message": "Content duplicated successfully"
            }
        
        return {
            "id": inserted_id_str,
            "slug": new_slug,
            "message": "Content duplicated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating {content_type} {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error duplicating content: {str(e)}")
