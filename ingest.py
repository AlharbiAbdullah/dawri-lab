from pathlib import Path
from urllib.parse import quote

import httpx

BASE = "https://api-sdp.spl.com.sa/v1/spl/football"

STORAGE_PATH = "data"
MATCHES_DIR = f"{STORAGE_PATH}/matches"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def fetch_matches(season_id: str) -> bytes:
    season_id = quote(f"spl::Football_Season::{season_id}", safe="")
    url = f"{BASE}/seasons/{season_id}/matches?locale=en-GB"
    response = httpx.get(url)
    response.raise_for_status()
    return response.content


def write_matches(matches: bytes, season: str) -> None:
    ensure_dir(Path(MATCHES_DIR))
    FILE_NAME = f"{MATCHES_DIR}/{season}.json"
    Path(FILE_NAME).write_bytes(matches)


def main() -> None:
    seasons = {
        "2025/2026": "0de9cda0d297418699a8357a8825d46c",
    }
    season_year_text, season_id = next(iter(seasons.items()))
    matches = fetch_matches(season_id)
    write_matches(matches, season=season_year_text)


if __name__ == "__main__":
    main()
