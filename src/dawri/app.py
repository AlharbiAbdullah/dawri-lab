"""Dawri on localhost: the league for a season, or one team's page.

Every number comes through semantic.py from the Ossie document, read from the
serving copy, so the page holds no SQL and the build can run beside it.
"""

import streamlit as st

from dawri import semantic
from dawri.config import LIVE_SEASON, SEASONS

ALL_TEAMS = "All teams"
TEAM_PAGE = [
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
SPLIT = ["matches_played", "points", "goal_difference", "xg_for", "xg_against"]
VENUE = "fct_team_matches.venue"
VENUES = ["home", "away"]


def table(header: list[str], rows: list[tuple]) -> list[dict]:
    """Rows as dawri metrics prints them: floats at two decimals."""
    return [
        dict(zip(header, map(semantic.format_value, row), strict=True)) for row in rows
    ]


st.title("Dawri")
seasons = list(SEASONS)
season = st.selectbox("Season", seasons, index=seasons.index(LIVE_SEASON))

# Opened per rerun: about 25 ms after the first, and it holds no lock.
con = semantic.connect_serving()
try:
    header, league = semantic.team_metrics(con, season)
    team = st.selectbox("Team", [ALL_TEAMS, *sorted(row[0] for row in league)])
    if team == ALL_TEAMS:
        st.dataframe(table(header, league), hide_index=True)
    else:
        st.subheader(f"{team}, {season}")
        _, (row,) = semantic.team_metrics(con, season, TEAM_PAGE, team=team)
        values = map(semantic.format_value, row[1:])
        st.dataframe(
            [{"metric": m, "value": v} for m, v in zip(TEAM_PAGE, values, strict=True)],
            hide_index=True,
        )
        header, split = semantic.team_metrics(con, season, SPLIT, team=team, by=[VENUE])
        split.sort(key=lambda r: VENUES.index(r[1]))
        st.dataframe(table(header[1:], [r[1:] for r in split]), hide_index=True)
finally:
    con.close()
