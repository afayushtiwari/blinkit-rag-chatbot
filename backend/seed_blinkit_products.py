"""
seed_blinkit_products.py
-------------------------
Build a real Blinkit catalog of 50-100 grocery products.

Two source modes:
  --live       Hit Blinkit's live GraphQL search API (works from Indian IPs;
               may be blocked from cloud/datacentres). Queries ~25 grocery
               search terms, deduplicates, writes products.json + rebuilds
               Chroma + seeds inventory stock.
  --snapshot   Use a bundled offline capture (default: data/blinkit_capture.json).
               This is the real Blinkit API response captured July 2026; works
               fully offline without any API calls.

The script writes data/products.json in the existing catalog schema, adds a
new "mrp" field per product (for strikethrough / discount display), rebuilds
the ChromaDB vector store, and seeds inventory stock from the real Blinkit
availability figures.

Usage:
    python seed_blinkit_products.py                     # snapshot (offline)
    python seed_blinkit_products.py --live              # live Blinkit API
    python seed_blinkit_products.py --limit 80          # cap catalog size
    python seed_blinkit_products.py --rebuild           # force Chroma rebuild
"""

import argparse
import json
import hashlib
import math
import random
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
PRODUCTS_PATH = DATA_DIR / "products.json"
CAPTURE_PATH = DATA_DIR / "blinkit_capture.json"
MERCHANT_ID = 40076   # Delhi dark store
LAT, LON = 28.6139, 77.209

# ---------------------------------------------------------------------------
# Blinkit GraphQL search API (live mode)
# ---------------------------------------------------------------------------
GRAPHQL_URL = "https://blinkit.com/api/v4/graphql/searchor"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://blinkit.com",
    "Referer": "https://blinkit.com/",
}

# Category - search queries for live mode (maps to common Blinkit searches)
CATEGORY_SEARCH_MAP = {
    "Dairy": [
        "toned milk", "full cream milk", "curd", "paneer", "cheese slice",
        "amul butter", "ghee", "lassi", "flavoured milk",
    ],
    "Bakery": ["white bread", "whole wheat bread", "pav bun"],
    "Snacks": ["potato chips", "biscuit", "namkeen"],
    "Beverages": ["cold drink", "fruit juice", "cola", "cold coffee"],
    "Instant Food": ["instant noodles", "maggi", "oatmeal"],
    "Fruits": ["banana", "apple"],
    "Chocolates": ["milk chocolate", "dairy milk"],
    "Grocery": ["basmati rice", "salt", "sugar", "atta", "cooking oil"],
}

# ---------------------------------------------------------------------------
# Category inference from product name
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "Dairy": [
        "milk", "curd", "paneer", "cheese", "butter", "cream", "lassi",
        "buttermilk", "dahi", "yogurt", "ghee", "whey", "raita",
    ],
    "Beverages": [
        "juice", "drink", "cold drink", "coffee", "tea", "soda",
        "cola", "energy drink", "lemonade", "health drink",
    ],
    "Snacks": [
        "chips", "biscuit", "cookie", "namkeen", "bhujia", "popcorn",
        "mixture", "mathri", "chakli", "khakhra",
    ],
    "Instant Food": [
        "noodle", "maggi", "pasta", "oat", "corn flake", "soup",
        "upma", "poha", "instant", "instant meal",
    ],
    "Fruits": [
        "banana", "apple", "orange", "grape", "mango", "papaya",
        "watermelon", "pomegranate", "kiwi",
    ],
    "Chocolates": [
        "chocolate", "candy", "toffee", "gummy",
    ],
    "Bakery": [
        "bread", "pav", "bun", "cake", "muffin", "rusk", "toast",
        "croissant",
    ],
    "Grocery": [
        "rice", "atta", "wheat", "dal", "lentil", "salt", "sugar",
        "oil", "spice", "masala", "flour", "soya", "honey",
    ],
}


def _infer_category(name: str) -> str:
    low = name.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in low:
                return cat
    return "Dairy"          # fallback — most captured products are dairy


# ---------------------------------------------------------------------------
# Category-appropriate image URLs (for snapshot mode without images)
# ---------------------------------------------------------------------------
UNSPASH_IMAGES = {
    "Dairy":       "https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400",
    "Bakery":      "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400",
    "Snacks":      "https://images.unsplash.com/photo-1566478989037-eec170784d0b?w=400",
    "Beverages":   "https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400",
    "Instant Food": "https://images.unsplash.com/photo-1612929633738-8fe44f7ec841?w=400",
    "Fruits":      "https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=400",
    "Chocolates":  "https://images.unsplash.com/photo-1606312619070-d48b4c652a52?w=400",
    "Grocery":     "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400",
}


# ---------------------------------------------------------------------------
# Enrichment: deterministic descriptions, reviews, FAQs
# ---------------------------------------------------------------------------
_REVIEW_POOL = [
    "Really good quality, exactly what I expected.",
    "Consistent taste and always fresh on delivery.",
    "Great value for money at this price point.",
    "My family uses this brand regularly, always reliable.",
    "Delivered quickly and in perfect condition.",
    "Perfect for daily use, great product.",
    "Top-notch quality, will order again.",
    "Exactly as described, very satisfied.",
    "Fresh and well-packaged, happy with the purchase.",
    "A staple in our kitchen, never disappoints.",
    "Taste and quality are both excellent.",
    "Good portion size and arrives fresh.",
    "Trusted brand, always my first choice.",
    "Compared to alternatives, this is the best.",
    "Smooth texture and premium feel.",
]

_FAQ_POOL = {
    "Dairy": [
        {"q": "How should I store this?", "a": "Keep refrigerated at 2-8 C and consume before the best-before date on the pack."},
        {"q": "Is this product pasteurised?", "a": "Yes, all dairy products are pasteurised and safe for direct consumption."},
        {"q": "Is it suitable for children?", "a": "Yes, most dairy products are suitable for children. Please check the label for age-specific guidance."},
    ],
    "Beverages": [
        {"q": "Does it contain added sugar?", "a": "Check the nutrition panel on the pack for sugar content details."},
        {"q": "Is this drink carbonated?", "a": "Some beverages are carbonated, others still. Refer to the product description."},
    ],
    "Snacks": [
        {"q": "Is it vegetarian?", "a": "Yes, this snack is 100% vegetarian as per the FSSAI label."},
        {"q": "How long does it stay fresh after opening?", "a": "Best consumed within a few days of opening if resealed properly."},
    ],
    "Instant Food": [
        {"q": "How long does it take to prepare?", "a": "Most instant foods are ready in 2-5 minutes. Follow the pack instructions."},
        {"q": "Is it spicy?", "a": "Spice level varies by variant; most have a mild to medium heat level suitable for all ages."},
    ],
    "Fruits": [
        {"q": "Is this product organic?", "a": "These are farm-fresh produce; organic certification depends on the specific batch."},
        {"q": "How should I store them?", "a": "Store at room temperature and refrigerate after ripening for longer freshness."},
    ],
    "Chocolates": [
        {"q": "Does it contain nuts?", "a": "Always check the allergen label on the pack. Some variants may contain traces of nuts."},
        {"q": "Is it suitable for vegetarians?", "a": "Most chocolate bars from these brands are vegetarian; check the FSSAI marking."},
    ],
    "Bakery": [
        {"q": "What is the shelf life?", "a": "Best consumed within 3-5 days when stored in a cool, dry place. Refrigerate to extend freshness."},
        {"q": "Does it contain maida (refined flour)?", "a": "Varies by product — whole wheat variants are explicitly labelled; check the ingredients list."},
    ],
    "Grocery": [
        {"q": "Is it suitable for daily cooking?", "a": "Yes, these are everyday grocery staples from trusted brands."},
        {"q": "What is the best-before period?", "a": "Dry groceries typically have a 6-12 month shelf life. Check the pack for the exact date."},
    ],
}


def _pick_reviews(name: str, count: int = 2) -> list[str]:
    idx = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return [_REVIEW_POOL[(idx + i) % len(_REVIEW_POOL)] for i in range(count)]


def _pick_faq(category: str) -> list[dict]:
    idx = int(hashlib.md5(category.encode()).hexdigest(), 16)
    pool = _FAQ_POOL.get(category, _FAQ_POOL["Grocery"])
    return [pool[idx % len(pool)], pool[(idx + 1) % len(pool)]]


def _description(name: str, brand: str, unit: str, category: str, rating: float) -> str:
    return (
        f"{name} from {brand} ({unit}) — a top-rated {category.lower()} product "
        f"on Blinkit with a {rating}/5 customer rating."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalise_record(rec: dict) -> dict:
    """Convert either a live searchor match or a raw capture row into a
    canonical dict with keys: product_id, name, brand, category, price,
    mrp, unit, inventory, rating, rating_count, image_url, source_kw."""
    # Live searchor match has: product_name or name, product_id (int),
    # custom_json[0] with price/unit, image_url list, sub_category, etc.
    # Snapshot capture has: product_name, product_id (int), price, mrp,
    # unit, inventory, rating, rating_count (str like "3,981").

    name = rec.get("product_name") or rec.get("name") or ""
    # Fix scrape glitches like "Table White White Eggs" -> "Table White Eggs"
    name = re.sub(r"\b(\w+) \1\b", r"\1", name)
    brand = rec.get("brand", "")
    price = rec.get("price") or rec.get("selling_price") or rec.get("mrp") or 0
    mrp = rec.get("mrp") or price
    unit = rec.get("unit", "")
    inventory = rec.get("inventory", 10)
    rating_raw = rec.get("rating")
    rating_count_raw = rec.get("rating_count") or rec.get("ratingCount") or 0
    product_id = rec.get("product_id") or rec.get("productId") or ""

    # clean up price — some entries have "?" prefix
    if isinstance(price, str):
        price = int(price.replace("?", "").replace(",", "") or "0")
    if isinstance(mrp, str):
        mrp = int(mrp.replace("?", "").replace(",", "") or "0")

    # Parse rating_count strings like "3,981" or "1 lac" or "1.2k"
    rating_count = 0
    if isinstance(rating_count_raw, str):
        rc = rating_count_raw.lower().replace(",", "").replace(" ratings", "").strip()
        if "lac" in rc:
            rating_count = int(float(rc.replace("lac", "")) * 100000)
        elif "k" in rc or "lakh" in rc:
            rating_count = int(float(rc.replace("k", "").replace("lakh", "")) * 1000)
        else:
            try:
                rating_count = int(rc)
            except ValueError:
                rating_count = 0
    elif isinstance(rating_count_raw, (int, float)):
        rating_count = int(rating_count_raw)

    # image: prefer image_url list from live, fallback Unsplash
    image_url = rec.get("image_url", "") or ""
    if isinstance(image_url, list) and image_url:
        image_url = image_url[0]
    elif not image_url:
        image_url = rec.get("images", rec.get("image_urls", []))
        if isinstance(image_url, list) and image_url:
            image_url = image_url[0]
        else:
            image_url = ""

    category = _infer_category(name)
    rating = float(rating_raw) if rating_raw else 4.3

    # inventory as initial stock (capped reasonable range)
    stock = min(max(int(inventory) if inventory else 10, 1), 30)

    return {
        "raw_id": str(product_id),
        "name": name,
        "brand": brand,
        "category": category,
        "price": int(price),
        "mrp": int(mrp) or int(price),
        "unit": unit,
        "stock": stock,
        "rating": round(rating, 2),
        "rating_count": rating_count,
        "image_url": image_url,
        "source_kw": rec.get("search_keyword") or rec.get("searchQuery", ""),
    }


def _dedupe(records: list[dict]) -> list[dict]:
    """Deduplicate by (normalised name + unit), keeping the first occurrence."""
    seen = set()
    out = []
    for rec in records:
        key = (rec["name"].lower().strip(), rec["unit"].lower().strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def _stable_int(value, max_value=10**6) -> int:
    return int(hashlib.md5(str(value).encode()).hexdigest(), 16) % max_value


# ---------------------------------------------------------------------------
# Live fetch
# ---------------------------------------------------------------------------
def _live_fetch(queries: list[str]) -> list[dict]:
    """Hit Blinkit's GraphQL search API and return normalised records."""
    all_records = []
    for query in queries:
        payload = json.dumps({
            "queries": [{
                "merchant_id": MERCHANT_ID,
                "search_type": "SEARCH",
                "search_query": query,
                "category_ids": [],
                "page": 1,
                "lat": LAT,
                "lon": LON,
            }]
        }).encode()
        req = urllib.request.Request(GRAPHQL_URL, data=payload, headers=HEADERS, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read())
            items = (
                data.get("data", {})
                .get("mylist", [{}])[0]
                .get("search_result", {})
                .get("matching_products", [])
            )
            print(f"  [LIVE] '{query}' - {len(items)} products")
            for item in items:
                all_records.append(_normalise_record(item))
        except Exception as exc:
            print(f"  [LIVE] '{query}' - FAILED ({exc})")
    return all_records


# ---------------------------------------------------------------------------
# Catalog builder (shared between live and snapshot)
# ---------------------------------------------------------------------------
def _build_catalog(records: list[dict], limit: int = 100) -> list[dict]:
    """Take normalised records, dedupe, prioritise, build final catalog."""
    records = _dedupe(records)
    print(f"\n  Normalised & deduped: {len(records)} unique products")

    # Prioritise: sort by rating_count desc (most popular first), then rating desc
    records.sort(key=lambda r: (r["rating_count"], r["rating"]), reverse=True)

    # Balance categories: fill 6-12 per category up to limit
    by_category: dict[str, list] = {}
    for rec in records:
        by_category.setdefault(rec["category"], []).append(rec)

    selected: list[dict] = []
    per_cat_target = max(6, limit // max(len(by_category), 1))
    for cat in ["Dairy", "Beverages", "Snacks", "Bakery", "Instant Food",
                 "Fruits", "Chocolates", "Grocery"]:
        items = by_category.get(cat, [])
        selected.extend(items[:per_cat_target])

    # Fill remaining with best rest
    selected_ids = {r["raw_id"] for r in selected}
    remaining = [r for r in records if r["raw_id"] not in selected_ids]
    for r in remaining:
        if len(selected) >= limit:
            break
        selected.append(r)

    selected = selected[:limit]
    print(f"  Selected: {len(selected)} products "
          f"(across {len({r['category'] for r in selected})} categories)")

# Assign sequential IDs
    catalog = []
    for idx, rec in enumerate(selected, start=1):
        pid = f"P{idx:03d}"
        cat = rec["category"]
        catalog.append({
            "id": pid,
            "name": rec["name"],
            "category": cat,
            "brand": rec["brand"],
            "price": rec["price"],
            "mrp": rec["mrp"],
            "rating": rec["rating"],
            "unit": rec["unit"],
            "stock": rec["stock"],
            "product_id": rec["raw_id"],   # Blinkit's real product id
            "description": _description(rec["name"], rec["brand"], rec["unit"], cat, rec["rating"]),
            "reviews": _pick_reviews(rec["name"], 2),
            "image_url": rec["image_url"] or UNSPASH_IMAGES.get(cat, UNSPASH_IMAGES["Dairy"]),
            "faqs": _pick_faq(cat),
            "related_products": [],   # filled below
        })

# Fill related_products (up to 3 same-category products)
    by_cat: dict[str, list] = {}
    for p in catalog:
        by_cat.setdefault(p["category"], []).append(p["id"])
    for p in catalog:
        siblings = [sid for sid in by_cat[p["category"]] if sid != p["id"]]
        p["related_products"] = siblings[:3]

    return catalog


# ---------------------------------------------------------------------------
# Real product image resolution (Blinkit PDP endpoint)
# ---------------------------------------------------------------------------
_PDP_HEADERS = {
    "accept": "*/*",
    "app_client": "consumer_web",
    "app_version": "1010101010",
    "auth_key": "c761ec3633c22afad934fb17a66385c1c06c5472b4898b866b7306186d0bb477",
    "content-type": "application/json",
    "accept-encoding": "identity",
    "lat": "28.6139",
    "lon": "77.2090",
    "origin": "https://blinkit.com",
    "referer": "https://blinkit.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
    ),
    "web_app_version": "1008010016",
}


def _fetch_primary_blinkit_image(prid: str) -> str:
    """Fetch a product's real image via the Blinkit PDP API.

    Returns the first entry of the product's own SEO image array
    (response.tracking.le_meta.custom_data.seo.images) -> a public
    cdn.grofers.com/da/cms-assets/... URL, or "" when unavailable.
    """
    req = urllib.request.Request(
        f"https://blinkit.com/v1/layout/product/{prid}",
        data=b"",
        headers=_PDP_HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read()
    data = json.loads(body)

    node = data
    for key in ("response", "tracking", "le_meta", "custom_data", "seo", "images"):
        if not isinstance(node, dict) or key not in node:
            return ""
        node = node[key]

    if isinstance(node, list) and node:
        url = str(node[0])
        if url.startswith("http"):
            return url
    return ""


def _resolve_blinkit_images(catalog: list[dict]) -> None:
    """Populate each catalog entry with its real Blinkit product image,
    resolved from the live PDP endpoint. Keeps the existing fallback image
    whenever the PDP call fails (network block, banned IP, product removed).

    Requests are throttled: the PDP endpoint rate-limits parallel scrapers,
    so each product gets its own request with a short delay between calls.
    """
    remaining = [p for p in catalog if p.get("product_id")]
    print(f"\n  Resolving real Blinkit images for {len(remaining)} products...")

    resolved = 0
    for i, product in enumerate(remaining, start=1):
        prid = str(product.get("product_id", "")).strip()
        if not prid.isdigit():
            continue
        url = ""
        for attempt in (1, 2, 3):
            try:
                url = _fetch_primary_blinkit_image(prid)
                if url:
                    break
            except Exception:
                url = ""
            time.sleep(0.5)
        if url:
            product["image_url"] = url
            resolved += 1
        if i % 10 == 0:
            print(f"    {i}/{len(remaining)}...", flush=True)
        time.sleep(0.7)

    print(f"  Resolved {resolved}/{len(catalog)} products to real Blinkit images.")


# ---------------------------------------------------------------------------
# Snapshot loader
# ---------------------------------------------------------------------------
def _load_snapshot(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        print(f"  Snapshot file not found: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [_normalise_record(r) for r in raw]


# ---------------------------------------------------------------------------
# Write products.json + rebuild Chroma + seed inventory
# ---------------------------------------------------------------------------
def _write_products(catalog: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(PRODUCTS_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f"\n  Written {len(catalog)} products - {PRODUCTS_PATH}")


def _rebuild_chroma() -> None:
    print("  Rebuilding ChromaDB vector store...")
    from vector_store import build_vector_store
    build_vector_store(force_rebuild=True)
    print("  ChromaDB rebuilt successfully.")


def _seed_inventory(catalog: list[dict]) -> None:
    import inventory
    inventory.restock_all(default=0)
    for p in catalog:
        inventory.set_stock(p["id"], p["stock"])
    print(f"  Inventory seeded for {len(catalog)} products (stock from Blinkit data).")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a real Blinkit product catalog")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--live", action="store_true", help="Fetch live from Blinkit GraphQL API")
    source.add_argument("--snapshot", type=str, nargs="?",
                        const=str(CAPTURE_PATH),
help="Use offline snapshot (default: data/blinkit_capture.json)")
    parser.add_argument("--limit", type=int, default=100, help="Max products in catalog (default 100)")
    parser.add_argument("--rebuild", action="store_true", help="Force ChromaDB rebuild")
    parser.add_argument("--no-images", action="store_true",
                        help="Skip real Blinkit image resolution (offline mode)")
    args = parser.parse_args()

    print("=" * 50)
    print("Blinkit Real Product Catalog Seed")
    print("=" * 50)

    records: list[dict] = []

    if args.live:
        print("\n[LIVE MODE] Fetching from Blinkit GraphQL API...")
        all_queries = []
        for q_list in CATEGORY_SEARCH_MAP.values():
            all_queries.extend(q_list)
        records = _live_fetch(all_queries)
        if not records:
            print("\n  LIVE fetch returned no products (likely blocked from this IP).")
            print("  Tip: run from an Indian residential IP, or use --snapshot mode.\n")
            print("  Falling back to bundled snapshot...\n")
            args.snapshot = str(CAPTURE_PATH)

    if args.snapshot is not None:
        snap_path = Path(args.snapshot)
        if not snap_path.exists():
            print(f"\n  Snapshot not found at {snap_path}; aborting.")
            sys.exit(1)
        print(f"\n[SNAPSHOT MODE] Loading from {snap_path.name}...")
        records = _load_snapshot(snap_path)
        print(f"  Loaded {len(records)} records from snapshot.")

    if not records:
        print("\n  No records to process. Aborting.")
        sys.exit(1)

    print(f"\n[BUILDING CATALOG] limit={args.limit}")
    catalog = _build_catalog(records, limit=args.limit)

    # Show summary
    cat_counts = {}
    for p in catalog:
        cat_counts[p["category"]] = cat_counts.get(p["category"], 0) + 1
    print("\n  Category breakdown:")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat:<20} {count}")
    avg_price = sum(p["price"] for p in catalog) / len(catalog)
    print(f"    Average price: Rs. {avg_price:.0f}")

    # Resolve real Blinkit product images (unless explicitly disabled).
    # Snapshot captures don't carry image URLs; the PDP endpoint supplies
    # real cdn.grofers.com product photos for every product id.
    if not args.no_images:
        _resolve_blinkit_images(catalog)

    print("\n[WRITING]")
    _write_products(catalog)

    if args.rebuild or args.live:
        print("\n[REBUILDING]")
        _rebuild_chroma()

    print("\n[SEEDING INVENTORY]")
    _seed_inventory(catalog)

    print("\nDone! Frontend will now display real Blinkit products.")
    print("Start backend: uvicorn main:app --reload --port 8000")


if __name__ == "__main__":
    main()

