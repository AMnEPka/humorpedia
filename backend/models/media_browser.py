from pydantic import BaseModel


class MediaBrowseItem(BaseModel):
    path: str
    url: str
    name: str


class MediaBrowseResponse(BaseModel):
    items: list[MediaBrowseItem]
    total: int
