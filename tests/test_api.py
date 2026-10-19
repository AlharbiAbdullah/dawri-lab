import json
import logging
import re
import shutil
from pathlib import Path

import duckdb
import pytest
import uvicorn
from conftest import RECORDED, build_standings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from dawri import config, load, publish, semantic
from dawri.api import app
from dawri.cli import app as cli

FIELDS = [
    "rank",
    "team_name",
    "played",
    "won",
    "drawn",
    "lost",
    "goals_for",
    "goals_against",
    "goal_difference",
    "points",
]
FIRST = dict(zip(FIELDS, [1, "NEOM SC", 1, 1, 0, 0, 2, 0, 2, 3], strict=True))
LAST = dict(zip(FIELDS, [4, "Al Faisaly", 1, 0, 0, 1, 0, 2, -2, 0], strict=True))


def test_health(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "DB_PATH", config.DB_PATH.with_name("missing.duckdb"))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_seasons(client: TestClient) -> None:
    response = client.get("/seasons")
    assert response.status_code == 200
    assert response.json() == [
        {
            "season": "2025/2026",
            "season_id": "0de9cda0d297418699a8357a8825d46c",
            "finished": 0,
            "upcoming": 0,
        },
        {
            "season": "2026/2027",
            "season_id": "3677a75aaa514e43b2840e7fa367c91d",
            "finished": 2,
            "upcoming": 1,
        },
    ]


def test_standings_table(client: TestClient) -> None:
    response = client.get("/seasons/2026-2027/standings")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 4
    assert rows[0] == FIRST
    assert rows[-1] == LAST
    assert [row["rank"] for row in rows] == [1, 2, 3, 4]
    for row in rows:
        assert list(row) == FIELDS
        assert all(type(row[field]) is int for field in FIELDS if field != "team_name")
    assert client.get("/seasons/2026-2027/standings?type=table").json() == rows
    empty = client.get("/seasons/2025-2026/standings")
    assert empty.status_code == 200
    assert empty.json() == []


def test_standings_home(client: TestClient) -> None:
    response = client.get("/seasons/2026-2027/standings?type=home")
    assert response.status_code == 200
    rows = response.json()
    assert [(row["team_name"], row["points"]) for row in rows] == [
        ("Diriyah", 1),
        ("Al Faisaly", 0),
    ]
    away = client.get("/seasons/2026-2027/standings?type=away")
    assert away.status_code == 200
    assert [(row["team_name"], row["points"]) for row in away.json()] == [
        ("NEOM SC", 3),
        ("Al Kholood", 1),
    ]


def test_unknown_season_404(client: TestClient) -> None:
    response = client.get("/seasons/2024-2025/standings")
    assert response.status_code == 404
    assert response.json() == {"detail": "unknown season: 2024-2025"}


def test_bad_type_422(client: TestClient) -> None:
    response = client.get("/seasons/2026-2027/standings?type=all")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "type"]


def test_metrics_recorded(client: TestClient) -> None:
    response = client.get("/seasons/2026-2027/metrics?metric=points&metric=xg_for")
    assert response.status_code == 200
    assert response.json() == [
        {"team_name": "NEOM SC", "points": 3, "xg_for": 1.30},
        {"team_name": "Al Kholood", "points": 1, "xg_for": 1.41},
        {"team_name": "Diriyah", "points": 1, "xg_for": 0.56},
        {"team_name": "Al Faisaly", "points": 0, "xg_for": 0.60},
    ]
    assert list(response.json()[0]) == ["team_name", "points", "xg_for"]
    assert type(response.json()[0]["points"]) is int
    reversed_metrics = client.get(
        "/seasons/2026-2027/metrics?metric=xg_for&metric=points"
    )
    assert reversed_metrics.status_code == 200
    rows = reversed_metrics.json()
    assert [row["team_name"] for row in rows] == [
        "Al Kholood",
        "NEOM SC",
        "Al Faisaly",
        "Diriyah",
    ]
    assert list(rows[0]) == ["team_name", "xg_for", "points"]


def test_metrics_unknown_422(client: TestClient) -> None:
    document = semantic.load_document()["semantic_model"][0]
    known = ", ".join(sorted(metric["name"] for metric in document["metrics"]))
    response = client.get("/seasons/2026-2027/metrics?metric=elo")
    assert response.status_code == 422
    assert response.json() == {"detail": f"unknown metric: elo. Known: {known}"}


def test_match_finished(client: TestClient) -> None:
    response = client.get("/matches/cb556acbac334114887ef91fcb725e0c")
    assert response.status_code == 200
    assert response.json() == {
        "match_id": "cb556acbac334114887ef91fcb725e0c",
        "season": "2026/2027",
        "kickoff_utc": "2026-08-21T18:00:00Z",
        "status": "FINISHED",
        "stadium": "Al Majma'a Sport City Stadium",
        "home": {"team_name": "Al Faisaly", "score": 0},
        "away": {"team_name": "NEOM SC", "score": 2},
        "goals": [
            {
                "minute": minute,
                "additional_minutes": 0,
                "side": "away",
                "team_name": "NEOM SC",
                "player_name": "A. Lacazette",
                "goal_type": "goal",
            }
            for minute in (51, 60)
        ],
    }


def test_match_upcoming(client: TestClient) -> None:
    response = client.get("/matches/a10a6c353d734675b6e000b253df6335")
    assert response.status_code == 200
    match = response.json()
    assert match["status"] == "UPCOMING"
    assert match["home"]["score"] is None and match["away"]["score"] is None
    assert match["goals"] == []
    assert match["kickoff_utc"] == "2026-10-09T13:50:00Z"


def test_match_unknown_404(client: TestClient) -> None:
    match_id = "f" * 32
    response = client.get(f"/matches/{match_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": f"unknown match: {match_id}"}


@pytest.mark.parametrize("match_id", ["cb556", "F" * 32, "g" * 32])
def test_match_malformed_422(client: TestClient, match_id: str) -> None:
    response = client.get(f"/matches/{match_id}")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "match_id"]


def test_metrics_required_422(client: TestClient) -> None:
    response = client.get("/seasons/2026-2027/metrics")
    assert response.status_code == 422


def test_metrics_unknown_season_404(client: TestClient) -> None:
    response = client.get("/seasons/2024-2025/metrics?metric=points")
    assert response.status_code == 404
    assert response.json() == {"detail": "unknown season: 2024-2025"}


def test_serving_while_writer_open(client: TestClient, api_database: Path) -> None:
    with duckdb.connect(str(api_database)) as writer:
        writer.execute("BEGIN TRANSACTION")
        writer.execute("CREATE TABLE rebuilding AS SELECT 1 AS work")
        try:
            for path in (
                "/seasons",
                "/seasons/2026-2027/standings",
                "/seasons/2026-2027/metrics?metric=points",
                "/matches/cb556acbac334114887ef91fcb725e0c",
            ):
                assert client.get(path).status_code == 200
        finally:
            writer.execute("ROLLBACK")


def test_new_publish_visible(
    client: TestClient,
    api_database: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shutil.copyfile(api_database, data_dir / "dawri.duckdb")
    monkeypatch.setattr(config, "DB_PATH", data_dir / "dawri.duckdb")
    monkeypatch.setattr(config, "SERVING_DIR", data_dir / "serving")
    publish.publish()
    before = client.get("/seasons").json()
    with duckdb.connect(str(config.DB_PATH)) as writer:
        writer.execute("UPDATE raw.matches SET status = 'UPCOMING'")
    assert client.get("/seasons").json() == before
    publish.publish()
    after = client.get("/seasons").json()
    assert after[1]["finished"] == 0
    assert after[1]["upcoming"] == 3


def test_own_goal_missing_player(
    client: TestClient,
    api_database: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shutil.copyfile(api_database, data_dir / "dawri.duckdb")
    monkeypatch.setattr(config, "DB_PATH", data_dir / "dawri.duckdb")
    monkeypatch.setattr(config, "SERVING_DIR", data_dir / "serving")
    with duckdb.connect(str(config.DB_PATH)) as writer:
        writer.execute(
            "UPDATE marts.fct_goals SET goal_type = 'own-goal', player_id = 'missing',"
            " scorer_team_id = (SELECT home_team_id FROM staging.stg_matches"
            " WHERE match_id = marts.fct_goals.match_id) WHERE minute = 51"
        )
    publish.publish()
    response = client.get("/matches/cb556acbac334114887ef91fcb725e0c")
    assert response.status_code == 200
    assert response.json()["goals"][0] == {
        "minute": 51,
        "additional_minutes": 0,
        "side": "away",
        "team_name": "NEOM SC",
        "player_name": None,
        "goal_type": "own-goal",
    }


def test_openapi_contract() -> None:
    expected = json.loads((config.ROOT / "docs" / "openapi.json").read_text())
    assert app.openapi() == expected, (
        "docs/openapi.json no longer matches: run mise run openapi"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/seasons",
        "/seasons/2026-2027/standings",
        "/seasons/2026-2027/metrics?metric=points",
        "/matches/cb556acbac334114887ef91fcb725e0c",
    ],
)
def test_etag_stable(client: TestClient, path: str) -> None:
    first, second = client.get(path), client.get(path)
    assert first.status_code == second.status_code == 200
    assert "etag" in first.headers
    assert re.fullmatch(r'"[0-9a-f]{64}"', first.headers["etag"])
    assert first.headers["etag"] == second.headers["etag"]
    assert first.content == second.content


@pytest.mark.parametrize("condition", ["{etag}", "W/{etag}", '"old", {etag}', "*"])
def test_if_none_match_304(client: TestClient, condition: str) -> None:
    first = client.get("/seasons")
    etag = first.headers.get("etag")
    assert etag is not None
    response = client.get(
        "/seasons", headers={"If-None-Match": condition.format(etag=etag)}
    )
    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["etag"] == etag
    assert "content-length" not in response.headers


def test_if_none_match_miss(client: TestClient) -> None:
    response = client.get("/seasons", headers={"If-None-Match": '"old"'})
    assert response.status_code == 200
    assert "etag" in response.headers
    assert len(response.json()) == 2


def test_etag_changes_after_load(
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
    before = client.get("/seasons")
    etag = before.headers.get("etag")
    assert etag is not None
    path = data_dir / "matches" / f"{config.SEASONS['2026/2027']}.json"
    payload = json.loads(path.read_text())
    finished = next(
        match for match in payload["matches"] if match["status"] == "FINISHED"
    )
    finished["status"] = "UPCOMING"
    path.write_text(json.dumps(payload))
    load.main()
    build_standings(data_dir)
    publish.publish()
    after = client.get("/seasons", headers={"If-None-Match": etag})
    assert after.status_code == 200
    assert after.headers["etag"] != etag
    assert after.json()[1]["finished"] == 1
    assert after.json()[1]["upcoming"] == 2
    assert (
        client.get(
            "/seasons", headers={"If-None-Match": after.headers["etag"]}
        ).status_code
        == 304
    )


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/seasons/2024-2025/standings", 404),
        ("/seasons/2026-2027/standings?type=all", 422),
    ],
)
def test_errors_are_not_cached(client: TestClient, path: str, status: int) -> None:
    response = client.get(path, headers={"If-None-Match": "*"})
    assert response.status_code == status
    assert "etag" not in response.headers


@pytest.mark.parametrize(
    ("args", "port", "verbose"),
    [(["serve"], 8000, False), (["--verbose", "serve", "--port", "8081"], 8081, True)],
)
def test_serve(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    port: int,
    verbose: bool,
) -> None:
    def run(application: FastAPI, *, host: str, port: int, log_config: object) -> None:
        assert application is app
        assert host == "127.0.0.1"
        assert port == expected_port
        assert log_config is None
        logging.getLogger("uvicorn.error").info("server ready")
        logging.getLogger("uvicorn.access").info("request served")

    expected_port = port
    monkeypatch.setattr(uvicorn, "run", run)
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    lines = (data_dir.parent / "dawri.log").read_text().splitlines()
    for name, message in [
        ("uvicorn.error", "server ready"),
        ("uvicorn.access", "request served"),
    ]:
        assert any(
            re.fullmatch(
                r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z INFO "
                rf"{re.escape(name)} {message}",
                line,
            )
            for line in lines
        )
        assert (message in result.stderr) is verbose
