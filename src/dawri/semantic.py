"""Read the committed Ossie document in the shape DuckDB's ossie extension accepts."""

import json
import tempfile
from pathlib import Path

import duckdb
import yaml

from dawri.config import DB_PATH, ROOT, SEASONS

DOC_PATH = ROOT / "semantic" / "dawri.ossie.yaml"
DEFAULT_METRICS = ["points", "goal_difference", "xg_for", "xg_against"]
TEAM_NAME = "dim_teams.team_name"


class UnknownMetric(ValueError):
    """A metric name that is not in the Ossie document."""


def to_v011(doc: dict) -> dict:
    """0.2.0.dev0 has one model at the root; 0.1.1 wants a semantic_model list."""
    model = {key: value for key, value in doc.items() if key != "version"}
    return {"version": "0.1.1", "semantic_model": [model]}


def load_document(path: Path = DOC_PATH) -> dict:
    return to_v011(yaml.safe_load(path.read_text()))


def connect(
    db_path: Path = DB_PATH, doc_path: Path = DOC_PATH
) -> duckdb.DuckDBPyConnection:
    """Read-only connection with the ossie extension and the document loaded."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        con.execute("LOAD ossie")
    except duckdb.Error:
        con.execute("INSTALL ossie FROM community")
        con.execute("LOAD ossie")

    with tempfile.TemporaryDirectory() as tmp:
        converted = Path(tmp) / "dawri.ossie.json"
        converted.write_text(json.dumps(load_document(doc_path)))
        con.execute("CALL ossie_load(?)", [str(converted)])
    return con


def team_metrics(
    con: duckdb.DuckDBPyConnection, season: str, metrics: list[str] | None = None
) -> tuple[list[str], list[tuple]]:
    """One row per team with a finished match in the season. Returns (header, rows)."""
    explicit = bool(metrics)
    metrics = list(metrics) if metrics else DEFAULT_METRICS

    known = {
        name for (name,) in con.execute("SELECT name FROM ossie_metrics()").fetchall()
    }
    for metric in metrics:
        if metric not in known:
            raise UnknownMetric(metric)

    season_id = SEASONS[season].replace("'", "''")
    season_filter = f"fct_team_matches.season_id = '{season_id}'"

    rel = con.execute(
        "SELECT * FROM ossie_query(?, ?, ?)", [metrics, [TEAM_NAME], [season_filter]]
    )
    columns = [col[0] for col in rel.description]
    raw = rel.fetchall()

    # Reorder to team_name + metrics in the order asked,
    # whatever order the extension returns.
    positions = [columns.index(TEAM_NAME)] + [columns.index(m) for m in metrics]
    rows = [tuple(row[i] for i in positions) for row in raw]

    # Default: points, then goal difference, both descending, then name.
    # With --metric: the first metric descending, then name.
    sort_by = [metrics[0]] if explicit else ["points", "goal_difference"]
    sort_idx = [1 + metrics.index(m) for m in sort_by]
    rows.sort(key=lambda row: tuple(-row[i] for i in sort_idx) + (row[0],))

    return ["team_name", *metrics], rows


def format_value(value: object) -> str:
    """Integers as integers; floats always with two decimals (5.70, not 5.7)."""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def to_csv_lines(header: list[str], rows: list[tuple]) -> list[str]:
    return [",".join(header)] + [",".join(format_value(v) for v in row) for row in rows]
