"""Mzansi Rush — event logger.

This is the "data collection layer" from the data engineering report
(Section 7.3.6 / 9.3 / Appendix C). It doesn't talk to a server or a
database yet — it just writes one structured JSON object per line
(JSONL) to data/events/events.jsonl every time something notable
happens in the game.

Why JSONL and not straight into a database:
  - It's dependency-free (stdlib only), so it can't break the game.
  - It's an append-only raw event log — exactly the "data lake" /
    "extract" source the ETL pipeline (Section 9.4) is meant to read
    from later. When you build the DB step, you write a small ETL
    script that reads this file and loads it into Player/Match/
    Telemetry tables — you don't have to touch the game code again.

Usage:
    from telemetry.event_logger import EventLogger

    logger = EventLogger(player_id="P-abc123")
    logger.log("race_start", match_id="M-1", track="mzansi_asphalt")
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

EVENTS_DIR = os.path.join("data", "events")
EVENTS_FILE = os.path.join(EVENTS_DIR, "events.jsonl")


class EventLogger:
    """Append-only structured event logger.

    One EventLogger is created per game session (see main.py) and
    passed around via game_data["telemetry"] so any screen (race,
    garage, lobby) can log events without knowing where they end up.
    """

    def __init__(self, player_id: str, session_id: str | None = None,
                 path: str = EVENTS_FILE):
        self.player_id = player_id
        self.session_id = session_id or str(uuid.uuid4())
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def log(self, event_type: str, **fields) -> dict:
        """Write one event. Extra keyword args become extra JSON fields.

        Every event automatically gets: event, player_id, session_id,
        timestamp. Callers add whatever else is relevant, e.g.:
            logger.log("checkpoint_reached", match_id=mid, lap=2, speed=210)
        """
        record = {
            "event": event_type,
            "player_id": self.player_id,
            "session_id": self.session_id,
            "timestamp": _now_iso(),
        }
        record.update(fields)

        try:
            with open(self.path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except OSError as e:
            # Telemetry must never crash the game — log and move on.
            print(f"[Telemetry] failed to write event: {e}")

        return record


def _now_iso() -> str:
    """UTC timestamp, matching the format used in the report's examples
    (e.g. '2026-07-21T09:00:00Z')."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def new_match_id() -> str:
    """Generate a unique ID for a single race, analogous to Match_ID
    in the report's database design (Section 8.4.3)."""
    return f"M-{uuid.uuid4().hex[:12]}"
