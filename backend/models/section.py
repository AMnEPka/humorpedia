"""Section/Project model for hierarchical content structure"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import uuid4

from .base import ContentStatus, MediaFile, SEOData
from .modules import PageModule


class Section(BaseModel):
    """
    Section/Project - hierarchical content pages.
    Examples: /kvn, /kvn/vysshaya-liga, /kvn/vysshaya-liga/2024
    """
    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    
    # Basic info
    title: str  # Display title
    slug: str  # URL segment (e.g., "vysshaya-liga")
    full_path: str = ""  # Full URL path (e.g., "/kvn/vysshaya-liga") - auto-generated
    description: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    
    # Hierarchy
    parent_id: Optional[str] = None  # Parent section ID
    parent_path: Optional[str] = None  # Parent full path (for breadcrumbs)
    level: int = 0  # Nesting level (0 = root)
    order: int = 0  # Sort order among siblings
    
    # Navigation
    in_main_menu: bool = False  # Show in main menu
    menu_title: Optional[str] = None  # Short title for menu (if different)
    
    # Content
    modules: List[PageModule] = Field(default_factory=list)
    
    # Child content settings
    child_types: List[str] = Field(default_factory=list)  # Allowed child types: ["section", "team", "person", "article"]
    show_children_list: bool = True  # Auto-show list of children on page
    
    # SEO & Meta
    seo: SEOData = Field(default_factory=SEOData)
    tags: List[str] = Field(default_factory=list)
    status: ContentStatus = ContentStatus.DRAFT
    
    # Stats
    views: int = 0
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        populate_by_name = True


class SectionCreate(BaseModel):
    """Create section request"""
    title: str
    slug: str
    description: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    parent_id: Optional[str] = None
    order: int = 0
    in_main_menu: bool = False
    menu_title: Optional[str] = None
    modules: List[PageModule] = Field(default_factory=list)
    child_types: List[str] = Field(default_factory=list)
    show_children_list: bool = True
    seo: Optional[SEOData] = None
    tags: List[str] = Field(default_factory=list)
    status: ContentStatus = ContentStatus.DRAFT


class SectionUpdate(BaseModel):
    """Update section request"""
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    parent_id: Optional[str] = None
    order: Optional[int] = None
    in_main_menu: Optional[bool] = None
    menu_title: Optional[str] = None
    modules: Optional[List[PageModule]] = None
    child_types: Optional[List[str]] = None
    show_children_list: Optional[bool] = None
    seo: Optional[SEOData] = None
    tags: Optional[List[str]] = None
    status: Optional[ContentStatus] = None


class SectionTree(BaseModel):
    """Section with children for tree view"""
    id: str
    title: str
    slug: str
    full_path: str
    level: int
    order: int
    status: str
    in_main_menu: bool
    children: List["SectionTree"] = Field(default_factory=list)


SectionTree.model_rebuild()
