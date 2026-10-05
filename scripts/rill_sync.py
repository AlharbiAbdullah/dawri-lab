#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "apache-ossie @ git+https://github.com/apache/ossie@adfa9e4#subdirectory=python",
#     "pyyaml",
# ]
# ///
"""Generate rill/metrics/team_matches.yaml from semantic/dawri.ossie.yaml."""

import sys
from pathlib import Path

import yaml
from ossie.models import OssieDataset, OssieDocument  # ty: ignore[unresolved-import]
from ossie_read import (  # ty: ignore[unresolved-import]
    SOURCE,
    ansi_sql,
    dataset,
    load,
    table_name,
)

TARGET = Path("rill/metrics/team_matches.yaml")
MODELS = Path("rill/models")
SERVING = "data/serving"  # relative to the repo root, where Rill runs
FACT = "fct_team_matches"


def time_field(fact: OssieDataset) -> str:
    for field in fact.fields:
        if field.dimension and field.dimension.is_time:
            return ansi_sql(field.expression)
    raise SystemExit(f"no time dimension on {fact.name}")


def parquet(table: str) -> str:
    return f"read_parquet('{SERVING}/{table}.parquet')"


def model_sql(ds: OssieDataset, header: str) -> str:
    """A view over the serving copy: Parquet is re-read on every query."""
    table = table_name(ds)
    return f"{header}-- @materialize: false\nSELECT * FROM {parquet(table)}\n"


def plain_dimensions(fact: OssieDataset) -> list[dict]:
    return [
        {"name": field.name, "column": ansi_sql(field.expression)}
        for field in fact.fields
        if field.dimension and not field.dimension.is_time
    ]


def joined_dimensions(doc: OssieDocument, fact: OssieDataset) -> list[dict]:
    # Rill's lookup_table fails on DuckDB, so each name is a correlated subquery.
    # It reads the Parquet file itself: a metrics view cannot depend on a second
    # model, and the alias keeps the dbt name the expressions use.
    dims = []
    for rel in doc.relationships or []:
        if rel.from_dataset != fact.name:
            continue
        other = dataset(doc, rel.to)
        table = table_name(other)
        on = " AND ".join(
            f"{table}.{to} = {fact.name}.{fr}"
            for fr, to in zip(rel.from_columns, rel.to_columns, strict=True)
        )
        for field in other.fields:
            if field.dimension and not field.dimension.is_time:
                column = ansi_sql(field.expression)
                source = f"{parquet(table)} AS {table}"
                select = f"SELECT {table}.{column} FROM {source}"  # noqa: S608
                expression = f"({select} WHERE {on})"
                dims.append({"name": field.name, "expression": expression})
    return dims


def metrics_view(doc: OssieDocument) -> dict:
    fact = dataset(doc, FACT)
    return {
        "version": 1,
        "type": "metrics_view",
        "model": table_name(fact),
        "timeseries": time_field(fact),
        "smallest_time_grain": "day",
        "dimensions": plain_dimensions(fact) + joined_dimensions(doc, fact),
        "measures": [
            {"name": metric.name, "expression": ansi_sql(metric.expression)}
            for metric in doc.metrics
        ],
        "explore": {
            "dimensions": "*",
            "measures": "*",
            "defaults": {"time_range": "inf"},
        },
        # The serving copy changes under Rill; a cached answer would be stale.
        "cache": {"enabled": False},
    }


def render(doc: OssieDocument, source: Path) -> dict[Path, str]:
    """Every generated file and its content. Writing and checking share this."""
    note = f"Generated from {source} by scripts/rill_sync.py. Do not edit.\n"
    view = metrics_view(doc)
    return {
        TARGET: f"# {note}" + yaml.dump(view, sort_keys=False, width=1000),
        MODELS / f"{FACT}.sql": model_sql(dataset(doc, FACT), f"-- {note}"),
    }


def main() -> int:
    args = sys.argv[1:]
    check = "--check" in args
    paths = [a for a in args if a != "--check"]
    source = Path(paths[0]) if paths else SOURCE
    doc = load(source)
    files = render(doc, source)
    if check:
        stale = [
            p for p, text in files.items() if not p.exists() or p.read_text() != text
        ]
        for path in stale:
            print(f"{path} is stale", file=sys.stderr)
        if not stale:
            print("rill-sync: generated files match the Ossie document")
        return 1 if stale else 0
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    view = metrics_view(doc)
    measures, dimensions = len(view["measures"]), len(view["dimensions"])
    print(
        f"wrote {TARGET}: {measures} measures, {dimensions} dimensions,"
        f" timeseries {view['timeseries']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
