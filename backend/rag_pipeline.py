"""
rag_pipeline.py
---------------
Orchestrates the agentic RAG flow for each chat message:

  1. MEMORY     -> load the customer's name and conversation history (SQLite).
  2. AGENT LOOP -> the LLM decides which tools to call (see agent.py). The
                   `search_products` tool internally performs RETRIEVE over
                   ChromaDB -- this is the RAG grounding that stops the model
                   from hallucinating prices/products.
  3. ATTACH     -> every product the agent touched during the turn gets its
                   full structured data (image, price, rating, reviews,
                   related products) attached to the reply so the frontend can
                   render rich product cards inside the chat bubble.

This is "agentic": the LLM chooses whether to search, fetch details, answer
directly, or modify the customer's cart, rather than following a fixed script.
"""

import logging
import re
import uuid
from typing import Dict, List, Optional, Any

from langchain_google_genai import ChatGoogleGenerativeAI

from settings import settings
from vector_store import build_vector_store, get_product_by_id, load_products
import memory as memory_module
from agent import run_agent_turn

logger = logging.getLogger("blinkit.rag")


class RAGPipeline:
    def __init__(self):
        self.vector_store = build_vector_store()
        self.llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
        )

    # ---------------------------------------------------------------
    # Helper: try to detect the user's name from their message
    # ---------------------------------------------------------------
    _NAME_PATTERNS = [
        r"my name is ([A-Za-z]+)",
        r"i am ([A-Za-z]+)",
        r"i'm ([A-Za-z]+)",
        r"call me ([A-Za-z]+)",
    ]

    @staticmethod
    def _maybe_extract_name(message: str) -> Optional[str]:
        for pattern in RAGPipeline._NAME_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).capitalize()
        return None

    # ---------------------------------------------------------------
    # Main entry point: run the agentic loop for one user message
    # ---------------------------------------------------------------
    def generate_response(self, session_id: str, user_message: str) -> Dict[str, Any]:
        # Remember the customer's name if they just introduced themselves
        detected_name = self._maybe_extract_name(user_message)
        if detected_name:
            memory_module.set_user_name(session_id, detected_name)
        user_name = memory_module.get_user_name(session_id)

        # Pull prior conversation turns from memory
        chat_history = memory_module.get_chat_history_text(session_id)

        name_line = f"The customer's name is {user_name}." if user_name else \
            "You do not know the customer's name yet."

        # Products the agent touched during this turn (id -> full product record)
        seen_products: Dict[str, dict] = {}

        answer_text = run_agent_turn(
            chat_model=self.llm,
            session_id=session_id,
            user_message=user_message,
            history_blob=chat_history,
            name_line=name_line,
            vector_store=self.vector_store,
            seen_products=seen_products,
        )

        # Save this turn into memory
        memory_module.save_turn(session_id, user_message, answer_text)

        # Anti-hallucination self-check: if the reply name-drops a catalog
        # product whose details were never loaded from a tool this turn (and
        # the user didn't already mention it or read about it earlier), append
        # a transparent note instead of silently trusting the claim.
        answer_text, guard_notes = self._self_check_answer(
            answer_text, user_message, chat_history, seen_products
        )
        if guard_notes:
            logger.info("Anti-hallucination guard flagged: %s", guard_notes)

        # ATTACH structured product cards for any product the agent handled
        product_cards = self._build_product_cards(answer_text, seen_products)

        return {
            "message_id": str(uuid.uuid4()),
            "answer": answer_text,
            "products": product_cards,
        }

    # ---------------------------------------------------------------
    # Anti-hallucination provenance guard
    # ---------------------------------------------------------------
    def _self_check_answer(
        self,
        answer: str,
        user_message: str,
        history_blob: str,
        seen_products: Dict[str, dict],
    ) -> (str, List[str]):
        """Verify every catalog product mentioned in the final answer was
        actually retrieved (or already known to the user). Names the model
        name-drops from general knowledge get an honest caveat appended."""
        catalog = load_products()
        low = answer.lower()
        known_text = f"{user_message} {history_blob or ''}".lower()
        seen_ids = {p["id"] for p in seen_products.values()}

        verified = {
            p["name"].lower()
            for p in catalog
            if p["name"].lower() in low and p["id"] in seen_ids
        }
        user_known = {
            p["name"].lower()
            for p in catalog
            if p["name"].lower() in known_text
        }

        flagged = [
            p["name"]
            for p in catalog
            if p["name"].lower() in low
            and p["name"].lower() not in verified
            and p["name"].lower() not in user_known
        ][:3]

        if not flagged:
            return answer, []

        if len(flagged) == 1:
            note = (
                f'\n\n[Note: I have not actually checked "{flagged[0]}" against '
                f'the catalog in this chat - ask me, "show details of '
                f'{flagged[0]}", and I will confirm before you add it.]'
            )
        else:
            names = ", ".join(f'"{n}"' for n in flagged)
            note = (
                f"\n\n[Note: I referenced {names} without checking them against "
                f"the catalog in this chat - ask me for their details before "
                f"adding them to the cart.]"
            )
        return answer + note, flagged

    # ---------------------------------------------------------------
    # ATTACH structured product data for rendering
    # ---------------------------------------------------------------
    def _build_product_cards(
        self, answer_text: str, seen_products: Dict[str, dict]
    ) -> List[dict]:
        cards = []
        catalog = [p for p in seen_products.values() if p and p.get("name")]

        # Primary signal: product named in the answer by its exact name /
        # id. Secondary (fallback): at least one card so the UI isn't bare.
        mentioned_ids = {
            p["id"]
            for p in catalog
            if p["name"].lower() in answer_text.lower()
            or p["id"].lower() in answer_text.lower()
        }

        chosen = [p for p in catalog if p["id"] in mentioned_ids]
        if not chosen and catalog:
            chosen = [catalog[0]]

        for product in chosen:
            cards.append(self._attach_full(product))

        return cards

    def _attach_full(self, product: dict) -> dict:
        full = get_product_by_id(product["id"]) or product
        related = []
        for rel_id in full.get("related_products", []):
            rel_product = get_product_by_id(rel_id)
            if rel_product:
                related.append({
                    "id": rel_product["id"],
                    "name": rel_product["name"],
                    "price": rel_product["price"],
                    "image_url": rel_product["image_url"],
                })

        return {
            "id": product["id"],
            "name": product["name"],
            "brand": product.get("brand", ""),
            "category": product.get("category", ""),
            "price": product.get("price", 0),
            "rating": product.get("rating", 0),
            "image_url": product.get("image_url", ""),
            "description": full.get("description", ""),
            "reviews": full.get("reviews", []),
            "faqs": full.get("faqs", []),
            "related_products": related,
        }


# A single shared pipeline instance (loaded once at server startup)
_pipeline_instance = None


def get_pipeline() -> RAGPipeline:
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = RAGPipeline()
    return _pipeline_instance