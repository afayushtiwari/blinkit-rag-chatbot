"""SQLite-backed cart service for the BlinkBot demo.

Cart contents are stored in `carts.db` so they survive backend restarts.
Each cart row is keyed by (session_id, product_id).
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from fastapi import HTTPException

from vector_store import get_product_by_id


DATABASE_PATH = Path(__file__).with_name("carts.db")
_db_lock = Lock()


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _initialise_database() -> None:
    with _connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cart_items (
                session_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (session_id, product_id)
            )
            """
        )


def _quantities(session_id: str) -> dict[str, int]:
    _initialise_database()
    with _connection() as connection:
        rows = connection.execute(
            "SELECT product_id, quantity FROM cart_items WHERE session_id = ?",
            (session_id,),
        ).fetchall()
    return {row["product_id"]: row["quantity"] for row in rows}


def _cart_summary(session_id: str) -> dict:
    quantities = _quantities(session_id)
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_cart(session_id: str) -> dict:
    with _db_lock:
        return _cart_summary(session_id)


def add_to_cart(session_id: str, product_id: str, quantity: int = 1) -> dict:
    if not get_product_by_id(product_id):
        raise HTTPException(status_code=404, detail="Product not found")

    with _db_lock:
        _initialise_database()
        with _connection() as connection:
            connection.execute(
                """
                INSERT INTO cart_items (session_id, product_id, quantity, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, product_id)
                DO UPDATE SET
                    quantity = quantity + excluded.quantity,
                    updated_at = excluded.updated_at
                """,
                (session_id, product_id, quantity, _now()),
            )
        return _cart_summary(session_id)


def update_quantity(session_id: str, product_id: str, quantity: int) -> dict:
    with _db_lock:
        _initialise_database()
        with _connection() as connection:
            row = connection.execute(
                "SELECT quantity FROM cart_items WHERE session_id = ? AND product_id = ?",
                (session_id, product_id),
            ).fetchone()
            if row is None:
                raise HTTPException(
                    status_code=404, detail="Product is not in the cart")
            if quantity <= 0:
                connection.execute(
                    "DELETE FROM cart_items WHERE session_id = ? AND product_id = ?",
                    (session_id, product_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE cart_items SET quantity = ?, updated_at = ?
                    WHERE session_id = ? AND product_id = ?
                    """,
                    (quantity, _now(), session_id, product_id),
                )
        return _cart_summary(session_id)


def remove_from_cart(session_id: str, product_id: str) -> dict:
    with _db_lock:
        _initialise_database()
        with _connection() as connection:
            row = connection.execute(
                "SELECT quantity FROM cart_items WHERE session_id = ? AND product_id = ?",
                (session_id, product_id),
            ).fetchone()
            if row is None:
                raise HTTPException(
                    status_code=404, detail="Product is not in the cart")
            connection.execute(
                "DELETE FROM cart_items WHERE session_id = ? AND product_id = ?",
                (session_id, product_id),
            )
        return _cart_summary(session_id)


def clear_cart(session_id: str) -> dict:
    """Remove all items from a session cart after a successful checkout."""
    with _db_lock:
        _initialise_database()
        with _connection() as connection:
            connection.execute(
                "DELETE FROM cart_items WHERE session_id = ?", (session_id,))
        return _cart_summary(session_id)


def count_carts_with_items() -> int:
    """Number of sessions that have ever added an item to a cart."""
    _initialise_database()
    with _connection() as connection:
        row = connection.execute(
            "SELECT COUNT(DISTINCT session_id) FROM cart_items").fetchone()
    return row[0] if row else 0