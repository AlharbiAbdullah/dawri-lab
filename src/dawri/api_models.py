"""Data models shared by the JSON API and page specifications."""

from pydantic import BaseModel, Field


class SeasonSummary(BaseModel, strict=True):
    season: str
    season_id: str
    finished: int
    upcoming: int


class Standing(BaseModel, strict=True):
    rank: int
    team_name: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int


class TeamMetrics(BaseModel, extra="allow", strict=True):
    team_name: str
    __pydantic_extra__: dict[str, int | float] = Field(init=False)
