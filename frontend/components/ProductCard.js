export default function ProductCard({ product, onAddToCart, compact = false }) {
  if (!product) return null;

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

        <div className="mt-auto pt-2 flex items-center justify-between">
          <span className="font-bold text-gray-900 dark:text-white">
            ₹{product.price}
          </span>
          <button
            onClick={() => onAddToCart && onAddToCart(product)}
            className="text-xs font-bold border border-blinkit-green text-blinkit-green px-3 py-1 rounded-lg hover:bg-blinkit-green hover:text-white transition-colors"
          >
            ADD
          </button>
        </div>
      </div>
    </div>
  );
}
