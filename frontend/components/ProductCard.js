export default function ProductCard({ product, onAddToCart, compact = false }) {
  if (!product) return null;

  const stock = Number.isFinite(product.stock) ? product.stock : null;
  const outOfStock = stock !== null && stock <= 0;
  const lowStock = stock !== null && stock > 0 && stock <= 3;

  return (
    <div
      className={`bg-white dark:bg-gray-800 rounded-xl2 shadow-soft hover:shadow-lg transition-shadow overflow-hidden flex flex-col ${
        compact ? "w-56" : ""
      }`}
    >
      <div className="relative bg-gray-50 dark:bg-gray-700">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={product.image_url}
          alt={product.name}
          className="w-full h-32 object-cover"
        />
        {product.rating && (
          <span className="absolute top-2 left-2 bg-blinkit-green text-white text-xs font-bold px-2 py-0.5 rounded-md flex items-center gap-1">
            ★ {product.rating}
          </span>
        )}
        {outOfStock && (
          <span className="absolute top-2 right-2 bg-red-600 text-white text-xs font-bold px-2 py-0.5 rounded-md">
            Out of stock
          </span>
        )}
      </div>

      <div className="p-3 flex flex-col flex-1">
        <h3 className="font-semibold text-gray-800 dark:text-gray-100 text-sm line-clamp-2">
          {product.name}
        </h3>
        {product.description && !compact && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">
            {product.description}
          </p>
        )}

        {lowStock && (
          <p className="mt-1 text-xs font-semibold text-orange-600 dark:text-orange-400">
            Only {stock} left
          </p>
        )}

        <div className="mt-auto pt-2 flex items-center justify-between">
          <span className="font-bold text-gray-900 dark:text-white">
            ₹{product.price}
          </span>
          <button
            onClick={() => onAddToCart && onAddToCart(product)}
            disabled={outOfStock}
            className={
              outOfStock
                ? "text-xs font-bold border border-gray-300 text-gray-400 px-3 py-1 rounded-lg cursor-not-allowed"
                : "text-xs font-bold border border-blinkit-green text-blinkit-green px-3 py-1 rounded-lg hover:bg-blinkit-green hover:text-white transition-colors"
            }
          >
            {outOfStock ? "SOLD OUT" : "ADD"}
          </button>
        </div>
      </div>
    </div>
  );
}