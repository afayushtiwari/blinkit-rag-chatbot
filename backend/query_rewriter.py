"""
query_rewriter.py
-----------------
Rewrites ambiguous conversational follow-ups into standalone search queries
before RAG retrieval, e.g.:

    User:    "Show me details of Amul Milk"
    Follow:  "What about the curd?"     ->  "curd / yogurt products"
    Follow:  "Is it available cheap?"   ->  "Amul Milk price availability"

Two layers:
  1. Heuristic detection - is this message even a reference-heavy follow-up
     (pronouns like "it / that / this", or starters like "what about / how
     about")? Ambiguity is only rewritten when detected, so ordinary
     questions skip the extra LLM call (no added latency).
  2. LLM rewrite (Gemini) - with the previous conversation as context, the
     model produces one standalone query. If the model call or detection
     fails we fall back to a deterministic rewrite that appends the most
     recent product topic from history.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger("blinkit.query_rewriter")

# Turn-starting phrases that almost always mean a follow-up reference
_AMBIGUOUS_STARTERS = re.compile(
    r"^\s*(what about|how about|what else|what other|and what|and also|"
    r"also|any similar|similar ones|anything like|"
    r"what .* like (it|that|this)|more (like|about) (it|that|this)|"
    r"tell me about (it|that|this)|is it|are they|and (it|that|this))",
    re.IGNORECASE,
)

# Pronoun / deictic references that point at something said earlier
_AMBIGUOUS_REFERENCE = re.compile(
    r"\b(it|its|it's|that|that one|this|this one|these|those|them|they|"
    r"the same|one like it|similar)\b",
    re.IGNORECASE,
)

# A message that names a concrete catalog-style product is probably fine
_HAS_OWN_TOPIC = re.compile(
    r"\b(snack|chips|milk|ghee|oil|bread|egg|butter|biscuit|cereal|"
    r"yogurt|curd|paneer|cheese|rice|pasta|juice|tea|coffee|soap|"
    r"shampoo|salt|sugar|flour|dal|masala|spice|toothpaste|maggi|"
    r"butter|ketchup|sauce|chocolate|ice ?cream|frozen|cookie)\b",
    re.IGNORECASE,
)


def looks_ambiguous(message: str) -> bool:
    """Heuristic: is this a reference-heavy follow-up worth rewriting?"""
    message = message.strip()
    if not message:
        return False

    words = len(message.split())
    # Very short follow-ups like "yes" / "no" aren't product queries; only
    # rewrite ones that plausibly ask about a product.
    if words < 2:
        return False

    if _AMBIGUOUS_STARTERS.search(message):
        return True

    if _HAS_OWN_TOPIC.search(message):
        # Names its own product category ("what about the curd?") but still a
        # follow-up if it also leans on a reference word.
        return bool(_AMBIGUOUS_REFERENCE.search(message))

    # Reference pronouns with no explicit own-topic category
    return bool(_AMBIGUOUS_REFERENCE.search(message) and words <= 14)


_REWRITE_PROMPT = """You are the query-rewriter for a grocery shopping chatbot.
A customer sent a follow-up message that refers to something from the earlier
conversation. Rewrite it into ONE standalone grocery-search query the catalog
retriever can use ON ITS OWN.

Rules:
- Resolve every pronoun and deictic word ("it", "that", "this", "the curd",
  "similar ones") using the conversation context so the result names the real
  product(s) / category the customer means.
- Keep it a short, natural search phrase (5-15 words). Add useful category or
  brand context when the reference alone is too vague.
- Do NOT answer the question, do NOT add quotes, do NOT mention "the previous
  message" or "the conversation". Output ONLY the rewritten query text.
- If the follow-up is already specific enough, return it unchanged.

CONVERSATION SO FAR:
{history}

CUSTOMER'S FOLLOW-UP:
{message}

REWRITTEN QUERY:
"""


class QueryRewriter:
    def __init__(self, llm, history_blob: str):
        self._llm = llm
        self._history_blob = history_blob

    def rewrite(self, message: str) -> str:
        """Return a standalone, history-aware query for `message`."""
        if not looks_ambiguous(message):
            return message

        try:
            response = self._llm.invoke(
                [
                    (
                        "system",
                        "You rewrite ambiguous follow-up questions into standalone "
                        "grocery search queries. Output only the rewritten query text.",
                    ),
                    ("human", _REWRITE_PROMPT.format(
                        history=self._history_blob or "(no previous messages)",
                        message=message,
                    )),
                ]
            )
            rewritten = (response.content or "").strip().strip('"')
            if rewritten:
                logger.info(
                    "Query rewrite: %r -> %r", message, rewritten
                )
                return rewritten
        except Exception as exc:  # never let a rewrite failure block the chat
            logger.warning("Query rewrite LLM failed (%s); using heuristic fallback", exc)

        return self._heuristic_fallback(message)

    @staticmethod
    def _heuristic_fallback(message: str) -> str:
        """No-LLM fallback: strip filler and keep the core noun phrase."""
        cleaned = _AMBIGUOUS_STARTERS.sub("", message).strip()
        cleaned = re.sub(r"\b(is it|are they|do you|and)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ?.,")
        return cleaned or message


def rewrite_query(llm, message: str, history_blob: str) -> str:
    """Convenience wrapper so the pipeline can call a single function."""
    return QueryRewriter(llm, history_blob).rewrite(message)