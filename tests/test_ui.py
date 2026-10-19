import pytest

from dawri.api import SeasonSummary
from dawri.ui import season_header


@pytest.mark.parametrize(
    ("season", "season_id", "finished", "upcoming", "content"),
    [
        (
            "2026/2027",
            "3677a75aaa514e43b2840e7fa367c91d",
            2,
            1,
            "2026/2027: 2 finished, 1 upcoming",
        ),
        (
            "2025/2026",
            "0de9cda0d297418699a8357a8825d46c",
            0,
            0,
            "2025/2026: 0 finished, 0 upcoming",
        ),
    ],
)
def test_season_header(
    season: str, season_id: str, finished: int, upcoming: int, content: str
) -> None:
    summary = SeasonSummary(
        season=season, season_id=season_id, finished=finished, upcoming=upcoming
    )
    original = summary.model_copy(deep=True)

    assert season_header(summary) == {
        "root": "summary",
        "elements": {
            "summary": {
                "type": "Text",
                "props": {"content": content},
                "children": [],
            }
        },
    }
    assert summary == original
