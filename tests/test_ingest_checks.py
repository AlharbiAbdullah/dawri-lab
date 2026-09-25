import json
from collections.abc import Callable
from pathlib import Path

import pytest

from dawri import ingest

FIXTURES = Path(__file__).parent / "fixtures"
SEASON_ID = "3677a75aaa514e43b2840e7fa367c91d"
PLAYED = "cb556acbac334114887ef91fcb725e0c"

CHECKS: dict[str, Callable[[dict], bool]] = {
    "teamstats": ingest.has_teamstats_data,
    "playerstats": ingest.has_playerstats_data,
    "lineups": ingest.has_lineups_data,
    "matchfacts": ingest.has_matchfacts_data,
    "feed": ingest.has_feed_data,
}


def test_cleaned_match_id() -> None:
    match = {"matchId": f"spl::Football_Match::{PLAYED}"}
    assert ingest.cleaned_match_id(match) == PLAYED


@pytest.mark.parametrize(
    ("family", "path", "expected"),
    [
        (family, FIXTURES / "recorded" / family / SEASON_ID / f"{PLAYED}.json", True)
        for family in CHECKS
    ]
    + [(family, FIXTURES / "unplayed" / f"{family}.json", False) for family in CHECKS],
    ids=[f"{family}-played" for family in CHECKS]
    + [f"{family}-unplayed" for family in CHECKS],
)
def test_has_data(family: str, path: Path, expected: bool) -> None:
    payload = json.loads(path.read_bytes())
    assert CHECKS[family](payload) is expected
