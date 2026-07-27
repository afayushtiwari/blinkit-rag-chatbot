import { useState } from "react";

export default function Header({ darkMode, setDarkMode, cartCount, searchTerm, setSearchTerm, onCartClick }) {
  const [location, setLocation] = useState("Delhi, India");

  return (
    <header className="sticky top-0 z-40 bg-white dark:bg-gray-900 shadow-soft">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-4">
        {/* Logo */}
        <div className="flex items-center gap-1 shrink-0">
          <span className="text-2xl font-extrabold text-blinkit-green">Quick</span>
          <span className="text-2xl font-extrabold text-blinkit-yellow-dark">Cart</span>
        </div>

        {/* Location selector */}
        <button
          className="hidden md:flex flex-col items-start px-3 py-1 rounded-lg hover:bg-blinkit-green-light dark:hover:bg-gray-800 text-left"
          onClick={() => alert("Location selector — demo only")}
        >
          <span className="text-xs text-gray-400">Delivery in 8 minutes</span>
          <span className="text-sm font-semibold text-gray-800 dark:text-gray-100 truncate max-w-[160px]">
            📍 {location}
          </span>
        </button>

        {/* Search bar */}
        <div className="flex-1">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search for milk, chips, bread..."
            className="w-full rounded-xl border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-white px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blinkit-green"
          />
        </div>

        {/* Dark mode toggle */}
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="w-9 h-9 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-lg"
          title="Toggle dark mode"
        >
          {darkMode ? "☀️" : "🌙"}
        </button>

        {/* Cart */}
        <button onClick={onCartClick} className="relative flex items-center gap-2 bg-blinkit-green text-white px-4 py-2 rounded-xl font-semibold hover:bg-blinkit-green-dark transition-colors">
          🛒 Cart
          {cartCount > 0 && (
            <span className="absolute -top-2 -right-2 bg-blinkit-yellow text-gray-900 text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center">
              {cartCount}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}
