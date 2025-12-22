"""User and authentication models"""
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from .base import generate_uuid, utc_now


class UserRole(str, Enum):
    """User roles"""
    USER = "user"
    MODERATOR = "moderator"
    EDITOR = "editor"
    ADMIN = "admin"


class AuthProvider(str, Enum):
    """Authentication providers"""
    EMAIL = "email"
    VK = "vk"
    YANDEX = "yandex"


class UserProfile(BaseModel):
    """User profile data"""
    full_name: Optional[str] = None
    avatar: Optional[str] = None
    bio: Optional[str] = None
    birth_date: Optional[str] = None
    location: Optional[str] = None


class UserStats(BaseModel):
    """User activity statistics"""
    articles_count: int = 0
    comments_count: int = 0
    votes_count: int = 0
    quiz_attempts: int = 0


class OAuthData(BaseModel):
    """OAuth provider data"""
    vk_id: Optional[str] = None
    yandex_id: Optional[str] = None
    vk_data: Optional[Dict[str, Any]] = None
    yandex_data: Optional[Dict[str, Any]] = None


class User(BaseModel):
    """User model"""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    id: str = Field(default_factory=generate_uuid, alias="_id")
    
    # Authentication
    username: str
    email: Optional[str] = None
    password_hash: Optional[str] = None  # bcrypt hash
    
    # Profile
    profile: UserProfile = Field(default_factory=UserProfile)
    
    # Role and permissions
    role: UserRole = UserRole.USER
    permissions: List[str] = Field(default_factory=lambda: ["comment", "vote"])
    
    # OAuth
    oauth: OAuthData = Field(default_factory=OAuthData)
    auth_provider: AuthProvider = AuthProvider.EMAIL
    
    # Statistics
    stats: UserStats = Field(default_factory=UserStats)
    
    # Status
    active: bool = True
    verified: bool = False
    banned: bool = False
    
    # Legacy
    old_id: Optional[int] = None  # MODX user ID
    
    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_login_at: Optional[datetime] = None


class UserCreate(BaseModel):
    """Create user via email registration"""
    username: str
    email: EmailStr
    password: str
    profile: Optional[UserProfile] = None


class UserLogin(BaseModel):
    """Login request"""
    email: str
    password: str


class UserUpdate(BaseModel):
    """Update user profile"""
    username: Optional[str] = None
    email: Optional[str] = None
    profile: Optional[UserProfile] = None


class UserAdminUpdate(BaseModel):
    """Admin update user"""
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    permissions: Optional[List[str]] = None
    active: Optional[bool] = None
    verified: Optional[bool] = None
    banned: Optional[bool] = None


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


class OAuthCallback(BaseModel):
    """OAuth callback data"""
    code: str
    state: Optional[str] = None


# === COMMENTS ===

class Comment(BaseModel):
    """Comment model"""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    id: str = Field(default_factory=generate_uuid, alias="_id")
    
    # Reference
    resource_type: str  # person, team, article, news, etc.
    resource_id: str
    
    # Author
    user_id: str
    author_name: str  # Denormalized
    author_avatar: Optional[str] = None
    
    # Content
    text: str
    
    # Threading
    parent_id: Optional[str] = None
    level: int = 0
    
    # Moderation
    approved: bool = True
    deleted: bool = False
    edited: bool = False
    edited_at: Optional[datetime] = None
    
    # Reactions
    likes: int = 0
    dislikes: int = 0
    
    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CommentCreate(BaseModel):
    """Create comment request"""
    resource_type: str
    resource_id: str
    text: str
    parent_id: Optional[str] = None


class CommentUpdate(BaseModel):
    """Update comment request"""
    text: str


# === TAGS ===

class Tag(BaseModel):
    """Tag model"""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    id: str = Field(default_factory=generate_uuid, alias="_id")
    name: str
    slug: str
    old_id: Optional[int] = None  # MODX tagger ID
    usage_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)


class TagCreate(BaseModel):
    """Create tag request"""
    name: str
    slug: Optional[str] = None


# === MEDIA ===

class Media(BaseModel):
    """Media file model"""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    id: str = Field(default_factory=generate_uuid, alias="_id")
    
    # File info
    filename: str
    original_name: str
    path: str
    url: str
    
    # Type and size
    mime_type: str
    file_size: int  # bytes
    
    # For images
    width: Optional[int] = None
    height: Optional[int] = None
    
    # Variants (thumbnails)
    variants: Dict[str, str] = Field(default_factory=dict)  # {thumbnail: url, medium: url, etc.}
    
    # Metadata
    alt: Optional[str] = None
    caption: Optional[str] = None
    copyright: Optional[str] = None
    
    # Usage tracking
    used_in: List[Dict[str, str]] = Field(default_factory=list)  # [{type: "person", id: "..."}]
    
    # Upload info
    uploaded_by: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=utc_now)
    
    # Status
    status: str = "active"  # active, archived, deleted


class MediaCreate(BaseModel):
    """Create media record"""
    filename: str
    original_name: str
    path: str
    url: str
    mime_type: str
    file_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    alt: Optional[str] = None
    caption: Optional[str] = None
