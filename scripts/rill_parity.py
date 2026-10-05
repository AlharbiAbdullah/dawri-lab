"""Rill parity: the team_metrics API against dawri metrics, all metrics, by season."""

import sys

import duckdb
import httpx

from dawri.config import SEASONS
from dawri.semantic import connect, format_value, team_metrics

API = "http://localhost:9009/v1/instances/default/api/team_metrics"


def rill_rows() -> list[dict]:
    try:
        response = httpx.get(API, timeout=60)
    except httpx.ConnectError:
        print(
            "rill parity failed: Rill is not running (rill start rill)", file=sys.stderr
        )
        sys.exit(1)
    response.raise_for_status()
    return response.json()


def metric_names(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute("SELECT name FROM ossie_metrics() ORDER BY name").fetchall()
    return [name for (name,) in rows]


def compare(season: str, ours: dict, theirs: dict) -> int:
    teams = sorted(ours.keys() | theirs.keys())
    differences = 0
    for team in teams:
        if ours.get(team) != theirs.get(team):
            differences += 1
            print(
                f"  {team}: dawri={ours.get(team)} rill={theirs.get(team)}",
                file=sys.stderr,
            )
    print(f"rill parity {season}: {len(teams)} teams, {differences} differences")
    return differences


def main() -> int:
    rows = rill_rows()
    con = connect()
    try:
        metrics = metric_names(con)
        differences = 0
        for season, season_id in SEASONS.items():
            _, dawri = team_metrics(con, season, metrics)
            ours = {row[0]: [format_value(v) for v in row[1:]] for row in dawri}
            theirs = {
                row["team_name"]: [format_value(row[m]) for m in metrics]
                for row in rows
                if row["season_id"] == season_id
            }
            differences += compare(season, ours, theirs)
    finally:
        con.close()
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
