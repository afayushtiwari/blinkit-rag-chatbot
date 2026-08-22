"""Persistent conversation memory for BlinkBot.

The data is keyed by the browser session ID and stored in SQLite, so the
assistant remembers the same visitor after a refresh or a backend restart.
"""

from typing import Optional

import session_store


def save_turn(session_id: str, user_message: str, bot_response: str) -> None:
    session_store.save_message(session_id, "user", user_message)
    session_store.save_message(session_id, "bot", bot_response)


def get_chat_history_text(session_id: str) -> str:
    """Return the most recent persisted turns for the RAG prompt."""
    return session_store.get_history_text(session_id)


def get_session_messages(session_id: str) -> list[dict]:
    """Return persisted messages in the frontend chat shape."""
    return session_store.get_messages(session_id)


def set_user_name(session_id: str, name: str) -> None:
    session_store.set_user_name(session_id, name)


def get_user_name(session_id: str) -> Optional[str]:
    return session_store.get_user_name(session_id)


def clear_session(session_id: str) -> None:
    """Clear remembered name and chat history, while retaining the cart."""
    session_store.clear_session_memory(session_id)
