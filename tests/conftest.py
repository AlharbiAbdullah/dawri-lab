import json
import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import duckdb
import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from dawri import config, load, publish
from dawri.api import app

RECORDED = Path(__file__).parent / "fixtures" / "recorded"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--view-contract", type=Path, help="Export recorded /view responses"
    )


@pytest.fixture(scope="session", autouse=True)
def export_view_contract(request: pytest.FixtureRequest) -> None:
    destination: Path | None = request.config.getoption("--view-contract")
    if destination is None:
        return
    database: Path = request.getfixturevalue("api_database")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(config, "SERVING_DIR", database.parent / "serving")
        with TestClient(app) as client:
            payload = {}
            for season in config.SEASONS:
                response = client.get(f"/seasons/{season.replace('/', '-')}/view")
                assert response.status_code == 200
                payload[season] = response.json()
    destination.write_text(json.dumps(payload))


SEASON_URL = re.compile(
    r"/seasons/spl::Football_Season::(?P<season_id>\w+)/(?P<rest>.+)"
)
MATCH_REST = re.compile(
    r"(?:match|matches)/spl::Football_Match::(?P<match_id>\w+)/(?P<family>\w+)"
)


class FakeApi:
    """Answers each SPL API URL with its recorded body; refuses the rest."""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.unrecorded: list[str] = []
        self.overrides: dict[tuple[str, str], Path] = {}

    def serve(self, family: str, match_id: str, path: Path) -> None:
        self.overrides[(family, match_id)] = path

    def recording_for(self, url_path: str) -> Path | None:
        season = SEASON_URL.search(url_path)
        if season is None:
            return None
        season_id, rest = season["season_id"], season["rest"]
        match = MATCH_REST.fullmatch(rest)
        if match is None:
            return RECORDED / rest.split("/")[0] / f"{season_id}.json"
        family, match_id = match["family"], match["match_id"]
        if (family, match_id) in self.overrides:
            return self.overrides[(family, match_id)]
        return RECORDED / family / season_id / f"{match_id}.json"

    def respond(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.urls.append(url)
        path = self.recording_for(request.url.path)
        if path is None or not path.exists():
            self.unrecorded.append(url)
            raise AssertionError(f"no recording for {url}")
        return httpx.Response(200, content=path.read_bytes())


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "data"
    folder.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", folder)
    monkeypatch.setattr(config, "DB_PATH", folder / "dawri.duckdb")
    monkeypatch.setattr(config, "SERVING_DIR", folder / "serving")
    monkeypatch.setattr(config, "LOG_PATH", tmp_path / "dawri.log")
    monkeypatch.setattr(config, "REQUEST_GAP", 0)
    return folder


@pytest.fixture
def fake_api() -> Iterator[FakeApi]:
    api = FakeApi()
    with respx.mock(base_url=config.BASE_URL, assert_all_called=False) as router:
        router.route().mock(side_effect=api.respond)
        yield api
    assert api.unrecorded == []


def build_standings(data_dir: Path) -> None:
    """Build the API's real dbt models, keeping all outputs in the temp folder."""
    folder = data_dir.parent
    dbt = shutil.which("dbt")
    assert dbt is not None, "dbt must be installed to build the recorded marts"
    result = subprocess.run(  # noqa: S603
        [
            dbt,
            "run",
            "--project-dir",
            str(config.DBT_DIR),
            "--profiles-dir",
            str(config.DBT_DIR),
            "--target-path",
            str(folder / "target"),
            "--log-path",
            str(folder / "logs"),
            "--select",
            "+mart_standings",
            "+dim_teams",
            "+fct_team_matches",
            "+fct_goals",
            "stg_lineups",
            "stg_matchdays",
            "--threads",
            "1",
            "--no-send-anonymous-usage-stats",
            "--no-version-check",
            "--quiet",
        ],
        env={**os.environ, "DAWRI_DATA_DIR": str(data_dir)},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope="session")
def api_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the real standings mart once, using only the recorded SPL responses."""
    data_dir = tmp_path_factory.mktemp("api") / "data"
    shutil.copytree(RECORDED, data_dir)
    db_path = data_dir / "dawri.duckdb"
    with duckdb.connect() as con:
        con.execute(
            "LOAD ossie"
        )  # Cache is prepared before pytest, never download here.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(config, "DATA_DIR", data_dir)
        patch.setattr(config, "DB_PATH", db_path)
        patch.setattr(config, "SERVING_DIR", data_dir / "serving")
        load.main()
        build_standings(data_dir)
        publish.publish()
    return db_path


@pytest.fixture
def client(api_database: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(config, "DB_PATH", api_database)
    monkeypatch.setattr(config, "SERVING_DIR", api_database.parent / "serving")
    with TestClient(app) as client:
        yield client
