"""City model for Geography section"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from .base import BaseContent, ContentType, MediaFile, SEOData, ContentStatus, generate_uuid, utc_now
from .modules import PageModule


class City(BaseContent):
    """City page for Geography section"""
    content_type: ContentType = ContentType.PAGE  # Using PAGE type for cities
    
    # Basic info
    name: str
    poster: Optional[MediaFile] = None
    description: Optional[str] = None  # Short description/intro
    facts: Dict[str, str] = Field(default_factory=dict)  # Key-value facts
    facts_order: List[str] = Field(default_factory=list)  # Stable order of facts keys
    
    # Modular content
    modules: List[PageModule] = Field(default_factory=list)
    
    # Relations
    related_person_ids: List[str] = Field(default_factory=list)  # Famous people from this city
    related_team_ids: List[str] = Field(default_factory=list)  # Teams from this city
    
    # Legacy
    old_id: Optional[int] = None  # MODX resource ID


class CityCreate(BaseModel):
    """Create city request"""
    title: str
    slug: str
    name: str
    poster: Optional[MediaFile] = None
    description: Optional[str] = None
    facts: Optional[Dict[str, str]] = None
    facts_order: Optional[List[str]] = None
    modules: List[PageModule] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    seo: Optional[SEOData] = None
    status: ContentStatus = ContentStatus.DRAFT
    related_person_ids: Optional[List[str]] = None
    related_team_ids: Optional[List[str]] = None


class CityUpdate(BaseModel):
    """Update city request"""
    title: Optional[str] = None
    slug: Optional[str] = None
    name: Optional[str] = None
    poster: Optional[MediaFile] = None
    description: Optional[str] = None
    facts: Optional[Dict[str, str]] = None
    facts_order: Optional[List[str]] = None
    modules: Optional[List[PageModule]] = None
    tags: Optional[List[str]] = None
    seo: Optional[SEOData] = None
    status: Optional[ContentStatus] = None
    related_person_ids: Optional[List[str]] = None
    related_team_ids: Optional[List[str]] = None
    rating: Optional[float] = None
    votes_count: Optional[int] = None
