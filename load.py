import hashlib
import json
from pathlib import Path

import duckdb as db
import pyarrow as pa
from pydantic.alias_generators import to_snake

import contracts

DATA_GLOB = Path("data")
DB_PATH = Path("data/dawri.duckdb")
FAMILY_DIRS = {
    "lineup_events": "lineups",
    "match_facts": "matchfacts",
    "match_officials": "matchfacts",
    "feed_events": "feed",
}
SEASON_GRAIN = {"matches", "matchdays", "teams", "standings"}
TABLES = (
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


def feed_event_side(event: dict) -> str | None:
    if event.get("home") is not None:
        return "home"
    if event.get("away") is not None:
        return "away"
    return None


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
    if data_family == "matchdays":
        return data["matchdays"]
    if data_family == "teams":
        return data["teams"]
    if data_family == "standings":
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
    if data_family == "lineups":
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
    if data_family == "lineup_events":
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
    if data_family == "match_facts":
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
    if data_family == "match_officials":
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
    if data_family == "feed_events":
        return [
            unpack_feed_event(match_id=data["matchId"], event=event)
            for event in data["events"]
        ]
    if data_family == "teamstats":
        return [{**stat, "matchId": data["matchId"]} for stat in data["stats"]]
    if data_family == "playerstats":
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
    raise ValueError(f"unknown data family: {data_family}")


def classify_matches(rows: list[dict]) -> tuple[list[dict], int, int, int]:
    keep: list[dict] = []
    valid = 0
    rejected = 0
    skipped = 0
    for row in rows:
        if row.get("status") != "FINISHED":
            skipped += 1
            keep.append(row)
            continue
        if contracts.is_valid(row):
            valid += 1
            keep.append(row)
        else:
            rejected += 1
    return keep, valid, rejected, skipped


def snake_rows(rows: list[dict], season_id: str) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        snaked = {
            to_snake(key): value
            for key, value in row.items()
            if to_snake(key) != "season_id"
        }
        out.append({"season_id": season_id, **snaked})
    return out


def season_id_from_path(path: Path, family_root: Path) -> str:
    relative = path.relative_to(family_root)
    if len(relative.parts) == 1:
        return relative.stem
    return relative.parts[0]


def season_id_from_relative(relative: str) -> str:
    parts = Path(relative).parts
    if len(parts) == 2:
        return Path(parts[1]).stem
    return parts[1]


def match_id_from_path(path: Path) -> str:
    return f"spl::Football_Match::{path.stem}"


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def family_root(table_name: str) -> Path:
    return DATA_GLOB / FAMILY_DIRS.get(table_name, table_name)


def ensure_ledger(conn: db.DuckDBPyConnection) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS raw._load_ledger (
            file_path VARCHAR,
            table_name VARCHAR,
            content_sha256 VARCHAR,
            PRIMARY KEY (file_path, table_name)
        )
        """
    )


def reset_tables_without_ledger(conn: db.DuckDBPyConnection) -> None:
    urn_season = False
    if table_exists(conn, "matches"):
        urn_season = (
            conn.execute(
                "SELECT 1 FROM raw.matches WHERE season_id LIKE '%::%' LIMIT 1"
            ).fetchone()
            is not None
        )
    row = conn.execute("SELECT count(*) FROM raw._load_ledger").fetchone()
    ledger_empty = row is None or int(row[0]) == 0
    if not urn_season and not ledger_empty:
        return
    for table_name in TABLES:
        conn.execute(f"DROP TABLE IF EXISTS raw.{table_name} CASCADE")
    if urn_season:
        conn.execute("DELETE FROM raw._load_ledger")


def table_exists(conn: db.DuckDBPyConnection, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'raw' AND table_name = ?
        """,
        [table_name],
    ).fetchone()
    return row is not None


def ledger_digest(
    conn: db.DuckDBPyConnection, file_path: str, table_name: str
) -> str | None:
    row = conn.execute(
        """
        SELECT content_sha256
        FROM raw._load_ledger
        WHERE file_path = ? AND table_name = ?
        """,
        [file_path, table_name],
    ).fetchone()
    if row is None:
        return None
    return str(row[0])


def upsert_ledger(
    conn: db.DuckDBPyConnection, file_path: str, table_name: str, digest: str
) -> None:
    conn.execute(
        """
        DELETE FROM raw._load_ledger
        WHERE file_path = ? AND table_name = ?
        """,
        [file_path, table_name],
    )
    conn.execute(
        """
        INSERT INTO raw._load_ledger (file_path, table_name, content_sha256)
        VALUES (?, ?, ?)
        """,
        [file_path, table_name, digest],
    )


def as_arrow(rows: list[dict]) -> pa.Table:
    table = pa.Table.from_pylist(rows)
    for index, field in enumerate(table.schema):
        if pa.types.is_timestamp(field.type) or pa.types.is_date(field.type):
            table = table.set_column(index, field.name, table[index].cast(pa.string()))
    return table


def delete_file_rows(
    conn: db.DuckDBPyConnection, table_name: str, season_id: str, path: Path
) -> None:
    if table_name not in TABLES:
        raise ValueError(f"unknown table: {table_name}")
    if table_name in SEASON_GRAIN:
        conn.execute(
            f"DELETE FROM raw.{table_name} WHERE season_id = ?",  # noqa: S608
            [season_id],
        )
        return
    conn.execute(
        f"DELETE FROM raw.{table_name} WHERE season_id = ? AND match_id = ?",  # noqa: S608
        [season_id, match_id_from_path(path)],
    )


def insert_rows(conn: db.DuckDBPyConnection, table_name: str, rows: list[dict]) -> None:
    if table_name not in TABLES:
        raise ValueError(f"unknown table: {table_name}")
    if not rows:
        return
    table = as_arrow(rows)
    conn.register("_batch", table)
    if not table_exists(conn, table_name):
        conn.execute(f"CREATE TABLE raw.{table_name} AS SELECT * FROM _batch")  # noqa: S608
        conn.unregister("_batch")
        return
    existing = {
        str(row[0]) for row in conn.execute(f"DESCRIBE raw.{table_name}").fetchall()
    }
    conn.execute(
        "CREATE OR REPLACE TEMP TABLE _batch_types AS SELECT * FROM _batch LIMIT 0"
    )
    for column, duck_type, *_ in conn.execute("DESCRIBE _batch_types").fetchall():
        if str(column) not in existing:
            conn.execute(
                f'ALTER TABLE raw.{table_name} ADD COLUMN "{column}" {duck_type}'
            )
    conn.execute(f"INSERT INTO raw.{table_name} BY NAME SELECT * FROM _batch")  # noqa: S608
    conn.unregister("_batch")


def load_family(conn: db.DuckDBPyConnection, table_name: str) -> int:
    root = family_root(table_name)
    loaded = 0
    if not root.exists():
        return 0
    for path in sorted(root.rglob("*.json")):
        relative = path.relative_to(DATA_GLOB).as_posix()
        digest = file_digest(path)
        if ledger_digest(conn, relative, table_name) == digest:
            continue
        payload = json.loads(path.read_bytes())
        rows = unpack_json_pattern(data_family=table_name, data=payload)
        if table_name == "matches":
            rows, _, _, _ = classify_matches(rows)
        season_id = season_id_from_path(path, root)
        if table_exists(conn, table_name):
            delete_file_rows(conn, table_name, season_id, path)
        insert_rows(conn, table_name, snake_rows(rows, season_id))
        upsert_ledger(conn, relative, table_name, digest)
        loaded += 1
    return loaded


def contract_from_files() -> tuple[int, int, int]:
    valid = rejected = skipped = 0
    matches_dir = DATA_GLOB / "matches"
    if not matches_dir.exists():
        return 0, 0, 0
    for path in sorted(matches_dir.glob("*.json")):
        rows = json.loads(path.read_bytes())["matches"]
        _, file_valid, file_rejected, file_skipped = classify_matches(rows)
        valid += file_valid
        rejected += file_rejected
        skipped += file_skipped
    return valid, rejected, skipped


def prune_missing(conn: db.DuckDBPyConnection) -> None:
    rows = conn.execute("SELECT file_path, table_name FROM raw._load_ledger").fetchall()
    for file_path, table_name in rows:
        path = DATA_GLOB / str(file_path)
        if path.exists():
            continue
        season_id = season_id_from_relative(str(file_path))
        if table_exists(conn, str(table_name)):
            delete_file_rows(conn, str(table_name), season_id, path)
        conn.execute(
            """
            DELETE FROM raw._load_ledger
            WHERE file_path = ? AND table_name = ?
            """,
            [file_path, table_name],
        )


def count_table(conn: db.DuckDBPyConnection, table_name: str) -> int:
    if table_name not in TABLES:
        raise ValueError(f"unknown table: {table_name}")
    if not table_exists(conn, table_name):
        return 0
    row = conn.execute(f"SELECT count(*) FROM raw.{table_name}").fetchone()  # noqa: S608
    if row is None:
        return 0
    return int(row[0])


def main() -> None:
    with db.connect(DB_PATH) as conn:
        ensure_ledger(conn)
        reset_tables_without_ledger(conn)
        loaded = 0
        for table_name in TABLES:
            loaded += load_family(conn, table_name)
        prune_missing(conn)
        valid, rejected, skipped = contract_from_files()
        print(f"loaded: {loaded} files")
        print(f"contract: {valid} valid, {rejected} rejected")
        print(f"skipped: {skipped} unplayed")
        for table_name in TABLES:
            print(f"{table_name}: {count_table(conn, table_name)}")


if __name__ == "__main__":
    main()
