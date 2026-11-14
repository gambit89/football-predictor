
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent.parent / "predictions.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fixture_id INTEGER,
                match_date TEXT,
                home_team TEXT,
                away_team TEXT,
                prediction_json TEXT,
                created_at TEXT
            )
        """)


def save_prediction(match, prediction):
    init_db()

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO predictions (
                fixture_id,
                match_date,
                home_team,
                away_team,
                prediction_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            match.get("fixture_id"),
            match.get("date"),
            match.get("home"),
            match.get("away"),
            json.dumps(prediction, ensure_ascii=False),
            datetime.now(timezone.utc).isoformat()
        ))


def get_predictions(limit=100):
    init_db()

    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT fixture_id, match_date, home_team,
                   away_team, prediction_json, created_at
            FROM predictions
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

        return cursor.fetchall()
