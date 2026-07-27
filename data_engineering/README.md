# data_engineering/

This folder contains the entire data engineering side of Mzansi Rush —
event logging, the database, and the ETL pipeline — kept separate from
the game/UI code so it can be developed independently.

```
data_engineering/
├── telemetry/          # Step 1: capture structured events from gameplay
│   ├── event_logger.py     EventLogger class — writes JSONL events
│   └── event_report.py     CLI: quick summary of the raw event log
│
├── database/            # Step 2: turn events into a real database
│   ├── schema.sql           table definitions (Player, Match, Telemetry, ...)
│   ├── db.py                connect / initialize the SQLite database
│   ├── etl.py                incremental ETL: events.jsonl -> database
│   └── queries.py           example analytics queries (leaderboard, etc.)
│
└── data/                 # generated at runtime — gitignored, not source
    ├── events/events.jsonl      raw event log
    └── mzansi_rush.db            SQLite database
```

## How it connects to the game (for whoever's on UI/gameplay)

The data engineering code does **not** live inside `game/` or `ui/`.
It only gets called from three small hook points, so there's minimal
overlap if you're editing those files at the same time:

| File | What was added |
|---|---|
| `main.py` | Creates one `EventLogger` per game session; logs `player_login` / `player_logout` |
| `game/race.py` | Logs `race_start`, `checkpoint_reached`, `lap_completed`, `race_completed`, `collision`, `telemetry_sample` |
| `ui/garage.py` | Logs `vehicle_purchased`, `vehicle_upgrade` |

Everywhere else, the game just does `game_data.get("telemetry")` and
calls `.log(event_name, **fields)` — if `telemetry` isn't set for some
reason, those calls are guarded and skipped, so the game never breaks
because of this folder.

## Running it

```bash
# 1. Play the game normally — events are written automatically
python3 main.py

# 2. Load new events into the database (safe to re-run any time,
#    only loads what's new since the last run)
python3 -m data_engineering.database.etl

# 3. See real analytics from your own play data
python3 -m data_engineering.database.queries

# (optional) quick sanity check of the raw event log itself
python3 -m data_engineering.telemetry.event_report
```

## Design notes

- **SQLite**, not Postgres/MySQL — zero install, zero server, still a
  real relational DB with PKs/FKs/constraints. `schema.sql` ports to
  Postgres/MySQL with minor type changes if this becomes a real
  multiplayer backend later.
- **JSONL event log as the source of truth for raw events** — the ETL
  reads from `data_engineering/data/events/events.jsonl`, so the
  database can always be rebuilt from scratch (`--reset` flag) without
  losing anything.
- **Everything under `data_engineering/data/` is generated, not
  source** — it's in `.gitignore`. Don't hand-edit it.
