import { useMemo, useState } from "react";

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

  const deliveryFee = useMemo(
    () => (cart.subtotal >= 199 ? 0 : 25),
    [cart.subtotal]
  );
  const total = Number(cart.subtotal) + deliveryFee;

  const updateField = (event) => {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/api/orders/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, ...form }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Checkout could not be completed.");

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
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
            Your demo order will be delivered to {order.city}.
          </p>
          <div className="mt-5 rounded-xl bg-gray-50 p-4 text-left dark:bg-gray-800">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Order ID</p>
            <p className="font-mono font-bold text-gray-900 dark:text-white">{order.order_id}</p>
            <div className="mt-3 flex justify-between text-sm"><span>Status</span><span className="font-semibold text-blinkit-green">{order.status}</span></div>
            <div className="mt-2 flex justify-between text-sm"><span>Payment</span><span>{order.payment_method}</span></div>
            <div className="mt-2 flex justify-between font-bold"><span>Total</span><span>₹{order.total}</span></div>
          </div>
          <a
            href={`${API_URL}/api/orders/${order.order_id}/invoice`}
            className="mt-5 block w-full rounded-xl border border-blinkit-green px-4 py-3 font-semibold text-blinkit-green hover:bg-green-50"
          >
            Download PDF Invoice
          </a>
          <p className="mt-4 text-xs text-gray-500">Payment is demo-only; no real charge was made.</p>
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

          {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

          <button disabled={submitting} className="w-full rounded-xl bg-blinkit-green px-4 py-3 font-semibold text-white hover:bg-blinkit-green-dark disabled:opacity-60">
            {submitting ? "Placing your order..." : `Place demo order · ₹${total}`}
          </button>
        </form>
      </section>
    </div>
  );
}
