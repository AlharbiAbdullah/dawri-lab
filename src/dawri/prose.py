"""Optional prose. Membership of numbers does not prove a sentence true."""

import json
import os
import re
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
import typer

if TYPE_CHECKING:
    from dawri.brief import Fixture

NUMBERS = re.compile(r"\d+(?:\.\d+)?")
WORDS = re.compile(
    r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|"
    r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b",
    re.IGNORECASE,
)


def offending_number(paragraph: str, facts: dict) -> str | None:
    """Reject number words; allow only numeric tokens present in these facts."""
    allowed = {Decimal(token) for token in NUMBERS.findall(json.dumps(facts))}
    candidates = [
        (m.start(), m.group())
        for m in NUMBERS.finditer(paragraph)
        if Decimal(m.group()) not in allowed
    ]
    candidates.extend((m.start(), m.group()) for m in WORDS.finditer(paragraph))
    return min(candidates)[1] if candidates else None


def generate(facts: dict) -> str:
    """Use the already configured cloud model through the local Ollama daemon."""
    response = httpx.post(
        "http://127.0.0.1:11434/api/chat",
        timeout=120,
        json={
            "model": os.getenv("DAWRI_PROSE_MODEL", "deepseek-v4.1-flash:cloud"),
            "stream": False,
            "think": False,
            "messages": [
                {
                    "role": "system",
                    "content": "Write one paragraph of at most three sentences "
                    "about this fixture using only the supplied facts. "
                    "No predictions, arithmetic, odds or opinions. "
                    "Use digits for numbers. Do not add a heading.",
                },
                {"role": "user", "content": json.dumps(facts)},
            ],
        },
    )
    response.raise_for_status()
    content = response.json()["message"]["content"]
    if not isinstance(content, str):
        raise TypeError("model content is not text")
    return content.strip()


def paragraphs(fixtures: list[Fixture]) -> list[str]:
    kept = []
    for fixture in fixtures:
        name = f"{fixture.home} v {fixture.away}"
        try:
            paragraph = generate(fixture.facts())
            bad = offending_number(paragraph, fixture.facts())
            if bad:
                raise ValueError(f"{bad} not in facts")
            if (
                not paragraph
                or "\n" in paragraph
                or len(re.split(r"(?<=[.!?])\s+", paragraph)) > 3
            ):
                raise ValueError("expected one paragraph of at most three sentences")
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            typer.echo(f"rejected {name}: {exc}", err=True)
            paragraph = ""
        kept.append(paragraph)
    accepted = sum(bool(p) for p in kept)
    typer.echo(
        f"prose: {len(fixtures)} fixtures, {accepted} kept, "
        f"{len(fixtures) - accepted} rejected",
        err=True,
    )
    return kept
