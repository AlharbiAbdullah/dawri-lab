import json
import shutil
from pathlib import Path

import duckdb
import pytest
from conftest import RECORDED, build_standings
from fastapi.testclient import TestClient

from dawri import config, load, publish, semantic

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


def test_view_structure(client: TestClient) -> None:
    response = client.get("/seasons/2026-2027/view")
    assert response.status_code == 200
    spec = response.json()
    assert spec["root"] == "page"
    assert set(spec["elements"]) == {"page", "summary", "standings", "metrics"}
    assert spec["elements"]["page"] == {
        "type": "Page",
        "props": {"title": "Dawri"},
        "children": ["summary", "standings", "metrics"],
    }
    for name, title, columns in [
        ("standings", "Standings", STANDINGS_COLUMNS),
        ("metrics", "Team metrics", METRIC_COLUMNS),
    ]:
        element = spec["elements"][name]
        assert element["type"] == "Table"
        assert element["children"] == []
        assert element["props"]["title"] == title
        assert element["props"]["columns"] == [
            {"key": key, "label": label, "format": fmt} for key, label, fmt in columns
        ]


def test_view_facts(client: TestClient) -> None:
    elements = client.get("/seasons/2026-2027/view").json()["elements"]
    assert elements["summary"] == {
        "type": "Text",
        "props": {"content": "2026/2027: 2 finished, 1 upcoming"},
        "children": [],
    }
    assert len(elements["standings"]["props"]["rows"]) == 4
    assert (
        elements["standings"]["props"]["rows"]
        == client.get("/seasons/2026-2027/standings").json()
    )
    assert (
        elements["metrics"]["props"]["rows"]
        == client.get(
            "/seasons/2026-2027/metrics",
            params=[
                ("metric", name)
                for name in ["points", "goal_difference", "xg_for", "xg_against"]
            ],
        ).json()
    )


def test_view_empty_season(client: TestClient) -> None:
    response = client.get("/seasons/2025-2026/view")
    assert response.status_code == 200
    elements = response.json()["elements"]
    assert elements["summary"]["props"]["content"] == (
        "2025/2026: 0 finished, 0 upcoming"
    )
    for name in ("standings", "metrics"):
        assert elements[name]["props"]["rows"] == []
        assert elements[name]["props"]["columns"]


def test_view_unknown_season(client: TestClient) -> None:
    response = client.get("/seasons/2024-2025/view")
    assert response.status_code == 404
    assert response.json() == {"detail": "unknown season: 2024-2025"}


def test_view_conditional_response(client: TestClient) -> None:
    response = client.get("/seasons/2026-2027/view")
    etag = response.headers["etag"]
    assert client.get("/seasons/2026-2027/view").headers["etag"] == etag
    cached = client.get("/seasons/2026-2027/view", headers={"If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.content == b""


def test_view_one_generation(
    client: TestClient, api_database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = []
    connect = semantic.connect_serving

    def tracked(serving: Path) -> duckdb.DuckDBPyConnection:
        seen.append(serving)
        return connect(serving)

    monkeypatch.setattr(semantic, "connect_serving", tracked)
    assert client.get("/seasons/2026-2027/view").status_code == 200
    assert seen == [(api_database.parent / "serving").resolve(strict=True)]


def test_view_etag_changes_after_publication(
    client: TestClient,
    api_database: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shutil.copytree(RECORDED, data_dir, dirs_exist_ok=True)
    shutil.copyfile(api_database, data_dir / "dawri.duckdb")
    monkeypatch.setattr(config, "DB_PATH", data_dir / "dawri.duckdb")
    monkeypatch.setattr(config, "SERVING_DIR", data_dir / "serving")
    publish.publish()
    before = client.get("/seasons/2026-2027/view")
    path = data_dir / "matches" / f"{config.SEASONS['2026/2027']}.json"
    payload = json.loads(path.read_text())
    finished = next(row for row in payload["matches"] if row["status"] == "FINISHED")
    finished["status"] = "UPCOMING"
    path.write_text(json.dumps(payload))
    load.main()
    build_standings(data_dir)
    publish.publish()
    after = client.get(
        "/seasons/2026-2027/view", headers={"If-None-Match": before.headers["etag"]}
    )
    assert after.status_code == 200
    assert after.headers["etag"] != before.headers["etag"]
    assert after.json()["elements"]["summary"]["props"]["content"] == (
        "2026/2027: 1 finished, 2 upcoming"
    )
    assert (
        client.get(
            "/seasons/2026-2027/view", headers={"If-None-Match": after.headers["etag"]}
        ).status_code
        == 304
    )
