import { useState, useRef, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import ProductCard from "./ProductCard";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Chatbot({ onAddToCart, onCartChanged, sessionId }) {
  const [open, setOpen] = useState(false);
  const [generatedSessionId] = useState(() => uuidv4());
  const activeSessionId = sessionId || generatedSessionId;
  const [messages, setMessages] = useState([
    {
      role: "bot",
      text: "Hi! 👋 I'm BlinkBot, your AI shopping assistant. Ask me about any product — try \"Show me details of Amul Milk\" or \"What snacks do you have?\"",
      products: [],
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading, open]);

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    const userMsg = { role: "user", text: trimmed, products: [] };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: activeSessionId, message: trimmed }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server responded with ${res.status}`);
      }

      const data = await res.json();
      if (data.cart) onCartChanged?.(data.cart);
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: data.answer, products: data.products || [] },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          text:
            "⚠️ Sorry, I couldn't reach the assistant right now (" +
            (err.message || "network error") +
            "). Please make sure the backend server is running and try again.",
          products: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen(!open)}
        className="fixed bottom-6 right-6 z-50 bg-blinkit-green hover:bg-blinkit-green-dark text-white rounded-full w-16 h-16 shadow-lg flex items-center justify-center text-2xl transition-transform hover:scale-105"
        aria-label="Open chatbot"
      >
        {open ? "✕" : "💬"}
      </button>

      {/* Chat window */}
      {open && (
        <div className="fixed bottom-24 right-6 z-50 w-[92vw] max-w-sm h-[70vh] max-h-[600px] bg-white dark:bg-gray-900 rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-gray-100 dark:border-gray-800">
          {/* Header */}
          <div className="bg-blinkit-green text-white px-4 py-3 flex items-center gap-2">
            <span className="text-xl">🤖</span>
            <div>
              <p className="font-bold leading-tight">BlinkBot</p>
              <p className="text-xs text-green-100 leading-tight">AI Shopping Assistant</p>
            </div>
          </div>

          {/* Messages */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto chat-scroll px-3 py-4 space-y-4 bg-gray-50 dark:bg-gray-950"
          >
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`fade-in-up flex flex-col ${
                  msg.role === "user" ? "items-end" : "items-start"
                }`}
              >
                <div
                  className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm whitespace-pre-wrap ${
                    msg.role === "user"
                      ? "bg-blinkit-green text-white rounded-br-sm"
                      : "bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-100 rounded-bl-sm shadow-soft"
                  }`}
                >
                  {msg.text}
                </div>

                {/* Product cards inside chat */}
                {msg.products && msg.products.length > 0 && (
                  <div className="mt-2 flex gap-3 overflow-x-auto max-w-full pb-1">
                    {msg.products.map((p) => (
                      <ProductCard
                        key={p.id}
                        product={p}
                        onAddToCart={onAddToCart}
                        compact
                      />
                    ))}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex items-start">
                <div className="bg-white dark:bg-gray-800 px-4 py-3 rounded-2xl rounded-bl-sm shadow-soft flex gap-1">
                  <span className="typing-dot w-2 h-2 bg-gray-400 rounded-full inline-block" />
                  <span className="typing-dot w-2 h-2 bg-gray-400 rounded-full inline-block" />
                  <span className="typing-dot w-2 h-2 bg-gray-400 rounded-full inline-block" />
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="border-t border-gray-100 dark:border-gray-800 p-3 flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about a product..."
              className="flex-1 rounded-xl border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blinkit-green"
            />
            <button
              onClick={sendMessage}
              disabled={loading}
              className="bg-blinkit-green text-white rounded-xl px-4 py-2 text-sm font-semibold disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </>
  );
}
