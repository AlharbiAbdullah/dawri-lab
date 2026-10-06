#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Dawri's README diagrams: architecture (the solution) and tech stack (where each tool
lives), on one layout. Run it to regenerate both .excalidraw.svg files here.
The kit is Rai's /media → diagram; RAI_DIAGRAM_KIT points elsewhere if needed.
"""

import os
import sys
from collections.abc import Callable
from pathlib import Path

DEFAULT_KIT = Path.home() / "helm/03-rai/skills/media/scripts/diagram"
KIT = Path(os.environ.get("RAI_DIAGRAM_KIT", DEFAULT_KIT))
sys.path.insert(0, str(KIT))
from lib import MUTED, VIOLET, Scene, render  # ty: ignore[unresolved-import]

HERE = Path(__file__).parent
MISE = "url:https://raw.githubusercontent.com/jdx/mise/main/docs/public/logo.svg"
OSSIE = "url:https://ossie.apache.org/assets/images/ossie-logos/logo-mark.svg"
TY = "url:https://raw.githubusercontent.com/astral-sh/ty/main/docs/assets/logo-letter.svg"
# zone: (x, y, w, h, title)
Z = {
    "source": (0, 150, 190, 300, "SOURCE"),
    "ingest": (330, 150, 330, 300, "INGEST"),
    "warehouse": (780, 150, 330, 300, "WAREHOUSE"),
    "publish": (1230, 150, 200, 300, "PUBLISH"),
    "consume": (1550, 150, 290, 300, "CONSUME"),
    "semantic": (780, 560, 650, 150, "SEMANTIC"),
    "ci": (280, 860, 1600, 190, "CI/CD"),
}
MID = 300


def frame(s: Scene, header: Callable[[Scene], None]) -> None:
    """Zones, the project box and the labelled arrows: the same in both diagrams."""
    s.zone(280, 0, 1600, 790, None, dotted=True)
    header(s)
    for x, y, w, h, title in Z.values():
        s.zone(x, y, w, h, title)
    s.arrow([(192, MID), (328, MID)], label="fetch\nraw JSON", at=(190, MID - 60, 88))
    s.arrow([(662, MID), (778, MID)], label="load\ninto DuckDB",
            at=(660, MID - 60, 120))
    s.arrow([(1112, MID), (1228, MID)], label="export\nmarts", at=(1110, MID - 60, 120))
    s.arrow([(1432, MID), (1548, MID)], label="read\nserving copy",
            at=(1430, MID - 60, 120))
    s.arrow([(945, 452), (945, 558)], color=VIOLET, dashed=True,
            label="convert\nsemantic models", at=(955, 482, 170))
    s.arrow([(1432, 635), (1695, 635), (1695, 452)], color=VIOLET, dashed=True,
            label="define\nevery metric", at=(1450, 645, 230))
    s.arrow([(380, 858), (380, 792)], color=MUTED, dashed=True,
            label="check\nthe project", at=(390, 802, 130))


def row(
    s: Scene, zone: str, items: list[tuple[str, str]], top: int | None = None
) -> None:
    """Logos with names, spread evenly across a zone."""
    x, y, w, _, _ = Z[zone]
    slot = w / len(items)
    top = y + 90 if top is None else top
    for j, (key, name) in enumerate(items):
        s.tool(x + slot * j + slot / 2, top, key, name, w=slot)


def tech_stack() -> None:
    s = Scene()

    def header(s: Scene) -> None:
        s.tool(356, 14, MISE, "mise", w=110)
        s.tool(466, 14, "si:uv", "uv", w=110)

    frame(s, header)
    row(s, "source", [("si:json", "SPL API")])
    row(s, "ingest", [("si:pydantic", "Pydantic")])
    row(s, "warehouse", [("gh:duckdb", "DuckDB"), ("si:apachearrow", "PyArrow"),
                         ("si:dbt#FF694B", "dbt")])
    row(s, "publish", [("si:apacheparquet", "Parquet")])
    row(s, "consume", [("gh:rilldata", "Rill"), ("gh:evidence-dev", "Evidence")],
        top=200)
    row(s, "consume", [("si:streamlit", "Streamlit")], top=320)
    row(s, "semantic", [(OSSIE, "Apache Ossie")], top=600)
    row(s, "ci", [("si:githubactions", "GitHub Actions"), ("si:ruff+#261230", "Ruff"),
                  (TY, "ty"), ("si:pytest", "pytest")], top=910)
    s.save("tech-stack")


def architecture() -> None:
    s = Scene()

    frame(s, lambda s: None)

    def parts(
        zone: str, labels: list[str], top: int, h: int = 52, gap: int = 14
    ) -> None:
        x, _, w, _, _ = Z[zone]
        for label in labels:
            s.part(x + 20, top, w - 40, h, label)
            top += h + gap

    parts("source", ["league API", "Opta-fed"], top=230)
    parts("ingest", ["fetch every endpoint", "contract check", "raw JSON files"],
          top=220)
    parts("warehouse", ["raw", "staging", "marts, tested"], top=220)
    parts("publish", ["serving copy", "atomic swap"], top=255)
    parts("consume", ["dashboard", "report", "app", "CLI"], top=200, h=48, gap=12)
    parts("semantic", ["one definition per metric"], top=615, h=56)
    x, y, w, _, _ = Z["ci"]
    checks = ["lint", "types", "tests, network off", "build on recorded data",
              "sync checks"]
    slot = (w - 40) / len(checks)
    for j, label in enumerate(checks):
        s.part(x + 20 + slot * j + 8, y + 70, slot - 16, 64, label)
    s.save("architecture")


tech_stack()
architecture()
render(HERE, "architecture", "tech-stack")
