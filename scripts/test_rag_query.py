#!/usr/bin/env python3
"""
RAG pipeline smoke test — three checks in sequence:

  1. Collection count — confirms Qdrant index is intact (expect 2,523,881)
  2. Semantic query — encodes a natural-language query and returns top-5 hits
  3. Filtered query — same query but restricted to retained=True Electronics reviews

Usage:
    python3 scripts/test_rag_query.py
    python3 scripts/test_rag_query.py --query "battery life poor quality"
    python3 scripts/test_rag_query.py --qdrant-path data/qdrant --collection reviews
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QDRANT_PATH = PROJECT_ROOT / "data" / "qdrant"
DEFAULT_COLLECTION = "reviews"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_QUERY = "great product fast shipping highly recommend"


# ---------------------------------------------------------------------------
# Test 1: collection count
# ---------------------------------------------------------------------------

def test_count(client: QdrantClient, collection: str) -> bool:
    logger.info("=" * 60)
    logger.info("TEST 1: Collection count")
    logger.info("=" * 60)
    count = client.count(collection, exact=True).count
    logger.info(f"Points in '{collection}': {count:,}")
    ok = count > 0
    if ok:
        logger.info("PASS")
    else:
        logger.error("FAIL — collection is empty")
    return ok


# ---------------------------------------------------------------------------
# Test 2: semantic query (no filter)
# ---------------------------------------------------------------------------

def test_semantic_query(
    client: QdrantClient,
    collection: str,
    model: SentenceTransformer,
    query: str,
    top_k: int = 5,
) -> bool:
    logger.info("=" * 60)
    logger.info("TEST 2: Semantic query (no filter)")
    logger.info(f"  Query: {query!r}")
    logger.info("=" * 60)

    t0 = time.perf_counter()
    vector = model.encode(query, normalize_embeddings=True).tolist()
    encode_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    hits = client.query_points(
        collection_name=collection,
        query=vector,
        limit=top_k,
        with_payload=True,
    ).points
    query_ms = (time.perf_counter() - t1) * 1000

    logger.info(f"  Encode: {encode_ms:.1f}ms  |  Query: {query_ms:.1f}ms")
    logger.info(f"  Top {len(hits)} results:")
    for i, h in enumerate(hits, 1):
        cat = h.payload.get("category_name", "?")
        rating = h.payload.get("rating", "?")
        retained = h.payload.get("retained", "?")
        title = (h.payload.get("title") or "")[:60]
        text = (h.payload.get("text") or "")[:80]
        logger.info(
            f"  {i}. score={h.score:.4f} | cat={cat} | rating={rating} | "
            f"retained={retained}"
        )
        logger.info(f"     title: {title!r}")
        logger.info(f"     text:  {text!r}")

    ok = len(hits) == top_k and all(h.score > 0 for h in hits)
    logger.info("PASS" if ok else "FAIL — unexpected results")
    return ok


# ---------------------------------------------------------------------------
# Test 3: filtered semantic query
# ---------------------------------------------------------------------------

def test_filtered_query(
    client: QdrantClient,
    collection: str,
    model: SentenceTransformer,
    query: str,
    top_k: int = 5,
) -> bool:
    logger.info("=" * 60)
    logger.info("TEST 3: Filtered query (Electronics + retained=True)")
    logger.info(f"  Query: {query!r}")
    logger.info("=" * 60)

    vector = model.encode(query, normalize_embeddings=True).tolist()

    filt = Filter(
        must=[
            FieldCondition(key="category_name", match=MatchValue(value="Electronics")),
            FieldCondition(key="retained", match=MatchValue(value=True)),
        ]
    )

    t0 = time.perf_counter()
    hits = client.query_points(
        collection_name=collection,
        query=vector,
        query_filter=filt,
        limit=top_k,
        with_payload=True,
    ).points
    query_ms = (time.perf_counter() - t0) * 1000

    logger.info(f"  Query: {query_ms:.1f}ms")
    logger.info(f"  Top {len(hits)} results (all should be Electronics, retained=True):")
    all_correct = True
    for i, h in enumerate(hits, 1):
        cat = h.payload.get("category_name")
        retained = h.payload.get("retained")
        rating = h.payload.get("rating", "?")
        title = (h.payload.get("title") or "")[:60]
        correct = cat == "Electronics" and retained is True
        if not correct:
            all_correct = False
        flag = "" if correct else " !! FILTER VIOLATION"
        logger.info(
            f"  {i}. score={h.score:.4f} | cat={cat} | rating={rating} | "
            f"retained={retained}{flag}"
        )
        logger.info(f"     title: {title!r}")

    ok = len(hits) > 0 and all_correct
    logger.info("PASS" if ok else "FAIL — filter violation or no results")
    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="RAG pipeline smoke test")
    parser.add_argument("--qdrant-path", type=Path, default=DEFAULT_QDRANT_PATH)
    parser.add_argument("--collection", type=str, default=DEFAULT_COLLECTION)
    parser.add_argument("--query", type=str, default=DEFAULT_QUERY)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    logger.info(f"Opening Qdrant at {args.qdrant_path}")
    client = QdrantClient(path=str(args.qdrant_path))

    logger.info(f"Loading embedding model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    results = []
    results.append(test_count(client, args.collection))
    results.append(test_semantic_query(client, args.collection, model, args.query, args.top_k))
    results.append(test_filtered_query(client, args.collection, model, args.query, args.top_k))

    client.close()

    logger.info("=" * 60)
    passed = sum(results)
    total = len(results)
    logger.info(f"RESULTS: {passed}/{total} tests passed")
    if passed == total:
        logger.info("ALL TESTS PASSED")
        sys.exit(0)
    else:
        logger.error("SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
