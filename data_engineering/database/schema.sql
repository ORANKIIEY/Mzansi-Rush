-- Mzansi Rush database schema (SQLite)
--
-- This is the report's Section 8 database design, adapted to what the
-- game actually produces right now (single-player, local events).
-- Tables map directly onto event types written by telemetry/event_logger.py:
--
--   player_login / player_logout      -> Player, Player_Session
--   race_start / race_completed       -> Match
--   checkpoint_reached / lap_completed
--   / collision / telemetry_sample    -> Telemetry
--   vehicle_purchased / vehicle_upgrade -> Vehicle_Transaction
--
-- Using SQLite because it's stdlib (no server, no install) and this is
-- still a genuine relational database with PKs/FKs/constraints — the
-- same schema below runs on PostgreSQL/MySQL with only minor type
-- changes (TEXT -> VARCHAR, AUTOINCREMENT -> SERIAL, etc.) if this ever
-- moves to a real multiplayer backend.

PRAGMA foreign_keys = ON;

-- ── Player ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Player (
    Player_ID   TEXT PRIMARY KEY,
    Username    TEXT,
    Level       INTEGER,
    Coins       INTEGER,
    First_Seen  TEXT,
    Last_Seen   TEXT
);

-- ── Player_Session (Section 8.4.2) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS Player_Session (
    Session_ID   TEXT PRIMARY KEY,
    Player_ID    TEXT NOT NULL,
    Login_Time   TEXT,
    Logout_Time  TEXT,
    FOREIGN KEY (Player_ID) REFERENCES Player(Player_ID)
);

-- ── Match (Section 8.4.3) ───────────────────────────────────────────
-- One row per race. Player_ID here plays the role of Match_Player
-- (Section 8.4.4) since the game is currently single-player — one
-- player per match. When multiplayer is added, split Player_ID out
-- into its own Match_Player table (Match_ID, Player_ID, Position,
-- Score) so a Match can have many players.
CREATE TABLE IF NOT EXISTS Match (
    Match_ID          TEXT PRIMARY KEY,
    Player_ID         TEXT NOT NULL,
    Track             TEXT,
    Vehicle            TEXT,
    Laps              INTEGER,
    Difficulty        TEXT,
    Start_Time        TEXT,
    End_Time          TEXT,
    Total_Time        REAL,
    Best_Lap          REAL,
    Health_Remaining  REAL,
    Status            TEXT DEFAULT 'active',   -- active | completed
    FOREIGN KEY (Player_ID) REFERENCES Player(Player_ID)
);

-- ── Telemetry (Section 8.4.7) ───────────────────────────────────────
-- Sparse by design: each Event_Type only populates the columns that
-- make sense for it (e.g. Checkpoint is only set for checkpoint
-- events, Lap_Time only for lap_completed).
CREATE TABLE IF NOT EXISTS Telemetry (
    Event_ID    INTEGER PRIMARY KEY AUTOINCREMENT,
    Match_ID    TEXT,
    Player_ID   TEXT,
    Event_Type  TEXT NOT NULL,
    Lap         INTEGER,
    Checkpoint  INTEGER,
    Speed       REAL,
    X           REAL,
    Y           REAL,
    Health      REAL,
    Lap_Time    REAL,
    Best_Lap    REAL,
    Kind        TEXT,          -- e.g. collision kind: 'wall' | 'obstacle'
    Timestamp   TEXT NOT NULL,
    FOREIGN KEY (Match_ID)  REFERENCES Match(Match_ID),
    FOREIGN KEY (Player_ID) REFERENCES Player(Player_ID)
);

-- ── Vehicle_Transaction (economy: purchases + upgrades) ─────────────
CREATE TABLE IF NOT EXISTS Vehicle_Transaction (
    Transaction_ID    INTEGER PRIMARY KEY AUTOINCREMENT,
    Player_ID         TEXT NOT NULL,
    Vehicle            TEXT,
    Transaction_Type  TEXT,     -- 'purchase' | 'upgrade'
    Stat              TEXT,     -- upgrade stat, null for purchases
    Cost              INTEGER,
    Coins_Remaining   INTEGER,
    Timestamp         TEXT NOT NULL,
    FOREIGN KEY (Player_ID) REFERENCES Player(Player_ID)
);

-- ── Indexes (Section 6.2 performance requirement) ───────────────────
CREATE INDEX IF NOT EXISTS idx_match_player       ON Match(Player_ID);
CREATE INDEX IF NOT EXISTS idx_telemetry_match     ON Telemetry(Match_ID);
CREATE INDEX IF NOT EXISTS idx_telemetry_player    ON Telemetry(Player_ID);
CREATE INDEX IF NOT EXISTS idx_session_player      ON Player_Session(Player_ID);
CREATE INDEX IF NOT EXISTS idx_vehicle_tx_player    ON Vehicle_Transaction(Player_ID);

-- ── Leaderboard view (Section 8.4.8) ────────────────────────────────
-- Derived, not stored — always reflects the latest completed races.
-- Best lap time per player per track.
CREATE VIEW IF NOT EXISTS Leaderboard AS
SELECT
    m.Player_ID,
    p.Username,
    m.Track,
    MIN(m.Best_Lap)   AS Best_Lap_Time,
    COUNT(*)          AS Races_Completed
FROM Match m
JOIN Player p ON p.Player_ID = m.Player_ID
WHERE m.Status = 'completed'
GROUP BY m.Player_ID, m.Track
ORDER BY Best_Lap_Time ASC;
