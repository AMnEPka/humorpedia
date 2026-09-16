"""Модели соревнований (турнир → сезон → этап → игра → результат). Схема и логика — services/competitions.py."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ParticipantRef(_Model):
    """Участник в списке сезона/победителях. Для команд — team_id (teams._id), для людей — person_id."""
    team_id: Optional[str] = None
    person_id: Optional[str] = None
    slug: str = ""
    name: str = ""
    city: str = ""
    had_city: bool = False
    extra: Dict[str, Any] = Field(default_factory=dict)


class GameResult(ParticipantRef):
    place: Optional[int] = None
    total: Optional[float] = None
    scores: Dict[str, Any] = Field(default_factory=dict)
    passed: bool = False
    is_winner: bool = False
    is_additional: bool = False
    legacy_team_id: Optional[str] = None


class Game(_Model):
    id: Optional[str] = None
    had_legacy_id: bool = True
    legacy_id: Optional[str] = None
    name: str = ""
    order: Optional[float] = None
    date: str = ""
    date_raw: Optional[str] = None
    host: str = ""
    jury: List[str] = Field(default_factory=list)
    contests: List[str] = Field(default_factory=list)
    notes: str = ""
    is_cancelled: Optional[bool] = None
    results: List[GameResult] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)


class Stage(_Model):
    id: Optional[str] = None
    name: str = ""
    order: Optional[float] = None
    notes: str = ""
    additional_teams: List[str] = Field(default_factory=list)
    additional_notes: str = ""
    games: List[Game] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)


class SeasonUpdate(_Model):
    """Редактируемая часть сезона. Название/slug/путь принадлежат странице и здесь не меняются."""
    year: Optional[int] = None
    number: Optional[int] = None
    league_name: Optional[str] = None
    intro_html: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    host: Optional[str] = None
    hosts: Optional[List[Any]] = None
    editors: Optional[List[Any]] = None
    jury: Optional[List[Any]] = None
    extra_sections: Optional[List[Any]] = None
    late_joined_teams: Optional[List[Any]] = None
    teams: Optional[List[ParticipantRef]] = None
    winners: Optional[List[ParticipantRef]] = None
    stages: Optional[List[Stage]] = None
