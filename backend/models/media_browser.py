from pydantic import BaseModel
from typing import List, Optional


class MediaBrowseItem(BaseModel):
    path: str
    url: str
    name: str


class MediaBrowseFolder(BaseModel):
    name: str
    path: str


class MediaBrowseResponse(BaseModel):
    items: list[MediaBrowseItem]
    folders: list[MediaBrowseFolder]
    total: int
    parent_path: Optional[str] = None  # Путь к родительской папке (None для корня)
