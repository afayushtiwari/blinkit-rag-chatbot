import { useState, useRef, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import ProductCard from "./ProductCard";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const WELCOME_MESSAGE =
  "Hi! 👋 I'm BlinkBot, your AI shopping assistant. Ask me about any product — try \"Show me details of Amul Milk\", \"What snacks are under ₹50?\" or \"Add 2 Amul Milk to my cart\".";

export default function Chatbot({ onAddToCart, onCartChanged, sessionId }) {
  const [open, setOpen] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([
    {
      role: "bot",
      text: WELCOME_MESSAGE,
      products: [],
    },
  ]);
  const [feedback, setFeedback] = useState({});
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [listening, setListening] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [historyMessages, setHistoryMessages] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const scrollRef = useRef(null);
  const recognitionRef = useRef(null);

  const formatTime = (iso) => {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  };

  const openHistory = async () => {
    setHistoryOpen(true);
    setSelectedSession(null);
    setHistoryMessages([]);
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const res = await fetch(`${API_URL}/api/chat/sessions`);
      if (!res.ok) throw new Error(`Server responded ${res.status}`);
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch (err) {
      setHistoryError(err.message);
    } finally {
      setHistoryLoading(false);
    }
  };

  const loadSession = async (session) => {
    setSelectedSession(session);
    setHistoryMessages([]);
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const res = await fetch(
        `${API_URL}/api/chat/history?session_id=${encodeURIComponent(session.session_id)}`
      );
      if (!res.ok) throw new Error(`Server responded ${res.status}`);
      const data = await res.json();
      setHistoryMessages(data.messages || []);
    } catch (err) {
      setHistoryError(err.message);
      setHistoryMessages([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const resumeSession = () => {
    const converted = historyMessages.map((m) => ({
      role: m.role === "user" ? "user" : "bot",
      text: m.text,
      products: [],
    }));
    setMessages(
      converted.length
        ? converted
        : [{ role: "bot", text: WELCOME_MESSAGE, products: [] }]
    );
    if (selectedSession) setCurrentSessionId(selectedSession.session_id);
    setHistoryOpen(false);
  };

  const newChat = () => {
    setCurrentSessionId(uuidv4());
    setMessages([{ role: "bot", text: WELCOME_MESSAGE, products: [] }]);
    setHistoryOpen(false);
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading, open]);

  // Adopt the page-level persistent session id once it is ready, then restore
  // any persisted conversation so a refresh doesn't lose the chat.
  useEffect(() => {
    if (sessionId) setCurrentSessionId((prev) => prev || sessionId);
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || historyLoaded) return;

    fetch(`${API_URL}/api/chat/history/${sessionId}`)
      .then((res) => {
        if (!res.ok) throw new Error(`Server responded ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (data.messages?.length) {
          setMessages(data.messages);
        }
      })
      .catch((err) => console.error(err))
      .finally(() => setHistoryLoaded(true));
  }, [sessionId, historyLoaded]);

  const sendFeedback = async (messageId, vote, stars = 0, note = "") => {
    if (!messageId) return;
    setFeedback((prev) => ({ ...prev, [messageId]: { vote, stars, saved: true } }));
    try {
      await fetch(`${API_URL}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_id: messageId,
          session_id: currentSessionId,
          vote,
          stars,
          feedback: note,
        }),
      });
    } catch {
      setFeedback((prev) => {
        const next = { ...prev };
        delete next[messageId];
        return next;
      });
    }
  };

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading || !currentSessionId || !historyLoaded) return;

    const userMsg = { role: "user", text: trimmed, products: [] };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: currentSessionId, message: trimmed }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server responded with ${res.status}`);
      }

      const data = await res.json();
      if (data.cart) onCartChanged?.(data.cart);
      setMessages((prev) => [
        ...prev,
        {
          messageId: data.message_id,
          role: "bot",
          text: data.answer,
          products: data.products || [],
        },
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

  const toggleVoice = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      window.alert("Voice input isn't supported in this browser. Please try Google Chrome.");
      return;
    }

    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0].transcript)
        .join("");
      setInput(transcript);
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);

    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
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
            <div className="flex-1">
              <p className="font-bold leading-tight">BlinkBot</p>
              <p className="text-xs text-green-100 leading-tight">AI Shopping Assistant</p>
            </div>
            <button
              onClick={openHistory}
              title="Show conversation history"
              className="p-1.5 rounded-lg hover:bg-green-600/60 text-lg leading-none"
            >
              🕘
            </button>
            <button
              onClick={newChat}
              title="Start a new chat"
              className="p-1.5 rounded-lg hover:bg-green-600/60 text-lg leading-none"
            >
              ＋
            </button>
          </div>

          {/* Messages */}
          <div className="relative flex-1">
            <div
              ref={scrollRef}
              className="absolute inset-0 overflow-y-auto chat-scroll px-3 py-4 space-y-4 bg-gray-50 dark:bg-gray-950"
            >
            {!historyLoaded && (
              <p className="text-center text-xs text-gray-500 dark:text-gray-400">
                Restoring your chat...
              </p>
            )}
            {messages.map((msg, idx) => {
              const msgFeedback = msg.messageId ? feedback[msg.messageId] || {} : null;
              return (
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

                  {/* Feedback: thumbs + stars on every real bot answer */}
                  {msg.role === "bot" && msg.messageId && (
                    <div className="mt-1.5 flex items-center gap-2 text-[11px] text-gray-500 dark:text-gray-400">
                      <button
                        onClick={() => sendFeedback(msg.messageId, 2, msgFeedback.stars || 0)}
                        className={`px-1.5 py-0.5 rounded ${msgFeedback.vote === 2 ? "bg-green-100 text-green-600" : "hover:bg-gray-200 dark:hover:bg-gray-700"}`}
                        title="Good answer"
                      >
                        👍
                      </button>
                      <button
                        onClick={() => sendFeedback(msg.messageId, 1, msgFeedback.stars || 0)}
                        className={`px-1.5 py-0.5 rounded ${msgFeedback.vote === 1 ? "bg-red-100 text-red-500" : "hover:bg-gray-200 dark:hover:bg-gray-700"}`}
                        title="Bad answer"
                      >
                        👎
                      </button>
                      <div className="flex items-center gap-0.5 text-sm leading-none">
                        {[1, 2, 3, 4, 5].map((n) => (
                          <button
                            key={n}
                            onClick={() => sendFeedback(msg.messageId, msgFeedback.vote || 2, n)}
                            className={`${(msgFeedback.stars || 0) >= n ? "text-amber-400" : "text-gray-300 dark:text-gray-600 hover:text-amber-300"}`}
                            title={`${n} star${n > 1 ? "s" : ""}`}
                          >
                            ★
                          </button>
                        ))}
                      </div>
                      {msgFeedback.vote && (
                        <span className="text-green-600 dark:text-green-400">Thanks!</span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}

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

            {/* History panel (Feature #10) */}
            {historyOpen && (
              <div className="absolute inset-0 z-10 bg-white dark:bg-gray-900 flex flex-col">
                <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                  <p className="text-sm font-bold text-gray-800 dark:text-gray-100">
                    {selectedSession ? "Conversation" : "Recent conversations"}
                  </p>
                  <button
                    onClick={() => setHistoryOpen(false)}
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-sm px-2 py-0.5"
                  >
                    ✕
                  </button>
                </div>

                {selectedSession ? (
                  <>
                    <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
                      {historyMessages.map((m, i) => (
                        <div
                          key={i}
                          className={`flex ${
                            m.role === "user" ? "justify-end" : "justify-start"
                          }`}
                        >
                          <div
                            className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm whitespace-pre-wrap ${
                              m.role === "user"
                                ? "bg-blinkit-green text-white rounded-br-sm"
                                : "bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-100 rounded-bl-sm"
                            }`}
                          >
                            {m.text}
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="p-3 border-t border-gray-100 dark:border-gray-800 flex gap-2">
                      <button
                        onClick={() => setSelectedSession(null)}
                        className="flex-1 rounded-xl border border-gray-200 dark:border-gray-700 text-sm font-medium py-2 hover:bg-gray-50 dark:hover:bg-gray-800"
                      >
                        {`\u2190`} Back
                      </button>
                      <button
                        onClick={resumeSession}
                        className="flex-1 rounded-xl bg-blinkit-green text-white text-sm font-semibold py-2 hover:bg-blinkit-green-dark"
                      >
                        Resume this chat
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="flex-1 overflow-y-auto px-3 py-3">
                    {historyLoading && (
                      <p className="text-sm text-gray-500 dark:text-gray-400">Loading...</p>
                    )}
                    {historyError && (
                      <p className="text-sm text-red-500 dark:text-red-400">
                        Couldn&apos;t load history: {historyError}
                      </p>
                    )}
                    {!historyLoading &&
                      !historyError &&
                      sessions.length === 0 && (
                        <p className="text-sm text-gray-400 dark:text-gray-500">
                          No conversations yet. Start chatting and your history will appear here.
                        </p>
                      )}
                    {!historyLoading &&
                      !historyError &&
                      sessions.map((s) => (
                        <button
                          key={s.session_id}
                          onClick={() => loadSession(s)}
                          className="w-full text-left rounded-xl px-3 py-2.5 mb-2 border border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800"
                        >
                          <p className="text-sm font-semibold text-gray-800 dark:text-gray-100 truncate">
                            {s.user_name || "Guest"}
                          </p>
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                            {s.message_count} message{s.message_count !== 1 ? "s" : ""} ·{" "}
                            {formatTime(s.updated_at)}
                          </p>
                          <p className="text-xs text-gray-400 dark:text-gray-500 truncate mt-0.5">
                            {s.session_id}
                          </p>
                        </button>
                      ))}
                  </div>
                )}
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
              disabled={!currentSessionId}
              placeholder={
                !currentSessionId
                  ? "Preparing your chat..."
                  : listening
                    ? "Listening... speak now 🎙️"
                    : "Ask about a product..."
              }
              className="flex-1 rounded-xl border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blinkit-green disabled:opacity-60"
            />
            <button
              onClick={toggleVoice}
              disabled={!currentSessionId}
              title={listening ? "Stop voice input" : "Speak your question"}
              className={`rounded-xl px-3 py-2 text-base font-semibold transition-colors disabled:opacity-50 ${
                listening
                  ? "bg-red-500 text-white animate-pulse"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
              }`}
            >
              {listening ? "⏹" : "🎤"}
            </button>
            <button
              onClick={sendMessage}
              disabled={loading || !currentSessionId || !historyLoaded}
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
