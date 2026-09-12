# QuickCart — Blinkit-Style Agentic AI RAG Chatbot 🛒🤖

A full-stack, Blinkit-inspired grocery e-commerce website with an **Agentic RAG (Retrieval-Augmented Generation) chatbot** built for a Machine Learning / Generative AI / Agentic AI college project.

---

## 1. Project Folder Structure

```
blinkit-rag-chatbot/
├── backend/
│   ├── data/
│   │   └── products.json          # 20-product dataset (hierarchical fields)
│   ├── vector_store.py            # ChromaDB setup + embedding ingestion
│   ├── agent.py                   # Gemini function-calling tools + agent loop
│   ├── rag_pipeline.py            # Memory -> Agent loop -> Attach product cards
│   ├── memory.py                  # Conversation memory (name, history)
│   ├── feedback.py                # Chat feedback (thumbs + stars) in SQLite
│   ├── cart.py                    # SQLite-backed cart service
│   ├── orders.py                  # Demo checkout/order service
│   ├── main.py                    # FastAPI app & routes
│   ├── requirements.txt
│   └── .env.example                # Copy to .env and add your Gemini key
├── frontend/
│   ├── pages/
│   │   ├── _app.js
│   │   └── index.js               # Homepage (products, cart drawer, checkout)
│   ├── components/
│   │   ├── Header.js
│   │   ├── Hero.js
│   │   ├── CategoryCard.js
│   │   ├── ProductCard.js
│   │   ├── Chatbot.js             # Floating agentic chatbot widget
│   │   ├── CartDrawer.js
│   │   └── CheckoutModal.js
│   ├── styles/globals.css
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── next.config.js
│   ├── package.json
│   └── .env.local.example
└── README.md (this file)
```

---

## 2. How the (Agentic RAG) Pipeline Works

This chatbot is an **agent**, not a fixed-script bot. On every chat message
the backend runs a **tool-calling loop** where the Gemini model decides what
to do, calls tools, sees their results, and keeps going until it can answer:

1. **Ingest** — `vector_store.py` reads `products.json`, flattens each
   product's name, category, brand, price, rating, description, reviews, and
   FAQs into one text blob per product, and embeds it with a local
   sentence-transformer model (`all-MiniLM-L6-v2`) into **ChromaDB**.
2. **Agent loop** (`agent.py`) — the Gemini model is bound to real function
   declarations:
   - `search_products` → **Retrieve**: semantic similarity search over
     ChromaDB for the top-3 relevant products (this is the RAG grounding that
     prevents hallucinated prices/products).
   - `get_product_details` → fetch full reviews, FAQs, and related items.
   - `view_cart / add_to_cart / update_cart_quantity / remove_from_cart` →
     manage the customer's cart yourself, with product IDs coming from the
     search results — never inferred.
   - The loop runs up to 6 steps: model requests a tool → backend executes it
     → the result is fed back → repeat until the model writes a plain-text
     answer.
3. **Memory** — `memory.py` (SQLite) persists the customer's name and every
   turn, so follow-ups like *"what do customers like about it?"* stay grounded.
4. **Attach** — any product the agent touched and named in its answer gets its
   full structured data (image, price, rating, reviews, related products)
   attached, so the frontend renders a rich product card inside the chat
   bubble. The current cart is also returned with every chat reply so the UI
   badge stays in sync after the agent adds/removes items.

Because the model decides *how* to use its tools, this is genuinely agentic:
the same endpoint handles a product question, a review summary, a "recommend
similar items" request, *and* an "add 2 Amul Milk to my cart" command.

---

## 3. Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- A free **Google Gemini API key** — get one at
  https://aistudio.google.com/app/apikey

---

## 4. Running the Backend Locally

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Add your Gemini API key
cp .env.example .env
# then open .env and paste your real key after GOOGLE_API_KEY=
# (optional) LLM_MODEL lets you swap the Gemini model used by the agent

# Build the vector database (run once, or whenever products.json changes)
python vector_store.py

# Start the API server
uvicorn main:app --reload --port 8000
```

The backend will be live at **http://localhost:8000**. Visit
`http://localhost:8000/api/products` in your browser to confirm it's working.

---

## 5. Running the Frontend Locally

```bash
cd frontend
npm install

cp .env.local.example .env.local
# NEXT_PUBLIC_API_URL should already point to http://localhost:8000

npm run dev
```

Open **http://localhost:3000** — you should see the QuickCart homepage with
products loaded from your FastAPI backend, and a green chat bubble in the
bottom-right corner.

---

## 6. Connecting Frontend ↔ Backend

The connection is controlled by a single environment variable:

- `frontend/.env.local` → `NEXT_PUBLIC_API_URL=http://localhost:8000` (or your
  deployed Render URL in production)

Every API call in the frontend (`pages/index.js` and `components/Chatbot.js`)
reads this variable, so you never need to hardcode URLs — just update this
one value when you deploy.

---

## 7. Trying the Chatbot

Click the floating 💬 button and try:

- "Hi, my name is Ayush"
- "Show me details of Amul Milk"
- "What do customers like most about it?"
- "Can you recommend similar products?"
- "What snacks do you have under 50 rupees?"
- **Cart (via tools, not hardcoded rules):**
  - "Add 2 Amul Milk to my cart"
  - "Show my cart"
  - "Change Amul Milk quantity to 3"
  - "Remove Amul Butter from my cart"

The bot will remember your name and previous questions throughout the
session (until you refresh the page, which starts a new session ID), and any
cart changes it makes appear instantly in the cart badge/drawer.

---

## 8. Deployment

### Frontend → Vercel
1. Push this repo to GitHub.
2. Go to https://vercel.com/new and import the `frontend/` folder as the
   project root (set "Root Directory" to `frontend`).
3. Add an environment variable: `NEXT_PUBLIC_API_URL` = your Render backend
   URL (see below), e.g. `https://quickcart-backend.onrender.com`.
4. Deploy.

### Backend → Render
1. Go to https://render.com → New → Web Service → connect your GitHub repo.
2. Set **Root Directory** to `backend`.
3. Build command: `pip install -r requirements.txt && python vector_store.py`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variable `GOOGLE_API_KEY` with your Gemini key (and
   optionally `LLM_MODEL` if you want a different Gemini model).
6. Deploy, then copy the generated `https://....onrender.com` URL into
   Vercel's `NEXT_PUBLIC_API_URL`.

> Note: Render's free tier spins down after inactivity, so the first request
> after idle time may take ~30-60 seconds — mention this during your demo if
> it happens.

---

## 9. Explaining This Project to Your Teacher

Use this structure when presenting:

1. **Problem statement**: Traditional e-commerce search is keyword-based;
   customers can't ask natural questions. We built a RAG-based conversational
   assistant that understands intent and retrieves grounded product data.
2. **Agentic + RAG architecture**: Show the agentic loop — the LLM is bound
   to function declarations (`search_products`, `get_product_details`, cart
   tools) and *decides* which to call. `search_products` performs the
   **Retrieve** step (ChromaDB similarity search); tool results are fed back
   (the **Augment** step); then the model **Generates** a grounded answer; and
   the app **Attaches** structured product cards. Emphasize *why* RAG beats a
   plain LLM: retrieval grounds the model in actual product data, preventing
   hallucinated prices/products — and function calling is what lets the same
   bot answer questions *and* take real actions (cart) instead of being a
   read-only Q&A.
3. **Live demo**: Ask a product question, a follow-up ("what do customers
   like about it"), then a recommendation question, then "Add 2 Amul Milk to
   my cart" — this demonstrates retrieval, memory, dynamic generation, and
   **tool use (cart mutation)** in one flow.
4. **Tech stack justification**: LangChain (orchestration + tool-calling loop),
   ChromaDB (vector search), Gemini (LLM, function calling + embeddings),
   FastAPI (lightweight Python backend), Next.js + Tailwind (modern frontend).
5. **Memory**: Show that saying "my name is X" makes the bot use your name
   in later replies — this proves conversational memory, not just stateless
   Q&A.
6. **Code walkthrough** (if asked): Open `agent.py` and narrate the
   `_build_tools` (the function declarations and how each tool is backed by
   real code) and `run_agent_turn` (the loop), then `rag_pipeline.py` for how
   memory is loaded and product cards get attached.

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| Frontend shows "Couldn't load products" | Backend isn't running or wrong `NEXT_PUBLIC_API_URL` |
| Chatbot says it couldn't reach the assistant | Check backend terminal for errors; confirm `GOOGLE_API_KEY` is set |
| `GoogleGenerativeAIEmbeddings` errors on startup | Re-check your API key and that billing/usage limits aren't exceeded |
| Vector DB seems stale after editing products.json | Delete `backend/chroma_db/` and re-run `python vector_store.py` |

---

## 11. Next Features (Roadmap)

Status legend: ✅ **Done** · 🚧 **Partial** · ⬜ **Planned**

| # | Feature | Status | Notes |
|---|---|---|---|
| 1 | Multi-item cart in one message | ⬜ Planned | "Add 2 Amul Milk and 1 Maggi" triggers two `add_to_cart` calls in one agent turn |
| 2 | Streaming responses (SSE) | ⬜ Planned | Bot answer streams word-by-word instead of a spinner |
| 3 | Chat feedback 👍/👎 + ⭐ | ✅ Done | `feedback.py` (SQLite), `POST /api/feedback`, `GET /api/feedback/stats`; thumbs + 5-star row under every bot answer |
| 4 | Delivery slot booking | ✅ Done | `GET/POST /api/delivery-slots`, slot picker in checkout, slot is booked in the same transaction as the order |
| 5 | Order tracking | ✅ Done | `get_order_status` tool + live timeline (Placed → Packed → On the way → Delivered) that resolves from elapsed time; shown in the checkout confirmation and chat |
| 6 | Voice input | ✅ Done | Web Speech API mic button in the chat widget (works in Chrome; text answer still rendered) |
| 7 | Query rewriting | ⬜ Planned | Rewrite ambiguous follow-ups ("what about the curd?") into a standalone search query before retrieval |
| 8 | RAG evaluation harness | ✅ Done | `backend/evaluate.py` scores `search_products` over 24 question → expected-product pairs (Accuracy@1, Recall@3, MRR) |
| 9 | Admin analytics dashboard | ✅ Done | `/admin` page + `GET /api/admin/stats`: chat counts, top asked products, average ⭐, cart-abandonment, recent feedback |
| 10 | Conversation history UI | ✅ Done | 🕘 panel in the widget: `GET /api/chat/sessions` + `GET /api/chat/history`, browse and resume past chats |

---
