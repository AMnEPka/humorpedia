"""Module definitions for modular page builder"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union, Literal
from enum import Enum


class ModuleType(str, Enum):
    """Available module types"""
    # Universal modules
    HERO_CARD = "hero_card"           # Photo with facts
    TEXT_BLOCK = "text_block"         # Text with optional title
    TIMELINE = "timeline"             # Timeline of events
    TAGS = "tags"                     # Tags display
    TABLE = "table"                   # Data table with sorting
    GALLERY = "gallery"               # Image gallery
    VIDEO = "video"                   # Video embed
    QUOTE = "quote"                   # Quote block
    
    # Team-specific modules
    TEAM_MEMBERS = "team_members"     # Team composition
    TV_APPEARANCES = "tv_appearances" # TV broadcasts table
    GAMES_LIST = "games_list"         # List of games
    
    # Show-specific modules
    EPISODES_LIST = "episodes_list"   # Show episodes
    PARTICIPANTS = "participants"     # Show participants
    
    # Article modules
    BEST_ARTICLES = "best_articles"   # Best articles widget
    INTERESTING = "interesting"       # Interesting content
    RANDOM_PAGE = "random_page"       # Random page link
    
    # Quiz modules
    QUIZ_QUESTIONS = "quiz_questions" # Quiz questions
    QUIZ_RESULTS = "quiz_results"     # Quiz results


# --- Module Data Schemas ---

class FactItem(BaseModel):
    """Single fact item for hero card"""
    label: str
    value: str
    link: Optional[str] = None


class HeroCardData(BaseModel):
    """Data for hero_card module"""
    photo: Optional[str] = None
    photo_alt: Optional[str] = None
    facts: List[FactItem] = Field(default_factory=list)
    social_links: Optional[Dict[str, str]] = None


class TextBlockData(BaseModel):
    """Data for text_block module"""
    title: Optional[str] = None
    content: str  # HTML content


class TimelineItem(BaseModel):
    """Single timeline entry"""
    year: int
    month: Optional[int] = None
    title: str
    description: Optional[str] = None
    image: Optional[str] = None
    link: Optional[str] = None
    type: Optional[str] = None  # achievement, career, personal, etc.


class TimelineData(BaseModel):
    """Data for timeline module"""
    title: Optional[str] = "Хронология"
    items: List[TimelineItem] = Field(default_factory=list)


class TagsData(BaseModel):
    """Data for tags module"""
    tags: List[str] = Field(default_factory=list)


class TableColumn(BaseModel):
    """Table column definition"""
    key: str
    label: str
    sortable: bool = False
    highlight: bool = False
    width: Optional[str] = None


class TableData(BaseModel):
    """Data for table module"""
    title: Optional[str] = None
    columns: List[TableColumn] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    sortable: bool = False
    highlight_rules: Optional[Dict[str, str]] = None  # color rules


class GalleryItem(BaseModel):
    """Gallery image"""
    url: str
    thumbnail: Optional[str] = None
    alt: Optional[str] = None
    caption: Optional[str] = None


class GalleryData(BaseModel):
    """Data for gallery module"""
    title: Optional[str] = None
    items: List[GalleryItem] = Field(default_factory=list)


class VideoData(BaseModel):
    """Data for video module"""
    url: str  # YouTube, VK, etc.
    title: Optional[str] = None
    caption: Optional[str] = None


class QuoteData(BaseModel):
    """Data for quote module"""
    text: str
    author: Optional[str] = None
    source: Optional[str] = None


class TeamMember(BaseModel):
    """Team member entry"""
    person_id: Optional[str] = None  # Link to person
    name: str
    role: Optional[str] = None
    joined_year: Optional[int] = None
    left_year: Optional[int] = None
    active: bool = True
    photo: Optional[str] = None


class TeamMembersData(BaseModel):
    """Data for team_members module"""
    title: Optional[str] = "Состав команды"
    members: List[TeamMember] = Field(default_factory=list)


class TVAppearance(BaseModel):
    """TV broadcast entry"""
    date: Optional[str] = None
    season: Optional[str] = None
    league: Optional[str] = None
    episode: Optional[str] = None
    result: Optional[str] = None
    score: Optional[float] = None
    video_url: Optional[str] = None
    notes: Optional[str] = None


class TVAppearancesData(BaseModel):
    """Data for tv_appearances module"""
    title: Optional[str] = "ТВ эфиры"
    appearances: List[TVAppearance] = Field(default_factory=list)


class GameEntry(BaseModel):
    """Game list entry"""
    date: Optional[str] = None
    opponent: Optional[str] = None
    league: Optional[str] = None
    result: Optional[str] = None
    video_url: Optional[str] = None


class GamesListData(BaseModel):
    """Data for games_list module"""
    title: Optional[str] = "Список игр"
    games: List[GameEntry] = Field(default_factory=list)


class Episode(BaseModel):
    """Show episode"""
    season: Optional[int] = None
    episode: Optional[int] = None
    title: Optional[str] = None
    air_date: Optional[str] = None
    guests: List[str] = Field(default_factory=list)
    video_url: Optional[str] = None
    description: Optional[str] = None


class EpisodesListData(BaseModel):
    """Data for episodes_list module"""
    title: Optional[str] = "Список выпусков"
    episodes: List[Episode] = Field(default_factory=list)


class Participant(BaseModel):
    """Show participant"""
    person_id: Optional[str] = None
    name: str
    role: Optional[str] = None
    from_year: Optional[int] = None
    to_year: Optional[int] = None
    episodes_count: Optional[int] = None


class ParticipantsData(BaseModel):
    """Data for participants module"""
    title: Optional[str] = "Участники"
    participants: List[Participant] = Field(default_factory=list)


class QuizQuestion(BaseModel):
    """Quiz question"""
    id: int
    question: str
    image: Optional[str] = None
    options: List[Dict[str, Any]]  # {id, text, correct}
    explanation: Optional[str] = None


class QuizQuestionsData(BaseModel):
    """Data for quiz_questions module"""
    questions: List[QuizQuestion] = Field(default_factory=list)


class QuizResult(BaseModel):
    """Quiz result range"""
    min_score: int
    max_score: int
    title: str
    description: str
    image: Optional[str] = None


class QuizResultsData(BaseModel):
    """Data for quiz_results module"""
    results: List[QuizResult] = Field(default_factory=list)


# --- Main Module Model ---

class PageModule(BaseModel):
    """A single module on a page"""
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    type: ModuleType
    order: int = 0
    title: Optional[str] = None  # Optional override title
    visible: bool = True
    data: Dict[str, Any]  # Module-specific data
    
    class Config:
        use_enum_values = True


# --- Page Template ---

class PageTemplate(BaseModel):
    """Saved template (preset) of modules"""
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    name: str
    description: Optional[str] = None
    content_type: str  # Which content type this template is for
    modules: List[PageModule] = Field(default_factory=list)
    is_default: bool = False
    created_at: str = Field(default_factory=lambda: __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat())
