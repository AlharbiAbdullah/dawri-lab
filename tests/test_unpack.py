import json
from pathlib import Path

import pytest

from dawri import load

RECORDED = Path(__file__).parent / "fixtures" / "recorded"

ROWS = {
    "matches": 3,
    "matchdays": 34,
    "teams": 18,
    "standings": 54,
    "teamstats": 484,
    "playerstats": 8946,
    "lineups": 80,
    "lineup_events": 37,
    "match_facts": 2,
    "match_officials": 12,
    "feed_events": 134,
}


@pytest.mark.parametrize(("table_name", "expected"), ROWS.items())
def test_unpack_rows(table_name: str, expected: int) -> None:
    family_dir = RECORDED / load.FAMILY_DIRS.get(table_name, table_name)
    rows = 0
    for path in sorted(family_dir.rglob("*.json")):
        payload = json.loads(path.read_bytes())
        rows += len(load.unpack_json_pattern(table_name, payload))
    assert rows == expected
