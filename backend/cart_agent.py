"""Deterministic cart tools for BlinkBot's chat workflow.

Cart changes are intentionally handled by backend functions rather than by the
LLM so prices, quantities, and product IDs always come from the product data.
"""

import re
from typing import Optional

import cart
from vector_store import get_product_by_id, load_products


_STOP_WORDS = {
    "add", "put", "include", "remove", "delete", "change", "set", "update",
    "my", "the", "a", "an", "to", "from", "in", "cart", "quantity", "qty",
    "of", "please", "item", "items", "me",
}


def _tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in _STOP_WORDS}


def _find_product(product_text: str, allowed_ids: Optional[set[str]] = None) -> Optional[dict]:
    query_tokens = _tokens(product_text)
    if not query_tokens:
        return None

    best_product = None
    best_score = 0
    for product in load_products():
        if allowed_ids is not None and product["id"] not in allowed_ids:
            continue
        product_tokens = _tokens(f"{product['name']} {product.get('brand', '')}")
        score = len(query_tokens & product_tokens)
        if product["name"].lower() in product_text.lower():
            score += 10
        if score > best_score:
            best_product = product
            best_score = score

    return best_product if best_score else None


def _cart_message(summary: dict) -> str:
    if not summary["items"]:
        return "Your cart is empty."
    item_text = ", ".join(f"{item['name']} × {item['quantity']}" for item in summary["items"])
    return f"Your cart has {summary['item_count']} item(s): {item_text}. Subtotal: ₹{summary['subtotal']}."


def _response(answer: str, summary: dict, products: Optional[list] = None) -> dict:
    return {"answer": answer, "products": products or [], "cart": summary}


def handle_cart_command(session_id: str, message: str) -> Optional[dict]:
    """Return a cart action response if *message* requests one, otherwise None."""
    text = " ".join(message.lower().split())
    has_cart_reference = "cart" in text

    # Show cart: "show my cart", "what is in my cart", or simply "my cart".
    is_show_request = (
        text in {"cart", "my cart"}
        or bool(re.search(r"\b(show|view|open|check)\b.*\bcart\b", text))
        or bool(re.search(r"\bwhat(?:'s| is)?\b.*\bcart\b", text))
    )

    if is_show_request:
        current_cart = cart.get_cart(session_id)
        return _response(_cart_message(current_cart), current_cart)

    # Remove: "remove Amul Milk from my cart".
    if re.search(r"\b(remove|delete)\b", text) and has_cart_reference:
        current_cart = cart.get_cart(session_id)
        allowed_ids = {item["product_id"] for item in current_cart["items"]}
        product = _find_product(text, allowed_ids)

        if not product:
            return _response("I couldn't find that product in your cart.", current_cart)

        updated_cart = cart.remove_from_cart(session_id, product["id"])
        return _response(f"Removed {product['name']} from your cart.", updated_cart)

    # Quantity: "change Amul Milk quantity to 3 in my cart".
    quantity_match = re.search(
        r"\b(change|set|update)\b.*?\b(?:quantity|qty)\b.*?\bto\s+(\d+)",
        text,
    )

    if quantity_match and has_cart_reference:
        quantity = int(quantity_match.group(2))
        current_cart = cart.get_cart(session_id)
        allowed_ids = {item["product_id"] for item in current_cart["items"]}
        product = _find_product(text, allowed_ids)

        if not product:
            return _response("I couldn't find that product in your cart.", current_cart)

        updated_cart = cart.update_quantity(session_id, product["id"], quantity)
        verb = "Removed" if quantity == 0 else "Updated"
        return _response(f"{verb} {product['name']} in your cart.", updated_cart)

    # Add: "add 2 Amul Milk to my cart".
    if has_cart_reference and re.search(r"\b(add|put|include)\b", text):
        quantity_match = re.search(r"\b(add|put|include)\s+(\d+)\b", text)
        quantity = int(quantity_match.group(2)) if quantity_match else 1
        product = _find_product(text)

        if not product:
            return _response(
                "I couldn't match that product. Please use its name, "
                "for example: Add Amul Milk to my cart.",
                cart.get_cart(session_id),
            )

        updated_cart = cart.add_to_cart(session_id, product["id"], quantity)
        return _response(
            f"Added {quantity} × {product['name']} to your cart.",
            updated_cart,
            [product],
        )

    return None



    # Remove: "remove Amul Milk from my cart".
    if re.search(r"\b(remove|delete)\b", text) and has_cart_reference:
        current_cart = cart.get_cart(session_id)
        allowed_ids = {item["product_id"] for item in current_cart["items"]}
        product = _find_product(text, allowed_ids)
        if not product:
            return _response("I couldn't find that product in your cart.", current_cart)
        updated_cart = cart.remove_from_cart(session_id, product["id"])
        return _response(f"Removed {product['name']} from your cart.", updated_cart)

    # Quantity: "change Amul Milk quantity to 3".
    quantity_match = re.search(r"\b(change|set|update)\b.*?\b(?:quantity|qty)\b.*?\bto\s+(\d+)", text)
    if quantity_match and has_cart_reference:
        quantity = int(quantity_match.group(2))
        current_cart = cart.get_cart(session_id)
        allowed_ids = {item["product_id"] for item in current_cart["items"]}
        product = _find_product(text, allowed_ids)
        if not product:
            return _response("I couldn't find that product in your cart.", current_cart)
        updated_cart = cart.update_quantity(session_id, product["id"], quantity)
        verb = "Removed" if quantity == 0 else "Updated"
        return _response(f"{verb} {product['name']} in your cart.", updated_cart)

    # Add: "add 2 Amul Milk to my cart".
    if has_cart_reference and re.search(r"\b(add|put|include)\b", text):
        quantity_match = re.search(r"\b(add|put|include)\s+(\d+)\b", text)
        quantity = int(quantity_match.group(2)) if quantity_match else 1
        product = _find_product(text)
        if not product:
            return _response("I couldn't match that product. Please use its name, for example: Add Amul Milk to my cart.", cart.get_cart(session_id))
        updated_cart = cart.add_to_cart(session_id, product["id"], quantity)
        return _response(
            f"Added {quantity} × {product['name']} to your cart.",
            updated_cart,
            [product],
        )

    return None
