"""Small in-memory cart service used by the BlinkBot demo."""

from threading import Lock
from typing import Dict

from fastapi import HTTPException

from vector_store import get_product_by_id


_carts: Dict[str, Dict[str, int]] = {}
_cart_lock = Lock()


def _cart_summary(session_id: str) -> dict:
    quantities = _carts.get(session_id, {})
    items = []
    subtotal = 0.0

    for product_id, quantity in quantities.items():
        product = get_product_by_id(product_id)
        if not product:
            continue
        price = float(product["price"])
        line_total = round(price * quantity, 2)
        subtotal += line_total
        items.append({
            "product_id": product_id,
            "name": product["name"],
            "price": price,
            "quantity": quantity,
            "line_total": line_total,
            "image_url": product.get("image_url", ""),
        })

    return {
        "session_id": session_id,
        "items": items,
        "item_count": sum(item["quantity"] for item in items),
        "subtotal": round(subtotal, 2),
    }


def get_cart(session_id: str) -> dict:
    with _cart_lock:
        return _cart_summary(session_id)


def add_to_cart(session_id: str, product_id: str, quantity: int = 1) -> dict:
    if not get_product_by_id(product_id):
        raise HTTPException(status_code=404, detail="Product not found")

    with _cart_lock:
        cart = _carts.setdefault(session_id, {})
        cart[product_id] = cart.get(product_id, 0) + quantity
        return _cart_summary(session_id)


def update_quantity(session_id: str, product_id: str, quantity: int) -> dict:
    with _cart_lock:
        cart = _carts.setdefault(session_id, {})
        if product_id not in cart:
            raise HTTPException(status_code=404, detail="Product is not in the cart")
        if quantity <= 0:
            cart.pop(product_id, None)
        else:
            cart[product_id] = quantity
        return _cart_summary(session_id)


def remove_from_cart(session_id: str, product_id: str) -> dict:
    with _cart_lock:
        cart = _carts.setdefault(session_id, {})
        if product_id not in cart:
            raise HTTPException(status_code=404, detail="Product is not in the cart")
        cart.pop(product_id)
        return _cart_summary(session_id)



def clear_cart(session_id: str) -> dict:
    """Remove all items from a session cart after a successful checkout."""
    with _cart_lock:
        _carts.pop(session_id, None)
        return _cart_summary(session_id)
