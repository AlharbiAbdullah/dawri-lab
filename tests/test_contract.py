import copy
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from dawri import contracts, load

FIXTURES = Path(__file__).parent / "fixtures"
SEASON_ID = "3677a75aaa514e43b2840e7fa367c91d"
WIN = "spl::Football_Match::cb556acbac334114887ef91fcb725e0c"
DRAW = "spl::Football_Match::fed56d6495e048d6aa008ecec45017b2"


def recorded_matches() -> list[dict]:
    path = FIXTURES / "recorded" / "matches" / f"{SEASON_ID}.json"
    return json.loads(path.read_bytes())["matches"]


def recorded_match(match_id: str) -> dict:
    return next(m for m in recorded_matches() if m["matchId"] == match_id)


def winner_is_the_loser(match: dict) -> None:
    match["winTeamId"] = match["home"]["teamId"]


def same_team_twice(match: dict) -> None:
    match["away"] = copy.deepcopy(match["home"])


def time_as_text(match: dict) -> None:
    match["additionalTime"] = "13+2"


def negative_score(match: dict) -> None:
    match["homeScorePush"] = -1


def no_z(match: dict) -> None:
    match["matchDateUtc"] = match["matchDateUtc"].removesuffix("Z")


def no_id(match: dict) -> None:
    del match["matchId"]


def draw_with_winner(match: dict) -> None:
    match["winTeamId"] = match["home"]["teamId"]


def extra_field(match: dict) -> None:
    match["attendance"] = 21450


def unchanged(match: dict) -> None:
    pass


CASES: list[tuple[str, str, Callable[[dict], None], bool]] = [
    ("recorded win", WIN, unchanged, True),
    ("recorded draw", DRAW, unchanged, True),
    ("winner is the loser", WIN, winner_is_the_loser, False),
    ("same team twice", WIN, same_team_twice, False),
    ("time as text", WIN, time_as_text, False),
    ("negative score", WIN, negative_score, False),
    ("no Z", WIN, no_z, False),
    ("no id", WIN, no_id, False),
    ("draw with winner", DRAW, draw_with_winner, False),
    ("extra field", WIN, extra_field, True),
]


@pytest.mark.parametrize(
    ("base", "change", "accepted"),
    [case[1:] for case in CASES],
    ids=[case[0].replace(" ", "-") for case in CASES],
)
def test_contract(base: str, change: Callable[[dict], None], accepted: bool) -> None:
    match = copy.deepcopy(recorded_match(base))
    change(match)
    assert contracts.is_valid(match) is accepted


def test_classify_recorded_matches() -> None:
    _, valid, rejected, skipped = load.classify_matches(recorded_matches())
    assert (valid, rejected, skipped) == (2, 0, 1)
