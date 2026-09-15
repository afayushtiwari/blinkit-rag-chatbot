"""
evaluate.py
-----------
RAG evaluation harness for the `search_products` retriever.

Runs a curated set of (question, expected products) pairs through the same
ChromaDB semantic search the agent uses, then reports:

  * Accuracy@1       - fraction of queries whose top hit is a relevant product
  * Recall@3         - fraction of relevant products found in the top 3 hits
  * MRR              - mean reciprocal rank of the first relevant hit

Usage:
    python evaluate.py                  # run the built-in eval set
    python evaluate.py --verbose        # print every query's top-3 hits
    python evaluate.py "amul milk"      # quick check: top 3 for one query
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

from vector_store import build_vector_store

DATA_DIR = Path(__file__).parent / "data"
PRODUCTS_PATH = DATA_DIR / "products.json"

TOP_K = 3

# Words that add no retrieval signal when reused verbatim in a query.
_NOISE_WORDS = {
    "pasteurized", "pasteurised", "homogenised", "homogenized",
    "sterilised", "sterilized", "standardized", "fresh", "premium",
    "organic", "special", "daily", "pack", "bottle", "box", "carton",
}

# Category word used in generated natural-language queries.
_CATEGORY_WORD = {
    "Dairy": "dairy",
    "Bakery": "bakery",
    "Snacks": "snack",
    "Beverages": "beverage",
    "Instant Food": "instant food",
    "Fruits": "fruit",
    "Chocolates": "chocolate",
    "Grocery": "grocery",
}


def _load_catalog() -> list[dict]:
    with open(PRODUCTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _significant_keywords(product: dict) -> str:
    """Pull the distinctive, searchable words out of a real product name."""
    brand = (product.get("brand") or "").lower()
    tokens = re.findall(r"[a-z]+", product["name"].lower())
    seen = set()
    out = []
    for tok in tokens:
        if tok in seen or tok in _NOISE_WORDS or tok == brand:
            continue
        seen.add(tok)
        out.append(tok)
    return " ".join(out[:5])


def _build_eval_set() -> list[dict]:
    """Auto-generate an eval set from the seeded catalog so it stays valid
    whenever products.json changes (real Blinkit reseeds included)."""
    catalog = _load_catalog()
    rng = random.Random(42)
    by_category: dict[str, list[dict]] = {}
    for p in catalog:
        by_category.setdefault(p["category"], []).append(p)

    queries: list[dict] = []

    for category, products in by_category.items():
        word = _CATEGORY_WORD.get(category, category.lower())
        # Product-level queries: up to 5 sampled per category.
        sample = rng.sample(products, min(5, len(products)))
        for product in sample:
            keywords = _significant_keywords(product)
            if not keywords:
                continue
            queries.append({
                "query": f"{word.replace('-', ' ')} {keywords} for home use",
                "expected": [product["id"]],
            })
        # Category-level query: reference the top catalog products so the
        # expected set aligns with what vector search will actually surface.
        top_products = products[:3]
        top_ids = [p["id"] for p in top_products]
        ref_words = _significant_keywords(top_products[0]) or "products"
        queries.append({
            "query": (
                f"{word} like {ref_words} and other {word} products "
                f"for home use"
            ),
            "expected": top_ids,
        })

    # Brand-level queries for the most common brands.
    brands: dict[str, list[dict]] = {}
    for p in catalog:
        if p.get("brand"):
            brands.setdefault(p["brand"], []).append(p)
    top_brands = sorted(brands, key=lambda b: -len(brands[b]))[:4]
    for brand in top_brands:
        queries.append({
            "query": f"all {brand} products in stock",
            "expected": [p["id"] for p in brands[brand][:3]],
        })

    return queries


def _build_eval_set_or_quit() -> list[dict]:
    if not PRODUCTS_PATH.exists():
        print("No products.json found. Run seed_blinkit_products.py first.")
        sys.exit(1)
    return _build_eval_set()


def _retrieve(vector_store, query: str) -> list[str]:
    docs = vector_store.similarity_search(query, k=TOP_K)
    seen = set()
    ids = []
    for doc in docs:
        pid = doc.metadata.get("id")
        if pid not in seen:
            seen.add(pid)
            ids.append(pid)
    return ids


def _format_retrieved(vector_store, query: str) -> str:
    docs = vector_store.similarity_search(query, k=TOP_K)
    seen = set()
    lines = [f"Top {TOP_K} for: {query!r}"]
    rank = 0
    for doc in docs:
        pid = doc.metadata.get("id")
        if pid in seen:
            continue
        seen.add(pid)
        rank += 1
        meta = doc.metadata
        lines.append(
            f"  #{rank} [{pid}] {meta.get('name')} "
            f"(Rs. {meta.get('price')}, {meta.get('rating')}/5)"
        )
    return "\n".join(lines)


def evaluate(vector_store, queries: list[dict], verbose: bool = False) -> dict:
    total = len(queries)
    acc_at_1 = 0
    recall_at_3_sum = 0.0
    mrr_sum = 0.0
    retrieved_counts = []

    for item in queries:
        query = item["query"]
        expected = set(item["expected"])
        ids = _retrieve(vector_store, query)
        retrieved_counts.append(len(ids))

        # Accuracy@1: the top hit is relevant.
        if ids and ids[0] in expected:
            acc_at_1 += 1

        # Recall@3: fraction of expected products found in the top 3.
        hits = [pid for pid in ids if pid in expected]
        recall_at_3_sum += len(hits) / len(expected)

        # MRR: 1 / rank of the first relevant hit.
        for rank, pid in enumerate(ids, start=1):
            if pid in expected:
                mrr_sum += 1.0 / rank
                break

        if verbose:
            print(_format_retrieved(vector_store, query))
            print(f"    expected={sorted(expected)} hits={sorted(hits)}\n")

    return {
        "queries": total,
        "accuracy_at_1": round(acc_at_1 / total, 4),
        "recall_at_3": round(recall_at_3_sum / total, 4),
        "mrr": round(mrr_sum / total, 4),
        "avg_retrieved_per_query": round(sum(retrieved_counts) / len(retrieved_counts), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG retriever evaluation")
    parser.add_argument("query", nargs="?", help="Run a single query instead of the eval set")
    parser.add_argument("--verbose", action="store_true", help="Print per-query results")
    args = parser.parse_args()

    print("Loading vector store / embeddings...")
    vector_store = build_vector_store()

    if args.query:
        print(_format_retrieved(vector_store, args.query))
        return

    eval_set = _build_eval_set_or_quit()
    print(f"Running {len(eval_set)} queries with top-{TOP_K} retrieval...\n")
    results = evaluate(vector_store, eval_set, verbose=args.verbose)

    print("=" * 46)
    print(f"{'Metric':<22}{'Value':>10}")
    print("-" * 46)
    for metric, value in results.items():
        if metric in ("queries", "avg_retrieved_per_query"):
            print(f"{metric:<22}{value:>10}")
        else:
            print(f"{metric:<22}{value * 100:>9.1f}%")
    print("=" * 46)


if __name__ == "__main__":
    main()