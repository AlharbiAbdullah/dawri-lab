import logging
import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager

import typer

from dawri import ingest, load
from dawri.config import DATA_DIR, DBT_DIR, LOG_PATH

app = typer.Typer()

log = logging.getLogger("dawri")


@app.callback()
def setup(
    verbose: bool = typer.Option(
        False, "--verbose", help="Also show INFO log lines on stderr."
    ),
) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(LOG_PATH)
    file_handler.setLevel(logging.INFO)
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.INFO if verbose else logging.WARNING)
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03dZ %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time.gmtime
    for handler in (file_handler, stderr_handler):
        handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stderr_handler])


@contextmanager
def step(name: str, detail: str = "") -> Iterator[None]:
    if detail:
        log.info("%s start: %s", name, detail)
    else:
        log.info("%s start", name)
    started = time.monotonic()
    try:
        yield
    except typer.Exit:
        raise
    except Exception:
        log.exception("%s failed after %.2fs", name, time.monotonic() - started)
        raise
    log.info("%s end: %.2fs", name, time.monotonic() - started)


@app.command(name="load")
def load_() -> None:
    with step("load"):
        load.main()


@app.command(name="ingest")
def ingest_(season: ingest.Season) -> None:
    with step("ingest", season.value):
        ingest.main(season_text=season.value)


@app.command(name="build")
def build_() -> None:
    with step("build"):
        dbt = shutil.which("dbt")
        if dbt is None:
            log.error("build failed: dbt not found on PATH")
            raise typer.Exit(code=1)
        env: dict[str, str] = {
            **os.environ,
            "DAWRI_DATA_DIR": str(DATA_DIR),
            "NO_COLOR": "1",
        }
        result = subprocess.run(  # noqa: S603
            [
                dbt,
                "build",
                "--project-dir",
                str(DBT_DIR),
                "--profiles-dir",
                str(DBT_DIR),
            ],
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        for line in lines:
            log.info("dbt: %s", line)
        for line in lines[-2:]:
            print(line)
        if result.returncode != 0:
            log.error("build failed: dbt exited %s", result.returncode)
            raise typer.Exit(code=result.returncode)


@app.command(name="run")
def run_(season: ingest.Season) -> None:
    with step("run", season.value):
        ingest_(season)
        load_()
        build_()
