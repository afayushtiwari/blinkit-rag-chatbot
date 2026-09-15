import { useEffect, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const paymentOptions = ["Cash on Delivery", "UPI (Demo)", "Card (Demo)"];

export default function CheckoutModal({ cart, sessionId, onClose, onOrderPlaced }) {
  const [form, setForm] = useState({
    customer_name: "",
    phone: "",
    address: "",
    city: "",
    pincode: "",
    payment_method: "Cash on Delivery",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [order, setOrder] = useState(null);
  const [dates, setDates] = useState([]);
  const [slots, setSlots] = useState([]);
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedSlot, setSelectedSlot] = useState("");

  const deliveryFee = useMemo(
    () => (cart.subtotal >= 199 ? 0 : 25),
    [cart.subtotal]
  );
  const total = Number(cart.subtotal) + deliveryFee;

  // Items that can't be checked out: out of stock, or quantity over available.
  const stockIssues = useMemo(() => {
    const problems = [];
    for (const item of cart.items || []) {
      if (item.in_stock === false) {
        problems.push(`${item.name} is currently out of stock.`);
      } else if (item.stock != null && item.quantity > item.stock) {
        problems.push(
          `${item.name}: only ${item.stock} available but your cart has ${item.quantity}.`
        );
      }
    }
    return problems;
  }, [cart.items]);
  const checkoutBlocked = stockIssues.length > 0;

  useEffect(() => {
    fetch(`${API_URL}/api/delivery-slots`)
      .then((res) => res.json())
      .then((data) => {
        if (data.dates && data.dates.length) {
          setDates(data.dates);
          setSelectedDate(data.dates[0].date);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedDate) return;
    setSelectedSlot("");
    fetch(`${API_URL}/api/delivery-slots?date=${selectedDate}`)
      .then((res) => res.json())
      .then((data) => setSlots(data.slots || []))
      .catch(() => {});
  }, [selectedDate]);

  const updateField = (event) => {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!selectedDate || !selectedSlot) {
      setError("Please pick a delivery slot to continue.");
      return;
    }
    setSubmitting(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/api/orders/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          ...form,
          delivery_date: selectedDate,
          delivery_slot: selectedSlot,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = Array.isArray(data.detail)
          ? data.detail.map((item) => item.msg || "Invalid input").join("; ")
          : data.detail || "Checkout could not be completed.";
        throw new Error(message);
      }

      setOrder(data.order);
      onOrderPlaced?.(data.cart);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (order) {
    return (
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4">
        <section className="w-full max-w-md rounded-2xl bg-white p-6 text-center shadow-2xl dark:bg-gray-900">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-green-100 text-3xl">✓</div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Order confirmed!</h2>
          <p className="mt-4 text-sm text-gray-600 dark:text-gray-300">
            Your demo order will be delivered to {order.city}.
          </p>
          {order.delivery && (
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
              Slot: <span className="font-semibold text-gray-900 dark:text-white">{order.delivery.slot}</span> on{" "}
              <span className="font-semibold text-gray-900 dark:text-white">{order.delivery.date}</span>
            </p>
          )}

          {Array.isArray(order.status_timeline) && order.status_timeline.length > 0 && (
            <div className="mt-4 rounded-xl bg-gray-50 p-4 text-left dark:bg-gray-800">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Order progress
              </p>
              <ol className="mt-2 space-y-1.5">
                {order.status_timeline.map((stage, i) => (
                  <li key={stage.status} className="flex items-center gap-2 text-sm">
                    <span className={stage.done ? "text-blinkit-green" : "text-gray-300 dark:text-gray-600"}>
                      {stage.done ? "✓" : "○"}
                    </span>
                    <span className={stage.done ? "font-medium text-gray-900 dark:text-white" : "text-gray-500 dark:text-gray-400"}>
                      {stage.status}
                    </span>
                    {stage.done && i === 0 && (
                      <span className="ml-auto text-xs text-gray-400">now</span>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}
          <div className="mt-5 rounded-xl bg-gray-50 p-4 text-left dark:bg-gray-800">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Order ID</p>
            <p className="font-mono font-bold text-gray-900 dark:text-white">{order.order_id}</p>
            <div className="mt-3 flex justify-between text-sm"><span>Status</span><span className="font-semibold text-blinkit-green">{order.status}</span></div>
            <div className="mt-2 flex justify-between text-sm"><span>Payment</span><span>{order.payment_method}</span></div>
            <div className="mt-2 flex justify-between font-bold"><span>Total</span><span>₹{order.total}</span></div>
          </div>
          <p className="mt-4 text-xs text-gray-500">Payment and email are demo-only; no real charge was made.</p>
          <button onClick={onClose} className="mt-5 w-full rounded-xl bg-blinkit-green px-4 py-3 font-semibold text-white hover:bg-blinkit-green-dark">
            Continue shopping
          </button>
        </section>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[60] overflow-y-auto bg-black/50 p-4">
      <section className="mx-auto my-6 w-full max-w-xl rounded-2xl bg-white p-5 shadow-2xl dark:bg-gray-900 sm:p-6">
        <div className="mb-5 flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Checkout</h2>
            <p className="text-sm text-gray-500">Enter a delivery address and choose a demo payment method.</p>
          </div>
          <button onClick={onClose} className="text-2xl text-gray-500" aria-label="Close checkout">×</button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-200">Full name
              <input required name="customer_name" value={form.customer_name} onChange={updateField} className="mt-1 w-full rounded-lg border p-2.5 text-gray-900" />
            </label>
            <label className="text-sm font-medium text-gray-700 dark:text-gray-200">Phone number
              <input required name="phone" inputMode="tel" value={form.phone} onChange={updateField} className="mt-1 w-full rounded-lg border p-2.5 text-gray-900" />
            </label>
          </div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">Delivery address
            <textarea required name="address" value={form.address} onChange={updateField} rows="3" className="mt-1 w-full rounded-lg border p-2.5 text-gray-900" placeholder="House/flat number, street, landmark" />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-200">City
              <input required name="city" value={form.city} onChange={updateField} className="mt-1 w-full rounded-lg border p-2.5 text-gray-900" />
            </label>
            <label className="text-sm font-medium text-gray-700 dark:text-gray-200">PIN code
              <input required name="pincode" inputMode="numeric" value={form.pincode} onChange={updateField} className="mt-1 w-full rounded-lg border p-2.5 text-gray-900" />
            </label>
          </div>

          <fieldset>
            <legend className="text-sm font-semibold text-gray-700 dark:text-gray-200">Delivery slot</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {dates.map((date) => (
                <button
                  key={date.date}
                  type="button"
                  onClick={() => setSelectedDate(date.date)}
                  className={
                    "rounded-lg border px-3 py-2 text-sm " +
                    (selectedDate === date.date
                      ? "border-blinkit-green bg-green-50 text-gray-900 font-medium dark:bg-gray-800"
                      : "text-gray-600 dark:text-gray-300 hover:border-gray-300")
                  }
                >
                  {date.date}
                </button>
              ))}
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {slots.map((slot) => (
                <button
                  key={slot.label}
                  type="button"
                  disabled={slot.full}
                  onClick={() => setSelectedSlot(slot.label)}
                  className={
                    "rounded-lg border p-2.5 text-left text-sm " +
                    (selectedSlot === slot.label
                      ? "border-blinkit-green bg-green-50 text-gray-900 dark:bg-gray-800"
                      : "text-gray-600 dark:text-gray-300") +
                    (slot.full ? " opacity-40 cursor-not-allowed" : " hover:border-gray-300")
                  }
                >
                  <span className="font-medium">{slot.label}</span>
                  <span className="block text-xs text-gray-400">
                    {slot.full ? "Fully booked" : `${slot.available} slots left`}
                  </span>
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="text-sm font-semibold text-gray-700 dark:text-gray-200">Payment method</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              {paymentOptions.map((option) => (
                <label key={option} className={"cursor-pointer rounded-lg border p-3 text-sm " + (form.payment_method === option ? "border-blinkit-green bg-green-50 text-gray-900" : "text-gray-600 dark:text-gray-300")}>
                  <input type="radio" name="payment_method" value={option} checked={form.payment_method === option} onChange={updateField} className="mr-2 accent-green-600" />
                  {option}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="rounded-xl bg-gray-50 p-4 text-sm text-gray-700 dark:bg-gray-800 dark:text-gray-200">
            <div className="flex justify-between"><span>Subtotal ({cart.item_count} items)</span><span>₹{cart.subtotal}</span></div>
            <div className="mt-2 flex justify-between"><span>Delivery</span><span>{deliveryFee ? `₹${deliveryFee}` : "FREE"}</span></div>
            <div className="mt-3 flex justify-between border-t pt-3 text-base font-bold dark:border-gray-700"><span>Total</span><span>₹{total}</span></div>
          </div>

          {stockIssues.length > 0 && (
            <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
              <p className="font-semibold">Some items can&apos;t be ordered right now:</p>
              <ul className="mt-1 list-disc pl-4">
                {stockIssues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </div>
          )}

          {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

          <button disabled={submitting || checkoutBlocked} className="w-full rounded-xl bg-blinkit-green px-4 py-3 font-semibold text-white hover:bg-blinkit-green-dark disabled:opacity-60">
            {submitting ? "Placing your order..." : `Place demo order · ₹${total}`}
          </button>
        </form>
      </section>
    </div>
  );
}
