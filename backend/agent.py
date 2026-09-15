"""
agent.py
--------
The agentic brain of BlinkBot.

The assistant is powered by an LLM that can DECIDE to call tools. Gemini is
bound to a set of function declarations, and on every user message the backend
runs a short agent loop:

    model decides to call a tool  ->  we execute it  ->  the tool result is
    folded back into the conversation  ->  repeat until the model is done.

The tools are the "hands" the agent can use:
  * search_products             - RAG retrieval over ChromaDB (semantic search)
  * get_product_details         - full product record (reviews, FAQs, related)
  * view_cart / add_to_cart / update_cart_quantity / remove_from_cart
                                - full cart management driven by the LLM
  * get_delivery_slots          - show available delivery dates/slots
  * get_order_status            - look up an order and its delivery slot

This replaces the old regex-based `cart_agent.py`: the model now decides
whether to answer, retrieve, or mutate the customer's cart based on what it is
asked, which is what makes the flow genuinely agentic.

Compatibility note: tool results are returned to the model as plain text
rather than as Gemini function-response parts. Gemini 3+ requires a
`thought_signature` to be echoed back on every replayed functionCall part, and
the pinned langchain-google-genai 2.0.1 cannot preserve it. Feeding results
back as text keeps the loop valid while still using genuine Gemini function
calling to decide which tool to invoke.
"""

import json
import logging
from typing import Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

import cart
import orders as orders_module
from vector_store import get_product_by_id

logger = logging.getLogger("blinkit.agent")

AGENT_SYSTEM_PROMPT = """You are "BlinkBot", an agentic shopping assistant for a Blinkit-style \
grocery delivery app. You help customers find products, understand pricing, read review summaries, \
discover related items, and manage their cart.

You are an AGENT: you have real tools you can call, and you decide when to call them.

HOW TO WORK:
1. For ANY product question (details, price, rating, reviews, recommendations, "under Rs. X", \
"similar products"), FIRST call search_products() with a query that matches the catalog.
2. If the user asks for deeper detail (customer reviews, FAQs, related products), follow up by \
calling get_product_details() with the EXACT product id (e.g. "P001") returned by the search.
3. If the user asks to add / remove / change quantity of an item, use the cart tools with the EXACT \
product id from the search results - never guess an id, a name, or a price.
4. If the user asks about delivery times (e.g. "when can I get this delivered?" or "what slots are \
open?"), call get_delivery_slots(). Remind them the slot is picked and confirmed on the checkout screen.
5. If the user asks "where is my order" / "order status", call get_order_status() with the order id \
(e.g. BLK-...); if they don't know it, ask them to share it.
6. You may need several tool calls. Do not stop after the first search: look at the results and \
decide whether you have everything you need before answering.

RULES:
- NEVER answer a product question from memory or general knowledge. Product facts (what exists, \
its price, rating, reviews, availability) may come ONLY from the tool results shown in this \
conversation.
- Never invent products, prices, ratings, or reviews. Base every answer on what your tools return.
- Only quote a price, rating, or review when it actually appeared in a tool result this turn. If \
you don't have the figure, don't guess -- say so instead.
- If search_products() returns "No matching products were found": tell the customer honestly that \
you could not find it in the catalog and offer to search for something else. NEVER invent or \
suggest a similar product as if it were real.
- Refer to products by their exact catalog name so a product card can be attached in the app.
- If the customer says "it" / "the milk" in a follow-up, infer the product from the earlier \
conversation and search again to confirm before answering.
- Be warm, concise, and conversational. Use the customer's name if you know it.
- STRICTLY GROCERIES ONLY: if the user asks anything unrelated to grocery
  shopping or their order (general knowledge, trivia such as "who is Albert
  Einstein?", news, tech, math, etc.), do NOT answer the question. Say
  something like "I can only help with your grocery shopping!" and ask what
  they need. Never engage or elaborate on the off-topic topic.
- If you truly don't have the information, say so honestly instead of guessing.

- When you are done, reply with a normal text answer. Feel free to keep it under ~120 words.
- NEVER use markdown formatting in your replies (**bold**, *italics*, __underline__, #, >, or backticks). Write clean, professional plain text only; use simple labels like "Price: Rs. 40".
"""

MAX_AGENT_STEPS = 6


def _cart_summary_lines(summary: dict) -> str:
    """Render a cart summary as text the model can reason about and the user
    can read (the frontend also refreshes the cart from the API response)."""
    if not summary["items"]:
        return "The cart is currently empty."
    lines = [f"Cart status: {summary['item_count']} item(s), subtotal Rs. {summary['subtotal']}."]
    for item in summary["items"]:
        lines.append(
            f"- {item['name']} (id {item['product_id']}) x {item['quantity']} "
            f"= Rs. {item['line_total']}"
        )
    return "\n".join(lines)


def _build_tools(
    session_id: str,
    seen_products: Dict[str, dict],
    vector_store,
) -> List:
    """Create the tool set for one conversation turn, closing over the session
    id so the tools read/write that session's cart. Every tool that touches a
    product records its full record in `seen_products`, which the caller later
    uses to attach rich product cards to the final answer."""

    def _remember(product: dict) -> None:
        if product:
            seen_products.setdefault(product["id"], product)

    def _as_quantity(value) -> int:
        """Gemini may send whole numbers as floats (e.g. 2.0); normalise to int
        so the SQLite cart stores clean INTEGER quantities."""
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return 1

    @tool
    def search_products(query: str) -> str:
        """Search the grocery catalog for products relevant to the customer's \
question. Call this FIRST for any product question about details, price, rating, \
reviews, or recommendations. Returns the most relevant products with their id, \
name, brand, category, price, rating and a short summary."""
        docs = vector_store.similarity_search(query, k=3)
        lines = []
        seen_ids = set()
        for doc in docs:
            meta = doc.metadata
            if meta["id"] in seen_ids:
                continue  # skip duplicate documents from stale collections
            seen_ids.add(meta["id"])
            _remember(get_product_by_id(meta["id"]))
            lines.append(
                f"[{meta['id']}] {meta['name']} - brand {meta['brand']}, "
                f"category {meta['category']}, Rs. {meta['price']}, "
                f"rating {meta['rating']}/5"
            )
            lines.append("Details: " + doc.page_content.strip())
        if not lines:
            return "No matching products were found in the catalog."
        return "\n\n---\n\n".join(lines)

    @tool
    def get_product_details(product_id: str) -> str:
        """Get the full details of a product by its id (e.g. 'P001'): \
description, customer reviews, FAQs, and related products."""
        product = get_product_by_id(product_id)
        if not product:
            return f"Product with id '{product_id}' was not found."
        _remember(product)
        return json.dumps(product, indent=2, ensure_ascii=False)

    @tool
    def view_cart() -> str:
        """Show what is currently in the customer's cart: items, quantities, \
and subtotal."""
        return _cart_summary_lines(cart.get_cart(session_id))

    @tool
    def add_to_cart(product_id: str, quantity: int = 1) -> str:
        """Add a product to the customer's cart by its product id (e.g. \
'P001'). If the product is already in the cart, the quantity is increased."""
        product = get_product_by_id(product_id)
        if not product:
            return f"Product with id '{product_id}' was not found."
        _remember(product)
        try:
            summary = cart.add_to_cart(session_id, product_id, _as_quantity(quantity))
        except Exception as exc:
            return f"Could not add to cart: {exc}"
        return _cart_summary_lines(summary)

    @tool
    def update_cart_quantity(product_id: str, quantity: int) -> str:
        """Set the quantity of a cart line for a product id (e.g. 'P001'). \
A quantity of 0 removes the line."""
        product = get_product_by_id(product_id)
        if not product:
            return f"Product with id '{product_id}' was not found."
        _remember(product)
        try:
            summary = cart.update_quantity(session_id, product_id, _as_quantity(quantity))
        except Exception as exc:
            return f"Could not update the cart: {exc}"
        return _cart_summary_lines(summary)

    @tool
    def remove_from_cart(product_id: str) -> str:
        """Remove a product from the customer's cart by its product id (e.g. \
'P001')."""
        product = get_product_by_id(product_id)
        if not product:
            return f"Product with id '{product_id}' was not found."
        _remember(product)
        try:
            summary = cart.remove_from_cart(session_id, product_id)
        except Exception as exc:
            return f"Could not remove from cart: {exc}"
        return _cart_summary_lines(summary)

    @tool
    def get_delivery_slots(date: str = "") -> str:
        """Show which delivery dates and time slots are available. With no \
date, shows the next 3 bookable days; with a date (YYYY-MM-DD) shows that \
day's slots. Booking happens at checkout."""
        try:
            if not date:
                dates = orders_module.available_dates()
                lines = [
                    "Available delivery dates:",
                    *[f"- {d['label']} ({d['date']})" for d in dates],
                    "",
                    "Ask me which slots are free on a date (e.g. 'slots on "
                    "2026-09-13') or pick one on the checkout screen.",
                ]
                return "\n".join(lines)
            slots = orders_module.get_delivery_slots(date.strip())
            lines = [f"Delivery slots for {date.strip()}:",
                     *[f"- {s['label']} ({'FULL' if s['full'] else str(s['available']) + ' left'})" for s in slots]]
            return "\n".join(lines)
        except Exception as exc:
            return f"Could not load delivery slots: {exc}"

    @tool
    def get_order_status(order_id: str) -> str:
        """Look up a customer's order status, delivery slot, and lifecycle \
timeline by its order id (e.g. 'BLK-20260913-AB12CD'). Timeline stages are \
Placed -> Packed -> On the way -> Delivered."""
        try:
            order = orders_module.get_order(order_id.strip())
        except Exception as exc:
            return f"Order '{order_id}' was not found: {exc}"
        delivery = order.get("delivery")
        lines = [
            f"Order {order['order_id']}: {order['status']}",
            f"Total: Rs. {order['total']}",
        ]
        for stage in order.get("status_timeline", []):
            marker = "done" if stage["done"] else "next"
            lines.append(
                f"- {stage['status']} ({marker})"
            )
        if delivery:
            lines.append(
                f"Delivery: {delivery['slot']} on {delivery['date']}"
            )
        else:
            lines.append("Delivery slot: not booked yet.")
        return "\n".join(lines)

    return [
        search_products,
        get_product_details,
        view_cart,
        add_to_cart,
        update_cart_quantity,
        remove_from_cart,
        get_delivery_slots,
        get_order_status,
    ]


def run_agent_turn(
    chat_model,
    session_id: str,
    user_message: str,
    history_blob: str,
    name_line: str,
    vector_store,
    seen_products: Dict[str, dict],
    rewritten_query: str = None,
    trace: List[dict] = None,
) -> str:
    """Run the model-versus-tools loop for one user message.

    Returns the final plain-text answer. As a side effect it fills
    `seen_products` with the full records of every product the agent touched,
    so the caller can attach rich product cards to the reply. If a `trace`
    list is passed in, each step is appended to it (tool name, args, result)
    for debugging and logging.

    `rewritten_query` (optional) is a standalone, history-aware search query
    produced by query_rewriter.py for ambiguous follow-ups ("what about the
    curd?"); when supplied it is injected as explicit guidance so the
    agent's `search_products` call runs against the disambiguated query.

    Design note: Gemini 3+ models require a `thought_signature` to be echoed
    back whenever a previous `functionCall` part is replayed in the request
    history (a requirement of the pinned langchain-google-genai 2.0.1). To stay
    compatible we never replay function-call parts: the model STILL uses native
    Gemini function calling to *decide* which tool to call, but each tool's
    result is fed back to the model as plain text inside the next request, so
    the API never validates a replayed signature.
    """
    if trace is None:
        trace = []

    tools = _build_tools(session_id, seen_products, vector_store)
    tools_by_name = {t.name: t for t in tools}
    model = chat_model.bind_tools(tools)

    # One big text blob that grows as tools get called. Sent as a single user
    # turn each step (no functionCall/functionResponse parts in history).
    conversation = (
        f"{name_line}\n\n"
        f"CONVERSATION HISTORY SO FAR:\n{history_blob or '(no previous messages)'}\n\n"
        f"CUSTOMER'S NEW QUESTION:\n{user_message}"
    )

    if rewritten_query:
        conversation += (
            f"\n\nSEARCH GUIDANCE (provided by the query rewriter): the customer's "
            f"follow-up refers to context from earlier in the chat. When you call "
            f"search_products(), use THIS standalone query so retrieval matches the "
            f"right products:\n{rewritten_query}"
        )

    for step in range(MAX_AGENT_STEPS):
        response = model.invoke(
            [SystemMessage(content=AGENT_SYSTEM_PROMPT), HumanMessage(content=conversation)]
        )

        calls = getattr(response, "tool_calls", None)
        if not calls:
            answer = response.content if response.content else "I'm all out of ideas on that one!"
            logger.info("Agent step %d: no tool call -> final answer.", step + 1)
            return answer

        # Replay exactly ONE tool call per step (parallel-call support varies
        # by model/SDK, this keeps the loop simple and predictable).
        call = calls[0]
        name = call.get("name")
        args = call.get("args") or {}

        tool_fn = tools_by_name.get(name)
        if tool_fn is None:
            result = f"Unknown tool '{name}'."
        else:
            try:
                result = tool_fn.invoke(args)
            except Exception as exc:  # never let a tool crash the loop
                result = f"Error calling '{name}': {exc}"

        trace.append({
            "step": step + 1,
            "tool": name,
            "args": args,
            "result": result,
        })
        logger.info(
            "Agent step %d: tool=%s args=%s -> %s",
            step + 1,
            name,
            json.dumps(args, ensure_ascii=False),
            str(result)[:200],
        )

        call_label = f"{name} (id {call['id']})" if call.get("id") else name
        conversation += (
            f"\n\n[Tool call {call_label}: {json.dumps(args, ensure_ascii=False)}]\n"
            f"Tool result:\n{result}"
        )

    logger.warning("Agent loop hit step limit (%d) for message %r", MAX_AGENT_STEPS, user_message)
    return (
        "I couldn't finish that in the allowed number of steps. "
        "Could you rephrase what you're looking for?"
    )