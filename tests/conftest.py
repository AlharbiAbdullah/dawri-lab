import re
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx

from dawri import config

RECORDED = Path(__file__).parent / "fixtures" / "recorded"

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
