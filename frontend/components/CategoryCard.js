const CATEGORY_ICONS = {
  Dairy: "🥛",
  Bakery: "🍞",
  Snacks: "🍟",
  Beverages: "🥤",
  "Instant Food": "🍜",
  Fruits: "🍎",
  Chocolates: "🍫",
  Grocery: "🧂",
};

export default function CategoryCard({ category, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center justify-center gap-2 min-w-[110px] p-4 rounded-xl2 shadow-soft transition-transform hover:-translate-y-1 ${
        active
          ? "bg-blinkit-green text-white"
          : "bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-100"
      }`}
    >
      <span className="text-3xl">{CATEGORY_ICONS[category] || "🛒"}</span>
      <span className="text-sm font-semibold">{category}</span>
    </button>
  );
}
