"""Read the committed Ossie document in the shape DuckDB's ossie extension accepts."""

import json
import tempfile
from pathlib import Path

import duckdb
import yaml

from dawri import config
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
    return with_ossie(duckdb.connect(str(db_path), read_only=True), doc_path)


def connect_serving(
    serving: Path | None = None, doc_path: Path = DOC_PATH
) -> duckdb.DuckDBPyConnection:
    """The serving copy, for readers beside the build: no file lock, no half build.

    An in-memory catalog named `dawri` (the document's sources are
    dawri.marts.<table>) with one view per Parquet file. Each query re-reads
    the files through the serving symlink, so a publish shows on the next query.
    """
    serving = serving or config.SERVING_DIR
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS dawri")
    con.execute("USE dawri")
    con.execute("CREATE SCHEMA marts")
    for path in sorted(serving.glob("*.parquet")):
        source = str(path).replace("'", "''")
        con.execute(
            f"CREATE VIEW marts.{path.stem} AS SELECT * FROM read_parquet('{source}')"  # noqa: S608
        )
    return with_ossie(con, doc_path)


def with_ossie(
    con: duckdb.DuckDBPyConnection, doc_path: Path
) -> duckdb.DuckDBPyConnection:
    """Load the ossie extension and the document into an open connection."""
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
    con: duckdb.DuckDBPyConnection,
    season: str,
    metrics: list[str] | None = None,
    team: str | None = None,
    by: list[str] | None = None,
) -> tuple[list[str], list[tuple]]:
    """One row per team with a finished match in the season. Returns (header, rows).

    team keeps one team's rows. by adds dimensions from the document
    (e.g. "fct_team_matches.venue"): one row per team and value, after the name.
    """
    explicit = bool(metrics)
    metrics = list(metrics) if metrics else DEFAULT_METRICS
    by = list(by or [])

    known = {
        name for (name,) in con.execute("SELECT name FROM ossie_metrics()").fetchall()
    }
    for metric in metrics:
        if metric not in known:
            raise UnknownMetric(metric)

    season_id = SEASONS[season].replace("'", "''")
    filters = [f"fct_team_matches.season_id = '{season_id}'"]
    if team is not None:
        filters.append(f"{TEAM_NAME} = '{team.replace("'", "''")}'")

    rel = con.execute(
        "SELECT * FROM ossie_query(?, ?, ?)", [metrics, [TEAM_NAME, *by], filters]
    )
    columns = [col[0] for col in rel.description]
    raw = rel.fetchall()

    # Reorder to team_name + by + metrics in the order asked,
    # whatever order the extension returns.
    keys = [TEAM_NAME, *by]
    positions = [columns.index(k) for k in keys] + [columns.index(m) for m in metrics]
    rows = [tuple(row[i] for i in positions) for row in raw]

    # Default: points, then goal difference, both descending, then name.
    # With --metric: the first metric descending, then name.
    sort_by = [metrics[0]] if explicit else ["points", "goal_difference"]
    sort_idx = [len(keys) + metrics.index(m) for m in sort_by]
    rows.sort(key=lambda row: tuple(-row[i] for i in sort_idx) + row[: len(keys)])

    return ["team_name", *(b.split(".")[-1] for b in by), *metrics], rows


def format_value(value: object) -> str:
    """Integers as integers; floats always with two decimals (5.70, not 5.7)."""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def to_csv_lines(header: list[str], rows: list[tuple]) -> list[str]:
    return [",".join(header)] + [",".join(format_value(v) for v in row) for row in rows]
