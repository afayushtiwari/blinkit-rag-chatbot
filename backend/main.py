"""
main.py
-------
FastAPI backend exposing:
  GET  /api/products              -> list all products (for the homepage grid)
  GET  /api/products/{product_id} -> get one product's full details
  GET  /api/cart/{session_id}     -> get current cart for a session
  POST /api/cart/add              -> add an item to a session cart
  POST /api/cart/update-quantity  -> set quantity for a cart line
  POST /api/cart/remove           -> remove an item from a session cart
  POST /api/orders/checkout       -> confirm a demo order
  GET  /api/orders/{order_id}     -> get order details
  GET  /api/delivery-slots        -> bookable delivery dates / time slots
  POST /api/delivery-slots        -> reserve a delivery slot for an order
  POST /api/feedback              -> save thumbs / stars for a chat reply
  GET  /api/feedback/stats        -> aggregated feedback for the admin page
  POST /api/chat                  -> send a chat message, get back the
                                     agentic RAG-generated answer + any
                                     product cards + the current cart
  POST /api/chat/reset            -> clear a session's conversation memory
  GET  /api/chat/sessions         -> recent conversation sessions (history UI)
  GET  /api/chat/history          -> messages for one session (history UI)
  GET  /api/admin/stats           -> admin dashboard aggregates

The chat endpoint is fully agentic: the LLM decides whether to search the
catalog, fetch product details, or manage the cart using Gemini function
calling -- see agent.py and rag_pipeline.py.

Run locally with:
    uvicorn main:app --reload --port 8000
"""

import logging
import os
import re
import traceback
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

from settings import settings
from vector_store import load_products, get_product_by_id
import memory as memory_module
import cart as cart_module
import feedback as feedback_module
import orders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("blinkit")

# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])

app = FastAPI(title="Blinkit RAG Chatbot API")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please slow down and try again."},
    )


# ---------------------------------------------------------------------------
# CORS - restricted to configured origins only
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

logger.info("CORS allowed origins: %s", settings.cors_origins)

# Lazy import/init of the RAG pipeline so the server can still start up
# (and serve /api/products) even before GOOGLE_API_KEY is configured.
_pipeline = None


def get_rag_pipeline():
    global _pipeline
    if _pipeline is None:
        try:
            from rag_pipeline import get_pipeline
            _pipeline = get_pipeline()
        except Exception as e:
            logger.warning("RAG pipeline init failed (missing GOOGLE_API_KEY?): %s", e)
            raise
    return _pipeline


# ---------------------------------------------------------------------------
# Request / Response models with input validation
# ---------------------------------------------------------------------------
SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-]{8,128}$")


class ChatRequest(BaseModel):
    session_id: str = Field(
        min_length=8,
        max_length=128,
        pattern=r"^[a-zA-Z0-9\-]+$",
        description="UUID session identifier",
    )
    message: str = Field(
        min_length=1,
        max_length=1000,
        description="User's chat message (max 1000 chars)",
    )


class ChatResponse(BaseModel):
    message_id: str
    answer: str
    products: List[dict]
    cart: Optional[dict] = None


class FeedbackRequest(BaseModel):
    message_id: str = Field(min_length=8, max_length=64)
    session_id: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9\-]+$")
    vote: int = Field(ge=1, le=2, description="1 = thumbs down, 2 = thumbs up")
    stars: int = Field(default=0, ge=0, le=5, description="Optional 1-5 rating")
    feedback: str = Field(default="", max_length=500)


class BookSlotRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9\-]+$")
    order_id: str = Field(min_length=3, max_length=64)
    delivery_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    delivery_slot: str = Field(min_length=3, max_length=40)


class CheckoutRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9\-]+$")
    customer_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=20, pattern=r"^[0-9+\-\s]+$")
    address: str = Field(min_length=3, max_length=300)
    city: str = Field(min_length=2, max_length=100)
    pincode: str = Field(min_length=4, max_length=12, pattern=r"^[0-9]+$")
    payment_method: str
    delivery_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    delivery_slot: Optional[str] = Field(default=None, max_length=40)


class CartItemRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9\-]+$")
    product_id: str = Field(min_length=1, max_length=50)
    quantity: int = Field(default=1, ge=1, le=99)


class CartQuantityRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9\-]+$")
    product_id: str = Field(min_length=1, max_length=50)
    quantity: int = Field(ge=0, le=99)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
@limiter.exempt
def root():
    return {"status": "ok", "message": "Blinkit RAG Chatbot API is running."}


@app.get("/api/products")
@limiter.exempt
def get_products():
    """Returns the full product catalog for the homepage."""
    return load_products()


@app.get("/api/products/{product_id}")
@limiter.exempt
def get_product(product_id: str):
    product = get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.get("/api/cart/{session_id}")
@limiter.exempt
def get_cart(session_id: str):
    if not SESSION_ID_PATTERN.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    return cart_module.get_cart(session_id)


@app.post("/api/cart/add")
def add_cart_item(request: Request, body: CartItemRequest):
    return cart_module.add_to_cart(body.session_id, body.product_id, body.quantity)


@app.post("/api/cart/update-quantity")
def update_cart_quantity(request: Request, body: CartQuantityRequest):
    return cart_module.update_quantity(body.session_id, body.product_id, body.quantity)


@app.post("/api/cart/remove")
def remove_cart_item(request: Request, body: CartItemRequest):
    return cart_module.remove_from_cart(body.session_id, body.product_id)


@app.post("/api/orders/checkout")
def checkout(request: Request, body: CheckoutRequest):
    allowed_payment_methods = {"Cash on Delivery", "UPI (Demo)", "Card (Demo)"}
    if body.payment_method not in allowed_payment_methods:
        raise HTTPException(status_code=400, detail="Choose a valid payment method.")

    logger.info("Checkout attempt for session=%s method=%s", body.session_id, body.payment_method)

    order, updated_cart = orders.create_order(
        session_id=body.session_id,
        customer_name=body.customer_name,
        phone=body.phone,
        address=body.address,
        city=body.city,
        pincode=body.pincode,
        payment_method=body.payment_method,
        delivery_date=body.delivery_date,
        delivery_slot=body.delivery_slot,
    )
    return {"order": order, "cart": updated_cart}


@app.get("/api/orders/{order_id}")
def get_order(request: Request, order_id: str):
    return orders.get_order(order_id)


@app.get("/api/delivery-slots")
@limiter.exempt
def delivery_slots(request: Request, date: str = None):
    """List bookable delivery dates/slots. With no date, returns the next
    three bookable dates; with a date, returns that day's time slots."""
    if not date:
        return {"dates": orders.available_dates()}
    return {"date": date, "slots": orders.get_delivery_slots(date)}


@app.post("/api/delivery-slots")
def book_delivery_slot(request: Request, body: BookSlotRequest):
    return orders.book_delivery_slot(
        session_id=body.session_id,
        order_id=body.order_id,
        date_str=body.delivery_date,
        slot_label=body.delivery_slot,
    )


@app.post("/api/feedback")
def save_feedback(request: Request, body: FeedbackRequest):
    logger.info(
        "Feedback message=%s session=%s vote=%d stars=%d",
        body.message_id, body.session_id, body.vote, body.stars,
    )
    return feedback_module.save_feedback(
        message_id=body.message_id,
        session_id=body.session_id,
        vote=body.vote,
        stars=body.stars,
        feedback=body.feedback,
    )


@app.get("/api/feedback/stats")
@limiter.exempt
def feedback_stats(request: Request):
    return feedback_module.get_feedback_stats()


# ---------------------------------------------------------------------------
# Admin analytics (Feature #9) + chat history (Feature #10)
# ---------------------------------------------------------------------------
# Words that add no signal when matching product names in chat messages.
_ADMIN_STOPWORDS = {
    "the", "and", "with", "for", "of", "in", "on", "to", "a", "an",
    "fresh", "classic", "pure", "mild", "rich", "per", "original",
}

def _product_name_tokens(name: str, brand: str) -> set[str]:
    """Significant search terms for a product name (brand + stop words dropped)."""
    tokens = set()
    for word in re.split(r"[\s/()\-+&]+", name):
        w = word.lower()
        if not w or len(w) < 3 or w in _ADMIN_STOPWORDS:
            continue
        if brand and w == brand.lower():
            continue
        tokens.add(w)
    return tokens


@app.get("/api/admin/stats")
@limiter.exempt
def admin_stats(request: Request):
    """Aggregated dashboard: chat usage, feedback, top products, cart
    abandonment and order volume from the local SQLite DBs."""
    chat = memory_module.get_chat_stats()
    fdb = feedback_module.get_feedback_stats()

    products = load_products()
    user_messages = [msg.lower() for msg in memory_module.get_user_messages()]
    product_mentions = []
    for product in products:
        name = product.get("name", "")
        brand = product.get("brand", "")
        tokens = _product_name_tokens(name, brand)
        if not tokens:
            continue
        # Count messages that mention the product by any of its name tokens
        # (e.g. "amul milk" counts towards "Amul Taaza Toned Milk"), one per
        # message so a single long message can't inflate the number.
        count = sum(1 for text in user_messages if any(t in text for t in tokens))
        if count > 0:
            product_mentions.append({"id": product["id"], "name": name, "count": count})
    product_mentions.sort(key=lambda p: p["count"], reverse=True)

    carts_with_items = cart_module.count_carts_with_items()
    checked_out = len(orders.order_sessions())
    abandoned = max(carts_with_items - checked_out, 0)

    return {
        "chat": chat,
        "feedback": fdb,
        "top_products": product_mentions[:10],
        "orders": {
            "total": orders.count_orders(),
            "carts_started": carts_with_items,
            "checked_out_sessions": checked_out,
            "abandoned_sessions": abandoned,
            "abandonment_pct": (
                round(abandoned / carts_with_items * 100, 1) if carts_with_items else 0
            ),
        },
        "recent_feedback": feedback_module.list_recent(10),
    }


@app.get("/api/chat/sessions")
@limiter.exempt
def chat_sessions(request: Request, limit: int = 50):
    """Recent conversation sessions, newest first."""
    return {"sessions": memory_module.list_sessions(min(max(limit, 1), 200))}


@app.get("/api/chat/history")
@limiter.exempt
def chat_history(request: Request, session_id: str):
    if not SESSION_ID_PATTERN.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    history = memory_module.get_history(session_id)
    if not history:
        raise HTTPException(status_code=404, detail="No conversation found for this session")
    return {"session_id": session_id, "messages": history}


@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
def chat(request: Request, body: ChatRequest):
    logger.info("Chat message session=%s length=%d", body.session_id, len(body.message))

    try:
        pipeline = get_rag_pipeline()
        result = pipeline.generate_response(body.session_id, body.message)
        result["cart"] = cart_module.get_cart(body.session_id)
        return result
    except Exception as e:
        logger.error("Chat pipeline error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Chatbot failed to generate a response: {str(e)}",
        )


@app.post("/api/chat/reset")
def reset_chat(request: Request, session_id: str):
    if not SESSION_ID_PATTERN.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    memory_module.clear_session(session_id)
    logger.info("Session cleared: %s", session_id)
    return {"status": "cleared", "session_id": session_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
