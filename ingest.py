import json
from pathlib import Path
from urllib.parse import quote

import httpx

BASE = "https://api-sdp.spl.com.sa/v1/spl/football"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def fetch_matches(season_id: str) -> bytes:
    encoded_season_id = quote(f"spl::Football_Season::{season_id}", safe="")
    url = f"{BASE}/seasons/{encoded_season_id}/matches?locale=en-GB"
    response = httpx.get(url)
    response.raise_for_status()
    return response.content


def matches_path(season_id: str) -> Path:
    storage_path = "data/matches"
    return Path(f"{storage_path}/{season_id}.json")


def write_matches(matches: bytes, season_id: str) -> None:
    path = matches_path(season_id)
    ensure_dir(path.parent)
    path.write_bytes(matches)


def main() -> None:
    seasons = {
        "2025/2026": "0de9cda0d297418699a8357a8825d46c",
    }
    season_text, season_id = next(iter(seasons.items()))
    matches = fetch_matches(season_id=season_id)
    write_matches(matches=matches, season_id=season_id)
    matches_json = json.loads(matches)
    print(f"landed {len(matches_json['matches'])} matches for {season_text}")


if __name__ == "__main__":
    main()
