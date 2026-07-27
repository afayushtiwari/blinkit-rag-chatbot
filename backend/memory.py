"""
memory.py
---------
Manages per-user conversation memory so the chatbot remembers:
  - the user's name (once given)
  - previous questions and answers
  - the running context of the conversation

We key memory by a `session_id` (sent from the frontend, generated once per
browser tab and stored in React state). Each session gets its own
LangChain ConversationBufferMemory instance, kept in an in-memory dict.

NOTE: This in-memory store resets when the backend restarts. For a real
production deployment you'd back this with Redis or a database, but for a
college demo project, in-process memory is sufficient and easy to explain.
"""

from typing import Dict, Optional
from langchain.memory import ConversationBufferMemory

# session_id -> ConversationBufferMemory
_session_memories: Dict[str, ConversationBufferMemory] = {}

# session_id -> user's name (once they mention it)
_session_user_names: Dict[str, str] = {}


def get_memory(session_id: str) -> ConversationBufferMemory:
    """Return the ConversationBufferMemory for a session, creating one if
    it doesn't exist yet."""
    if session_id not in _session_memories:
        _session_memories[session_id] = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
        )
    return _session_memories[session_id]


def save_turn(session_id: str, user_message: str, bot_response: str) -> None:
    """Persist a user/bot turn into that session's memory buffer."""
    memory = get_memory(session_id)
    memory.chat_memory.add_user_message(user_message)
    memory.chat_memory.add_ai_message(bot_response)


def get_chat_history_text(session_id: str) -> str:
    """Return the conversation so far as plain text, for injecting into
    the LLM prompt."""
    memory = get_memory(session_id)
    lines = []
    for msg in memory.chat_memory.messages:
        role = "User" if msg.type == "human" else "Assistant"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


def set_user_name(session_id: str, name: str) -> None:
    _session_user_names[session_id] = name


def get_user_name(session_id: str) -> Optional[str]:
    return _session_user_names.get(session_id)


def clear_session(session_id: str) -> None:
    _session_memories.pop(session_id, None)
    _session_user_names.pop(session_id, None)
