import json
from pathlib import Path

import duckdb as db
import pyarrow as pa

# configs
DATA_GLOB = Path("data")
DB_PATH = Path("data/dawri.duckdb")


def read_data_from_json(data_path: Path, data_name: str) -> dict[str, pa.Table]:
    """read data from a json file into a duckdb table"""
    full_path = data_path / data_name
    for file in full_path.glob("*.json"):
        with file.open("r") as f:
            data = json.load(f)
            data_table = pa.Table.from_pylist(data[data_name])
    return {data_name: data_table}


def load_data_to_duckdb(data_dict: dict[str, pa.Table], schema: str) -> None:
    with db.connect(DB_PATH) as conn:
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        for data_name, data_table in data_dict.items():
            conn.execute(f"""
            DROP TABLE IF EXISTS {schema}.{data_name}
            """)
            conn.from_arrow(data_table).create(f"{schema}.{data_name}")


#  i want to pass sql query to read data from duckdb
def read_data_from_duckdb(query: str) -> list[tuple]:
    with db.connect(DB_PATH) as conn:
        return conn.execute(query).fetchall()


if __name__ == "__main__":
    matches = read_data_from_json(DATA_GLOB, "matches")
    load_data_to_duckdb(matches, "raw")
    sql_query = """
    SELECT count(*) FROM raw.matches
    """
    print(f"matches: {read_data_from_duckdb(sql_query)[0][0]}")
