import copy
import json
from pathlib import Path
from typing import Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from dawri.config import DATA_DIR

DIR = DATA_DIR / "matches"


class TeamContract(BaseModel):
    team_id: str = Field(alias="teamId")
    short_name: str = Field(alias="shortName")


class MatchSetContract(BaseModel):
    name: str


class MatchContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    match_id: str = Field(alias="matchId")
    home_team: TeamContract = Field(alias="home")
    away_team: TeamContract = Field(alias="away")
    home_score_push: int = Field(alias="homeScorePush", ge=0)
    away_score_push: int = Field(alias="awayScorePush", ge=0)
    win_team_id: str | None = Field(alias="winTeamId")
    match_set: MatchSetContract = Field(alias="matchSet")
    match_date: AwareDatetime = Field(alias="matchDateUtc")
    match_time: int = Field(alias="time")
    additional_time: int = Field(alias="additionalTime")

    @field_validator("match_date", mode="before")
    @classmethod
    def match_date_must_end_in_z(cls, value: object) -> object:
        if isinstance(value, str) and not value.endswith("Z"):
            raise ValueError("matchDateUtc must end in Z")
        return value

    @model_validator(mode="after")
    def teams_and_winner_agree(self) -> Self:
        if self.home_team.team_id == self.away_team.team_id:
            raise ValueError("home and away must be different teams")

        draw = self.home_score_push == self.away_score_push
        if draw:
            if self.win_team_id is not None:
                raise ValueError("a draw must have winTeamId unset")
            return self

        winner_id = (
            self.home_team.team_id
            if self.home_score_push > self.away_score_push
            else self.away_team.team_id
        )
        if self.win_team_id != winner_id:
            raise ValueError("winTeamId must be the team that scored more")
        return self


def get_matches(matches_dir: Path) -> list[dict]:
    matches: list[dict] = []
    for file in sorted(matches_dir.glob("*.json")):
        with file.open("r") as f:
            payload = json.load(f)
        matches.extend(payload["matches"])
    return matches


def plant_records(matches: list[dict]) -> dict[str, dict]:
    first = matches[0]
    first_win = next(
        match
        for match in matches
        if match["matchId"] == "spl::Football_Match::ff995f1389cb4c93b0e5513a46ef2ec3"
    )
    planted = {
        label: copy.deepcopy(first) for label in ("p1", "p2", "p3", "p4", "p5", "p6")
    }
    planted["p7"] = copy.deepcopy(first_win)
    planted["p8"] = copy.deepcopy(first)

    planted["p1"]["winTeamId"] = "spl::Football_Team::2c0af0b9b0f0474f8742b5427dc351c6"
    planted["p2"]["away"] = copy.deepcopy(first["home"])
    planted["p3"]["additionalTime"] = "13+2"
    planted["p4"]["homeScorePush"] = -1
    planted["p5"]["matchDateUtc"] = "2025-08-28T16:05:00"
    del planted["p6"]["matchId"]
    planted["p7"]["winTeamId"] = "spl::Football_Team::02f22b11aa604566a1858f96addb669c"
    planted["p8"]["attendance"] = 21450
    return planted


def is_valid(record: dict) -> bool:
    try:
        MatchContract.model_validate(record)
    except ValidationError:
        return False
    return True


def count_valid(records: list[dict]) -> tuple[int, int]:
    valid = sum(1 for record in records if is_valid(record))
    return valid, len(records) - valid


def classify_planted(planted: dict[str, dict]) -> tuple[list[str], list[str]]:
    accepted = [label for label, record in planted.items() if is_valid(record)]
    rejected = [label for label in planted if label not in accepted]
    return accepted, rejected


if __name__ == "__main__":
    matches = get_matches(matches_dir=Path(DIR))
    planted = plant_records(matches)
    landed_valid, landed_rejected = count_valid(matches)
    accepted, rejected = classify_planted(planted)
    print(f"landed: {landed_valid} valid, {landed_rejected} rejected")
    print(f"planted: {len(accepted)} valid, {len(rejected)} rejected")
    print(f"rejected: {' '.join(rejected)}")
    print(f"accepted: {' '.join(accepted)}")
