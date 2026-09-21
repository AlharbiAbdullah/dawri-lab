import argparse
import json
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

import httpx

BASE = "https://api-sdp.spl.com.sa/v1/spl/football"
REQUEST_GAP = 0.25
SEASONS = {
    "2025/2026": "0de9cda0d297418699a8357a8825d46c",
    "2026/2027": "3677a75aaa514e43b2840e7fa367c91d",
}
LIVE_SEASON = "2026/2027"


# ensure the directory exists
def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


# get the path to the matches for a given season
def matches_path(season_id: str) -> Path:
    storage_path = "data/matches"
    return Path(f"{storage_path}/{season_id}.json")


# get the path to the matchdays for a given season
def matchdays_path(season_id: str) -> Path:
    storage_path = "data/matchdays"
    return Path(f"{storage_path}/{season_id}.json")


# get the path to the standings for a given season
def standings_path(season_id: str) -> Path:
    storage_path = "data/standings"
    return Path(f"{storage_path}/{season_id}.json")


# get the path to the teams for a given season
def teams_path(season_id: str) -> Path:
    storage_path = "data/teams"
    return Path(f"{storage_path}/{season_id}.json")


# get the path to the teamstats for a given season
def teamstats_path(season_id: str, match_id: str) -> Path:
    storage_path = "data/teamstats"
    return Path(f"{storage_path}/{season_id}/{match_id}.json")


# get the path to the playerstats for a given season
def playerstats_path(season_id: str, match_id: str) -> Path:
    storage_path = "data/playerstats"
    return Path(f"{storage_path}/{season_id}/{match_id}.json")


# get the path to the lineups for a given season
def lineups_path(season_id: str, match_id: str) -> Path:
    storage_path = "data/lineups"
    return Path(f"{storage_path}/{season_id}/{match_id}.json")


# get the path to the matchfacts for a given season
def matchfacts_path(season_id: str, match_id: str) -> Path:
    storage_path = "data/matchfacts"
    return Path(f"{storage_path}/{season_id}/{match_id}.json")


# get the path to the feed for a given season
def feed_path(season_id: str, match_id: str) -> Path:
    storage_path = "data/feed"
    return Path(f"{storage_path}/{season_id}/{match_id}.json")


# fetch matches for a given season
def fetch_matches(season_id: str) -> bytes:
    encoded_season_id = quote(f"spl::Football_Season::{season_id}", safe="")
    url = f"{BASE}/seasons/{encoded_season_id}/matches?locale=en-GB"
    response = httpx.get(url)
    response.raise_for_status()
    return response.content


# fetch matchdays for a given season
def fetch_matchday(season_id: str) -> bytes:
    encoded_season_id = quote(f"spl::Football_Season::{season_id}", safe="")
    url = f"{BASE}/seasons/{encoded_season_id}/matchdays?locale=en-GB"
    response = httpx.get(url)
    response.raise_for_status()
    return response.content


# fetch teams for a given season
def fetch_teams(season_id: str) -> bytes:
    encoded_season_id = quote(f"spl::Football_Season::{season_id}", safe="")
    url = f"{BASE}/seasons/{encoded_season_id}/teams?locale=en-GB"
    response = httpx.get(url)
    response.raise_for_status()
    return response.content


# fetch standings for a given season
def fetch_standings(season_id: str) -> bytes:
    encoded_season_id = quote(f"spl::Football_Season::{season_id}", safe="")
    url = f"{BASE}/seasons/{encoded_season_id}/standings/overall?locale=en-GB"
    response = httpx.get(url)
    response.raise_for_status()
    return response.content


# fetch teamstats for a given season
def fetch_teamstats(season_id: str, match_id: str) -> bytes:
    encoded_season_id = quote(f"spl::Football_Season::{season_id}", safe="")
    encoded_match_id = quote(match_id, safe="")
    url = (
        f"{BASE}/seasons/{encoded_season_id}"
        f"/match/{encoded_match_id}/teamstats?locale=en-GB"
    )
    response = httpx.get(url)
    response.raise_for_status()
    return response.content


# fetch playerstats for a given season
def fetch_playerstats(season_id: str, match_id: str) -> bytes:
    encoded_season_id = quote(f"spl::Football_Season::{season_id}", safe="")
    encoded_match_id = quote(match_id, safe="")
    url = (
        f"{BASE}/seasons/{encoded_season_id}"
        f"/match/{encoded_match_id}/playerstats?locale=en-GB"
    )
    response = httpx.get(url)
    response.raise_for_status()
    return response.content


# fetch lineups for a given match
def fetch_lineups(season_id: str, match_id: str) -> bytes:
    encoded_season_id = quote(f"spl::Football_Season::{season_id}", safe="")
    encoded_match_id = quote(match_id, safe="")
    url = (
        f"{BASE}/seasons/{encoded_season_id}"
        f"/matches/{encoded_match_id}/lineups?locale=en-GB"
    )
    response = httpx.get(url)
    response.raise_for_status()
    return response.content


# fetch matchfacts for a given match
def fetch_matchfacts(season_id: str, match_id: str) -> bytes:
    encoded_season_id = quote(f"spl::Football_Season::{season_id}", safe="")
    encoded_match_id = quote(match_id, safe="")
    url = (
        f"{BASE}/seasons/{encoded_season_id}"
        f"/match/{encoded_match_id}/matchfacts?locale=en-GB"
    )
    response = httpx.get(url)
    response.raise_for_status()
    return response.content


# fetch the event feed for a given match
def fetch_feed(season_id: str, match_id: str) -> bytes:
    encoded_season_id = quote(f"spl::Football_Season::{season_id}", safe="")
    encoded_match_id = quote(match_id, safe="")
    url = (
        f"{BASE}/seasons/{encoded_season_id}"
        f"/matches/{encoded_match_id}/feed?locale=en-GB"
    )
    response = httpx.get(url)
    response.raise_for_status()
    return response.content


# write the matches to a file
def write_matches(matches: bytes, season_id: str) -> None:
    path = matches_path(season_id)
    ensure_dir(path.parent)
    path.write_bytes(matches)


# write the matchdays to a file
def write_matchdays(matchdays: bytes, season_id: str) -> None:
    path = matchdays_path(season_id)
    ensure_dir(path.parent)
    path.write_bytes(matchdays)


# write the teams to a file
def write_teams(teams: bytes, season_id: str) -> None:
    path = teams_path(season_id)
    ensure_dir(path.parent)
    path.write_bytes(teams)


# write the standings to a file
def write_standings(standings: bytes, season_id: str) -> None:
    path = standings_path(season_id)
    ensure_dir(path.parent)
    path.write_bytes(standings)


# write the teamstats to a file
def write_teamstats(teamstats: bytes, season_id: str, match_id: str) -> None:
    path = teamstats_path(season_id=season_id, match_id=match_id)
    ensure_dir(path.parent)
    path.write_bytes(teamstats)


# write the playerstats to a file
def write_playerstats(playerstats: bytes, season_id: str, match_id: str) -> None:
    path = playerstats_path(season_id=season_id, match_id=match_id)
    ensure_dir(path.parent)
    path.write_bytes(playerstats)


# write the lineups to a file
def write_lineups(lineups: bytes, season_id: str, match_id: str) -> None:
    path = lineups_path(season_id=season_id, match_id=match_id)
    ensure_dir(path.parent)
    path.write_bytes(lineups)


# write the matchfacts to a file
def write_matchfacts(matchfacts: bytes, season_id: str, match_id: str) -> None:
    path = matchfacts_path(season_id=season_id, match_id=match_id)
    ensure_dir(path.parent)
    path.write_bytes(matchfacts)


# write the feed to a file
def write_feed(feed: bytes, season_id: str, match_id: str) -> None:
    path = feed_path(season_id=season_id, match_id=match_id)
    ensure_dir(path.parent)
    path.write_bytes(feed)


def count_stat_files(directory: Path, payload_key: str) -> int:
    count = 0
    for path in directory.rglob("*.json"):
        landed = json.loads(path.read_bytes())
        if landed.get(payload_key):
            count += 1
    return count


def parse_season() -> tuple[str, str]:
    parser = argparse.ArgumentParser()
    parser.add_argument("season", choices=SEASONS)
    args = parser.parse_args()
    return args.season, SEASONS[args.season]


def cleaned_match_id(match: dict) -> str:
    return match["matchId"].replace("spl::Football_Match::", "")


def has_teamstats_data(payload: dict) -> bool:
    return payload.get("stats") is not None


def has_playerstats_data(payload: dict) -> bool:
    return payload.get("players") is not None


def has_lineups_data(payload: dict) -> bool:
    home = payload.get("home") or {}
    away = payload.get("away") or {}
    return bool(home.get("fielded") or away.get("fielded"))


def has_matchfacts_data(payload: dict) -> bool:
    return bool(payload.get("referees"))


def has_feed_data(payload: dict) -> bool:
    return bool(payload.get("events"))


def land_season_file(
    path: Path,
    fetch: Callable[[str], bytes],
    write: Callable[[bytes, str], None],
    season_id: str,
    refresh: bool,
) -> tuple[dict, int]:
    if refresh or not path.exists():
        body = fetch(season_id)
        write(body, season_id)
        time.sleep(REQUEST_GAP)
        return json.loads(body), 1
    return json.loads(path.read_bytes()), 0


def land_match_family(
    matches: list[dict],
    season_id: str,
    dest: Callable[[str, str], Path],
    fetch: Callable[[str, str], bytes],
    write: Callable[[bytes, str, str], None],
    has_data: Callable[[dict], bool],
) -> int:
    requests = 0
    for match in matches:
        if match.get("status") != "FINISHED":
            continue
        match_id = cleaned_match_id(match)
        if dest(season_id, match_id).exists():
            continue
        body = fetch(season_id, match["matchId"])
        requests += 1
        if has_data(json.loads(body)):
            write(body, season_id, match_id)
        time.sleep(REQUEST_GAP)
    return requests


def main() -> None:
    season_text, season_id = parse_season()
    refresh_season_level = season_text == LIVE_SEASON
    request_count = 0

    matches_json, n = land_season_file(
        matches_path(season_id),
        fetch_matches,
        write_matches,
        season_id,
        refresh_season_level,
    )
    request_count += n
    _, n = land_season_file(
        matchdays_path(season_id),
        fetch_matchday,
        write_matchdays,
        season_id,
        refresh_season_level,
    )
    request_count += n
    _, n = land_season_file(
        teams_path(season_id),
        fetch_teams,
        write_teams,
        season_id,
        refresh_season_level,
    )
    request_count += n
    _, n = land_season_file(
        standings_path(season_id),
        fetch_standings,
        write_standings,
        season_id,
        refresh_season_level,
    )
    request_count += n

    request_count += land_match_family(
        matches_json["matches"],
        season_id,
        teamstats_path,
        fetch_teamstats,
        write_teamstats,
        has_teamstats_data,
    )
    request_count += land_match_family(
        matches_json["matches"],
        season_id,
        playerstats_path,
        fetch_playerstats,
        write_playerstats,
        has_playerstats_data,
    )
    request_count += land_match_family(
        matches_json["matches"],
        season_id,
        lineups_path,
        fetch_lineups,
        write_lineups,
        has_lineups_data,
    )
    request_count += land_match_family(
        matches_json["matches"],
        season_id,
        matchfacts_path,
        fetch_matchfacts,
        write_matchfacts,
        has_matchfacts_data,
    )
    request_count += land_match_family(
        matches_json["matches"],
        season_id,
        feed_path,
        fetch_feed,
        write_feed,
        has_feed_data,
    )

    landed_matches = json.loads(matches_path(season_id=season_id).read_bytes())[
        "matches"
    ]
    print(f"requests: {request_count}")
    print(f"matches: {len(landed_matches)}")
    print(f"distinct: {len({match['matchId'] for match in landed_matches})}")
    print(f"teamstats: {count_stat_files(Path('data/teamstats'), 'stats')}")
    print(f"playerstats: {count_stat_files(Path('data/playerstats'), 'players')}")
    print(f"lineups: {count_stat_files(Path('data/lineups'), 'home')}")
    print(f"matchfacts: {count_stat_files(Path('data/matchfacts'), 'referees')}")
    print(f"feed: {count_stat_files(Path('data/feed'), 'events')}")


if __name__ == "__main__":
    main()
