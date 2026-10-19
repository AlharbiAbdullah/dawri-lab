"""Serve Dawri's facts over HTTP."""

import hashlib
import json
from collections.abc import Callable, Coroutine, Iterator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

import duckdb
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.routing import APIRoute
from pydantic import BaseModel

from dawri import config, semantic, ui
from dawri.api_models import SeasonSummary, Standing, TeamMetrics
from dawri.ui_models import PageSpec


class ConditionalRoute(APIRoute):
    """Apply conditional GET after FastAPI validates and serializes the response."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """Keep FastAPI's coroutine send/yield types in the handler signature."""
        original = super().get_route_handler()
        if not self.path.startswith(("/seasons", "/matches")):
            return original

        async def conditional(request: Request) -> Response:
            response = await original(request)
            if response.status_code != 200:
                return response
            etag = f'"{hashlib.sha256(response.body).hexdigest()}"'
            condition = ",".join(request.headers.getlist("if-none-match"))
            candidates = (
                value.strip().removeprefix("W/") for value in condition.split(",")
            )
            if condition.strip() == "*" or etag in candidates:
                return Response(status_code=304, headers={"ETag": etag})
            response.headers["ETag"] = etag
            return response

        return conditional


app = FastAPI(title="Dawri")
app.router.route_class = ConditionalRoute


class Health(BaseModel, strict=True):
    status: Literal["ok"]


class MatchTeam(BaseModel, strict=True):
    team_name: str
    score: int | None


class Goal(BaseModel, strict=True):
    minute: int
    additional_minutes: int
    side: Literal["home", "away"]
    team_name: str
    player_name: str | None
    goal_type: Literal["goal", "penalty-goal", "own-goal"]


class MatchDetail(BaseModel, strict=True):
    match_id: str
    season: str
    kickoff_utc: datetime
    status: str
    stadium: str | None
    home: MatchTeam
    away: MatchTeam
    goals: list[Goal]


def database() -> Iterator[duckdb.DuckDBPyConnection]:
    """Read one published Parquet generation for this request, then close it."""
    serving = config.SERVING_DIR.resolve(strict=True)
    with semantic.connect_serving(serving) as con:
        yield con


Connection = Annotated[duckdb.DuckDBPyConnection, Depends(database)]


def season_name(season: str) -> str:
    """Translate a URL season to its config name, or return the shared 404."""
    name = season.replace("-", "/")
    if name not in config.SEASONS:
        raise HTTPException(status_code=404, detail=f"unknown season: {season}")
    return name


@app.get("/health")
def health() -> Health:
    """Report that the server is running without querying the database."""
    return Health(status="ok")


@app.get("/seasons/{season}/view")
def season_view(season: str, con: Connection) -> PageSpec:
    """Describe a season page using one published generation."""
    name = season_name(season)
    summary = next(summary for summary in seasons(con) if summary.season == name)
    return ui.season_page(
        summary, standings(season, con), metrics(season, con, ui.METRICS)
    )


@app.get("/seasons")
def seasons(con: Connection) -> list[SeasonSummary]:
    """List configured seasons with their finished and upcoming match counts."""
    rows = con.execute(
        """
        SELECT season_id,
               count(*) FILTER (WHERE status = 'FINISHED'),
               count(*) FILTER (WHERE status = 'UPCOMING')
        FROM staging.stg_matches
        GROUP BY season_id
        """
    ).fetchall()
    counts = {season_id: (finished, upcoming) for season_id, finished, upcoming in rows}
    return [
        SeasonSummary(
            season=name,
            season_id=season_id,
            finished=counts.get(season_id, (0, 0))[0],
            upcoming=counts.get(season_id, (0, 0))[1],
        )
        for name, season_id in config.SEASONS.items()
    ]


@app.get("/seasons/{season}/standings")
def standings(
    season: str,
    con: Connection,
    standings_type: Annotated[
        Literal["table", "home", "away"], Query(alias="type")
    ] = "table",
) -> list[Standing]:
    """Return one season's existing standings mart in rank order."""
    season_id = config.SEASONS[season_name(season)]
    result = con.execute(
        """
        SELECT rank, team_name, played, won, drawn, lost,
               goals_for, goals_against, goal_difference, points
        FROM marts.mart_standings
        WHERE season_id = ? AND type = ?
        ORDER BY rank
        """,
        [season_id, standings_type],
    )
    columns = [column[0] for column in result.description]
    return [
        Standing.model_validate(dict(zip(columns, row, strict=True)))
        for row in result.fetchall()
    ]


@app.get("/seasons/{season}/metrics")
def metrics(
    season: str,
    con: Connection,
    metric: Annotated[list[str], Query(min_length=1)],
) -> list[TeamMetrics]:
    """Ask the same semantic reader as the CLI, preserving requested metric order."""
    name = season_name(season)
    try:
        columns, rows = semantic.team_metrics(con, name, metric)
    except semantic.UnknownMetric as exc:
        known = ", ".join(
            name
            for (name,) in con.execute(
                "SELECT name FROM ossie_metrics() ORDER BY name"
            ).fetchall()
        )
        raise HTTPException(
            status_code=422, detail=f"unknown metric: {exc}. Known: {known}"
        ) from None
    answers = []
    for row in rows:
        values = {
            column: round(value, 2) if isinstance(value, float) else value
            for column, value in zip(columns, row, strict=True)
        }
        answers.append(TeamMetrics.model_validate(values))
    return answers


def match_goals(con: duckdb.DuckDBPyConnection, match_key: str) -> list[Goal]:
    """Read goals in clock order, naming the credited team and optional scorer."""
    result = con.execute(
        """
        SELECT g.minute, g.additional_minutes, g.scoring_side AS side,
               t.team_name, l.player_name, g.goal_type
        FROM marts.fct_goals g
        JOIN marts.dim_teams t ON t.team_id = g.scoring_team_id
        LEFT JOIN staging.stg_lineups l
          ON l.season_id = g.season_id AND l.match_id = g.match_id
         AND l.player_id = g.player_id
        WHERE g.match_id = ?
        ORDER BY g.minute, g.additional_minutes
        """,
        [match_key],
    )
    columns = [column[0] for column in result.description]
    return [
        Goal.model_validate(dict(zip(columns, row, strict=True)))
        for row in result.fetchall()
    ]


@app.get("/matches/{match_id}")
def match_detail(
    match_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")],
    con: Connection,
) -> MatchDetail:
    """Return a match's facts, with scores and goals only for finished matches."""
    match_key = f"spl::Football_Match::{match_id}"
    row = con.execute(
        """
        SELECT m.season_id, m.kickoff_utc, m.status, m.stadium_name,
               h.team_name, m.home_score, a.team_name, m.away_score
        FROM staging.stg_matches m
        JOIN marts.dim_teams h ON h.team_id = m.home_team_id
        JOIN marts.dim_teams a ON a.team_id = m.away_team_id
        WHERE m.match_id = ?
        """,
        [match_key],
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown match: {match_id}")
    season_id, kickoff, status, stadium, home, home_score, away, away_score = row
    name = next(name for name, sid in config.SEASONS.items() if sid == season_id)
    finished = status == "FINISHED"
    return MatchDetail(
        match_id=match_id,
        season=name,
        kickoff_utc=kickoff.replace(tzinfo=UTC),
        status=status,
        stadium=stadium,
        home=MatchTeam(team_name=home, score=home_score if finished else None),
        away=MatchTeam(team_name=away, score=away_score if finished else None),
        goals=match_goals(con, match_key) if finished else [],
    )


def write_openapi() -> None:
    """Write the API contract as stable, readable JSON for review."""
    path = config.ROOT / "docs" / "openapi.json"
    path.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(f"Wrote {path.relative_to(config.ROOT)}")
