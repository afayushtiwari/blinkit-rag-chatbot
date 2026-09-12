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
import sys
from pathlib import Path

from vector_store import build_vector_store

# (query, [expected product ids]) -- a question can map to several products.
EVAL_SET = [
    {"query": "show me details of amul milk", "expected": ["P001"]},
    {"query": "fresh toned milk for tea and coffee", "expected": ["P001"]},
    {"query": "cream and curd from amul", "expected": ["P002", "P003"]},
    {"query": "butter to spread on paratha", "expected": ["P003"]},
    {"query": "whole wheat bread for breakfast", "expected": ["P004"]},
    {"query": "tea time biscuits", "expected": ["P005", "P019"]},
    {"query": "crispy salted potato chips", "expected": ["P006"]},
    {"query": "spicy masala flavoured chips", "expected": ["P007"]},
    {"query": "cold soft drink cola bottle", "expected": ["P008"]},
    {"query": "mixed fruit juice with vitamin c", "expected": ["P009"]},
    {"query": "instant noodles in two minutes", "expected": ["P010"]},
    {"query": "bananas rich in potassium", "expected": ["P011"]},
    {"query": "shimla apples", "expected": ["P012"]},
    {"query": "smoothest milk chocolate", "expected": ["P013"]},
    {"query": "chocolate egg with a toy for kids", "expected": ["P014"]},
    {"query": "iodized cooking salt", "expected": ["P015"]},
    {"query": "sunflower oil for frying", "expected": ["P016"]},
    {"query": "long grain rice for biryani", "expected": ["P017"]},
    {"query": "instant coffee for morning", "expected": ["P018"]},
    {"query": "crunchy aloo bhujia namkeen", "expected": ["P019"]},
    {"query": "soft paneer for paneer tikka", "expected": ["P020"]},
    {"query": "snacks under 50 rupees", "expected": ["P005", "P006", "P007", "P010"]},
    {"query": "healthy drinks and juices", "expected": ["P008", "P009", "P018"]},
    {"query": "dairy products for home", "expected": ["P001", "P002", "P020"]},
]

TOP_K = 3


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

    print(f"Running {len(EVAL_SET)} queries with top-{TOP_K} retrieval...\n")
    results = evaluate(vector_store, EVAL_SET, verbose=args.verbose)

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