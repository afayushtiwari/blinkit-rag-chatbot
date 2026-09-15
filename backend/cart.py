"""Persistent cart service for the BlinkBot demo."""

from fastapi import HTTPException

from session_store import (
    add_cart_quantity,
    clear_cart as clear_persisted_cart,
    get_cart_quantities,
    get_cart_sessions_count,
    remove_cart_item,
    set_cart_quantity,
)
from vector_store import get_product_by_id
import inventory


def _cart_summary(session_id: str) -> dict:
    quantities = get_cart_quantities(session_id)
    items = []
    subtotal = 0.0

    for product_id, quantity in quantities.items():
        product = get_product_by_id(product_id)
        if not product:
            continue
        price = float(product["price"])
        stock = int(product.get("stock", 0))
        line_total = round(price * quantity, 2)
        subtotal += line_total
        items.append(
            {
                "product_id": product_id,
                "name": product["name"],
                "price": price,
                "quantity": quantity,
                "line_total": line_total,
                "image_url": product.get("image_url", ""),
                "stock": stock,
                "in_stock": stock > 0,
                "max_quantity": max(min(quantity, stock), 1) if stock > 0 else 0,
            }
        )

    return {
        "session_id": session_id,
        "items": items,
        "item_count": sum(item["quantity"] for item in items),
        "subtotal": round(subtotal, 2),
    }


def get_cart(session_id: str) -> dict:
    return _cart_summary(session_id)


def add_to_cart(session_id: str, product_id: str, quantity: int = 1) -> dict:
    product = get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    stock = int(product.get("stock", 0))
    if stock <= 0:
        raise HTTPException(
            status_code=409,
            detail=f"Sorry, {product['name']} is currently out of stock.",
        )

    current = get_cart_quantities(session_id).get(product_id, 0)
    requested = current + quantity
    if requested > stock:
        raise HTTPException(
            status_code=409,
            detail=f"Only {stock} unit(s) of {product['name']} are available.",
        )

    add_cart_quantity(session_id, product_id, quantity)
    return _cart_summary(session_id)


def update_quantity(session_id: str, product_id: str, quantity: int) -> dict:
    current_cart = get_cart_quantities(session_id)
    if product_id not in current_cart:
        raise HTTPException(status_code=404, detail="Product is not in the cart")

    if quantity > 0:
        product = get_product_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        stock = int(product.get("stock", 0))
        if stock <= 0:
            raise HTTPException(
                status_code=409,
                detail=f"Sorry, {product['name']} is currently out of stock.",
            )
        if quantity > stock:
            raise HTTPException(
                status_code=409,
                detail=f"Only {stock} unit(s) of {product['name']} are available.",
            )

    set_cart_quantity(session_id, product_id, quantity)
    return _cart_summary(session_id)


def remove_from_cart(session_id: str, product_id: str) -> dict:
    if not remove_cart_item(session_id, product_id):
        raise HTTPException(status_code=404, detail="Product is not in the cart")
    return _cart_summary(session_id)


def clear_cart(session_id: str) -> dict:
    """Remove all items after successful checkout."""
    clear_persisted_cart(session_id)
    return _cart_summary(session_id)


def count_carts_with_items() -> int:
    """Number of sessions that have ever added an item to a cart."""
    return get_cart_sessions_count()
