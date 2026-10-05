"""Evidence parity: the Parquet the build ships against dawri metrics, by season."""

import sys
from pathlib import Path

import duckdb

from dawri.config import ROOT, SEASONS
from dawri.semantic import connect, format_value, team_metrics

# npm run build copies each source query to a folder named by a hash.
SHIPPED = ROOT / "evidence" / "build" / "data" / "dawri" / "team_metrics"


def shipped_file() -> Path:
    files = sorted(SHIPPED.glob("*/team_metrics.parquet"))
    if len(files) != 1:
        print(
            f"evidence parity failed: {len(files)} built team_metrics files"
            " (run npm run sources && npm run build in evidence/)",
            file=sys.stderr,
        )
        sys.exit(1)
    return files[0]


def as_dawri(value: object, like: object) -> str:
    """Integer sums ship as DOUBLE (86.0); match the type dawri metrics returns."""
    if isinstance(like, int) and isinstance(value, float) and value.is_integer():
        value = int(value)
    return format_value(value)


def compare(season: str, ours: dict, theirs: dict) -> int:
    teams = sorted(ours.keys() | theirs.keys())
    differences = 0
    for team in teams:
        if ours.get(team) != theirs.get(team):
            differences += 1
            print(
                f"  {team}: dawri={ours.get(team)} evidence={theirs.get(team)}",
                file=sys.stderr,
            )
    print(f"evidence parity {season}: {len(teams)} teams, {differences} differences")
    return differences


def main() -> int:
    shipped = duckdb.connect()
    rel = shipped.execute("SELECT * FROM read_parquet(?)", [str(shipped_file())])
    columns = [c[0] for c in rel.description]
    rows = [dict(zip(columns, row, strict=True)) for row in rel.fetchall()]
    con = connect()
    try:
        names = con.execute("SELECT name FROM ossie_metrics() ORDER BY name").fetchall()
        metrics = [name for (name,) in names]
        differences = 0
        for season, season_id in SEASONS.items():
            _, dawri = team_metrics(con, season, metrics)
            types = {row[0]: row[1:] for row in dawri}
            ours = {
                team: [format_value(v) for v in vals] for team, vals in types.items()
            }
            theirs = {}
            for row in rows:
                if row["season_id"] != season_id:
                    continue
                like = types.get(row["team_name"], [None] * len(metrics))
                theirs[row["team_name"]] = [
                    as_dawri(row[m], t) for m, t in zip(metrics, like, strict=True)
                ]
            differences += compare(season, ours, theirs)
    finally:
        con.close()
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
