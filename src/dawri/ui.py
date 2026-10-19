"""Describe Dawri pages as JSON-compatible component specifications."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from dawri.ui_models import PageSpec

if TYPE_CHECKING:
    from dawri.api_models import SeasonSummary, Standing, TeamMetrics

METRICS = ["points", "goal_difference", "xg_for", "xg_against"]
STANDINGS_COLUMNS = [
    ("rank", "Rank", "integer"),
    ("team_name", "Team", "text"),
    ("played", "Played", "integer"),
    ("won", "Won", "integer"),
    ("drawn", "Drawn", "integer"),
    ("lost", "Lost", "integer"),
    ("goals_for", "GF", "integer"),
    ("goals_against", "GA", "integer"),
    ("goal_difference", "GD", "integer"),
    ("points", "Points", "integer"),
]
METRIC_COLUMNS = [
    ("team_name", "Team", "text"),
    ("points", "Points", "integer"),
    ("goal_difference", "GD", "integer"),
    ("xg_for", "xG for", "decimal"),
    ("xg_against", "xG against", "decimal"),
]


def season_header(summary: SeasonSummary) -> dict[str, object]:
    """Describe a Text element using the season's supplied match counts."""
    content = (
        f"{summary.season}: {summary.finished} finished, {summary.upcoming} upcoming"
    )
    return {
        "root": "summary",
        "elements": {
            "summary": {
                "type": "Text",
                "props": {"content": content},
                "children": [],
            }
        },
    }


def season_page(
    summary: SeasonSummary, standings: list[Standing], metrics: list[TeamMetrics]
) -> PageSpec:
    """Add the two existing data tables around easy's unchanged header."""
    spec = season_header(summary)
    elements = {
        "page": {
            "type": "Page",
            "props": {"title": "Dawri"},
            "children": ["summary", "standings", "metrics"],
        },
        **cast(dict[str, object], spec["elements"]),
    }
    for name, title, columns, rows in [
        ("standings", "Standings", STANDINGS_COLUMNS, standings),
        ("metrics", "Team metrics", METRIC_COLUMNS, metrics),
    ]:
        elements[name] = {
            "type": "Table",
            "props": {
                "title": title,
                "columns": [
                    {"key": key, "label": label, "format": fmt}
                    for key, label, fmt in columns
                ],
                "rows": [row.model_dump() for row in rows],
            },
            "children": [],
        }
    return PageSpec.model_validate({"root": "page", "elements": elements})
