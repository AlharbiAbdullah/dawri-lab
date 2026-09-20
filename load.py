import json
from pathlib import Path

import duckdb as db
import pyarrow as pa
from pydantic import BaseModel, ValidationError
from pydantic.alias_generators import to_snake

import contracts

# configs
DATA_GLOB = Path("data")
# the folder a family reads from, when it is not the family name itself
FAMILY_DIRS = {
    "lineup_events": "lineups",
    "match_facts": "matchfacts",
    "match_officials": "matchfacts",
    "feed_events": "feed",
}
DB_PATH = Path("data/dawri.duckdb")


def validate_data(data: list, contract: type[BaseModel], id_key: str) -> None:
    for row in data:
        try:
            contract.model_validate(row)
        except ValidationError as e:
            print(f"error {row[id_key]}:{e.errors()}")
            raise SystemExit(1)


# the home or away slot of a feed event, whichever one is filled
def feed_event_side(event: dict) -> str | None:
    if event.get("home") is not None:
        return "home"
    if event.get("away") is not None:
        return "away"
    return None


# one feed event, flattened out of the slot it happened in
def unpack_feed_event(match_id: str, event: dict) -> dict:
    side = feed_event_side(event)
    slot = event[side] if side else {}
    player = slot.get("player") or {}
    return {
        "matchId": match_id,
        "eventId": event["eventId"],
        "type": event["type"],
        "label": event["label"],
        "side": side,
        "teamId": (slot.get("team") or {}).get("teamId"),
        "playerId": player.get("playerId"),
        "relatedPlayerId": player.get("relatedPlayerId"),
        "time": slot.get("time"),
        "additionalTime": slot.get("additionalTime"),
        "phase": slot.get("phase") or event.get("phase"),
        "homeScorePush": event.get("homeScorePush"),
        "awayScorePush": event.get("awayScorePush"),
        "timeStamp": event["timeStamp"],
    }


def unpack_json_pattern(data_family: str, data: dict) -> list[dict]:
    if data_family == "matches":
        return data["matches"]
    elif data_family == "matchdays":
        return data["matchdays"]
    elif data_family == "teams":
        return data["teams"]
    elif data_family == "standings":
        return [
            {
                "type": block["type"],
                **team,
                "stats": [
                    {**stat, "statsValue": json.dumps(stat["statsValue"])}
                    for stat in team["stats"]
                ],
            }
            for block in data["standings"]
            for team in block["teams"]
        ]

    elif data_family == "lineups":
        return [
            {
                "matchId": data["matchId"],
                "teamId": data[side]["teamId"],
                "side": side,
                "selection": selection,
                "tacticalFormation": data[side]["tacticalFormation"],
                "playerId": player["playerId"],
                "bibNumber": player["bibNumber"],
                "role": player["role"],
                "roleLabel": player["roleLabel"],
                "shortName": player["shortName"],
                "shirtName": player["shirtName"],
                "nationality": player["nationality"],
                "nationalityIsoCode": player["nationalityIsoCode"],
                "isCaptain": player["isCaptain"],
                "isGoalkeeper": player["isGoalkeeper"],
                "tacticalXPosition": player["tacticalXPosition"],
                "tacticalYPosition": player["tacticalYPosition"],
            }
            for side in ("home", "away")
            for selection in ("fielded", "benched")
            for player in data[side][selection]
        ]

    elif data_family == "lineup_events":
        return [
            {
                "matchId": data["matchId"],
                "teamId": data[side]["teamId"],
                "playerId": player["playerId"],
                "type": event["type"],
                "label": event["label"],
                "time": event["time"],
                "additionalTime": event["additionalTime"],
                "relatedPlayerId": event["relatedPlayerId"],
                "phase": event["phase"],
            }
            for side in ("home", "away")
            for selection in ("fielded", "benched")
            for player in data[side][selection]
            for event in player["events"] or []
        ]

    elif data_family == "match_facts":
        return [
            {
                "matchId": data["matchId"],
                "stadiumId": data["stadium"]["stadiumId"],
                "stadiumName": data["stadium"]["stadiumName"],
                "cityName": data["location"]["cityName"],
                "numberOfSpectators": data["enviroment"]["numberOfSpectators"],
                "mapsGeoCodeLatitude": data["stadium"]["mapsGeoCodeLatitude"],
                "mapsGeoCodeLongitude": data["stadium"]["mapsGeoCodeLongitude"],
            }
        ]

    elif data_family == "match_officials":
        return [
            {
                "matchId": data["matchId"],
                "refereeId": referee["refereeId"],
                "role": referee["role"],
                "roleLabel": referee["roleLabel"],
                "shortName": referee["shortName"],
                "nationality": referee["nationality"],
            }
            for referee in data["referees"]
        ]

    elif data_family == "feed_events":
        return [
            unpack_feed_event(match_id=data["matchId"], event=event)
            for event in data["events"]
        ]

    elif data_family == "teamstats":
        return [{**stat, "matchId": data["matchId"]} for stat in data["stats"]]
    elif data_family == "playerstats":
        return [
            {
                **stat,
                "matchId": data["matchId"],
                "teamId": entry["team"]["teamId"],
                "playerId": entry["player"]["playerId"],
            }
            for entry in data["players"]
            for stat in entry["stats"]
        ]
    else:
        raise ValueError(f"unknown data family: {data_family}")


def read_data_from_json(data_path: Path, data_name: str) -> list[dict]:
    """read data from a json file into a python list of dicts"""
    data_list: list[dict] = []
    full_path = data_path / FAMILY_DIRS.get(data_name, data_name)
    for file in full_path.rglob("*.json"):
        with file.open("r") as f:
            data = json.load(f)
            unpacked_data = unpack_json_pattern(data_family=data_name, data=data)
            data_list.extend(unpacked_data)
    return data_list


def load_data_to_duckdb(table_name: str, data: list[dict], schema: str) -> None:
    """load data into duckdb"""
    with db.connect(DB_PATH) as conn:
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        conn.execute(f"DROP TABLE IF EXISTS {schema}.{table_name}")
        data = [{to_snake(key): value for key, value in row.items()} for row in data]
        conn.from_arrow(pa.Table.from_pylist(data)).create(f"{schema}.{table_name}")


def read_data_from_duckdb(query: str) -> list[tuple]:
    with db.connect(DB_PATH) as conn:
        return conn.execute(query).fetchall()


if __name__ == "__main__":
    matches = read_data_from_json(DATA_GLOB, "matches")
    matchdays = read_data_from_json(DATA_GLOB, "matchdays")
    teams = read_data_from_json(DATA_GLOB, "teams")
    standings = read_data_from_json(DATA_GLOB, "standings")
    teamstats = read_data_from_json(DATA_GLOB, "teamstats")
    playerstats = read_data_from_json(DATA_GLOB, "playerstats")
    lineups = read_data_from_json(DATA_GLOB, "lineups")
    lineup_events = read_data_from_json(DATA_GLOB, "lineup_events")
    match_facts = read_data_from_json(DATA_GLOB, "match_facts")
    match_officials = read_data_from_json(DATA_GLOB, "match_officials")
    feed_events = read_data_from_json(DATA_GLOB, "feed_events")
    validate_data(matches, contracts.MatchContract, id_key="matchId")
    load_data_to_duckdb("matches", matches, "raw")
    load_data_to_duckdb("matchdays", matchdays, "raw")
    load_data_to_duckdb("teams", teams, "raw")
    load_data_to_duckdb("standings", standings, "raw")
    load_data_to_duckdb("teamstats", teamstats, "raw")
    load_data_to_duckdb("playerstats", playerstats, "raw")
    load_data_to_duckdb("lineups", lineups, "raw")
    load_data_to_duckdb("lineup_events", lineup_events, "raw")
    load_data_to_duckdb("match_facts", match_facts, "raw")
    load_data_to_duckdb("match_officials", match_officials, "raw")
    load_data_to_duckdb("feed_events", feed_events, "raw")

    counts = {
        name: read_data_from_duckdb(f"SELECT count(*) FROM raw.{name}")[0][0]  # noqa: S608
        for name in (
            "matches",
            "matchdays",
            "teams",
            "standings",
            "teamstats",
            "playerstats",
            "lineups",
            "lineup_events",
            "match_facts",
            "match_officials",
            "feed_events",
        )
    }
    print(f"contract: {counts['matches']} valid, 0 rejected")
    for name, count in counts.items():
        print(f"{name}: {count}")
