"""Mzansi Rush — Module 3: Data Warehouse (connection + initialization).

Run directly to (re)create the database from schema.sql:
    python3 -m data_engineering.warehouse.db
"""

from __future__ import annotations

import os
import sqlite3

DB_PATH = os.path.join("data_engineering", "data", "mzansi_rush.db")
_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Create all tables/indexes/views if they don't already exist.
    Safe to call every time the game or ETL script starts — it never
    drops or overwrites existing data."""
    conn = get_connection(db_path)
    with open(_SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database ready at {DB_PATH}")
