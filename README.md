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
│   ├── memory.py                  # Conversation memory (name, history)
│   ├── rag_pipeline.py             # Retrieve -> Augment -> Generate -> Attach
│   ├── main.py                    # FastAPI app & routes
│   ├── requirements.txt
│   └── .env.example                # Copy to .env and add your Gemini key
├── frontend/
│   ├── pages/
│   │   ├── _app.js
│   │   └── index.js               # Homepage
│   ├── components/
│   │   ├── Header.js
│   │   ├── Hero.js
│   │   ├── CategoryCard.js
│   │   ├── ProductCard.js
│   │   └── Chatbot.js             # Floating RAG chatbot widget
│   ├── styles/globals.css
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── next.config.js
│   ├── package.json
│   └── .env.local.example
└── README.md (this file)
```

---

## 2. How the RAG Pipeline Works

1. **Ingest** — `vector_store.py` reads `products.json`, flattens each product's
   name, category, brand, price, rating, description, reviews, and FAQs into
   one text blob per product, and embeds it with Gemini's `text-embedding-004`
   model into **ChromaDB** (persisted to `backend/chroma_db/`).
2. **Retrieve** — On every chat message, `rag_pipeline.py` runs a similarity
   search against ChromaDB to find the top-3 most relevant products.
3. **Augment** — It builds a prompt combining: the system instructions, the
   user's name (if known), the conversation history from `memory.py`, the
   retrieved product context, and the new question.
4. **Generate** — The prompt is sent to **Gemini 1.5 Flash** to produce a
   dynamic, grounded answer — never a hardcoded response.
5. **Attach** — Any product mentioned in the answer gets its full structured
   data (image, price, rating, reviews, related products) attached so the
   frontend can render a rich product card inside the chat bubble.

This is what makes it **agentic**: the LLM decides how to use the retrieved
context (summarize reviews, recommend related items, answer a FAQ) rather
than following a fixed script.

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

The bot will remember your name and previous questions throughout the
session (until you refresh the page, which starts a new session ID).

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
5. Add environment variable `GOOGLE_API_KEY` with your Gemini key.
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
2. **RAG architecture**: Show the 4-step diagram — Retrieve (ChromaDB
   similarity search) → Augment (prompt + memory) → Generate (Gemini) →
   Attach (structured product cards). Emphasize *why* RAG beats a plain LLM:
   it prevents hallucinated prices/products by grounding answers in your
   actual product database.
3. **Live demo**: Ask a product question, a follow-up ("what do customers
   like about it"), then a recommendation question — this demonstrates
   retrieval, memory, and dynamic generation in one flow.
4. **Tech stack justification**: LangChain (orchestration), ChromaDB (vector
   search), Gemini (LLM + embeddings), FastAPI (lightweight Python backend),
   Next.js + Tailwind (modern frontend).
5. **Memory**: Show that saying "my name is X" makes the bot use your name
   in later replies — this proves conversational memory, not just stateless
   Q&A.
6. **Code walkthrough** (if asked): Open `rag_pipeline.py` and narrate the
   `retrieve → generate_response → _build_product_cards` flow.

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| Frontend shows "Couldn't load products" | Backend isn't running or wrong `NEXT_PUBLIC_API_URL` |
| Chatbot says it couldn't reach the assistant | Check backend terminal for errors; confirm `GOOGLE_API_KEY` is set |
| `GoogleGenerativeAIEmbeddings` errors on startup | Re-check your API key and that billing/usage limits aren't exceeded |
| Vector DB seems stale after editing products.json | Delete `backend/chroma_db/` and re-run `python vector_store.py` |
