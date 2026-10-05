from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from dawri import semantic

APP = Path(__file__).parents[1] / "src" / "dawri" / "app.py"
SEASON_ROWS = {
    "2026/2027": [("Team A", 18, 18, 25.0758, 8.2719), ("Team B", 9, -2, 7.5, 9.1)],
    "2025/2026": [("Team C", 86, 63, 64.3775, 21.95), ("Team A", 84, 58, 68.05, 19.7)],
}


class FakeConnection:
    def close(self) -> None:
        pass


def fake_team_metrics(
    con: object,
    season: str,
    metrics: list[str] | None = None,
    team: str | None = None,
    by: list[str] | None = None,
) -> tuple[list[str], list[tuple]]:
    """The reader's contract with made-up numbers: one value per metric asked."""
    if team is None:
        header = ["team_name", "points", "goal_difference", "xg_for", "xg_against"]
        return header, SEASON_ROWS[season]
    metrics = metrics or []
    values = tuple(float(i) + 0.5 if i % 2 else i for i in range(len(metrics)))
    if by:
        rows = [(team, "away", *values), (team, "home", *values)]
        return ["team_name", "venue", *metrics], rows
    return ["team_name", *metrics], [(team, *values)]


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setattr(semantic, "connect_serving", lambda: FakeConnection())
    monkeypatch.setattr(semantic, "team_metrics", fake_team_metrics)
    at = AppTest.from_file(str(APP)).run()
    assert not at.exception
    return at


def test_league_table_default_season(app: AppTest) -> None:
    assert app.title[0].value == "Dawri"
    assert app.selectbox[0].value == "2026/2027"
    table = app.dataframe[0].value
    assert list(table.columns) == [
        "team_name",
        "points",
        "goal_difference",
        "xg_for",
        "xg_against",
    ]
    assert table.iloc[0].to_list() == ["Team A", "18", "18", "25.08", "8.27"]


def test_season_switch(app: AppTest) -> None:
    app.selectbox[0].select("2025/2026").run()
    assert app.dataframe[0].value["team_name"].to_list() == ["Team C", "Team A"]
    assert app.selectbox[1].options == ["All teams", "Team A", "Team C"]


def test_team_page_replaces_league_table(app: AppTest) -> None:
    app.selectbox[1].select("Team A").run()
    assert app.subheader[0].value == "Team A, 2026/2027"
    assert len(app.dataframe) == 2
    assert "metric" in app.dataframe[0].value.columns
    assert app.dataframe[1].value["venue"].to_list() == ["home", "away"]


def test_team_page_order_and_decimals(app: AppTest) -> None:
    app.selectbox[1].select("Team A").run()
    page = app.dataframe[0].value
    assert page["metric"].to_list() == [
        "matches_played",
        "points",
        "points_per_match",
        "goals_for",
        "goals_against",
        "goal_difference",
        "xg_for",
        "xg_against",
        "xg_difference",
        "shots",
        "shots_on_target",
    ]
    assert page["value"].to_list()[:3] == ["0", "1.50", "2"]
