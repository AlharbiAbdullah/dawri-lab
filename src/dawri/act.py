"""Deliver new facts once, with a durable ledger separate from the warehouse."""

import fcntl
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

import duckdb
import httpx
import typer

from dawri import brief, config, semantic
from dawri.api import match_detail


@contextmanager
def ledger() -> Iterator[sqlite3.Connection]:
    """Serialize runs; each successful delivery gets its own committed mark."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (config.DATA_DIR / "actions.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        con = sqlite3.connect(config.DATA_DIR / "actions.sqlite3")
        try:
            con.execute("CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY)")
            con.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY)")
            con.execute(
                "CREATE TABLE IF NOT EXISTS pending "
                "(id TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )
            con.commit()
            yield con
        finally:
            con.close()


def finished_matches(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [
        mid.rsplit("::", 1)[-1]
        for (mid,) in con.execute(
            """
        SELECT match_id FROM staging.stg_matches
        WHERE season_id = ? AND status = 'FINISHED'
        ORDER BY kickoff_utc, match_id
        """,
            [config.SEASONS[config.LIVE_SEASON]],
        ).fetchall()
    ]


def result_note(con: duckdb.DuckDBPyConnection, match_id: str) -> str:
    match = match_detail(match_id, con)
    day = con.execute(
        """
        SELECT d.name FROM staging.stg_matches m
        JOIN staging.stg_matchdays d USING (season_id, matchday_id)
        WHERE m.match_id = ?
        """,
        [f"spl::Football_Match::{match_id}"],
    ).fetchall()[0][0]
    goals = []
    for goal in match.goals:
        minute = str(goal.minute)
        if goal.additional_minutes:
            minute += f"+{goal.additional_minutes}"
        own = " (og)" if goal.goal_type == "own-goal" else ""
        goals.append(
            f"{minute}' {goal.player_name or 'Unknown scorer'} ({goal.team_name}){own}"
        )
    _, metrics = semantic.team_metrics(con, match.season, ["points", "matches_played"])
    totals = {name: (points, played) for name, points, played in metrics}
    standings = []
    for team in (match.home, match.away):
        points, played = totals[team.team_name]
        standings.append(
            f"{team.team_name} now {points} "
            f"{'pt' if points == 1 else 'pts'} from {played} "
            f"{'match' if played == 1 else 'matches'}."
        )
    return (
        f"# {match.home.team_name} {match.home.score}-{match.away.score} "
        f"{match.away.team_name}\n{match.season}, {day}, "
        f"{brief.local_time(match.kickoff_utc):%a %Y-%m-%d %H:%M} Riyadh, "
        f"{match.stadium or '-'}\n\nGoals: {', '.join(goals) or 'none'}.\n"
        f"{' '.join(standings)}\n"
    )


def deliver(action_id: str, body: str) -> bool:
    brief.write_action(action_id, body)
    url = os.getenv("DAWRI_NOTIFY_URL")
    if url:
        try:
            response = httpx.post(
                url,
                content=body.encode(),
                timeout=30,
                headers={
                    "Title": body.splitlines()[0].removeprefix("# "),
                    "Idempotency-Key": action_id,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            typer.echo(f"failed {action_id}: {exc}", err=True)
            return False
    return True


def perform(con: duckdb.DuckDBPyConnection, state: sqlite3.Connection) -> None:
    done = {row[0] for row in state.execute("SELECT id FROM actions")}
    actions = [
        (f"result-{mid}", result_note(con, mid))
        for mid in finished_matches(con)
        if f"result-{mid}" not in done
    ]
    upcoming = brief.next_brief(con, config.LIVE_SEASON)
    if upcoming and upcoming[0] not in done:
        actions.append(upcoming)
    state.executemany("INSERT OR IGNORE INTO pending VALUES (?, ?)", actions)
    state.commit()
    pending = state.execute(
        "SELECT id, body FROM pending ORDER BY id LIKE 'brief-%', rowid"
    ).fetchall()
    sent = failed = 0
    for action_id, body in pending:
        if deliver(action_id, body):
            state.execute("INSERT INTO actions VALUES (?)", [action_id])
            state.execute("DELETE FROM pending WHERE id = ?", [action_id])
            state.commit()
            print(f"sent: {action_id}")
            sent += 1
        else:
            failed += 1
    print(f"ledger: {sent} sent, {failed} failed")
    if failed:
        raise typer.Exit(1)


def run(initialize: bool = False) -> None:
    with ledger() as state:
        if (
            not initialize
            and not state.execute(
                "SELECT 1 FROM state WHERE key = 'initialized'"
            ).fetchone()
        ):
            typer.echo("run dawri act --init first", err=True)
            raise typer.Exit(1)
        with semantic.connect_serving(config.SERVING_DIR.resolve(strict=True)) as con:
            if initialize:
                matches = finished_matches(con)
                state.executemany(
                    "INSERT OR IGNORE INTO actions VALUES (?)",
                    [(f"result-{mid}",) for mid in matches],
                )
                state.execute("INSERT OR IGNORE INTO state VALUES ('initialized')")
                state.execute(
                    "DELETE FROM pending WHERE id IN (SELECT id FROM actions)"
                )
                state.commit()
                print(f"ledger: {len(matches)} results marked done, 0 sent")
            else:
                perform(con, state)
