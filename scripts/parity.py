"""Parity: dawri metrics (DuckDB + Ossie) against MetricFlow, for the live season."""

import csv
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dawri.config import DBT_DIR, LIVE_SEASON, SEASONS
from dawri.semantic import DEFAULT_METRICS, connect, format_value, team_metrics

MF = "dbt-metricflow[dbt-duckdb]==0.15.0"


def from_text(text: str) -> str:
    """MetricFlow's CSV holds text; give it the same shape as dawri metrics."""
    try:
        return format_value(int(text))
    except ValueError:
        return format_value(float(text))


def dawri_rows(season: str) -> dict[str, list[str]]:
    con = connect()
    try:
        _, rows = team_metrics(con, season)
    finally:
        con.close()
    return {row[0]: [format_value(v) for v in row[1:]] for row in rows}


def metricflow_rows(season: str) -> dict[str, list[str]]:
    uvx = shutil.which("uvx")
    if uvx is None:
        print("parity failed: uvx not found on PATH", file=sys.stderr)
        sys.exit(1)
    where = f"{{{{ Dimension('team_match__season_id') }}}} = '{SEASONS[season]}'"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "mf.csv"
        result = subprocess.run(  # noqa: S603
            [
                uvx,
                "--from",
                MF,
                "mf",
                "query",
                "--metrics",
                ",".join(DEFAULT_METRICS),
                "--group-by",
                "team__team_name",
                "--where",
                where,
                "--csv",
                str(out),
            ],
            cwd=DBT_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout + result.stderr, file=sys.stderr)
            sys.exit(1)
        with out.open() as f:
            return {
                row["team__team_name"]: [from_text(row[m]) for m in DEFAULT_METRICS]
                for row in csv.DictReader(f)
            }


def main() -> int:
    season = LIVE_SEASON
    ours = dawri_rows(season)  # first, so its read-only connection is closed
    theirs = metricflow_rows(season)  # before MetricFlow opens the same file
    teams = sorted(ours.keys() | theirs.keys())

    differences = 0
    for team in teams:
        if ours.get(team) != theirs.get(team):
            differences += 1
            print(
                f"  {team}: dawri={ours.get(team)} metricflow={theirs.get(team)}",
                file=sys.stderr,
            )

    print(f"parity {season}: {len(teams)} teams, {differences} differences")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
