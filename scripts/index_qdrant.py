#!/usr/bin/env python3
"""
Stage 3 of RAG pipeline: build a local on-disk Qdrant collection from
the embedding shards produced by Stage 2.

Inputs:
    - data/rag/reviews_with_text.parquet   (payload source)
    - data/rag/embeddings/shard_NNNNN.parquet (or --embeddings-dir override)

Output:
    - data/qdrant/                          (Qdrant on-disk storage)
    - Collection name: reviews              (configurable via --collection)

Per-point payload stored in Qdrant:
    user_id, parent_asin, category_name, rating, date (ISO),
    retained (bool), observable (bool), first_category (str|null),
    title, text

The point ID is the row index in reviews_with_text.parquet
(same as Stage 2's point_id column).

Usage:
    # Full indexing run
    python3 scripts/index_qdrant.py

    # Dry-run / small slice, different paths
    python3 scripts/index_qdrant.py \
        --embeddings-dir data/rag/embed_probe_mps_bs256 \
        --qdrant-path data/rag/qdrant_probe \
        --collection reviews_probe

    # Wipe existing collection and rebuild
    python3 scripts/index_qdrant.py --recreate
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import polars as pl
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REVIEWS = PROJECT_ROOT / "data" / "rag" / "reviews_with_text.parquet"
DEFAULT_EMBED_DIR = PROJECT_ROOT / "data" / "rag" / "embeddings"
DEFAULT_QDRANT_PATH = PROJECT_ROOT / "data" / "qdrant"

DEFAULT_COLLECTION = "reviews"
EMBED_DIM = 384
DEFAULT_UPSERT_BATCH = 512

PAYLOAD_COLS = [
    "user_id",
    "parent_asin",
    "category_name",
    "rating",
    "date",
    "retained",
    "observable",
    "first_category",
    "title",
    "text",
]


def load_embedding_shards(embed_dir: Path) -> pl.DataFrame:
    shards = sorted(embed_dir.glob("shard_*.parquet"))
    if not shards:
        raise FileNotFoundError(f"No shard_*.parquet files in {embed_dir}")
    logger.info(f"Reading {len(shards)} embedding shards from {embed_dir}")
    df = pl.concat([pl.read_parquet(p) for p in shards], how="vertical")
    # Sort by point_id so joins are deterministic
    df = df.sort("point_id")
    logger.info(f"Embeddings loaded: {df.height:,} rows")
    return df


def load_payload_source(reviews_path: Path) -> pl.DataFrame:
    logger.info(f"Loading review payload source: {reviews_path}")
    df = pl.read_parquet(reviews_path, columns=PAYLOAD_COLS)
    # Give each row a stable point_id (row index). This mirrors Stage 2's
    # numbering scheme (embed_reviews.py uses the same row order via pl.read_parquet).
    df = df.with_row_index(name="point_id").with_columns(
        pl.col("point_id").cast(pl.Int64)
    )
    logger.info(f"Payload rows: {df.height:,}")
    return df


def ensure_collection(
    client: QdrantClient,
    collection: str,
    recreate: bool,
) -> None:
    exists = client.collection_exists(collection)
    if exists and recreate:
        logger.warning(f"Deleting existing collection '{collection}' (--recreate)")
        client.delete_collection(collection)
        exists = False
    if not exists:
        logger.info(
            f"Creating collection '{collection}' (size={EMBED_DIM}, cosine)"
        )
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )
    else:
        existing_count = client.count(collection, exact=True).count
        logger.info(
            f"Collection '{collection}' already exists with {existing_count:,} points"
        )


def iter_batches(n: int, batch: int) -> Iterable[tuple[int, int]]:
    start = 0
    while start < n:
        end = min(start + batch, n)
        yield start, end
        start = end


def payload_from_row(row: dict) -> dict:
    """Convert a polars row-dict into a Qdrant-friendly payload."""
    date = row.get("date")
    if date is not None and not isinstance(date, str):
        # Polars datetimes come through as python datetime objects
        date = date.isoformat()
    return {
        "user_id": row["user_id"],
        "parent_asin": row["parent_asin"],
        "category_name": row["category_name"],
        "rating": float(row["rating"]) if row["rating"] is not None else None,
        "date": date,
        "retained": bool(row["retained"]) if row["retained"] is not None else None,
        "observable": bool(row["observable"]) if row["observable"] is not None else None,
        "first_category": row["first_category"],
        "title": row["title"],
        "text": row["text"],
    }


def upsert_all(
    client: QdrantClient,
    collection: str,
    joined: pl.DataFrame,
    batch_size: int,
) -> None:
    n = joined.height
    logger.info(f"Upserting {n:,} points in batches of {batch_size}")
    t0 = time.perf_counter()
    done = 0
    for start, end in iter_batches(n, batch_size):
        slice_df = joined.slice(start, end - start)
        rows = slice_df.to_dicts()
        points = []
        for r in rows:
            vector = r["embedding"]
            if vector is None:
                raise ValueError(f"Null embedding at point_id={r['point_id']}")
            points.append(
                PointStruct(
                    id=int(r["point_id"]),
                    vector=vector,
                    payload=payload_from_row(r),
                )
            )
        client.upsert(collection_name=collection, points=points, wait=False)
        done += len(points)
        if done % (batch_size * 10) == 0 or done == n:
            elapsed = time.perf_counter() - t0
            rps = done / elapsed if elapsed > 0 else 0.0
            logger.info(
                f"  upserted {done:,}/{n:,} ({done/n*100:.1f}%)  "
                f"{rps:,.0f} points/s"
            )
    total = time.perf_counter() - t0
    logger.info(f"Upsert done in {total:.1f}s ({n/total:,.0f} points/s)")


def smoke_query(client: QdrantClient, collection: str) -> None:
    """Fetch one random point and do a tiny similarity query to verify health."""
    count = client.count(collection, exact=True).count
    logger.info(f"Collection '{collection}' final count: {count:,}")
    if count == 0:
        return
    sample = client.scroll(collection, limit=1, with_vectors=True)[0]
    if not sample:
        return
    pt = sample[0]
    logger.info(f"Sample point id={pt.id}")
    logger.info(f"Sample payload keys: {sorted(pt.payload.keys())}")
    logger.info(f"Sample category: {pt.payload.get('category_name')}  rating: {pt.payload.get('rating')}")
    title = (pt.payload.get('title') or '')[:60]
    logger.info(f"Sample title: {title!r}")

    # Cosine self-query: nearest neighbors of the point's own vector
    hits = client.query_points(
        collection_name=collection,
        query=pt.vector,
        limit=3,
        with_payload=True,
    ).points
    logger.info("Top-3 nearest (should include self as rank-1 with score ~1.0):")
    for h in hits:
        cat = h.payload.get("category_name")
        title = (h.payload.get("title") or "")[:50]
        logger.info(f"  id={h.id} score={h.score:.4f} cat={cat} title={title!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index embeddings into Qdrant")
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--embeddings-dir", type=Path, default=DEFAULT_EMBED_DIR)
    parser.add_argument("--qdrant-path", type=Path, default=DEFAULT_QDRANT_PATH)
    parser.add_argument("--collection", type=str, default=DEFAULT_COLLECTION)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_UPSERT_BATCH)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete collection before upsert",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only upsert first N joined rows (for dry-run)",
    )
    args = parser.parse_args()

    args.qdrant_path.mkdir(parents=True, exist_ok=True)

    embed_df = load_embedding_shards(args.embeddings_dir)
    payload_df = load_payload_source(args.reviews)

    # Validate coverage: embeddings must cover some prefix of the payload.
    emb_max = embed_df["point_id"].max()
    emb_min = embed_df["point_id"].min()
    logger.info(
        f"Embedding point_id range: [{emb_min:,}, {emb_max:,}]"
    )
    if emb_max >= payload_df.height:
        raise ValueError(
            f"Embedding point_id {emb_max} >= payload row count {payload_df.height}"
        )

    # Inner join embeddings to payload on point_id.
    logger.info("Joining embeddings to payload")
    joined = embed_df.join(payload_df, on="point_id", how="inner")
    logger.info(f"Joined rows: {joined.height:,}")
    if joined.height != embed_df.height:
        missing = embed_df.height - joined.height
        logger.warning(f"{missing} embeddings lacked a payload match")

    if args.limit is not None:
        joined = joined.head(args.limit)
        logger.info(f"--limit applied: upserting only {joined.height:,} points")

    logger.info(f"Opening Qdrant at {args.qdrant_path}")
    client = QdrantClient(path=str(args.qdrant_path))

    ensure_collection(client, args.collection, args.recreate)

    upsert_all(client, args.collection, joined, args.batch_size)

    smoke_query(client, args.collection)

    client.close()


if __name__ == "__main__":
    main()
