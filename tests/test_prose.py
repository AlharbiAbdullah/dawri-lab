import pytest

from dawri.prose import offending_number


@pytest.mark.parametrize(
    ("paragraph", "expected"),
    [
        ("Al Hilal sit 1st on 18 points.", None),
        ("Al Hilal have 19 points.", "19"),
        ("a one-point gap", "one"),
        ("won 2-0 with 3.58 xG per match", None),
        ("Al Ittihad have 18 points.", None),
    ],
)
def test_number_guard(paragraph: str, expected: str | None) -> None:
    """Number words are rejected, even if arithmetic is true or 1 occurs as rank."""
    facts = {
        "home": {"rank": 1, "points": 18, "xg": 3.58},
        "away": {"rank": 2, "points": 17},
        "score": "2-0",
    }
    assert offending_number(paragraph, facts) == expected


def test_prose_drops_invalid_block(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from dawri import prose
    from dawri.brief import Fixture

    fixture = Fixture(
        "Al Hilal",
        "Al Ittihad",
        "Sat 2026-10-10 21:00",
        "Arena",
        ["1", "18", "7", "6-0-1", "23-5", "3.58", "1.18", "W"],
        ["2", "17", "7", "5-2-0", "12-6", "2.02", "1.42", "W"],
        "Head to head in the data: none.",
    )
    monkeypatch.setattr(prose, "generate", lambda _: "Al Hilal have 19 points.")
    assert prose.paragraphs([fixture]) == [""]
    assert capsys.readouterr().err == (
        "rejected Al Hilal v Al Ittihad: 19 not in facts\n"
        "prose: 1 fixtures, 0 kept, 1 rejected\n"
    )
