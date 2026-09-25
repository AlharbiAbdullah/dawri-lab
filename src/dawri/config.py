import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("DAWRI_DATA_DIR", ROOT / "data"))
DB_PATH: Path = DATA_DIR / "dawri.duckdb"
DBT_DIR: Path = ROOT / "dbt"
LOG_PATH: Path = ROOT / "logs" / "dawri.log"

BASE_URL: str = "https://api-sdp.spl.com.sa/v1/spl/football"
REQUEST_GAP: float = 0.25
SEASONS: dict[str, str] = {
    "2025/2026": "0de9cda0d297418699a8357a8825d46c",
    "2026/2027": "3677a75aaa514e43b2840e7fa367c91d",
}
LIVE_SEASON: str = "2026/2027"
