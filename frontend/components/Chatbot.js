import { useEffect, useRef, useState } from "react";
import ProductCard from "./ProductCard";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const welcomeMessage = {
  role: "bot",
  text: "Hi! 👋 I'm BlinkBot, your AI shopping assistant. Ask me about any product - try \"Show me details of Amul Milk\" or \"What snacks do you have?\"",
  products: [],
};

export default function Chatbot({ onAddToCart, onCartChanged, sessionId }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([welcomeMessage]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (!sessionId) return;

    fetch(`${API_URL}/api/chat/history/${sessionId}`)
      .then((response) => {
        if (!response.ok) throw new Error("Could not restore chat history");
        return response.json();
      })
      .then((data) => {
        if (data.messages?.length) {
          setMessages(data.messages);
        }
      })
      .catch((error) => console.error(error))
      .finally(() => setHistoryLoaded(true));
  }, [sessionId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading, open]);

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading || !sessionId) return;

    const userMsg = { role: "user", text: trimmed, products: [] };
    setMessages((previous) => [...previous, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: trimmed }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server responded with ${response.status}`);
      }

      const data = await response.json();
      if (data.cart) onCartChanged?.(data.cart);
      setMessages((previous) => [
        ...previous,
        { role: "bot", text: data.answer, products: data.products || [] },
      ]);
    } catch (error) {
      setMessages((previous) => [
        ...previous,
        {
          role: "bot",
          text: `⚠️ Sorry, I couldn't reach the assistant right now (${error.message || "network error"}). Please make sure the backend server is running and try again.`,
          products: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className="fixed bottom-6 right-6 z-50 bg-blinkit-green hover:bg-blinkit-green-dark text-white rounded-full w-16 h-16 shadow-lg flex items-center justify-center text-2xl transition-transform hover:scale-105"
        aria-label="Open chatbot"
      >
        {open ? "✕" : "💬"}
      </button>

      {open && (
        <div className="fixed bottom-24 right-6 z-50 w-[92vw] max-w-sm h-[70vh] max-h-[600px] bg-white dark:bg-gray-900 rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-gray-100 dark:border-gray-800">
          <div className="bg-blinkit-green text-white px-4 py-3 flex items-center gap-2">
            <span className="text-xl">🤖</span>
            <div>
              <p className="font-bold leading-tight">BlinkBot</p>
              <p className="text-xs text-green-100 leading-tight">AI Shopping Assistant</p>
            </div>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto chat-scroll px-3 py-4 space-y-4 bg-gray-50 dark:bg-gray-950">
            {!historyLoaded && sessionId && <p className="text-center text-xs text-gray-500">Restoring your chat...</p>}
            {messages.map((message, index) => (
              <div key={index} className={`fade-in-up flex flex-col ${message.role === "user" ? "items-end" : "items-start"}`}>
                <div className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm whitespace-pre-wrap ${message.role === "user" ? "bg-blinkit-green text-white rounded-br-sm" : "bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-100 rounded-bl-sm shadow-soft"}`}>
                  {message.text}
                </div>

                {message.products?.length > 0 && (
                  <div className="mt-2 flex gap-3 overflow-x-auto max-w-full pb-1">
                    {message.products.map((product) => (
                      <ProductCard key={product.id} product={product} onAddToCart={onAddToCart} compact />
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

          <div className="border-t border-gray-100 dark:border-gray-800 p-3 flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              disabled={!sessionId}
              placeholder={sessionId ? "Ask about a product..." : "Preparing your chat..."}
              className="flex-1 rounded-xl border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blinkit-green disabled:opacity-60"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !sessionId}
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
