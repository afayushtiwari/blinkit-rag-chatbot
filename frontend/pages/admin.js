import { useEffect, useState } from "react";
import Head from "next/head";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function StatCard({ label, value, hint }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">
        {label}
      </p>
      <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{value}</p>
      {hint ? (
        <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{hint}</p>
      ) : null}
    </div>
  );
}

function Thumbs({ vote }) {
  if (vote === 2) return <span className="text-green-500">{`\u{1F44D}`}</span>;
  if (vote === 1) return <span className="text-red-500">{`\u{1F44E}`}</span>;
  return <span className="text-gray-400">—</span>;
}

function Stars({ stars }) {
  if (!stars) return <span className="text-gray-400 text-sm">not rated</span>;
  return (
    <span className="text-amber-400 text-sm">
      {"★".repeat(stars)}
      {"☆".repeat(Math.max(5 - stars, 0))}
    </span>
  );
}

export default function Admin() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/api/admin/stats`)
      .then((res) => {
        if (!res.ok) throw new Error(`Server responded ${res.status}`);
        return res.json();
      })
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const chat = data?.chat;
  const feedback = data?.feedback;
  const orderStats = data?.orders;
  const topProducts = data?.top_products || [];
  const maxMentions = topProducts.length ? topProducts[0].count : 1;
  const recentFeedback = data?.recent_feedback || [];

  return (
    <div className={darkMode ? "dark" : ""}>
      <Head>
        <title>Admin Dashboard — QuickCart Analytics</title>
      </Head>
      <div className="min-h-screen bg-gray-100 dark:bg-gray-950 transition-colors">
        <header className="bg-white dark:bg-gray-900 shadow-sm sticky top-0 z-10">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-gray-900 dark:text-white">
                Admin Dashboard
              </h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                QuickCart analytics &amp; demo insights
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                <button
                  onClick={() => setDarkMode(false)}
                  className={`px-3 py-1.5 text-xs font-medium ${
                    !darkMode
                      ? "bg-gray-900 text-white dark:bg-white dark:text-gray-900"
                      : "text-gray-500"
                  }`}
                >
                  Light
                </button>
                <button
                  onClick={() => setDarkMode(true)}
                  className={`px-3 py-1.5 text-xs font-medium ${
                    darkMode
                      ? "bg-gray-900 text-white dark:bg-white dark:text-gray-900"
                      : "text-gray-500"
                  }`}
                >
                  Dark
                </button>
              </div>
              <Link
                href="/"
                className="text-sm text-emerald-600 dark:text-emerald-400 font-medium hover:underline"
              >
                {`\u2190`} Store
              </Link>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 py-8">
          {loading && (
            <p className="text-gray-500 dark:text-gray-400">
              Fetching analytics from {API_URL}...
            </p>
          )}

          {error && (
            <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-xl p-4 text-sm text-red-600 dark:text-red-400">
              Couldn&apos;t load admin stats ({error}). Make sure the FastAPI server
              is running at {API_URL}.
            </div>
          )}

          {!loading && !error && data && (
            <>
              {/* Usage cards */}
              <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard
                  label="Chat Turns"
                  value={chat.total_chat_turns}
                  hint={`${chat.total_sessions} sessions`}
                />
                <StatCard
                  label="User Messages"
                  value={chat.total_user_messages}
                  hint={`${chat.messages_last_7_days} in last 7 days`}
                />
                <StatCard
                  label="Orders Placed"
                  value={orderStats.total}
                  hint={`${orderStats.checked_out_sessions} sessions checked out`}
                />
                <StatCard
                  label="Cart Abandonment"
                  value={`${orderStats.abandonment_pct}%`}
                  hint={`${orderStats.abandoned_sessions} of ${orderStats.carts_started} carts abandoned`}
                />
              </section>

              {/* Feedback cards */}
              <section className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard label="Avg. Rating" value={feedback.average_stars || "—"} hint={`based on ${feedback.starred_count} star ratings`} />
                <StatCard label="Satisfaction" value={`${feedback.satisfaction_pct}%`} hint={`${feedback.thumbs_up} up / ${feedback.thumbs_down} down`} />
                <StatCard label="Total Votes" value={feedback.raw_votes} hint={`${feedback.total_feedbacks} feedback records`} />
              </section>

              <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Top products */}
                <section className="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
                  <h2 className="text-sm font-bold text-gray-900 dark:text-white mb-4 uppercase tracking-wide">
                    Top Products Asked
                  </h2>
                  {topProducts.length === 0 ? (
                    <p className="text-sm text-gray-400 dark:text-gray-500">
                      No product mentions in chat yet.
                    </p>
                  ) : (
                    <ul className="space-y-3">
                      {topProducts.map((p) => (
                        <li key={p.id}>
                          <div className="flex justify-between text-sm mb-1">
                            <span className="text-gray-700 dark:text-gray-300 font-medium truncate">
                              {p.name}
                            </span>
                            <span className="text-gray-500 dark:text-gray-400">{p.count}</span>
                          </div>
                          <div className="h-2 rounded-full bg-gray-100 dark:bg-gray-700 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-emerald-600"
                              style={{ width: `${Math.max((p.count / maxMentions) * 100, 4)}%` }}
                            />
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>

                {/* Recent feedback */}
                <section className="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
                  <h2 className="text-sm font-bold text-gray-900 dark:text-white mb-4 uppercase tracking-wide">
                    Recent Feedback
                  </h2>
                  {recentFeedback.length === 0 ? (
                    <p className="text-sm text-gray-400 dark:text-gray-500">
                      No feedback yet. Ask a user to rate a chat reply.
                    </p>
                  ) : (
                    <ul className="space-y-3 max-h-72 overflow-y-auto">
                      {recentFeedback.map((r) => (
                        <li
                          key={r.message_id}
                          className="flex items-start justify-between gap-3 text-sm"
                        >
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <Thumbs vote={r.vote} />
                              <Stars stars={r.stars} />
                            </div>
                            <p className="mt-1 text-gray-600 dark:text-gray-300 line-clamp-2">
                              {r.feedback || <span className="text-gray-400 italic">No comment</span>}
                            </p>
                          </div>
                          <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
                            {new Date(r.created_at).toLocaleDateString()}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}