"""Build fixture briefs from one published generation and the semantic reader."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import typer

from dawri import config, prose, semantic

RIYADH = ZoneInfo("Asia/Riyadh")
ROWS = (
    "Position",
    "Points",
    "Played",
    "W-D-L",
    "Goals",
    "xG for per match",
    "xG against per match",
    "Last 5",
)


@dataclass
class Fixture:
    home: str
    away: str
    kickoff: str
    stadium: str
    home_facts: list[str]
    away_facts: list[str]
    meetings: str

    def facts(self) -> dict:
        """Only the facts printed in this fixture block go to the model."""
        return {
            "home": self.home,
            "away": self.away,
            "kickoff": self.kickoff,
            "stadium": self.stadium,
            "home_facts": dict(zip(ROWS, self.home_facts, strict=True)),
            "away_facts": dict(zip(ROWS, self.away_facts, strict=True)),
            "head_to_head": self.meetings,
        }

    def markdown(self, paragraph: str = "") -> str:
        lines = [f"## {self.home} v {self.away}"]
        if paragraph:
            lines.extend([paragraph, ""])
        lines.extend(
            [
                f"{self.kickoff}, {self.stadium}",
                "",
                f"|  | {self.home} | {self.away} |",
                "|---|---|---|",
            ]
        )
        lines.extend(
            f"| {label} | {home} | {away} |"
            for label, home, away in zip(
                ROWS, self.home_facts, self.away_facts, strict=True
            )
        )
        return "\n".join([*lines, "", self.meetings])


def local_time(kickoff: datetime) -> datetime:
    return kickoff.replace(tzinfo=UTC).astimezone(RIYADH)


def team_facts(con: duckdb.DuckDBPyConnection, season: str) -> dict[str, list[str]]:
    """Sporting rank stays in dbt; ratio arithmetic stays in Ossie."""
    standings = con.execute(
        """
        SELECT team_id, team_name, shared_rank,
               count(*) OVER (PARTITION BY shared_rank), points, played,
               won, drawn, lost, goals_for, goals_against
        FROM marts.mart_standings WHERE season_id = ? AND type = 'table'
        """,
        [config.SEASONS[season]],
    ).fetchall()
    _, metrics = semantic.team_metrics(
        con, season, ["xg_for_per_match", "xg_against_per_match"]
    )
    ratios = {name: (xgf, xga) for name, xgf, xga in metrics}
    facts = {}
    for tid, name, rank, tied, pts, played, won, drawn, lost, gf, ga in standings:
        form = con.execute(
            """
            SELECT result FROM marts.fct_team_matches
            WHERE season_id = ? AND team_id = ? ORDER BY kickoff_utc DESC, match_id
            LIMIT 5
            """,
            [config.SEASONS[season], tid],
        ).fetchall()
        xgf, xga = ratios[name]
        facts[tid] = [
            f"{'=' if tied > 1 else ''}{rank}",
            str(pts),
            str(played),
            f"{won}-{drawn}-{lost}",
            f"{gf}-{ga}",
            "-" if xgf is None else f"{xgf:.2f}",
            "-" if xga is None else f"{xga:.2f}",
            " ".join(result for (result,) in form),
        ]
    return facts


def head_to_head(con: duckdb.DuckDBPyConnection, home: str, away: str) -> str:
    rows = con.execute(
        """
        SELECT m.kickoff_utc, h.team_name, m.goals_for, m.goals_against, a.team_name,
               m.team_id
        FROM marts.fct_team_matches m
        JOIN marts.dim_teams h ON h.team_id = m.team_id
        JOIN marts.dim_teams a ON a.team_id = m.opponent_id
        WHERE m.venue = 'home' AND
          ((m.team_id = ? AND m.opponent_id = ?) OR
           (m.team_id = ? AND m.opponent_id = ?))
        ORDER BY m.kickoff_utc, m.match_id
        """,
        [home, away, away, home],
    ).fetchall()
    if not rows:
        return "Head to head in the data: none."
    names = dict(
        con.execute("SELECT team_id, team_name FROM marts.dim_teams").fetchall()
    )
    wins = sum((hg > ag if hid == home else ag > hg) for _, _, hg, ag, _, hid in rows)
    draws = sum(hg == ag for _, _, hg, ag, _, _ in rows)
    line = (
        f"Head to head in the data: {len(rows)} matches. {names[home]} "
        f"{wins} wins, {draws} draws, {names[away]} {len(rows) - wins - draws} wins."
    )
    meetings = [
        f"- {local_time(day):%Y-%m-%d} {h} {hg}-{ag} {a}"
        for day, h, hg, ag, a, _ in rows
    ]
    return "\n".join([line, *meetings])


def fixture_blocks(
    con: duckdb.DuckDBPyConnection, rows: list[tuple], facts: dict[str, list[str]]
) -> list[Fixture]:
    return [
        Fixture(
            h,
            a,
            f"{local_time(kick):%a %Y-%m-%d %H:%M}",
            stadium or "-",
            facts.get(hid, ["-"] * len(ROWS)),
            facts.get(aid, ["-"] * len(ROWS)),
            head_to_head(con, hid, aid),
        )
        for kick, stadium, hid, aid, h, a in rows
    ]


def next_brief(
    con: duckdb.DuckDBPyConnection, season: str, with_prose: bool = False
) -> tuple[str, str] | None:
    next_day = con.execute(
        """
        SELECT matchday_id FROM staging.stg_matches
        WHERE season_id = ? AND status = 'UPCOMING'
        ORDER BY kickoff_utc, match_id LIMIT 1
        """,
        [config.SEASONS[season]],
    ).fetchone()
    if next_day is None:
        return None
    day_id = next_day[0]
    name, short = con.execute(
        """
        SELECT name, short_name FROM staging.stg_matchdays
        WHERE season_id = ? AND matchday_id = ?
        """,
        [config.SEASONS[season], day_id],
    ).fetchall()[0]
    return render_brief(con, season, day_id, name, short, with_prose)


def render_brief(
    con: duckdb.DuckDBPyConnection,
    season: str,
    day_id: str,
    name: str,
    short: str,
    with_prose: bool,
) -> tuple[str, str]:
    rows = con.execute(
        """
        SELECT m.kickoff_utc, m.stadium_name, m.home_team_id, m.away_team_id,
               h.team_name, a.team_name
        FROM staging.stg_matches m
        JOIN marts.dim_teams h ON h.team_id = m.home_team_id
        JOIN marts.dim_teams a ON a.team_id = m.away_team_id
        WHERE m.season_id = ? AND m.matchday_id = ?
        ORDER BY m.kickoff_utc, h.team_name
        """,
        [config.SEASONS[season], day_id],
    ).fetchall()
    facts = team_facts(con, season)
    fixtures = fixture_blocks(con, rows, facts)
    finished = con.execute(
        """SELECT count(*) FROM staging.stg_matches
        WHERE season_id = ? AND status = 'FINISHED'""",
        [config.SEASONS[season]],
    ).fetchall()[0][0]
    header = (
        f"# {name}, {season}\n\n{len(rows)} matches, "
        f"{local_time(rows[0][0]):%a %Y-%m-%d} to "
        f"{local_time(rows[-1][0]):%a %Y-%m-%d}. Facts from {finished} "
        f"finished matches of {season}. Times are Riyadh (UTC+3)."
    )
    paragraphs = prose.paragraphs(fixtures) if with_prose else [""] * len(fixtures)
    blocks = [f.markdown(p) for f, p in zip(fixtures, paragraphs, strict=True)]
    action_id = f"brief-{season.replace('/', '-')}-{short.lower().replace(' ', '-')}"
    return action_id, "\n\n".join([header, *blocks]) + "\n"


def write_action(action_id: str, body: str) -> Path:
    folder = config.DATA_DIR / "outbox"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{action_id}.md"
    pending = path.with_suffix(".md.tmp")
    pending.write_text(body)
    pending.replace(path)
    return path


def write_brief(season: str, prose: bool = False) -> None:
    with semantic.connect_serving(config.SERVING_DIR.resolve(strict=True)) as con:
        result = next_brief(con, season, prose)
    if result is None:
        typer.echo(f"no upcoming matchday in {season}", err=True)
        raise typer.Exit(1)
    print(write_action(*result))
