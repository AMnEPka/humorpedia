"""Media upload and management routes"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Request
from typing import Optional, List
from datetime import datetime, timezone
import os
import uuid
import aiofiles
from pathlib import Path

from models.user import Media, MediaCreate
from models.media_browser import MediaBrowseResponse, MediaBrowseItem, MediaBrowseFolder
from utils.database import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/media", tags=["media"])

# Upload directory
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/app/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed file types
ALLOWED_EXTENSIONS = {
    "image": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
    "document": [".pdf", ".doc", ".docx"],
    "video": [".mp4", ".webm", ".mov"]
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def get_file_type(filename: str) -> Optional[str]:
    """Determine file type from extension"""
    ext = Path(filename).suffix.lower()
    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return file_type
    return None


@router.post("/upload", response_model=dict)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    alt: Optional[str] = Form(None),
    caption: Optional[str] = Form(None)
):
    """Upload a file to the default uploads directory"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    
    if user.get("role") not in ["admin", "editor", "moderator"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    # Validate file type
    file_type = get_file_type(file.filename)
    if not file_type:
        raise HTTPException(status_code=400, detail="Неподдерживаемый тип файла")
    
    # Read file content
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"Файл слишком большой. Максимум {MAX_FILE_SIZE // 1024 // 1024} MB")
    
    # Generate unique filename
    ext = Path(file.filename).suffix.lower()
    unique_filename = f"{uuid.uuid4()}{ext}"
    
    # Create date-based directory structure
    now = datetime.now(timezone.utc)
    date_path = f"{now.year}/{now.month:02d}"
    file_dir = UPLOAD_DIR / date_path
    file_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file
    file_path = file_dir / unique_filename
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)
    
    # Generate URL
    relative_path = f"/uploads/{date_path}/{unique_filename}"
    
    # Get image dimensions if image
    width, height = None, None
    if file_type == "image":
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(content))
            width, height = img.size
        except Exception:
            pass
    
    # Create media record
    db = await get_db()
    
    media = Media(
        filename=unique_filename,
        original_name=file.filename,
        path=str(file_path),
        url=relative_path,
        mime_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        width=width,
        height=height,
        alt=alt,
        caption=caption,
        uploaded_by=user["_id"]
    )
    
    doc = media.model_dump(by_alias=True)
    doc["uploaded_at"] = doc["uploaded_at"].isoformat()
    
    await db.media.insert_one(doc)
    
    return {
        "id": doc["_id"],
        "url": relative_path,
        "filename": unique_filename,
        "original_name": file.filename,
        "size": len(content),
        "width": width,
        "height": height
    }


@router.post("/upload-to-source", response_model=dict)
async def upload_to_source(
    request: Request,
    file: UploadFile = File(...),
    source: str = Form(..., description="Source directory: 'imported' or 'images'"),
    prefix: str = Form("", description="Path prefix (e.g., 'kvn-team' or 'images/people')"),
):
    """Upload a file to a specific source directory (imported or images volume)
    
    Sources:
    - 'imported': /app/frontend/public/media/imported/images (Docker volume)
    - 'images': /app/images (Docker volume)
    """
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    
    if user.get("role") not in ["admin", "editor", "moderator"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    if source not in ["imported", "images"]:
        raise HTTPException(status_code=400, detail="Некорректный source. Допустимые значения: 'imported', 'images'")
    
    # Определяем базовую директорию в зависимости от источника
    if source == "images":
        base_dir = Path("/app/images").resolve()
        url_prefix = "/images"
    else:
        base_dir = Path("/app/frontend/public/media/imported/images").resolve()
        url_prefix = "/media/imported/images"
    
    # Validate file type - только изображения для этих источников
    ext = Path(file.filename).suffix.lower()
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Разрешены только изображения (jpg, jpeg, png, webp, gif, svg)")
    
    # Read file content
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"Файл слишком большой. Максимум {MAX_FILE_SIZE // 1024 // 1024} MB")
    
    # Определяем целевую директорию
    if prefix:
        target_dir = (base_dir / prefix).resolve()
    else:
        target_dir = base_dir
    
    # Prevent path traversal
    if base_dir not in target_dir.parents and target_dir != base_dir:
        raise HTTPException(status_code=400, detail="Некорректный prefix")
    
    # Создаем директорию, если её нет
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Используем оригинальное имя файла (можно изменить логику, если нужны уникальные имена)
    filename = file.filename
    file_path = target_dir / filename
    
    # Проверяем, не существует ли уже файл с таким именем
    if file_path.exists():
        # Добавляем суффикс, если файл существует
        stem = file_path.stem
        counter = 1
        while file_path.exists():
            file_path = target_dir / f"{stem}_{counter}{ext}"
            counter += 1
        filename = file_path.name
    
    # Сохраняем файл
    try:
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Нет прав на запись в эту директорию")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении файла: {str(e)}")
    
    # Генерируем относительный путь для URL
    rel_path = file_path.relative_to(base_dir).as_posix()
    url = f"{url_prefix}/{rel_path}"
    
    return {
        "url": url,
        "path": rel_path,
        "filename": filename,
        "original_name": file.filename,
        "size": len(content),
        "source": source
    }


@router.get("", response_model=dict)
async def list_media(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    mime_type: Optional[str] = None,
    search: Optional[str] = None
):
    """List media files"""
    user = await get_current_user(request)
    if not user or user.get("role") not in ["admin", "editor", "moderator"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    db = await get_db()
    
    query = {"status": "active"}
    if mime_type:
        query["mime_type"] = {"$regex": f"^{mime_type}"}
    if search:
        query["$or"] = [
            {"original_name": {"$regex": search, "$options": "i"}},
            {"alt": {"$regex": search, "$options": "i"}}
        ]
    
    total = await db.media.count_documents(query)
    cursor = db.media.find(query).skip(skip).limit(limit).sort("uploaded_at", -1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/browse", response_model=MediaBrowseResponse)
async def browse_imported_media(
    request: Request,
    prefix: str = Query("", description="Path prefix (e.g., 'images/people' or 'kvn-team')"),
    source: str = Query("imported", description="Source directory: 'imported' or 'images'"),
    query: Optional[str] = Query(None, description="Case-insensitive substring filter"),
    limit: int = Query(200, ge=1, le=2000),
):
    """Browse local media files from different sources.

    Sources:
    - 'imported': /app/frontend/public/media/imported/images (Docker volume with imported images)
    - 'images': /app/images (Docker volume with site images)

    Returns URLs usable directly in <img src="...">.
    """
    user = await get_current_user(request)
    if not user or user.get("role") not in ["admin", "editor", "moderator"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    # Определяем базовую директорию в зависимости от источника
    if source == "images":
        # Docker volume с изображениями сайта
        base_dir = Path("/app/images").resolve()
        url_prefix = "/images"
    else:
        # Docker volume с импортированными изображениями
        base_dir = Path("/app/frontend/public/media/imported/images").resolve()
        url_prefix = "/media/imported/images"

    # Если prefix пустой, используем корень базовой директории
    if prefix:
        target_dir = (base_dir / prefix).resolve()
    else:
        target_dir = base_dir

    # prevent path traversal
    if base_dir not in target_dir.parents and target_dir != base_dir:
        raise HTTPException(status_code=400, detail="Некорректный prefix")

    if not target_dir.exists() or not target_dir.is_dir():
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Директория не существует или не является папкой: {target_dir} (source={source}, prefix={prefix})")
        return MediaBrowseResponse(items=[], folders=[], total=0)

    q = (query or "").lower() if query else None
    items: list[MediaBrowseItem] = []
    folders: list[MediaBrowseFolder] = []

    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}

    # Получаем только содержимое текущей папки (не рекурсивно)
    try:
        entries = list(target_dir.iterdir())
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Просмотр директории {target_dir}: найдено {len(entries)} элементов (source={source}, prefix={prefix})")
        
        for entry in entries:
            if entry.is_dir():
                # Это папка
                folder_rel = entry.relative_to(base_dir).as_posix()
                folders.append(
                    MediaBrowseFolder(
                        name=entry.name,
                        path=folder_rel,
                    )
                )
            elif entry.is_file() and entry.suffix.lower() in exts:
                # Это файл изображения
                rel = entry.relative_to(base_dir).as_posix()
                name = entry.name
                
                # Фильтр по поисковому запросу
                if q and q not in rel.lower() and q not in name.lower():
                    continue

                items.append(
                    MediaBrowseItem(
                        path=rel,
                        url=f"{url_prefix}/{rel}",
                        name=name,
                    )
                )
                if len(items) >= limit:
                    break
    except PermissionError:
        return MediaBrowseResponse(items=[], folders=[], total=0)

    # Сортируем папки и файлы
    folders.sort(key=lambda x: x.name.lower())
    items.sort(key=lambda x: x.name.lower())

    # Определяем путь к родительской папке
    parent_path = None
    if prefix:
        # Получаем родительский путь
        prefix_parts = prefix.split('/')
        if len(prefix_parts) > 1:
            parent_path = '/'.join(prefix_parts[:-1])
        elif len(prefix_parts) == 1:
            # Если prefix состоит из одной части, родитель - корень
            parent_path = ''
        # Если prefix пустой, parent_path остается None

    return MediaBrowseResponse(items=items, folders=folders, total=len(items), parent_path=parent_path)


@router.delete("/source/delete")
async def delete_from_source(
    request: Request,
    source: str = Query(..., description="Source directory: 'imported' or 'images'"),
    path: str = Query(..., description="File path relative to source base directory"),
):
    """Delete a file from a specific source directory (imported or images volume)
    
    Sources:
    - 'imported': /app/frontend/public/media/imported/images (Docker volume)
    - 'images': /app/images (Docker volume)
    """
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    
    if user.get("role") not in ["admin", "editor", "moderator"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    if source not in ["imported", "images"]:
        raise HTTPException(status_code=400, detail="Некорректный source. Допустимые значения: 'imported', 'images'")
    
    # Определяем базовую директорию в зависимости от источника
    if source == "images":
        base_dir = Path("/app/images").resolve()
    else:
        base_dir = Path("/app/frontend/public/media/imported/images").resolve()
    
    # Получаем путь к файлу
    file_path = (base_dir / path).resolve()
    
    # Prevent path traversal
    if base_dir not in file_path.parents and file_path != base_dir:
        raise HTTPException(status_code=400, detail="Некорректный путь")
    
    # Проверяем, что файл существует
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Указанный путь не является файлом")
    
    # Удаляем файл
    try:
        file_path.unlink()
    except PermissionError:
        raise HTTPException(status_code=403, detail="Нет прав на удаление файла")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении файла: {str(e)}")
    
    return {"deleted": True, "path": path, "source": source}


@router.put("/source/rename")
async def rename_file_in_source(
    request: Request,
    source: str = Query(..., description="Source directory: 'imported' or 'images'"),
    path: str = Query(..., description="Current file path relative to source base directory"),
    new_name: str = Query(..., description="New filename (without path)"),
):
    """Rename a file in a specific source directory (imported or images volume)
    
    Sources:
    - 'imported': /app/frontend/public/media/imported/images (Docker volume)
    - 'images': /app/images (Docker volume)
    """
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    
    if user.get("role") not in ["admin", "editor", "moderator"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    if source not in ["imported", "images"]:
        raise HTTPException(status_code=400, detail="Некорректный source. Допустимые значения: 'imported', 'images'")
    
    # Валидация нового имени файла
    if not new_name or '/' in new_name or '\\' in new_name:
        raise HTTPException(status_code=400, detail="Некорректное имя файла")
    
    # Определяем базовую директорию в зависимости от источника
    if source == "images":
        base_dir = Path("/app/images").resolve()
        url_prefix = "/images"
    else:
        base_dir = Path("/app/frontend/public/media/imported/images").resolve()
        url_prefix = "/media/imported/images"
    
    # Получаем путь к текущему файлу
    old_file_path = (base_dir / path).resolve()
    
    # Prevent path traversal
    if base_dir not in old_file_path.parents and old_file_path != base_dir:
        raise HTTPException(status_code=400, detail="Некорректный путь")
    
    # Проверяем, что файл существует
    if not old_file_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    if not old_file_path.is_file():
        raise HTTPException(status_code=400, detail="Указанный путь не является файлом")
    
    # Создаем новый путь с новым именем
    new_file_path = old_file_path.parent / new_name
    
    # Проверяем, не существует ли уже файл с таким именем
    if new_file_path.exists():
        raise HTTPException(status_code=400, detail="Файл с таким именем уже существует")
    
    # Переименовываем файл
    try:
        old_file_path.rename(new_file_path)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Нет прав на переименование файла")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при переименовании файла: {str(e)}")
    
    # Генерируем новый относительный путь для URL
    new_rel_path = new_file_path.relative_to(base_dir).as_posix()
    new_url = f"{url_prefix}/{new_rel_path}"
    
    return {
        "success": True,
        "old_path": path,
        "new_path": new_rel_path,
        "new_url": new_url,
        "new_name": new_name
    }


@router.get("/{media_id}", response_model=dict)
async def get_media(media_id: str):
    """Get media by ID"""
    db = await get_db()
    
    media = await db.media.find_one({"_id": media_id})
    
    if not media:
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    return media


@router.put("/{media_id}", response_model=dict)
async def update_media(
    media_id: str,
    request: Request,
    alt: Optional[str] = None,
    caption: Optional[str] = None
):
    """Update media metadata"""
    user = await get_current_user(request)
    if not user or user.get("role") not in ["admin", "editor", "moderator"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    db = await get_db()
    
    update_data = {}
    if alt is not None:
        update_data["alt"] = alt
    if caption is not None:
        update_data["caption"] = caption
    
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    
    result = await db.media.update_one({"_id": media_id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    return {"id": media_id, "updated": True}


@router.delete("/{media_id}")
async def delete_media(media_id: str, request: Request):
    """Delete media (soft delete)"""
    user = await get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    
    db = await get_db()
    
    result = await db.media.update_one(
        {"_id": media_id},
        {"$set": {"status": "deleted"}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    return {"id": media_id, "deleted": True}
