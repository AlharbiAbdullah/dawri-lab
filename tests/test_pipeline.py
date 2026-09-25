import json
import re
from pathlib import Path

from conftest import RECORDED, FakeApi
from typer.testing import CliRunner

from dawri.cli import app

SEASON = "2026/2027"
SEASON_ID = "3677a75aaa514e43b2840e7fa367c91d"
UNPLAYED = "a10a6c353d734675b6e000b253df6335"
PLAYED = "cb556acbac334114887ef91fcb725e0c"
DRAWN = "fed56d6495e048d6aa008ecec45017b2"
UNPLAYED_FEED = Path(__file__).parent / "fixtures" / "unplayed" / "feed.json"

INGEST_LANDED = (
    "2026/2027 finished: 2 of 3\n"
    "2026/2027 landed: 2 teamstats, 2 playerstats, 2 lineups, "
    "2 matchfacts, 2 feed\n"
)
LOAD_COUNTS = (
    "contract: 2 valid, 0 rejected\n"
    "skipped: 1 unplayed\n"
    "matches: 3\n"
    "matchdays: 34\n"
    "teams: 18\n"
    "standings: 54\n"
    "teamstats: 484\n"
    "playerstats: {playerstats}\n"
    "lineups: 80\n"
    "lineup_events: 37\n"
    "match_facts: 2\n"
    "match_officials: 12\n"
    "feed_events: 134\n"
)

runner = CliRunner()


def dawri(*args: str) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    return result.stdout


def landed_files(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*.json"))
    }


def test_first_ingest(data_dir: Path, fake_api: FakeApi) -> None:
    assert dawri("ingest", SEASON) == "requests: 14\n" + INGEST_LANDED
    assert landed_files(data_dir) == landed_files(RECORDED)


def test_second_ingest(data_dir: Path, fake_api: FakeApi) -> None:
    dawri("ingest", SEASON)
    assert dawri("ingest", SEASON) == "requests: 4\n" + INGEST_LANDED
    second = [url.split("?")[0].rsplit(SEASON_ID, 1)[1] for url in fake_api.urls[14:]]
    assert second == ["/matches", "/matchdays", "/teams", "/standings/overall"]


def test_unplayed_never_requested(data_dir: Path, fake_api: FakeApi) -> None:
    dawri("ingest", SEASON)
    dawri("ingest", SEASON)
    assert not [url for url in fake_api.urls if UNPLAYED in url]


def test_empty_body_not_written(data_dir: Path, fake_api: FakeApi) -> None:
    fake_api.serve("feed", DRAWN, UNPLAYED_FEED)
    first = dawri("ingest", SEASON)
    assert first.startswith("requests: 14\n")
    assert first.endswith("2 matchfacts, 1 feed\n")
    assert not (data_dir / "feed" / SEASON_ID / f"{DRAWN}.json").exists()
    assert dawri("ingest", SEASON).startswith("requests: 5\n")


def test_bad_season_exits_2(data_dir: Path, fake_api: FakeApi) -> None:
    result = runner.invoke(app, ["ingest", "2024/2025"])
    assert result.exit_code == 2
    assert fake_api.urls == []


def test_first_load(data_dir: Path, fake_api: FakeApi) -> None:
    dawri("ingest", SEASON)
    expected = "loaded: 18 files\n" + LOAD_COUNTS.format(playerstats=8946)
    assert dawri("load") == expected


def test_second_load_loads_nothing(data_dir: Path, fake_api: FakeApi) -> None:
    dawri("ingest", SEASON)
    dawri("load")
    expected = "loaded: 0 files\n" + LOAD_COUNTS.format(playerstats=8946)
    assert dawri("load") == expected


def test_changed_file_reloads_one(data_dir: Path, fake_api: FakeApi) -> None:
    dawri("ingest", SEASON)
    dawri("load")
    path = data_dir / "playerstats" / SEASON_ID / f"{PLAYED}.json"
    path.write_text(json.dumps(json.loads(path.read_bytes()), indent=1))
    expected = "loaded: 1 files\n" + LOAD_COUNTS.format(playerstats=8946)
    assert dawri("load") == expected


def test_deleted_file_is_pruned(data_dir: Path, fake_api: FakeApi) -> None:
    dawri("ingest", SEASON)
    dawri("load")
    (data_dir / "playerstats" / SEASON_ID / f"{DRAWN}.json").unlink()
    expected = "loaded: 0 files\n" + LOAD_COUNTS.format(playerstats=4505)
    assert dawri("load") == expected


def test_log_lines(data_dir: Path, fake_api: FakeApi) -> None:
    dawri("ingest", SEASON)
    lines = (data_dir.parent / "dawri.log").read_text().splitlines()
    requests = [line for line in lines if " INFO dawri.ingest request: " in line]
    starts = [
        line for line in lines if line.endswith(f" INFO dawri ingest start: {SEASON}")
    ]
    ends = [
        line
        for line in lines
        if re.search(r" INFO dawri ingest end: \d+\.\d{2}s$", line)
    ]
    assert (len(requests), len(starts), len(ends)) == (14, 1, 1)
