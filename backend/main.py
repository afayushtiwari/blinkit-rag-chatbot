"""
main.py
-------
FastAPI backend exposing:
  GET  /api/products            -> list all products (for the homepage grid)
  GET  /api/products/{product_id} -> get one product's full details
  POST /api/chat                -> send a chat message, get back the RAG
                                    generated answer + any product cards
  POST /api/chat/reset          -> clear a session's conversation memory

Run locally with:
    uvicorn main:app --reload --port 8000
"""

import os
import traceback
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from vector_store import load_products, get_product_by_id
import memory as memory_module
import cart as cart_module
from cart_agent import handle_cart_command

load_dotenv()

app = FastAPI(title="Blinkit RAG Chatbot API")

# Allow the Next.js frontend (localhost:3000 or your Vercel domain) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace "*" with your exact frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy import/init of the RAG pipeline so the server can still start up
# (and serve /api/products) even before GOOGLE_API_KEY is configured.
_pipeline = None


def get_rag_pipeline():
    global _pipeline
    if _pipeline is None:
        from rag_pipeline import get_pipeline
        _pipeline = get_pipeline()
    return _pipeline


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    answer: str
    products: List[dict]
    cart: Optional[dict] = None


class CartItemRequest(BaseModel):
    session_id: str
    product_id: str
    quantity: int = Field(default=1, ge=1)


class CartQuantityRequest(BaseModel):
    session_id: str
    product_id: str
    quantity: int = Field(ge=0)


@app.get("/")
def root():
    return {"status": "ok", "message": "Blinkit RAG Chatbot API is running."}


@app.get("/api/products")
def get_products():
    """Returns the full product catalog for the homepage."""
    return load_products()


@app.get("/api/products/{product_id}")
def get_product(product_id: str):
    product = get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.get("/api/cart/{session_id}")
def get_cart(session_id: str):
    return cart_module.get_cart(session_id)


@app.post("/api/cart/add")
def add_cart_item(request: CartItemRequest):
    return cart_module.add_to_cart(request.session_id, request.product_id, request.quantity)


@app.post("/api/cart/update-quantity")
def update_cart_quantity(request: CartQuantityRequest):
    return cart_module.update_quantity(request.session_id, request.product_id, request.quantity)


@app.post("/api/cart/remove")
def remove_cart_item(request: CartItemRequest):
    return cart_module.remove_from_cart(request.session_id, request.product_id)


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    cart_result = handle_cart_command(request.session_id, request.message)
    if cart_result is not None:
        return cart_result

    try:
        pipeline = get_rag_pipeline()
        result = pipeline.generate_response(request.session_id, request.message)
        return result
    except Exception as e:
        # Surface a friendly error to the frontend instead of a raw 500 crash,
        # while logging the full traceback server-side for debugging.
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Chatbot failed to generate a response: {str(e)}",
        )


@app.post("/api/chat/reset")
def reset_chat(session_id: str):
    memory_module.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
