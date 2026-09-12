"""
memory.py
---------
Manages per-user conversation memory so the chatbot remembers:
  - the user's name (once given)
  - previous questions and answers
  - the running context of the conversation

We key memory by a `session_id` (sent from the frontend, generated once per
browser tab and stored in React state). History and user names are stored in
`chat_memory.db` (SQLite) so conversations survive backend restarts.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from langchain.memory import ConversationBufferMemory


DATABASE_PATH = Path(__file__).with_name("chat_memory.db")
_db_lock = Lock()


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _initialise_database() -> None:
    with _connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_name TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)"
        )


def _load_turns(session_id: str) -> list[tuple[str, str]]:
    _initialise_database()
    with _connection() as connection:
        rows = connection.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [(row["role"], row["content"]) for row in rows]


def get_memory(session_id: str) -> ConversationBufferMemory:
    """Build a ConversationBufferMemory loaded from the database.

    Kept for compatibility; new callers should use get_chat_history_text.
    """
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
    )
    for role, content in _load_turns(session_id):
        if role == "human":
            memory.chat_memory.add_user_message(content)
        else:
            memory.chat_memory.add_ai_message(content)
    return memory


def save_turn(session_id: str, user_message: str, bot_response: str) -> None:
    """Persist a user/bot turn into that session's history."""
    with _db_lock:
        _initialise_database()
        now = datetime.now(timezone.utc).isoformat()
        with _connection() as connection:
            connection.executemany(
                """
                INSERT INTO messages (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (session_id, "human", user_message, now),
                    (session_id, "ai", bot_response, now),
                ],
            )


def get_chat_history_text(session_id: str) -> str:
    """Return the conversation so far as plain text, for injecting into
    the LLM prompt."""
    lines = []
    for role, content in _load_turns(session_id):
        speaker = "User" if role == "human" else "Assistant"
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def set_user_name(session_id: str, name: str) -> None:
    with _db_lock:
        _initialise_database()
        with _connection() as connection:
            connection.execute(
                """
                INSERT INTO sessions (session_id, user_name) VALUES (?, ?)
                ON CONFLICT(session_id)
                DO UPDATE SET user_name = excluded.user_name
                """,
                (session_id, name),
            )


def get_user_name(session_id: str) -> Optional[str]:
    _initialise_database()
    with _connection() as connection:
        row = connection.execute(
            "SELECT user_name FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return row["user_name"]


def clear_session(session_id: str) -> None:
    with _db_lock:
        _initialise_database()
        with _connection() as connection:
            connection.execute(
                "DELETE FROM messages WHERE session_id = ?", (session_id,))
            connection.execute(
                "DELETE FROM sessions WHERE session_id = ?", (session_id,))


# ---------------------------------------------------------------------------
# Admin / analytics helpers
# ---------------------------------------------------------------------------
def get_chat_stats() -> dict:
    """Aggregate chat usage stats for the admin dashboard."""
    _initialise_database()
    with _db_lock:
        with _connection() as connection:
            sessions = connection.execute(
                "SELECT COUNT(*) FROM sessions").fetchone()[0]
            human = connection.execute(
                "SELECT COUNT(*) FROM messages WHERE role = 'human'").fetchone()[0]
            ai = connection.execute(
                "SELECT COUNT(*) FROM messages WHERE role = 'ai'").fetchone()[0]
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            recent = connection.execute(
                "SELECT COUNT(*) FROM messages WHERE created_at >= ?",
                (cutoff,),
            ).fetchone()[0]
    return {
        "total_sessions": sessions,
        "total_user_messages": human,
        "total_bot_messages": ai,
        "total_chat_turns": min(human, ai),
        "messages_last_7_days": recent,
    }


def list_sessions(limit: int = 50) -> list[dict]:
    """Recent sessions with message count and last-message preview."""
    _initialise_database()
    with _db_lock:
        with _connection() as connection:
            rows = connection.execute(
                """
                SELECT s.session_id, s.user_name,
                       COUNT(m.id) AS message_count,
                       MAX(m.created_at) AS updated_at
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.session_id
                GROUP BY s.session_id
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    result = []
    for row in rows:
        result.append({
            "session_id": row["session_id"],
            "user_name": row["user_name"],
            "message_count": row["message_count"],
            "updated_at": row["updated_at"],
        })
    return result


def get_history(session_id: str) -> list[dict]:
    """Full conversation history for a session, oldest first."""
    _initialise_database()
    with _connection() as connection:
        rows = connection.execute(
            "SELECT role, content, created_at FROM messages "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [
        {
            "role": "user" if row["role"] == "human" else "bot",
            "text": row["content"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_user_messages() -> list[str]:
    """All user (human-role) messages, for top-products analysis."""
    _initialise_database()
    with _connection() as connection:
        rows = connection.execute(
            "SELECT content FROM messages WHERE role = 'human'").fetchall()
    return [row["content"] for row in rows]