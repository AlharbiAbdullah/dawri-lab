"""Publish the marts as Parquet, whole and in one step, for readers beside the build.

Readers open data/serving/<table>.parquet. data/serving is a symlink to one
serving-<ns> folder; a publish writes a new folder, then swaps the link with one
rename, so a reader sees the old marts or the new ones, never half of each.
"""

import logging
import shutil
import time
from pathlib import Path

import duckdb

from dawri import config

log = logging.getLogger("dawri")

SCHEMA = "marts"


def export(db_path: Path, folder: Path) -> list[str]:
    """Write every table in SCHEMA to folder/<table>.parquet. Returns the names."""
    folder.mkdir(parents=True)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = [
            name
            for (name,) in con.execute(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = ? ORDER BY table_name",
                [SCHEMA],
            ).fetchall()
        ]
        for table in tables:
            target = folder / f"{table}.parquet"
            con.execute(f"COPY {SCHEMA}.{table} TO '{target}' (FORMAT parquet)")
    finally:
        con.close()
    return tables


def swap(link: Path, folder: Path) -> Path | None:
    """Point link at folder with one rename. Returns the folder it pointed at before."""
    previous = link.resolve() if link.is_symlink() else None
    pending = link.with_name(f"{link.name}.tmp")
    pending.unlink(missing_ok=True)
    pending.symlink_to(folder.name)
    pending.replace(link)
    return previous


def publish() -> list[str]:
    """Export the marts and make them the serving copy. Keeps one older copy."""
    link = config.SERVING_DIR
    folder = link.with_name(f"{link.name}-{time.time_ns()}")
    tables = export(config.DB_PATH, folder)
    previous = swap(link, folder)
    # The copy before the previous one: no reader can still hold it open by name.
    for old in link.parent.glob(f"{link.name}-*"):
        if old.resolve() not in (folder.resolve(), previous):
            shutil.rmtree(old)
    log.info("publish: %s tables to %s", len(tables), folder.name)
    return tables
