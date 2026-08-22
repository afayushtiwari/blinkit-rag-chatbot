"""SQLite persistence for anonymous BlinkBot sessions.

The browser owns an opaque session ID. This module stores only the associated
cart, chat turns, and optional display name - never passwords or payment data.
"""

import sqlite3
from pathlib import Path
from threading import Lock


DATABASE_PATH = Path(__file__).with_name("session_data.db")
_initialise_lock = Lock()
_initialised = False


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_database() -> None:
    global _initialised
    if _initialised:
        return

    with _initialise_lock:
        if _initialised:
            return
        with _connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS session_profiles (
                    session_id TEXT PRIMARY KEY,
                    user_name TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS cart_items (
                    session_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    PRIMARY KEY (session_id, product_id)
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'bot')),
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_chat_messages_session
                    ON chat_messages(session_id, id);
                """
            )
        _initialised = True


def get_cart_quantities(session_id: str) -> dict[str, int]:
    _ensure_database()
    with _connection() as connection:
        rows = connection.execute(
            "SELECT product_id, quantity FROM cart_items WHERE session_id = ?",
            (session_id,),
        ).fetchall()
    return {row["product_id"]: row["quantity"] for row in rows}


def add_cart_quantity(session_id: str, product_id: str, quantity: int) -> None:
    _ensure_database()
    with _connection() as connection:
        connection.execute(
            """
            INSERT INTO cart_items (session_id, product_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id, product_id)
            DO UPDATE SET quantity = cart_items.quantity + excluded.quantity
            """,
            (session_id, product_id, quantity),
        )


def set_cart_quantity(session_id: str, product_id: str, quantity: int) -> None:
    _ensure_database()
    with _connection() as connection:
        if quantity <= 0:
            connection.execute(
                "DELETE FROM cart_items WHERE session_id = ? AND product_id = ?",
                (session_id, product_id),
            )
        else:
            connection.execute(
                """
                INSERT INTO cart_items (session_id, product_id, quantity)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id, product_id)
                DO UPDATE SET quantity = excluded.quantity
                """,
                (session_id, product_id, quantity),
            )


def remove_cart_item(session_id: str, product_id: str) -> bool:
    _ensure_database()
    with _connection() as connection:
        result = connection.execute(
            "DELETE FROM cart_items WHERE session_id = ? AND product_id = ?",
            (session_id, product_id),
        )
    return result.rowcount > 0


def clear_cart(session_id: str) -> None:
    _ensure_database()
    with _connection() as connection:
        connection.execute("DELETE FROM cart_items WHERE session_id = ?", (session_id,))


def save_message(session_id: str, role: str, content: str) -> None:
    _ensure_database()
    with _connection() as connection:
        connection.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )


def get_messages(session_id: str, limit: int = 30) -> list[dict]:
    _ensure_database()
    with _connection() as connection:
        rows = connection.execute(
            """
            SELECT role, content FROM (
                SELECT id, role, content
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
            ) ORDER BY id ASC
            """,
            (session_id, limit),
        ).fetchall()
    return [{"role": row["role"], "text": row["content"], "products": []} for row in rows]


def get_history_text(session_id: str, limit: int = 16) -> str:
    messages = get_messages(session_id, limit)
    labels = {"user": "User", "bot": "Assistant"}
    return "\n".join(f"{labels[message['role']]}: {message['text']}" for message in messages)


def set_user_name(session_id: str, name: str) -> None:
    _ensure_database()
    with _connection() as connection:
        connection.execute(
            """
            INSERT INTO session_profiles (session_id, user_name, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id)
            DO UPDATE SET user_name = excluded.user_name, updated_at = CURRENT_TIMESTAMP
            """,
            (session_id, name),
        )


def get_user_name(session_id: str) -> str | None:
    _ensure_database()
    with _connection() as connection:
        row = connection.execute(
            "SELECT user_name FROM session_profiles WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return row["user_name"] if row else None


def clear_session_memory(session_id: str) -> None:
    _ensure_database()
    with _connection() as connection:
        connection.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        connection.execute("DELETE FROM session_profiles WHERE session_id = ?", (session_id,))
