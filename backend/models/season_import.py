"""Проверенный редактором пакет нового сезона КВН; команды связаны ключами пакета."""
from datetime import date
from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from utils.team_matcher import normalize_team_name


class ImportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ImportTeam(ImportModel):
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    city: str = ""
    aliases: list[str] = Field(default_factory=list)
    existing_slug: str | None = None


class ImportResult(ImportModel):
    team_key: str
    place: int | None = Field(default=None, ge=1)
    total: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    scores: dict[str, float] = Field(default_factory=dict)
    passed: bool = False
    is_additional: bool = False
    is_winner: bool = False


class ImportGame(ImportModel):
    name: str = Field(min_length=1)
    order: int = Field(ge=1)
    date: date
    host: str = ""
    jury: list[str] = Field(default_factory=list)
    contests: list[str] = Field(default_factory=list)
    notes: str = ""
    results: list[ImportResult] = Field(min_length=1, max_length=100)


class ImportStage(ImportModel):
    name: str = Field(min_length=1)
    order: int = Field(ge=1)
    comment: str = ""
    additional_teams: list[str] = Field(default_factory=list)
    additional_notes: str = ""
    games: list[ImportGame] = Field(default_factory=list)


class SeasonImport(ImportModel):
    league_slug: str = Field(pattern=r"^[a-z0-9-]+$")
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=1)
    year: int = Field(ge=1986, le=2100)
    number: int | None = Field(default=None, ge=1)
    source_url: HttpUrl
    as_of: date
    status: Literal["draft", "published"] = "published"
    intro_html: str = ""
    editorial_notes: str = ""
    host: str = ""
    editors: list[str] = Field(default_factory=list)
    teams: list[ImportTeam] = Field(min_length=1, max_length=300)
    winners: list[str] = Field(default_factory=list)
    stages: list[ImportStage] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_results(self):
        keys = [team.key for team in self.teams]
        if len(keys) != len(set(keys)):
            raise ValueError("Ключи команд должны быть уникальны")
        names = [(normalize_team_name(team.name), normalize_team_name(team.city)) for team in self.teams]
        if len(names) != len(set(names)):
            raise ValueError("Повторное название команды и город")
        for index, team in enumerate(self.teams):
            team_names = {normalize_team_name(name) for name in [team.name, *team.aliases] if name}
            for other in self.teams[:index]:
                other_names = {normalize_team_name(name) for name in [other.name, *other.aliases] if name}
                overlap = team_names & other_names
                if overlap and (team.aliases or other.aliases):
                    raise ValueError(f"{team.name}: алиас совпадает с другим участником сезона")
        if not set(self.winners).issubset(keys):
            raise ValueError("Победитель отсутствует в списке команд")
        stage_orders = [stage.order for stage in self.stages]
        if len(stage_orders) != len(set(stage_orders)):
            raise ValueError("Порядок стадий должен быть уникален")
        for stage in self.stages:
            orders = [game.order for game in stage.games]
            if len(orders) != len(set(orders)):
                raise ValueError(f"{stage.name}: порядок игр должен быть уникален")
            for game in stage.games:
                if game.date.year != self.year or game.date > self.as_of:
                    raise ValueError(f"{game.name}: дата вне года сезона или позже даты среза")
                result_keys = [row.team_key for row in game.results]
                if len(result_keys) != len(set(result_keys)) or not set(result_keys).issubset(keys):
                    raise ValueError(f"{game.name}: неизвестная или повторная команда")
                if len(game.contests) != len(set(game.contests)):
                    raise ValueError(f"{game.name}: повторные конкурсы")
                for row in game.results:
                    if not set(row.scores).issubset(game.contests):
                        raise ValueError(f"{game.name}: оценка за неизвестный конкурс")
                    if any(not isfinite(score) or score < 0 for score in row.scores.values()):
                        raise ValueError(f"{game.name}: некорректная оценка")
                    if row.total is None:
                        raise ValueError(f"{game.name}: нужен опубликованный итог")
                    if row.scores and set(row.scores) == set(game.contests):
                        if abs(sum(row.scores.values()) - row.total) > 0.051:
                            raise ValueError(f"{game.name}: сумма оценок не совпадает с итогом {row.team_key}")
        return self


class SeasonImportRequest(ImportModel):
    package: SeasonImport
    preview_token: str | None = None
