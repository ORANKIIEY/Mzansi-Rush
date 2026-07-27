"""Quick sanity-check tool for the event log.

Not part of the game itself — run it from the command line after
playing a bit to see what's been captured:

    python3 -m telemetry.event_report

This is a tiny preview of the "Analytics Layer" (Section 7.3.9 /
11.5 of the report). Later, a real ETL job would read events.jsonl,
clean/aggregate it, and load it into the database instead of just
printing a summary.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

from telemetry.event_logger import EVENTS_FILE


def load_events(path: str = EVENTS_FILE) -> list[dict]:
    if not os.path.exists(path):
        return []
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # skip corrupt lines rather than crash
    return events


def summarize(events: list[dict]) -> None:
    if not events:
        print("No events logged yet. Play a race, then run this again.")
        return

    print(f"Total events: {len(events)}\n")

    by_type = Counter(e.get("event", "unknown") for e in events)
    print("Events by type:")
    for event_type, count in by_type.most_common():
        print(f"  {event_type:<20} {count}")

    matches = {e["match_id"] for e in events if "match_id" in e}
    print(f"\nRaces started: {by_type.get('race_start', 0)}")
    print(f"Races completed: {by_type.get('race_completed', 0)}")
    print(f"Unique match IDs seen: {len(matches)}")

    completions = [e for e in events if e.get("event") == "race_completed"]
    if completions:
        avg_total = sum(e.get("total_time", 0) for e in completions) / len(completions)
        best = min((e.get("best_lap", float("inf")) for e in completions), default=None)
        print(f"\nAverage total race time: {avg_total:.1f}s")
        if best is not None and best != float("inf"):
            print(f"Best single lap across all races: {best:.1f}s")

    purchases = [e for e in events if e.get("event") == "vehicle_purchased"]
    upgrades = [e for e in events if e.get("event") == "vehicle_upgrade"]
    if purchases or upgrades:
        print(f"\nVehicle purchases: {len(purchases)}")
        print(f"Vehicle upgrades: {len(upgrades)}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else EVENTS_FILE
    summarize(load_events(path))
