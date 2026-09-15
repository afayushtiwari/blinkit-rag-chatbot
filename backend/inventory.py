"""
inventory.py
------------
SQLite-backed stock management for every product in the catalog.

Each product starts with a default stock seeded from `products.json`. The
module exposes atomic get / set / decrement helpers so that cart operations,
checkout, and the chat agent can all reason about live availability.

No external accounts or services required -- pure local SQLite.
"""

import sqlite3
import os
import json
from pathlib import Path
from threading import Lock

from fastapi import HTTPException


DATABASE_PATH = Path(__file__).with_name("inventory.db")
PRODUCTS_PATH = Path(__file__).parent.joinpath("data", "products.json")
DEFAULT_STOCK = 10

_db_lock = Lock()
_initialised = False


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_database() -> None:
    global _initialised
    if _initialised:
        return
    with _db_lock:
        if _initialised:
            return
        with _connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock (
                    product_id TEXT PRIMARY KEY,
                    available INTEGER NOT NULL CHECK(available >= 0),
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        _initialised = True


def _seed_stock() -> None:
    """Seed default stock for any product not yet in the DB."""
    _ensure_database()
    with open(PRODUCTS_PATH, "r", encoding="utf-8") as f:
        products = json.load(f)
    with _db_lock:
        with _connection() as conn:
            for product in products:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO stock (product_id, available)
                    VALUES (?, ?)
                    """,
                    (product["id"], DEFAULT_STOCK),
                )


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_stock(product_id: str) -> int:
    """Return available stock for *product_id* (0 if out of stock)."""
    _ensure_database()
    _seed_stock()
    with _db_lock:
        with _connection() as conn:
            row = conn.execute(
                "SELECT available FROM stock WHERE product_id = ?",
                (product_id,),
            ).fetchone()
    return row["available"] if row else 0


def get_all_stock() -> dict[str, int]:
    """Return {product_id: available} for every tracked product."""
    _ensure_database()
    _seed_stock()
    with _db_lock:
        with _connection() as conn:
            rows = conn.execute("SELECT product_id, available FROM stock").fetchall()
    return {row["product_id"]: row["available"] for row in rows}


def decrement_stock(product_id: str, qty: int) -> int:
    """Atomically decrement stock by *qty*. Returns the new stock level.

    Raises HTTPException 409 if insufficient stock.
    """
    if qty <= 0:
        return get_stock(product_id)
    _ensure_database()
    with _db_lock:
        with _connection() as conn:
            row = conn.execute(
                "SELECT available FROM stock WHERE product_id = ?",
                (product_id,),
            ).fetchone()
            current = row["available"] if row else 0
            if current < qty:
                raise HTTPException(
                    status_code=409,
                    detail=f"Insufficient stock for {product_id}: requested {qty}, only {current} available.",
                )
            conn.execute(
                """
                UPDATE stock
                SET available = available - ?, updated_at = CURRENT_TIMESTAMP
                WHERE product_id = ?
                """,
                (qty, product_id),
            )
    return current - qty


def set_stock(product_id: str, qty: int) -> None:
    """Set absolute stock for a product (admin restock)."""
    if qty < 0:
        raise HTTPException(status_code=400, detail="Stock cannot be negative.")
    _ensure_database()
    with _db_lock:
        with _connection() as conn:
            conn.execute(
                """
                INSERT INTO stock (product_id, available)
                VALUES (?, ?)
                ON CONFLICT(product_id)
                DO UPDATE SET available = excluded.available, updated_at = CURRENT_TIMESTAMP
                """,
                (product_id, qty),
            )


def restock_all(default: int | None = None) -> None:
    """Reset every product to default stock. Useful for demo resets."""
    level = default if default is not None else DEFAULT_STOCK
    with open(PRODUCTS_PATH, "r", encoding="utf-8") as f:
        products = json.load(f)
    _ensure_database()
    with _db_lock:
        with _connection() as conn:
            for product in products:
                conn.execute(
                    """
                    INSERT INTO stock (product_id, available)
                    VALUES (?, ?)
                    ON CONFLICT(product_id)
                    DO UPDATE SET available = ?, updated_at = CURRENT_TIMESTAMP
                    """,
                    (product["id"], level, level),
                )


def low_stock_items(threshold: int = 3) -> list[dict]:
    """Products whose stock is at or below *threshold*."""
    _ensure_database()
    _seed_stock()
    with open(PRODUCTS_PATH, "r", encoding="utf-8") as f:
        products = json.load(f)
    price_map = {p["id"]: p for p in products}
    with _db_lock:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT product_id, available FROM stock WHERE available <= ?",
                (threshold,),
            ).fetchall()
    result = []
    for row in rows:
        product = price_map.get(row["product_id"])
        if product:
            result.append({
                "id": row["product_id"],
                "name": product["name"],
                "available": row["available"],
            })
    return result
