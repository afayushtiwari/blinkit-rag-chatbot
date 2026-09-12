"""
vector_store.py
----------------
Handles building and loading the ChromaDB vector database that stores
embeddings for every product's textual information (description, reviews,
FAQs, category, brand, etc). This is the "retrieval" half of our RAG system.

Each product is converted into ONE rich text "document" that concatenates
all of its hierarchical fields (name, category, brand, price, rating,
description, reviews, FAQs) so that the retriever can match a user's
question to the right product no matter which field they ask about.

The product's structured data (image_url, price, rating, related_products,
etc.) is stored separately in metadata so the frontend can render a full
product card, not just plain text.
"""

import json
import os
import shutil
from typing import List

from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.docstore.document import Document

load_dotenv()

# Path to persisted Chroma collection on disk
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
PRODUCTS_PATH = os.path.join(os.path.dirname(__file__), "data", "products.json")
COLLECTION_NAME = "blinkit_products"


def load_products() -> List[dict]:
    """Load the raw product dataset from JSON."""
    with open(PRODUCTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def product_to_document(product: dict) -> Document:
    """
    Flatten a hierarchical product record into a single natural-language
    text blob for embedding, while keeping the original structured fields
    as metadata for retrieval-time rendering (images, price, etc).
    """
    reviews_text = " | ".join(product.get("reviews", []))
    faqs_text = " | ".join(
        f"Q: {f['q']} A: {f['a']}" for f in product.get("faqs", [])
    )

    text = f"""
    Product Name: {product['name']}
    Category: {product['category']}
    Brand: {product['brand']}
    Price: Rs. {product['price']}
    Rating: {product['rating']} out of 5
    Description: {product['description']}
    Customer Reviews: {reviews_text}
    Frequently Asked Questions: {faqs_text}
    """.strip()

    metadata = {
        "id": product["id"],
        "name": product["name"],
        "category": product["category"],
        "brand": product["brand"],
        "price": product["price"],
        "rating": product["rating"],
        "image_url": product["image_url"],
        # Chroma metadata values must be primitives, so lists are joined.
        "related_products": ",".join(product.get("related_products", [])),
    }

    return Document(page_content=text, metadata=metadata)


def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


def build_vector_store(force_rebuild: bool = False) -> Chroma:
    embeddings = get_embeddings()

    if not force_rebuild and os.path.exists(CHROMA_DIR):
        return Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=CHROMA_DIR,
        )

    # A force rebuild MUST start from a clean collection. Chroma.from_documents
    # appends to an existing collection, so running this script repeatedly
    # previously created duplicate documents per product (which made top-k
    # retrieval return the same product twice).
    if force_rebuild and os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)

    products = load_products()
    documents = [product_to_document(p) for p in products]

    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_DIR,
    )

    print(f"Ingested {len(documents)} products into ChromaDB at {CHROMA_DIR}")
    return vector_store


def get_product_by_id(product_id: str) -> dict:
    """Utility to fetch the full raw product record by its ID (used to
    attach full product-card data, including related_products, to a chat
    response)."""
    products = load_products()
    for p in products:
        if p["id"] == product_id:
            return p
    return None


if __name__ == "__main__":
    build_vector_store(force_rebuild=True)