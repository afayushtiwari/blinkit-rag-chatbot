export default function ProductCard({ product, onAddToCart, compact = false }) {
  if (!product) return null;

  const stock = Number.isFinite(product.stock) ? product.stock : null;
  const outOfStock = stock !== null && stock <= 0;
  const lowStock = stock !== null && stock > 0 && stock <= 3;

  const FALLBACK_IMAGES = {
    Dairy: "https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400",
    Bakery: "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400",
    Snacks: "https://images.unsplash.com/photo-1566478989037-eec170784d0b?w=400",
    Beverages: "https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400",
    "Instant Food": "https://images.unsplash.com/photo-1612929633738-8fe44f7ec841?w=400",
    Fruits: "https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=400",
    Chocolates: "https://images.unsplash.com/photo-1606312619070-d48b4c652a52?w=400",
    Grocery: "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400",
  };

  const fallbackSrc =
    FALLBACK_IMAGES[product.category] || FALLBACK_IMAGES.Grocery;

  const handleImageError = (e) => {
    if (e.currentTarget.src !== fallbackSrc) {
      e.currentTarget.src = fallbackSrc;
    }
  };

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
          onError={handleImageError}
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
          <div className="flex flex-col">
            <div className="flex items-center gap-1">
              <span className="font-bold text-gray-900 dark:text-white">
                ₹{product.price}
              </span>
              {product.mrp && product.mrp > product.price && (
                <>
                  <span className="text-[10px] text-gray-400 line-through">
                    ₹{product.mrp}
                  </span>
                  <span className="text-[10px] font-bold text-green-600">
                    {Math.round((1 - product.price / product.mrp) * 100)}% OFF
                  </span>
                </>
              )}
            </div>
            {product.unit && (
              <span className="text-[10px] text-gray-400 dark:text-gray-500">
                {product.unit}
              </span>
            )}
          </div>
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