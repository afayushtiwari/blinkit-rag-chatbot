export default function CartDrawer({ cart, open, onClose, onUpdateQuantity, onRemove, onCheckout }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <aside
        className="h-full w-full max-w-md bg-white dark:bg-gray-900 shadow-2xl p-5 overflow-y-auto"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b dark:border-gray-700 pb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">Your Cart</h2>
            <p className="text-sm text-gray-500">{cart.item_count} item{cart.item_count === 1 ? "" : "s"}</p>
          </div>
          <button onClick={onClose} className="text-2xl text-gray-500" aria-label="Close cart">×</button>
        </div>

        {cart.items.length === 0 ? (
          <p className="py-12 text-center text-gray-500">Your cart is empty. Add a product to begin.</p>
        ) : (
          <>
            <div className="divide-y dark:divide-gray-700">
              {cart.items.map((item) => (
                <div key={item.product_id} className="py-4 flex gap-3">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={item.image_url} alt={item.name} className="h-16 w-16 rounded-lg object-cover bg-gray-100" />
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm text-gray-900 dark:text-white">{item.name}</p>
                    <p className="text-sm text-gray-500">₹{item.price} each</p>
                    <div className="mt-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <button onClick={() => onUpdateQuantity(item.product_id, item.quantity - 1)} className="w-7 h-7 border rounded font-bold">−</button>
                        <span className="w-5 text-center text-sm">{item.quantity}</span>
                        <button
                          onClick={() => onUpdateQuantity(item.product_id, item.quantity + 1)}
                          disabled={item.in_stock === false || item.quantity >= item.stock}
                          className="w-7 h-7 border rounded font-bold disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          +
                        </button>
                      </div>
                      <button onClick={() => onRemove(item.product_id)} className="text-xs font-semibold text-red-600">Remove</button>
                    </div>
                    {item.in_stock === false ? (
                      <p className="mt-1 text-xs font-semibold text-red-600">Out of stock</p>
                    ) : item.stock != null && item.quantity >= item.stock ? (
                      <p className="mt-1 text-xs text-orange-600">Only {item.stock} available — max reached</p>
                    ) : null}
                  </div>
                  <span className="font-bold text-sm text-gray-900 dark:text-white">₹{item.line_total}</span>
                </div>
              ))}
            </div>
            <div className="mt-5 border-t dark:border-gray-700 pt-4 flex justify-between text-lg font-bold text-gray-900 dark:text-white">
              <span>Subtotal</span><span>₹{cart.subtotal}</span>
            </div>
            <p className="mt-2 text-xs text-gray-500">Delivery is free above ₹199; otherwise ₹25 is added at checkout.</p>
            <button onClick={onCheckout} className="mt-5 w-full rounded-xl bg-blinkit-green px-4 py-3 font-semibold text-white hover:bg-blinkit-green-dark">
              Proceed to checkout
            </button>
          </>
        )}
      </aside>
    </div>
  );
}
