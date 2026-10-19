# ruff: noqa: E501
import shutil
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from dawri import act, config
from dawri.cli import app

BRIEF = """# Matchday 8, 2026/2027

1 matches, Fri 2026-10-09 to Fri 2026-10-09. Facts from 2 finished matches of 2026/2027. Times are Riyadh (UTC+3).

## Al Kholood v Al Qadsiah
Fri 2026-10-09 16:50, Al Hazem Club Stadium

|  | Al Kholood | Al Qadsiah |
|---|---|---|
| Position | =2 | - |
| Points | 1 | - |
| Played | 1 | - |
| W-D-L | 0-1-0 | - |
| Goals | 1-1 | - |
| xG for per match | 1.41 | - |
| xG against per match | 0.56 | - |
| Last 5 | D | - |

Head to head in the data: none.
"""
NOTE = """# Diriyah 1-1 Al Kholood
2026/2027, Matchday 3, Wed 2026-08-26 21:00 Riyadh, Al-Awwal Park

Goals: 71' Al Elewa (Al Kholood), 83' Al Nemr (Diriyah).
Diriyah now 1 pt from 1 match. Al Kholood now 1 pt from 1 match.
"""
runner = CliRunner()


@pytest.fixture
def actuator_data(
    api_database: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    monkeypatch.setattr(config, "SERVING_DIR", api_database.parent / "serving")
    monkeypatch.delenv("DAWRI_NOTIFY_URL", raising=False)
    return data_dir


def test_brief_recorded(actuator_data: Path) -> None:
    result = runner.invoke(app, ["brief", "2026/2027"])
    assert result.exit_code == 0, result.output
    path = actuator_data / "outbox" / "brief-2026-2027-md-8.md"
    assert result.stdout == f"{path}\n"
    assert path.read_text() == BRIEF
    assert runner.invoke(app, ["brief", "2026/2027"]).exit_code == 0
    assert path.read_text() == BRIEF


def test_brief_no_upcoming(actuator_data: Path) -> None:
    result = runner.invoke(app, ["brief", "2025/2026"])
    assert result.exit_code == 1
    assert result.stderr == "no upcoming matchday in 2025/2026\n"
    assert not (actuator_data / "outbox").exists()


def test_act_needs_init(actuator_data: Path) -> None:
    result = runner.invoke(app, ["act"])
    assert result.exit_code == 1
    assert "--init" in result.stderr
    assert not (actuator_data / "outbox").exists()


def test_act_init_sends_nothing(actuator_data: Path) -> None:
    result = runner.invoke(app, ["act", "--init"])
    assert result.exit_code == 0, result.output
    assert result.stdout == "ledger: 2 results marked done, 0 sent\n"
    assert not (actuator_data / "outbox").exists()


def test_act_brief_once(actuator_data: Path) -> None:
    assert runner.invoke(app, ["act", "--init"]).exit_code == 0
    first = runner.invoke(app, ["act"])
    assert first.exit_code == 0, first.output
    assert first.stdout == "sent: brief-2026-2027-md-8\nledger: 1 sent, 0 failed\n"
    assert runner.invoke(app, ["act"]).stdout == "ledger: 0 sent, 0 failed\n"
    shutil.rmtree(actuator_data / "outbox")
    assert runner.invoke(app, ["act"]).stdout == "ledger: 0 sent, 0 failed\n"


def test_act_result_note(actuator_data: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with respx.mock() as router:
        monkeypatch.setenv("DAWRI_NOTIFY_URL", "https://notify.test/topic")
        result = router.post("https://notify.test/topic").mock(
            side_effect=[httpx.Response(200), httpx.Response(500), httpx.Response(200)]
        )
        # Simulate the draw arriving after initialization at the query boundary.
        original = act.finished_matches
        with monkeypatch.context() as patch:
            patch.setattr(
                act,
                "finished_matches",
                lambda con: [
                    mid
                    for mid in original(con)
                    if mid != "fed56d6495e048d6aa008ecec45017b2"
                ],
            )
            assert runner.invoke(app, ["act", "--init"]).exit_code == 0
        output = runner.invoke(app, ["act"])
        assert output.exit_code == 1
        path = actuator_data / "outbox" / "result-fed56d6495e048d6aa008ecec45017b2.md"
        assert path.read_text() == NOTE
        assert result.calls[0].request.headers["Title"] == "Diriyah 1-1 Al Kholood"
        assert result.calls[0].request.headers["Idempotency-Key"] == (
            "result-fed56d6495e048d6aa008ecec45017b2"
        )


def test_act_retries_failed(
    actuator_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DAWRI_NOTIFY_URL", "https://notify.test/topic")
    with respx.mock() as router:
        post = router.post("https://notify.test/topic").mock(
            side_effect=[httpx.Response(500), httpx.Response(200)]
        )
        assert runner.invoke(app, ["act", "--init"]).exit_code == 0
        assert runner.invoke(app, ["act"]).exit_code == 1
        success = runner.invoke(app, ["act"])
        assert success.exit_code == 0, success.output
        assert success.stdout.endswith("ledger: 1 sent, 0 failed\n")
        assert runner.invoke(app, ["act"]).stdout == "ledger: 0 sent, 0 failed\n"
        assert post.call_count == 2


def test_pending_brief_survives_changed_matchday(
    actuator_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed brief remains pending even when it is no longer the next matchday."""
    monkeypatch.setenv("DAWRI_NOTIFY_URL", "https://notify.test/topic")
    with respx.mock() as router:
        post = router.post("https://notify.test/topic").mock(
            side_effect=[httpx.Response(500), httpx.Response(200)]
        )
        assert runner.invoke(app, ["act", "--init"]).exit_code == 0
        assert runner.invoke(app, ["act"]).exit_code == 1
        monkeypatch.setattr(act.brief, "next_brief", lambda *_: None)
        assert runner.invoke(app, ["act"]).stdout == (
            "sent: brief-2026-2027-md-8\nledger: 1 sent, 0 failed\n"
        )
        assert post.call_count == 2


def test_reinitialization_suppresses_pending_results(
    actuator_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DAWRI_NOTIFY_URL", "https://notify.test/topic")
    with monkeypatch.context() as patch:
        patch.setattr(act, "finished_matches", lambda _: [])
        assert runner.invoke(app, ["act", "--init"]).exit_code == 0
    with respx.mock() as router:
        post = router.post("https://notify.test/topic").mock(
            return_value=httpx.Response(500)
        )
        assert runner.invoke(app, ["act"]).exit_code == 1
        assert post.call_count == 3
        assert runner.invoke(app, ["act", "--init"]).exit_code == 0
        monkeypatch.setattr(act.brief, "next_brief", lambda *_: None)
        post.respond(200)
        output = runner.invoke(app, ["act"])
        assert output.exit_code == 0, output.output
        assert output.stdout == "sent: brief-2026-2027-md-8\nledger: 1 sent, 0 failed\n"
        assert post.call_count == 4


def test_head_to_head_uses_finished_mart(actuator_data: Path) -> None:
    from dawri import brief, semantic

    with semantic.connect_serving(config.SERVING_DIR.resolve()) as con:
        ids = dict(
            con.execute("SELECT team_name, team_id FROM marts.dim_teams").fetchall()
        )
        con.execute("DROP VIEW staging.stg_matches")
        assert brief.head_to_head(con, ids["Diriyah"], ids["Al Kholood"]) == (
            "Head to head in the data: 1 matches. Diriyah 0 wins, 1 draws, Al Kholood 0 wins.\n"
            "- 2026-08-26 Diriyah 1-1 Al Kholood"
        )
