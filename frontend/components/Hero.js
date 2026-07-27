export default function Hero() {
  return (
    <section className="max-w-7xl mx-auto px-4 mt-6">
      <div className="bg-gradient-to-r from-blinkit-green to-blinkit-green-dark rounded-xl2 p-8 md:p-12 flex flex-col md:flex-row items-center justify-between overflow-hidden shadow-soft">
        <div className="text-white max-w-lg">
          <p className="text-blinkit-yellow font-semibold mb-2">⚡ Delivery in 8 minutes</p>
          <h1 className="text-3xl md:text-4xl font-extrabold leading-tight mb-3">
            Groceries delivered before you finish scrolling
          </h1>
          <p className="text-green-50 mb-4">
            Fresh dairy, snacks, fruits &amp; more — ask our AI shopping assistant anything!
          </p>
          <button className="bg-blinkit-yellow text-gray-900 font-bold px-6 py-2 rounded-xl hover:bg-blinkit-yellow-dark transition-colors">
            Shop Now
          </button>
        </div>
        <div className="hidden md:block text-8xl">🛍️</div>
      </div>
    </section>
  );
}
