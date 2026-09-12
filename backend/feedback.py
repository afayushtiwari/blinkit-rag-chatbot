"""SQLite-backed chat feedback service.

Stores per-message thumbs (1 = down, 2 = up) and an optional 1-5 star rating
so the demo can show an admin analytics view and the frontend can display
👍/👎 confirmations.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


DATABASE_PATH = Path(__file__).with_name("feedback.db")
_db_lock = Lock()


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _initialise_database() -> None:
    with _connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_feedback (
                message_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                vote INTEGER NOT NULL,
                stars INTEGER NOT NULL DEFAULT 0,
                feedback TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_feedback(
    message_id: str,
    session_id: str,
    vote: int,
    stars: int = 0,
    feedback: str = "",
) -> dict:
    """Upsert feedback for a single chat message.

    `vote` should be 1 (thumbs down) or 2 (thumbs up); `stars` an optional
    1-5 rating (0 = not rated). `feedback` is an optional free-text note.
    Returns the stored record.
    """
    stars = 0 if stars is None else int(stars)
    stars = min(max(stars, 0), 5)
    feedback = (feedback or "").strip()[:500]
    _initialise_database()
    with _db_lock:
        with _connection() as connection:
            connection.execute(
                """
                INSERT INTO chat_feedback (message_id, session_id, vote, stars, feedback, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id)
                DO UPDATE SET
                    vote = excluded.vote,
                    stars = excluded.stars
                """,
                (message_id, session_id, vote, stars, feedback, _now()),
            )
    return {"message_id": message_id, "vote": vote, "stars": stars, "feedback": feedback}


def get_feedback_stats() -> dict:
    """Aggregate stats for the admin / demo dashboard."""
    _initialise_database()
    with _db_lock:
        with _connection() as connection:
            total = connection.execute("SELECT COUNT(*) FROM chat_feedback").fetchone()[0]
            votes = connection.execute("SELECT SUM(vote) FROM chat_feedback").fetchone()[0]
            thumbs_up = connection.execute(
                "SELECT COUNT(*) FROM chat_feedback WHERE vote = 2"
            ).fetchone()[0]
            thumbs_down = connection.execute(
                "SELECT COUNT(*) FROM chat_feedback WHERE vote = 1"
            ).fetchone()[0]
            starred = connection.execute(
                "SELECT AVG(stars) FROM chat_feedback WHERE stars > 0"
            ).fetchone()[0]
            stars_total = connection.execute(
                "SELECT COUNT(*) FROM chat_feedback WHERE stars > 0"
            ).fetchone()[0]

    satisfied = thumbs_up + thumbs_down
    return {
        "total_feedbacks": total,
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "satisfaction_pct": (
            round(thumbs_up / max(satisfied, 1) * 100, 1)
            if satisfied else 0
        ),
        "average_stars": round(float(starred or 0), 2) if stars_total else 0,
        "starred_count": stars_total,
        "raw_votes": votes or 0,
    }


def list_recent(limit: int = 50) -> list:
    """Return the latest feedback entries for the admin page."""
    _initialise_database()
    with _db_lock:
        with _connection() as connection:
            rows = connection.execute(
                "SELECT * FROM chat_feedback ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]