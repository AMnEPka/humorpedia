"""Content models for all page types"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from .base import BaseContent, ContentType, TeamType, MediaFile, SocialLinks, SEOData, ContentStatus, generate_uuid, utc_now
from .modules import PageModule


# === PERSON ===

class PersonBio(BaseModel):
    """Biographical data for a person"""
    birth_date: Optional[str] = None
    death_date: Optional[str] = None
    birth_place: Optional[str] = None
    current_city: Optional[str] = None
    occupation: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)


class Person(BaseContent):
    """Person/personality page"""
    content_type: ContentType = ContentType.PERSON
    
    # Basic info
    full_name: str
    photo: Optional[MediaFile] = None
    bio: PersonBio = Field(default_factory=PersonBio)
    social_links: SocialLinks = Field(default_factory=SocialLinks)
    
    # Modular content
    modules: List[PageModule] = Field(default_factory=list)
    
    # Relations
    team_ids: List[str] = Field(default_factory=list)  # Teams this person belongs to
    show_ids: List[str] = Field(default_factory=list)  # Shows participated in
    article_ids: List[str] = Field(default_factory=list)  # Related articles


class PersonCreate(BaseModel):
    """Create person request"""
    title: str
    slug: str
    full_name: str
    photo: Optional[MediaFile] = None
    bio: Optional[PersonBio] = None
    social_links: Optional[SocialLinks] = None
    modules: List[PageModule] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    seo: Optional[SEOData] = None
    status: ContentStatus = ContentStatus.DRAFT


class PersonUpdate(BaseModel):
    """Update person request"""
    title: Optional[str] = None
    slug: Optional[str] = None
    full_name: Optional[str] = None
    photo: Optional[MediaFile] = None
    bio: Optional[PersonBio] = None
    social_links: Optional[SocialLinks] = None
    modules: Optional[List[PageModule]] = None
    tags: Optional[List[str]] = None
    seo: Optional[SEOData] = None
    status: Optional[ContentStatus] = None
    team_ids: Optional[List[str]] = None
    show_ids: Optional[List[str]] = None


# === TEAM ===

class Team(BaseContent):
    """Team page (universal for KVN, Liga Smeha, Improv, etc.)"""
    content_type: ContentType = ContentType.TEAM
    
    # Team type for filtering
    team_type: TeamType = TeamType.KVN
    
    # Basic info
    name: str
    logo: Optional[MediaFile] = None
    facts: Dict[str, str] = Field(default_factory=dict)  # Flexible key-value pairs for team info
    social_links: SocialLinks = Field(default_factory=SocialLinks)
    
    # Modular content
    modules: List[PageModule] = Field(default_factory=list)
    
    # Relations
    member_ids: List[str] = Field(default_factory=list)  # Team members (persons)
    show_ids: List[str] = Field(default_factory=list)  # Related shows
    article_ids: List[str] = Field(default_factory=list)  # Related articles
    related_team_ids: List[str] = Field(default_factory=list)  # Similar teams


class TeamCreate(BaseModel):
    """Create team request"""
    title: str
    slug: str
    name: str
    team_type: TeamType = TeamType.KVN
    logo: Optional[MediaFile] = None
    facts: Optional[Dict[str, str]] = None
    social_links: Optional[SocialLinks] = None
    modules: List[PageModule] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    seo: Optional[SEOData] = None
    status: ContentStatus = ContentStatus.DRAFT


class TeamUpdate(BaseModel):
    """Update team request"""
    title: Optional[str] = None
    slug: Optional[str] = None
    name: Optional[str] = None
    team_type: Optional[TeamType] = None
    logo: Optional[MediaFile] = None
    facts: Optional[Dict[str, str]] = None
    social_links: Optional[SocialLinks] = None
    modules: Optional[List[PageModule]] = None
    tags: Optional[List[str]] = None
    seo: Optional[SEOData] = None
    status: Optional[ContentStatus] = None
    member_ids: Optional[List[str]] = None
    show_ids: Optional[List[str]] = None


# === SHOW ===

class ShowFacts(BaseModel):
    """Quick facts about a show"""
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    network: Optional[str] = None  # TV channel
    episodes_count: Optional[int] = None
    seasons_count: Optional[int] = None
    hosts: List[str] = Field(default_factory=list)  # Host names
    host_ids: List[str] = Field(default_factory=list)  # Host person IDs
    genre: List[str] = Field(default_factory=list)
    status: str = "ongoing"  # ongoing, ended, hiatus


class Show(BaseContent):
    """Show/Project page"""
    content_type: ContentType = ContentType.SHOW
    
    # Basic info
    name: str
    poster: Optional[MediaFile] = None
    facts: ShowFacts = Field(default_factory=ShowFacts)
    description: Optional[str] = None  # HTML
    
    # Hierarchy support
    parent_id: Optional[str] = None  # For child shows (seasons, episodes)
    child_show_ids: List[str] = Field(default_factory=list)  # List of child shows
    
    # Modular content
    modules: List[PageModule] = Field(default_factory=list)
    
    # Relations
    participant_ids: List[str] = Field(default_factory=list)  # Participants (persons)
    team_ids: List[str] = Field(default_factory=list)  # Teams in this show
    article_ids: List[str] = Field(default_factory=list)
    related_show_ids: List[str] = Field(default_factory=list)


class ShowCreate(BaseModel):
    """Create show request"""
    title: str
    slug: str
    name: str
    poster: Optional[MediaFile] = None
    facts: Optional[ShowFacts] = None
    description: Optional[str] = None
    modules: List[PageModule] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    seo: Optional[SEOData] = None
    status: ContentStatus = ContentStatus.DRAFT


class ShowUpdate(BaseModel):
    """Update show request"""
    title: Optional[str] = None
    slug: Optional[str] = None
    name: Optional[str] = None
    poster: Optional[MediaFile] = None
    facts: Optional[ShowFacts] = None
    description: Optional[str] = None
    modules: Optional[List[PageModule]] = None
    tags: Optional[List[str]] = None
    seo: Optional[SEOData] = None
    status: Optional[ContentStatus] = None
    participant_ids: Optional[List[str]] = None
    team_ids: Optional[List[str]] = None


# === ARTICLE ===

class Article(BaseContent):
    """Article page"""
    content_type: ContentType = ContentType.ARTICLE
    
    # Basic info
    excerpt: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    
    # Modular content
    modules: List[PageModule] = Field(default_factory=list)
    
    # Relations
    related_person_ids: List[str] = Field(default_factory=list)
    related_team_ids: List[str] = Field(default_factory=list)
    related_article_ids: List[str] = Field(default_factory=list)


class ArticleCreate(BaseModel):
    """Create article request"""
    title: str
    slug: str
    excerpt: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    featured: bool = False
    modules: List[PageModule] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    seo: Optional[SEOData] = None
    status: ContentStatus = ContentStatus.DRAFT


class ArticleUpdate(BaseModel):
    """Update article request"""
    title: Optional[str] = None
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    modules: Optional[List[PageModule]] = None
    tags: Optional[List[str]] = None
    seo: Optional[SEOData] = None
    status: Optional[ContentStatus] = None
    related_person_ids: Optional[List[str]] = None
    related_team_ids: Optional[List[str]] = None


# === NEWS ===

class News(BaseContent):
    """News page"""
    content_type: ContentType = ContentType.NEWS
    
    # Basic info
    excerpt: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    content: Optional[str] = None  # HTML content
    important: bool = False  # Highlight as important
    
    # Content modules
    modules: List[PageModule] = Field(default_factory=list)
    
    # Relations
    related_person_ids: List[str] = Field(default_factory=list)
    related_team_ids: List[str] = Field(default_factory=list)
    related_article_ids: List[str] = Field(default_factory=list)


class NewsCreate(BaseModel):
    """Create news request"""
    title: str
    slug: str
    excerpt: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    content: Optional[str] = None
    important: bool = False
    modules: List[PageModule] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    seo: Optional[SEOData] = None
    status: ContentStatus = ContentStatus.DRAFT


class NewsUpdate(BaseModel):
    """Update news request"""
    title: Optional[str] = None
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    content: Optional[str] = None
    important: Optional[bool] = None
    modules: Optional[List[PageModule]] = None
    tags: Optional[List[str]] = None
    seo: Optional[SEOData] = None
    status: Optional[ContentStatus] = None
    related_person_ids: Optional[List[str]] = None
    related_team_ids: Optional[List[str]] = None


# === QUIZ ===

class Quiz(BaseContent):
    """Quiz page"""
    content_type: ContentType = ContentType.QUIZ
    
    # Basic info
    description: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    
    # Modular content (quiz_questions and quiz_results modules)
    modules: List[PageModule] = Field(default_factory=list)
    
    # Statistics
    attempts_count: int = 0
    avg_score: Optional[float] = None
    completion_rate: Optional[float] = None


class QuizCreate(BaseModel):
    """Create quiz request"""
    title: str
    slug: str
    description: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    modules: List[PageModule] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    seo: Optional[SEOData] = None
    status: ContentStatus = ContentStatus.DRAFT


class QuizUpdate(BaseModel):
    """Update quiz request"""
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    modules: Optional[List[PageModule]] = None
    tags: Optional[List[str]] = None
    seo: Optional[SEOData] = None
    status: Optional[ContentStatus] = None


# === WIKI ===

class Wiki(BaseContent):
    """Wiki page (general encyclopedia entry)"""
    content_type: ContentType = ContentType.WIKI
    
    # Content
    content: Optional[str] = None  # HTML content
    cover_image: Optional[MediaFile] = None
    
    # For wiki_header type
    has_header: bool = False
    header_image: Optional[MediaFile] = None
    header_facts: List[Dict[str, str]] = Field(default_factory=list)
    
    # Modular content
    modules: List[PageModule] = Field(default_factory=list)
    
    # Relations
    related_ids: List[str] = Field(default_factory=list)


class WikiCreate(BaseModel):
    """Create wiki request"""
    title: str
    slug: str
    content: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    has_header: bool = False
    header_image: Optional[MediaFile] = None
    header_facts: List[Dict[str, str]] = Field(default_factory=list)
    modules: List[PageModule] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    seo: Optional[SEOData] = None
    status: ContentStatus = ContentStatus.DRAFT


class WikiUpdate(BaseModel):
    """Update wiki request"""
    title: Optional[str] = None
    slug: Optional[str] = None
    content: Optional[str] = None
    cover_image: Optional[MediaFile] = None
    has_header: Optional[bool] = None
    header_image: Optional[MediaFile] = None
    header_facts: Optional[List[Dict[str, str]]] = None
    modules: Optional[List[PageModule]] = None
    tags: Optional[List[str]] = None
    seo: Optional[SEOData] = None
    status: Optional[ContentStatus] = None
    related_ids: Optional[List[str]] = None
