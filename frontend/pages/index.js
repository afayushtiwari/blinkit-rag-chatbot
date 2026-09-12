import { useEffect, useState, useMemo } from "react";
import Head from "next/head";
import Header from "../components/Header";
import Hero from "../components/Hero";
import CategoryCard from "../components/CategoryCard";
import ProductCard from "../components/ProductCard";
import Chatbot from "../components/Chatbot";
import CartDrawer from "../components/CartDrawer";
import CheckoutModal from "../components/CheckoutModal";
import { v4 as uuidv4 } from "uuid";

const SESSION_KEY = "quickcart_session_id";

function getSessionId() {
  if (typeof window === "undefined") return uuidv4();
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = uuidv4();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [darkMode, setDarkMode] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [activeCategory, setActiveCategory] = useState(null);
  const [sessionId] = useState(() => getSessionId());
  const [cart, setCart] = useState({ items: [], item_count: 0, subtotal: 0 });
  const [cartOpen, setCartOpen] = useState(false);
  const [checkoutOpen, setCheckoutOpen] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/api/products`)
      .then((res) => {
        if (!res.ok) throw new Error(`Server responded ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setProducts(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const cartRequest = async (path, body) => {
    const response = await fetch(`${API_URL}${path}`, {
      method: path.startsWith("/api/cart/") && path !== `/api/cart/${sessionId}` ? "POST" : "GET",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify({ session_id: sessionId, ...body }) : undefined,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Could not update cart");
    }
    const data = await response.json();
    setCart(data);
    return data;
  };

  const handleAddToCart = async (product) => {
    try {
      await cartRequest("/api/cart/add", { product_id: product.id, quantity: 1 });
    } catch (error) {
      alert(error.message);
    }
  };

  const handleUpdateQuantity = async (productId, quantity) => {
    try {
      await cartRequest("/api/cart/update-quantity", { product_id: productId, quantity });
    } catch (error) {
      alert(error.message);
    }
  };

  const handleRemoveFromCart = async (productId) => {
    try {
      await cartRequest("/api/cart/remove", { product_id: productId, quantity: 1 });
    } catch (error) {
      alert(error.message);
    }
  };

  const categories = useMemo(
    () => [...new Set(products.map((p) => p.category))],
    [products]
  );

  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      const matchesSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCategory = activeCategory ? p.category === activeCategory : true;
      return matchesSearch && matchesCategory;
    });
  }, [products, searchTerm, activeCategory]);

  return (
    <div className={darkMode ? "dark" : ""}>
      <Head>
        <title>QuickCart — Groceries in Minutes</title>
        <meta
          name="description"
          content="Blinkit-inspired grocery delivery app with an AI RAG shopping assistant."
        />
      </Head>

      <div className="min-h-screen bg-gray-100 dark:bg-gray-950 transition-colors">
        <Header
          darkMode={darkMode}
          setDarkMode={setDarkMode}
          cartCount={cart.item_count}
          searchTerm={searchTerm}
          setSearchTerm={setSearchTerm}
          onCartClick={() => setCartOpen(true)}
        />

        <Hero />

        {/* Categories */}
        <section className="max-w-7xl mx-auto px-4 mt-8">
          <h2 className="text-lg font-bold text-gray-800 dark:text-gray-100 mb-3">
            Shop by Category
          </h2>
          <div className="flex gap-3 overflow-x-auto pb-2">
            <CategoryCard
              category="All"
              active={activeCategory === null}
              onClick={() => setActiveCategory(null)}
            />
            {categories.map((cat) => (
              <CategoryCard
                key={cat}
                category={cat}
                active={activeCategory === cat}
                onClick={() => setActiveCategory(cat)}
              />
            ))}
          </div>
        </section>

        {/* Products grid */}
        <section className="max-w-7xl mx-auto px-4 mt-8 pb-24">
          <h2 className="text-lg font-bold text-gray-800 dark:text-gray-100 mb-3">
            {activeCategory ? activeCategory : "All Products"}
          </h2>

          {loading && (
            <p className="text-gray-500 dark:text-gray-400">Loading products...</p>
          )}

          {error && (
            <p className="text-red-500">
              Couldn&apos;t load products from the backend ({error}). Make sure the
              FastAPI server is running at {API_URL}.
            </p>
          )}

          {!loading && !error && filteredProducts.length === 0 && (
            <p className="text-gray-500 dark:text-gray-400">No products match your search.</p>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {filteredProducts.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                onAddToCart={handleAddToCart}
              />
            ))}
          </div>
        </section>

        <Chatbot
          onAddToCart={handleAddToCart}
          onCartChanged={setCart}
          sessionId={sessionId}
        />
        <CartDrawer
          cart={cart}
          open={cartOpen}
          onClose={() => setCartOpen(false)}
          onUpdateQuantity={handleUpdateQuantity}
          onRemove={handleRemoveFromCart}
          onCheckout={() => {
            setCartOpen(false);
            setCheckoutOpen(true);
          }}
        />
        {checkoutOpen && (
          <CheckoutModal
            cart={cart}
            sessionId={sessionId}
            onClose={() => setCheckoutOpen(false)}
            onOrderPlaced={setCart}
          />
        )}
      </div>
    </div>
  );
}
