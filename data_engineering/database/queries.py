"""Mzansi Rush — example analytics queries (Section 5.7 / 5.8 of the report).

Run after the ETL has loaded some events:
    python3 -m database.queries
"""

from __future__ import annotations

from data_engineering.database.db import get_connection


def leaderboard(conn):
    return conn.execute("SELECT * FROM Leaderboard").fetchall()


def most_popular_vehicles(conn):
    return conn.execute(
        """
        SELECT Vehicle, COUNT(*) AS Times_Raced
        FROM Match
        GROUP BY Vehicle
        ORDER BY Times_Raced DESC
        """
    ).fetchall()


def average_race_time_by_track(conn):
    return conn.execute(
        """
        SELECT Track, ROUND(AVG(Total_Time), 2) AS Avg_Total_Time,
               COUNT(*) AS Races_Completed
        FROM Match
        WHERE Status = 'completed'
        GROUP BY Track
        ORDER BY Avg_Total_Time ASC
        """
    ).fetchall()


def collisions_per_race(conn):
    return conn.execute(
        """
        SELECT m.Match_ID, m.Track, COUNT(t.Event_ID) AS Collisions
        FROM Match m
        LEFT JOIN Telemetry t
               ON t.Match_ID = m.Match_ID AND t.Event_Type = 'collision'
        GROUP BY m.Match_ID
        ORDER BY Collisions DESC
        """
    ).fetchall()


def economy_summary(conn):
    return conn.execute(
        """
        SELECT Transaction_Type, COUNT(*) AS Count, SUM(Cost) AS Total_Coins_Spent
        FROM Vehicle_Transaction
        GROUP BY Transaction_Type
        """
    ).fetchall()


def _print_rows(title, rows):
    print(f"\n-- {title} --")
    if not rows:
        print("  (no data yet)")
        return
    for row in rows:
        print("  " + ", ".join(f"{k}={row[k]}" for k in row.keys()))


if __name__ == "__main__":
    conn = get_connection()
    _print_rows("Leaderboard (best lap per player per track)", leaderboard(conn))
    _print_rows("Most popular vehicles", most_popular_vehicles(conn))
    _print_rows("Average race time by track", average_race_time_by_track(conn))
    _print_rows("Collisions per race", collisions_per_race(conn))
    _print_rows("Economy summary (purchases vs upgrades)", economy_summary(conn))
    conn.close()
