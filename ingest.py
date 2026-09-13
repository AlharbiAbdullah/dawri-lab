import json
import time
from pathlib import Path
from urllib.parse import quote

import httpx

BASE = "https://api-sdp.spl.com.sa/v1/spl/football"


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
    url = f"{BASE}/seasons/{encoded_season_id}/match/{encoded_match_id}/teamstats?locale=en-GB"
    response = httpx.get(url)
    response.raise_for_status()
    return response.content


# fetch playerstats for a given season
def fetch_playerstats(season_id: str, match_id: str) -> bytes:
    encoded_season_id = quote(f"spl::Football_Season::{season_id}", safe="")
    encoded_match_id = quote(match_id, safe="")
    url = f"{BASE}/seasons/{encoded_season_id}/match/{encoded_match_id}/playerstats?locale=en-GB"
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


def count_stat_files(directory: Path, payload_key: str) -> int:
    count = 0
    for path in directory.rglob("*.json"):
        landed = json.loads(path.read_bytes())
        if landed.get(payload_key):
            count += 1
    return count


# main function to ingest the matches
def main() -> None:
    seasons = {
        "2025/2026": "0de9cda0d297418699a8357a8825d46c",
    }
    # select the first season
    season_text, season_id = next(iter(seasons.items()))
    request_count = 0
    # fetch the matches and load it into a file
    if not matches_path(season_id=season_id).exists():
        matches = fetch_matches(season_id=season_id)
        request_count += 1
        write_matches(matches=matches, season_id=season_id)
        matches_json = json.loads(matches)
        print(f"landed {len(matches_json['matches'])} matches for {season_text}")
    else:
        matches_json = json.loads(matches_path(season_id=season_id).read_bytes())

    # fetch the matchdays and load it into a file
    if not matchdays_path(season_id=season_id).exists():
        matchdays = fetch_matchday(season_id=season_id)
        request_count += 1
        write_matchdays(matchdays=matchdays, season_id=season_id)
        matchdays_json = json.loads(matchdays)
        print(f"landed {len(matchdays_json['matchdays'])} matchdays for {season_text}")
    else:
        matchdays_json = json.loads(matchdays_path(season_id=season_id).read_bytes())

    # fetch the teams and load it into a file
    if not teams_path(season_id=season_id).exists():
        teams = fetch_teams(season_id=season_id)
        request_count += 1
        write_teams(teams=teams, season_id=season_id)
        teams_json = json.loads(teams)
        print(f"landed {len(teams_json['teams'])} teams for {season_text}")
    else:
        teams_json = json.loads(teams_path(season_id=season_id).read_bytes())

    # fetch the standings and load it into a file
    if not standings_path(season_id=season_id).exists():
        standings = fetch_standings(season_id=season_id)
        request_count += 1
        write_standings(standings=standings, season_id=season_id)
        standings_json = json.loads(standings)
        print(f"landed {len(standings_json['standings'])} standings for {season_text}")
    else:
        standings_json = json.loads(standings_path(season_id=season_id).read_bytes())

    # fetch the teamstats and load it into a file
    for match in matches_json["matches"]:
        match_id_cleaned = match["matchId"].replace("spl::Football_Match::", "")
        if not teamstats_path(season_id=season_id, match_id=match_id_cleaned).exists():
            teamstats = fetch_teamstats(season_id=season_id, match_id=match["matchId"])
            request_count += 1
            teamstats_json = json.loads(teamstats)
            if teamstats_json.get("stats") is not None:
                write_teamstats(teamstats=teamstats, season_id=season_id, match_id=match_id_cleaned)
                print(f"landed {len(teamstats_json)} teamstats for {season_text}")
            time.sleep(0.5)
        else:
            teamstats_json = json.loads(
                teamstats_path(season_id=season_id, match_id=match_id_cleaned).read_bytes()
            )

    # fetch the playerstats and load it into a file
    for match in matches_json["matches"]:
        match_id_cleaned = match["matchId"].replace("spl::Football_Match::", "")
        if not playerstats_path(season_id=season_id, match_id=match_id_cleaned).exists():
            playerstats = fetch_playerstats(season_id=season_id, match_id=match["matchId"])
            request_count += 1
            playerstats_json = json.loads(playerstats)
            if playerstats_json.get("players") is not None:
                write_playerstats(
                    playerstats=playerstats, season_id=season_id, match_id=match_id_cleaned
                )
                print(f"landed {len(playerstats_json)} playerstats for {season_text}")
            time.sleep(0.5)
        else:
            playerstats_json = json.loads(
                playerstats_path(season_id=season_id, match_id=match_id_cleaned).read_bytes()
            )

    landed_matches = json.loads(matches_path(season_id=season_id).read_bytes())["matches"]
    print(f"requests: {request_count}")
    print(f"matches: {len(landed_matches)}")
    print(f"distinct: {len({match['matchId'] for match in landed_matches})}")
    print(f"teamstats: {count_stat_files(Path('data/teamstats'), 'stats')}")
    print(f"playerstats: {count_stat_files(Path('data/playerstats'), 'players')}")


if __name__ == "__main__":
    main()
