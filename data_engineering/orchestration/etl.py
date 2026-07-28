"""Mzansi Rush — Module 2: Orchestration (ETL job).

Loads data_engineering/data/events/events.jsonl into the warehouse
(Module 3). This is Section 9.4 of the report (Extract / Transform /
Load) applied to the actual event log the game now produces.

  Extract   -> read new lines from data_engineering/data/events/events.jsonl
  Transform -> route each event to the right table/columns, upsert
               the Player row, skip malformed lines
  Load      -> write into data_engineering/data/mzansi_rush.db via
               warehouse/schema.sql

Incremental by design: it remembers the byte offset it last read (in
data_engineering/data/events/.etl_offset) so re-running it after more
play sessions only loads the *new* events — this is the batch-processing
job described in Section 9.6, meant to be run periodically (or once per
session). There's no scheduler wired up yet (no Airflow/cron) — see the
README for how this would plug in later, mirroring the orchestration
module of the Data Engineering Zoomcamp.

Usage:
    python3 -m data_engineering.orchestration.etl            # load new events
    python3 -m data_engineering.orchestration.etl --reset    # reprocess everything
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys

from data_engineering.warehouse.db import DB_PATH, get_connection, init_db

EVENTS_FILE = os.path.join("data_engineering", "data", "events", "events.jsonl")
_OFFSET_FILE = os.path.join("data_engineering", "data", "events", ".etl_offset")


def run_etl(events_path: str = EVENTS_FILE, db_path: str = DB_PATH,
            reset: bool = False) -> int:
    if not os.path.exists(events_path):
        print("No events file found yet — play the game first, then re-run this.")
        return 0

    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()

    offset = 0 if reset else _read_offset()
    loaded, skipped = 0, 0

    with open(events_path) as f:
        f.seek(offset)
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            try:
                _load_event(cur, event)
                loaded += 1
            except sqlite3.Error as e:
                print(f"[ETL] skipped event due to DB error: {e}")
                skipped += 1
        new_offset = f.tell()

    conn.commit()
    conn.close()
    _write_offset(new_offset)

    print(f"ETL complete: {loaded} event(s) loaded, {skipped} skipped -> {db_path}")
    return loaded


def _load_event(cur: sqlite3.Cursor, e: dict) -> None:
    etype = e.get("event")
    pid = e.get("player_id")
    ts = e.get("timestamp")

    # Every event carries a player_id -> keep the Player row current.
    # COALESCE means fields not present on this event type (e.g. race_start
    # has no "coins") don't overwrite existing known values with NULL.
    if pid:
        cur.execute(
            """
            INSERT INTO Player (Player_ID, Username, Level, Coins, First_Seen, Last_Seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(Player_ID) DO UPDATE SET
                Username  = COALESCE(excluded.Username, Player.Username),
                Level     = COALESCE(excluded.Level, Player.Level),
                Coins     = COALESCE(excluded.Coins, Player.Coins),
                Last_Seen = excluded.Last_Seen
            """,
            (pid, e.get("username"), e.get("level"), e.get("coins"), ts, ts),
        )

    if etype == "player_login":
        cur.execute(
            "INSERT OR IGNORE INTO Player_Session (Session_ID, Player_ID, Login_Time) "
            "VALUES (?, ?, ?)",
            (e.get("session_id"), pid, ts),
        )

    elif etype == "player_logout":
        cur.execute(
            "UPDATE Player_Session SET Logout_Time = ? WHERE Session_ID = ?",
            (ts, e.get("session_id")),
        )

    elif etype == "race_start":
        cur.execute(
            """
            INSERT OR IGNORE INTO Match
                (Match_ID, Player_ID, Track, Vehicle, Laps, Difficulty, Start_Time, Status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (e.get("match_id"), pid, e.get("track"), e.get("vehicle"),
             e.get("laps"), e.get("difficulty"), ts),
        )

    elif etype == "race_completed":
        cur.execute(
            """
            UPDATE Match
            SET End_Time = ?, Total_Time = ?, Best_Lap = ?, Health_Remaining = ?,
                Status = 'completed'
            WHERE Match_ID = ?
            """,
            (ts, e.get("total_time"), e.get("best_lap"), e.get("health_remaining"),
             e.get("match_id")),
        )

    elif etype in ("checkpoint_reached", "lap_completed", "collision", "telemetry_sample"):
        cur.execute(
            """
            INSERT INTO Telemetry
                (Match_ID, Player_ID, Event_Type, Lap, Checkpoint, Speed, X, Y,
                 Health, Lap_Time, Best_Lap, Kind, Timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (e.get("match_id"), pid, etype, e.get("lap"), e.get("checkpoint"),
             e.get("speed"), e.get("x"), e.get("y"), e.get("health"),
             e.get("lap_time"), e.get("best_lap"), e.get("kind"), ts),
        )

    elif etype in ("vehicle_purchased", "vehicle_upgrade"):
        cur.execute(
            """
            INSERT INTO Vehicle_Transaction
                (Player_ID, Vehicle, Transaction_Type, Stat, Cost, Coins_Remaining, Timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pid, e.get("vehicle"),
                "purchase" if etype == "vehicle_purchased" else "upgrade",
                e.get("stat"),
                e.get("cost", e.get("price")),
                e.get("coins_remaining"),
                ts,
            ),
        )
    # unknown event types are simply not routed anywhere — Player upsert
    # above still ran, so nothing is lost silently without a trace.


def _read_offset() -> int:
    if os.path.exists(_OFFSET_FILE):
        try:
            with open(_OFFSET_FILE) as f:
                return int(f.read().strip() or 0)
        except ValueError:
            return 0
    return 0


def _write_offset(offset: int) -> None:
    with open(_OFFSET_FILE, "w") as f:
        f.write(str(offset))


if __name__ == "__main__":
    run_etl(reset="--reset" in sys.argv)
