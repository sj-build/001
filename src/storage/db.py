"""SQLite database connection and initialization."""
import sqlite3
from pathlib import Path
from src.app.config import get_settings

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

def get_connection() -> sqlite3.Connection:
    settings = get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db() -> None:
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
