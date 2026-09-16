import json
from pathlib import Path

import duckdb as db
import pyarrow as pa
from pydantic import BaseModel, ValidationError
from pydantic.alias_generators import to_snake

import contracts

# configs
DATA_GLOB = Path("data")
DB_PATH = Path("data/dawri.duckdb")


def validate_data(data: list, contract: type[BaseModel], id_key: str) -> None:
    for row in data:
        try:
            contract.model_validate(row)
        except ValidationError as e:
            print(f"error {row[id_key]}:{e.errors()}")
            raise SystemExit(1)


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
    full_path = data_path / data_name
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
    validate_data(matches, contracts.MatchContract, id_key="matchId")
    load_data_to_duckdb("matches", matches, "raw")
    load_data_to_duckdb("matchdays", matchdays, "raw")
    load_data_to_duckdb("teams", teams, "raw")
    load_data_to_duckdb("standings", standings, "raw")
    load_data_to_duckdb("teamstats", teamstats, "raw")
    load_data_to_duckdb("playerstats", playerstats, "raw")

    counts = {
        name: read_data_from_duckdb(f"SELECT count(*) FROM raw.{name}")[0][0]  # noqa: S608
        for name in (
            "matches",
            "matchdays",
            "teams",
            "standings",
            "teamstats",
            "playerstats",
        )
    }
    print(f"contract: {counts['matches']} valid, 0 rejected")
    for name, count in counts.items():
        print(f"{name}: {count}")
