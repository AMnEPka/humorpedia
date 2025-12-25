"""Media upload and management routes"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Request
from typing import Optional, List
from datetime import datetime, timezone
import os
import uuid
import aiofiles
from pathlib import Path

from models.user import Media, MediaCreate
from models.media_browser import MediaBrowseResponse, MediaBrowseItem
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
    """Upload a file"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    
    if not user.get("role") in ["admin", "editor", "moderator"]:
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
        except:
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
    prefix: str = Query("images/people", description="Path prefix under /media/imported"),
    query: Optional[str] = Query(None, description="Case-insensitive substring filter"),
    limit: int = Query(200, ge=1, le=2000),
):
    """Browse local imported media files from frontend/public/media/imported.

    Returns URLs usable directly in <img src="...">.
    """
    user = await get_current_user(request)
    if not user or user.get("role") not in ["admin", "editor", "moderator"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    base_dir = Path("/app/frontend/public/media/imported").resolve()
    target_dir = (base_dir / prefix).resolve()

    # prevent path traversal
    if base_dir not in target_dir.parents and target_dir != base_dir:
        raise HTTPException(status_code=400, detail="Некорректный prefix")

    if not target_dir.exists() or not target_dir.is_dir():
        return MediaBrowseResponse(items=[], total=0)

    q = (query or "").lower() if query else None
    items: list[MediaBrowseItem] = []

    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    for p in target_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue

        rel = p.relative_to(base_dir).as_posix()  # e.g. images/people/kvn/x.jpg
        name = p.name
        if q and q not in rel.lower() and q not in name.lower():
            continue

        items.append(
            MediaBrowseItem(
                path=rel,
                url=f"/media/imported/{rel}",
                name=name,
            )
        )
        if len(items) >= limit:
            break

    return MediaBrowseResponse(items=items, total=len(items))


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
