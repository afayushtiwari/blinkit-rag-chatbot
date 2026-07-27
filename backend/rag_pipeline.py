"""
rag_pipeline.py
---------------
The core Agentic RAG pipeline:

  1. RETRIEVE  -> search ChromaDB for the products most relevant to the
                  user's question (semantic similarity search).
  2. AUGMENT   -> build a prompt containing: the user's question, the
                  conversation history (memory), and the retrieved
                  product context.
  3. GENERATE  -> call Google Gemini to produce a dynamic, natural-language
                  answer that is grounded in the retrieved product data.
  4. ATTACH    -> attach structured product-card data (image, price,
                  rating, related products) for any product mentioned, so
                  the frontend can render rich cards inside the chat.

This is "agentic" in the sense that the LLM decides, based on the
retrieved context, whether to answer directly, summarize reviews, or
recommend related products -- it is not a hardcoded if/else chatbot.
"""

import os
import re
from typing import List, Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI

from vector_store import build_vector_store, get_product_by_id
import memory as memory_module

SYSTEM_PROMPT = """You are "BlinkBot", a friendly and knowledgeable shopping assistant for a \
Blinkit-style grocery delivery app. You help customers find products, understand pricing, \
read review summaries, and discover related items.

Rules you must follow:
- Only use the PRODUCT CONTEXT provided below to answer questions about products. \
Do not invent products, prices, or reviews that are not in the context.
- Be warm, concise, and conversational. Use the customer's name if you know it.
- If the user asks something unrelated to groceries/products, answer helpfully but briefly, \
and steer the conversation back to how you can help them shop.
- If you don't have information to answer a product question, say so honestly instead of \
making something up.
- When you mention a specific product from the context, refer to it by its exact name so the \
app can attach a product card automatically.
"""


class RAGPipeline:
    def __init__(self):
        self.vector_store = build_vector_store()
        self.llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)

    # ---------------------------------------------------------------
    # Step 1: RETRIEVE
    # ---------------------------------------------------------------
    def retrieve(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Semantic search over ChromaDB, returns top-k product metadata
        along with the matched text chunk."""
        results = self.vector_store.similarity_search(query, k=k)
        retrieved = []
        for doc in results:
            retrieved.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
            })
        return retrieved

    # ---------------------------------------------------------------
    # Helper: try to detect the user's name from their message
    # ---------------------------------------------------------------
    @staticmethod
    def _maybe_extract_name(message: str) -> str:
        patterns = [
            r"my name is ([A-Za-z]+)",
            r"i am ([A-Za-z]+)",
            r"i'm ([A-Za-z]+)",
            r"call me ([A-Za-z]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).capitalize()
        return None

    # ---------------------------------------------------------------
    # Step 2 + 3: AUGMENT + GENERATE
    # ---------------------------------------------------------------
    def generate_response(self, session_id: str, user_message: str) -> Dict[str, Any]:
        # Update name memory if the user just introduced themselves
        detected_name = self._maybe_extract_name(user_message)
        if detected_name:
            memory_module.set_user_name(session_id, detected_name)
        user_name = memory_module.get_user_name(session_id)

        # RETRIEVE relevant products
        retrieved_docs = self.retrieve(user_message, k=3)
        context_text = "\n\n---\n\n".join(d["content"] for d in retrieved_docs)

        # Pull prior conversation turns from memory
        chat_history = memory_module.get_chat_history_text(session_id)

        name_line = f"The customer's name is {user_name}." if user_name else \
            "You do not know the customer's name yet."

        prompt = f"""{SYSTEM_PROMPT}

{name_line}

CONVERSATION HISTORY SO FAR:
{chat_history if chat_history else "(no previous messages)"}

PRODUCT CONTEXT (retrieved from the product database for this question):
{context_text}

CUSTOMER'S NEW QUESTION:
{user_message}

Respond naturally as BlinkBot:"""

        ai_response = self.llm.invoke(prompt)
        answer_text = ai_response.content

        # Save this turn into memory
        memory_module.save_turn(session_id, user_message, answer_text)

        # ATTACH structured product cards for any retrieved product whose
        # name is mentioned in the answer (so the UI shows the right cards).
        product_cards = self._build_product_cards(answer_text, retrieved_docs)

        return {
            "answer": answer_text,
            "products": product_cards,
        }

    # ---------------------------------------------------------------
    # Step 4: ATTACH structured product data for rendering
    # ---------------------------------------------------------------
    def _build_product_cards(self, answer_text: str, retrieved_docs: List[Dict]) -> List[Dict]:
        cards = []
        seen_ids = set()

        for doc in retrieved_docs:
            meta = doc["metadata"]
            name = meta["name"]
            # Only attach a card if the product is actually relevant to the
            # generated answer (mentioned by name, case-insensitive) OR it
            # was the top retrieved match.
            if name.lower() in answer_text.lower() or doc is retrieved_docs[0]:
                if meta["id"] in seen_ids:
                    continue
                seen_ids.add(meta["id"])

                full_product = get_product_by_id(meta["id"]) or {}
                related = []
                for rel_id in meta.get("related_products", "").split(","):
                    rel_id = rel_id.strip()
                    if rel_id:
                        rel_product = get_product_by_id(rel_id)
                        if rel_product:
                            related.append({
                                "id": rel_product["id"],
                                "name": rel_product["name"],
                                "price": rel_product["price"],
                                "image_url": rel_product["image_url"],
                            })

                cards.append({
                    "id": meta["id"],
                    "name": name,
                    "brand": meta["brand"],
                    "category": meta["category"],
                    "price": meta["price"],
                    "rating": meta["rating"],
                    "image_url": meta["image_url"],
                    "description": full_product.get("description", ""),
                    "reviews": full_product.get("reviews", []),
                    "faqs": full_product.get("faqs", []),
                    "related_products": related,
                })

        return cards


# A single shared pipeline instance (loaded once at server startup)
_pipeline_instance = None


def get_pipeline() -> RAGPipeline:
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = RAGPipeline()
    return _pipeline_instance
