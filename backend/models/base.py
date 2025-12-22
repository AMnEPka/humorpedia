"""Base models and common types for Humorpedia"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ContentType(str, Enum):
    """Types of content pages"""
    PERSON = "person"
    TEAM = "team"
    SHOW = "show"
    ARTICLE = "article"
    NEWS = "news"
    QUIZ = "quiz"
    WIKI = "wiki"
    WIKI_HEADER = "wiki_header"
    PAGE = "page"


class TeamType(str, Enum):
    """Types of teams for different shows"""
    KVN = "kvn"
    LIGA_SMEHA = "liga_smeha"
    IMPROV = "improv"
    COMEDY_CLUB = "comedy_club"
    OTHER = "other"


class ContentStatus(str, Enum):
    """Publication status"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SEOData(BaseModel):
    """SEO metadata for pages"""
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    og_image: Optional[str] = None


class MediaFile(BaseModel):
    """Media file reference"""
    url: str
    alt: Optional[str] = None
    caption: Optional[str] = None
    thumbnail: Optional[str] = None


class SocialLinks(BaseModel):
    """Social media links"""
    vk: Optional[str] = None
    telegram: Optional[str] = None
    youtube: Optional[str] = None
    instagram: Optional[str] = None
    website: Optional[str] = None


class BaseDocument(BaseModel):
    """Base document model with common fields"""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    id: str = Field(default_factory=generate_uuid, alias="_id")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


class BaseContent(BaseDocument):
    """Base content model for all page types"""
    title: str
    slug: str
    content_type: ContentType
    status: ContentStatus = ContentStatus.DRAFT
    
    # Legacy ID from MODX for migration
    old_id: Optional[int] = None
    
    # SEO
    seo: SEOData = Field(default_factory=SEOData)
    
    # Tags
    tags: List[str] = Field(default_factory=list)
    
    # Statistics
    views: int = 0
    rating: Optional[float] = None
    votes_count: int = 0
    comments_count: int = 0
    
    # Publication
    published_at: Optional[datetime] = None
    featured: bool = False
