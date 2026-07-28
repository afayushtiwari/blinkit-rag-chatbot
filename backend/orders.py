"""Local demo order service for the BlinkBot checkout flow.

Orders are stored in SQLite so they survive a backend restart. Payments are never
processed: the selected method is saved as a demo choice only.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from fastapi import HTTPException

import cart


DATABASE_PATH = Path(__file__).with_name("orders.db")
_db_lock = Lock()


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _initialise_database() -> None:
    with _connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                address TEXT NOT NULL,
                city TEXT NOT NULL,
                pincode TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                status TEXT NOT NULL,
                subtotal REAL NOT NULL,
                delivery_fee REAL NOT NULL,
                total REAL NOT NULL,
                items_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def _public_order(row: sqlite3.Row) -> dict:
    order = dict(row)
    order["items"] = json.loads(order.pop("items_json"))
    return order


def create_order(
    session_id: str,
    customer_name: str,
    phone: str,
    email: str | None,
    address: str,
    city: str,
    pincode: str,
    payment_method: str,
) -> tuple[dict, dict]:
    """Create a confirmed demo order and clear the matching cart."""
    with _db_lock:
        current_cart = cart.get_cart(session_id)
        if not current_cart["items"]:
            raise HTTPException(status_code=400, detail="Your cart is empty.")

        subtotal = float(current_cart["subtotal"])
        delivery_fee = 0.0 if subtotal >= 199 else 25.0
        total = round(subtotal + delivery_fee, 2)
        order_id = f"BLK-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        created_at = datetime.now(timezone.utc).isoformat()
        status = "Confirmed"

        _initialise_database()
        with _connection() as connection:
            connection.execute(
                """
                INSERT INTO orders (
                    order_id, session_id, customer_name, phone, email, address, city,
                    pincode, payment_method, status, subtotal, delivery_fee,
                    total, items_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    session_id,
                    customer_name.strip(),
                    phone.strip(),
                    email.strip() if email else None,
                    address.strip(),
                    city.strip(),
                    pincode.strip(),
                    payment_method,
                    status,
                    subtotal,
                    delivery_fee,
                    total,
                    json.dumps(current_cart["items"]),
                    created_at,
                ),
            )

        cart.clear_cart(session_id)
        order = {
            "order_id": order_id,
            "session_id": session_id,
            "customer_name": customer_name.strip(),
            "phone": phone.strip(),
            "email": email.strip() if email else None,
            "address": address.strip(),
            "city": city.strip(),
            "pincode": pincode.strip(),
            "payment_method": payment_method,
            "status": status,
            "subtotal": subtotal,
            "delivery_fee": delivery_fee,
            "total": total,
            "items": current_cart["items"],
            "created_at": created_at,
        }
        return order, cart.get_cart(session_id)


def get_order(order_id: str) -> dict:
    _initialise_database()
    with _connection() as connection:
        row = connection.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return _public_order(row)
