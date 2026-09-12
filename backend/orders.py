"""Local demo order service for the BlinkBot checkout flow.

Orders are stored in SQLite so they survive a backend restart. Payments are never
processed: the selected method is saved as a demo choice only. Delivery slots
are also demo-generated: slots are "available" unless the order was already
booked into that slot (max a few per slot to look believable).
"""

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from fastapi import HTTPException

import cart


DATABASE_PATH = Path(__file__).with_name("orders.db")
_db_lock = Lock()

SLOT_LABELS = [
    "8:00 AM - 10:00 AM",
    "10:00 AM - 12:00 PM",
    "12:00 PM - 2:00 PM",
    "2:00 PM - 4:00 PM",
    "4:00 PM - 6:00 PM",
    "6:00 PM - 8:00 PM",
    "8:00 PM - 10:00 PM",
]
SLOTS_PER_DAY = 5  # fake capacity per slot so bookings actually matter

# Demo order lifecycle: status progresses automatically as time passes
# since the order was placed (minutes after creation).
STATUS_STAGES = [
    ("Placed", 0),
    ("Packed", 3),
    ("On the way", 8),
    ("Delivered", 15),
]


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
        # Migrate older DBs that predate the status timeline column.
        columns = [
            row[1]
            for row in connection.execute("PRAGMA table_info(orders)").fetchall()
        ]
        if columns and "timeline_json" not in columns:
            connection.execute("ALTER TABLE orders ADD COLUMN timeline_json TEXT")
        # delivery slots: one row per booked slot (session -> date+slot)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS delivery_slots (
                session_id TEXT NOT NULL,
                order_id TEXT NOT NULL,
                date TEXT NOT NULL,
                slot_label TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (session_id, order_id)
            )
            """
        )


def _public_order(row: sqlite3.Row) -> dict:
    order = dict(row)
    order["items"] = json.loads(order.pop("items_json"))
    timeline_json = order.pop("timeline_json", None)
    if timeline_json:
        timeline = json.loads(timeline_json)
    else:
        timeline = _build_timeline(order["created_at"])
    current_status, annotated = _resolve_status(timeline, datetime.now(timezone.utc))
    order["status"] = current_status
    order["status_timeline"] = annotated
    return order


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_timeline(created_at: str) -> list[dict]:
    """Return the staged order lifecycle as a list of events.

    Each stage stores its (estimated) timestamp relative to the order being
    placed, so the demo can show a status that advances as time passes.
    """
    placed_at = datetime.fromisoformat(created_at)
    timeline = []
    for status, minutes in STATUS_STAGES:
        at = placed_at + timedelta(minutes=minutes)
        timeline.append({
            "status": status,
            "at": at.isoformat(),
            "eta_minutes": minutes,
        })
    return timeline


def _resolve_status(timeline: list[dict] | None, now: datetime) -> tuple[str, list[dict]]:
    """Compute the current status from the timeline and mark stages complete.

    Returns (current_status, timeline_annotated) where each stage carries a
    `done` boolean and, when complete, a `completed_at` timestamp.
    """
    if not timeline:
        return "Placed", []
    now_ts = now.timestamp()
    now_iso = now.isoformat()
    current = timeline[0]["status"]
    annotated = []
    for stage in timeline:
        done = datetime.fromisoformat(stage["at"]).timestamp() <= now_ts
        if done:
            current = stage["status"]
        annotated.append({
            "status": stage["status"],
            "at": stage["at"],
            "eta_minutes": stage["eta_minutes"],
            "done": done,
            "completed_at": now_iso if done else None,
        })
    return current, annotated


def _validate_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")


def available_dates(days: int = 3) -> list[dict]:
    """Return the next `days` dates (starting tomorrow) a customer can book."""
    today = datetime.now(timezone.utc).date()
    return [
        {
            "date": (today + timedelta(days=i)).isoformat(),
            "label": (today + timedelta(days=i)).strftime("%A, %d %b %Y"),
        }
        for i in range(1, days + 1)
    ]


def get_delivery_slots(date_str: str) -> list[dict]:
    """List all time slots for a date with how many bookings each has left."""
    date_str = _validate_date(date_str)
    _initialise_database()
    with _db_lock:
        with _connection() as connection:
            rows = connection.execute(
                "SELECT slot_label, COUNT(*) AS cnt FROM delivery_slots "
                "WHERE date = ? GROUP BY slot_label",
                (date_str,),
            ).fetchall()
    booked = {row["slot_label"]: row["cnt"] for row in rows}
    slots = []
    for label in SLOT_LABELS:
        count = booked.get(label, 0)
        slots.append({
            "label": label,
            "booked": count,
            "available": max(SLOTS_PER_DAY - count, 0),
            "full": count >= SLOTS_PER_DAY,
        })
    return slots


def book_delivery_slot(
    session_id: str,
    order_id: str,
    date_str: str,
    slot_label: str,
) -> dict:
    """Reserve a delivery slot for an existing order."""
    if slot_label not in SLOT_LABELS:
        raise HTTPException(status_code=400, detail=f"Unknown slot '{slot_label}'.")
    date_str = _validate_date(date_str)
    if datetime.strptime(date_str, "%Y-%m-%d").date() <= datetime.now(timezone.utc).date():
        raise HTTPException(
            status_code=400, detail="You can only book slots for tomorrow or later."
        )

    _initialise_database()
    with _db_lock:
        with _connection() as connection:
            taken = connection.execute(
                "SELECT COUNT(*) FROM delivery_slots WHERE date = ? AND slot_label = ?",
                (date_str, slot_label),
            ).fetchone()[0]
            if taken >= SLOTS_PER_DAY:
                raise HTTPException(
                    status_code=409,
                    detail=f"Slot '{slot_label}' on {date_str} is fully booked. Pick another.",
                )
            already = connection.execute(
                "SELECT 1 FROM delivery_slots WHERE session_id = ? AND order_id = ?",
                (session_id, order_id),
            ).fetchone()
            if already:
                raise HTTPException(
                    status_code=409, detail="This order already has a delivery slot booked."
                )
            connection.execute(
                "INSERT INTO delivery_slots (session_id, order_id, date, slot_label, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, order_id, date_str, slot_label, _now()),
            )
    return {"order_id": order_id, "date": date_str, "slot": slot_label, "status": "booked"}


def get_booked_slot(order_id: str) -> dict | None:
    """Return the booked delivery slot for an order, or None."""
    _initialise_database()
    with _connection() as connection:
        row = connection.execute(
            "SELECT date, slot_label FROM delivery_slots WHERE order_id = ?",
            (order_id,),
        ).fetchone()
    if row is None:
        return None
    return {"date": row["date"], "slot": row["slot_label"]}


def create_order(
    session_id: str,
    customer_name: str,
    phone: str,
    address: str,
    city: str,
    pincode: str,
    payment_method: str,
    delivery_date: str = None,
    delivery_slot: str = None,
) -> tuple[dict, dict]:
    """Create a confirmed demo order and clear the matching cart.

    If `delivery_date` and `delivery_slot` are provided the slot is reserved
    inside the same transaction (slot must still be available).
    """
    if (delivery_date is None) != (delivery_slot is None):
        raise HTTPException(status_code=400, detail="Choose both a delivery date and a time slot.")

    with _db_lock:
        current_cart = cart.get_cart(session_id)
        if not current_cart["items"]:
            raise HTTPException(status_code=400, detail="Your cart is empty.")

        subtotal = float(current_cart["subtotal"])
        delivery_fee = 0.0 if subtotal >= 199 else 25.0
        total = round(subtotal + delivery_fee, 2)
        order_id = f"BLK-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        created_at = datetime.now(timezone.utc).isoformat()
        status = "Placed"
        timeline = _build_timeline(created_at)
        _, annotated_timeline = _resolve_status(timeline, datetime.now(timezone.utc))

        # Validate the requested slot BEFORE we create the order.
        booked_slot = None
        if delivery_slot:
            if delivery_slot not in SLOT_LABELS:
                raise HTTPException(status_code=400, detail=f"Unknown slot '{delivery_slot}'.")
            delivery_date = _validate_date(delivery_date)
            if datetime.strptime(delivery_date, "%Y-%m-%d").date() <= datetime.now(timezone.utc).date():
                raise HTTPException(
                    status_code=400, detail="You can only book slots for tomorrow or later."
                )

        _initialise_database()
        with _connection() as connection:
            if delivery_slot:
                taken = connection.execute(
                    "SELECT COUNT(*) FROM delivery_slots WHERE date = ? AND slot_label = ?",
                    (delivery_date, delivery_slot),
                ).fetchone()[0]
                if taken >= SLOTS_PER_DAY:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Slot '{delivery_slot}' on {delivery_date} is fully booked. Pick another.",
                    )

            connection.execute(
                """
                INSERT INTO orders (
                    order_id, session_id, customer_name, phone, address, city,
                    pincode, payment_method, status, subtotal, delivery_fee,
                    total, items_json, created_at, timeline_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    session_id,
                    customer_name.strip(),
                    phone.strip(),
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
                    json.dumps(timeline),
                ),
            )

            if delivery_slot:
                connection.execute(
                    "INSERT INTO delivery_slots (session_id, order_id, date, slot_label, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (session_id, order_id, delivery_date, delivery_slot, created_at),
                )
                booked_slot = {"date": delivery_date, "slot": delivery_slot}

        cart.clear_cart(session_id)
        order = {
            "order_id": order_id,
            "session_id": session_id,
            "customer_name": customer_name.strip(),
            "phone": phone.strip(),
            "address": address.strip(),
            "city": city.strip(),
            "pincode": pincode.strip(),
            "payment_method": payment_method,
            "status": status,
            "subtotal": subtotal,
            "delivery_fee": delivery_fee,
            "total": total,
            "items": current_cart["items"],
            "status_timeline": annotated_timeline,
            "delivery": booked_slot,
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
    order = _public_order(row)
    order["delivery"] = get_booked_slot(order_id)
    return order


def count_orders() -> int:
    """Total orders placed, for the admin dashboard."""
    _initialise_database()
    with _connection() as connection:
        row = connection.execute("SELECT COUNT(*) FROM orders").fetchone()
    return row[0] if row else 0


def order_sessions() -> set[str]:
    """Sessions that have completed checkout at least once."""
    _initialise_database()
    with _connection() as connection:
        rows = connection.execute("SELECT DISTINCT session_id FROM orders").fetchall()
    return {row["session_id"] for row in rows}
