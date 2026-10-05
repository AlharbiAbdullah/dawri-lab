"""Generate the Evidence sources from semantic/dawri.ossie.yaml and dawri.config.

Runs in the project environment with apache-ossie added (mise run evidence-sync).
--check regenerates in memory, writes nothing, and also fails on any page that
aggregates.
"""

import re
import sys
from pathlib import Path

from ossie.models import OssieDocument  # ty: ignore[unresolved-import]
from ossie_read import (
    SOURCE,
    ansi_sql,
    dataset,
    load,
    table_name,
)

from dawri.config import SEASONS

SOURCES = Path("evidence/sources/dawri")
PAGES = Path("evidence/pages")
SERVING = "../data/serving"  # relative to evidence/, where npm run sources runs
FACT = "fct_team_matches"
SEASON = "season_id"
NAME = "team_name"
AGGREGATE = re.compile(r"\b(SUM|AVG|COUNT|MIN|MAX)\s*\(", re.IGNORECASE)


def parquet(table: str) -> str:
    return f"read_parquet('{SERVING}/{table}.parquet')"


def team_metrics_sql(doc: OssieDocument) -> str:
    """One row per season and team, one column per Ossie metric.

    Each table is aliased to its dbt name, so the document's qualified
    expressions (SUM(fct_team_matches.points)) run unchanged.
    """
    fact = dataset(doc, FACT)
    season = next(f for f in fact.fields if f.name == SEASON)
    rel = next(r for r in doc.relationships or [] if r.from_dataset == FACT)
    dim = dataset(doc, rel.to)
    name = next(f for f in dim.fields if f.name == NAME)
    fact_t, dim_t = table_name(fact), table_name(dim)
    on = " AND ".join(
        f"{dim_t}.{to} = {fact_t}.{fr}"
        for fr, to in zip(rel.from_columns, rel.to_columns, strict=True)
    )
    columns = [
        f"{fact_t}.{ansi_sql(season.expression)} AS {SEASON}",
        f"{dim_t}.{ansi_sql(name.expression)} AS {NAME}",
        *(f"{ansi_sql(m.expression)} AS {m.name}" for m in doc.metrics),
    ]
    select = ",\n    ".join(columns)
    return (
        f"SELECT\n    {select}\n"
        f"FROM {parquet(fact_t)} AS {fact_t}\n"
        f"LEFT JOIN {parquet(dim_t)} AS {dim_t}\n    ON {on}\n"
        "GROUP BY 1, 2\n"
        "ORDER BY 1, 2\n"
    )


def seasons_sql() -> str:
    """The warehouse holds season ids only; the names live in dawri.config."""
    rows = ",\n    ".join(f"('{sid}', '{name}')" for name, sid in SEASONS.items())
    values = f"(VALUES\n    {rows}\n) AS seasons({SEASON}, season)"
    return f"SELECT * FROM {values}\n"  # noqa: S608


def render(doc: OssieDocument, source: Path) -> dict[Path, str]:
    """Every generated file and its content. Writing and checking share this."""
    note = f"-- Generated from {source} and dawri.config by scripts/evidence_sync.py."
    return {
        SOURCES / "team_metrics.sql": f"{note} Do not edit.\n{team_metrics_sql(doc)}",
        SOURCES / "seasons.sql": f"{note} Do not edit.\n{seasons_sql()}",
    }


def check(files: dict[Path, str]) -> int:
    stale = [p for p, text in files.items() if not p.exists() or p.read_text() != text]
    for path in stale:
        print(f"{path} is stale", file=sys.stderr)
    aggregating = [
        p for p in sorted(PAGES.rglob("*.md")) if AGGREGATE.search(p.read_text())
    ]
    for path in aggregating:
        print(
            f"{path} aggregates: pages select, filter and order only", file=sys.stderr
        )
    if stale or aggregating:
        return 1
    print("evidence-sync: sources match the Ossie document, no page aggregates")
    return 0


def main() -> int:
    args = sys.argv[1:]
    paths = [a for a in args if a != "--check"]
    source = Path(paths[0]) if paths else SOURCE
    doc = load(source)
    files = render(doc, source)
    if "--check" in args:
        return check(files)
    for path, text in files.items():
        path.write_text(text)
    metrics = len(doc.metrics)
    print(
        f"wrote {SOURCES}/team_metrics.sql: {metrics} metrics, by {SEASON} and {NAME}"
    )
    print(f"wrote {SOURCES}/seasons.sql: {len(SEASONS)} seasons")
    return 0


if __name__ == "__main__":
    sys.exit(main())
