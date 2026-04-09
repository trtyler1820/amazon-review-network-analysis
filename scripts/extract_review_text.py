#!/usr/bin/env python3
"""
Stage 1 of RAG pipeline: extract review text from raw JSONL files.

Streams each raw category JSONL file with polars (no full load), applies the
same filters as scripts/clean_data.py (verified_purchase=True, date range
[2023-01-01, 2023-07-01) UTC), and keeps review text + metadata. Writes one
parquet per category to data/rag/raw_text/{category}.parquet.

This step is resumable: per-category outputs are skipped if they already
exist unless --force is passed.

Rows at this stage include duplicates by (user_id, parent_asin, timestamp).
Stage 1b (scripts/join_rag_text.py) deduplicates, joins against the cleaned
CSV key set, and attaches behavioral metadata.

Usage:
    python3 scripts/extract_review_text.py                 # full run
    python3 scripts/extract_review_text.py --force         # re-extract all
    python3 scripts/extract_review_text.py --only Software # single category
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUT_DIR = PROJECT_ROOT / "data" / "rag" / "raw_text"

REVIEW_FILES = {
    "Software": "Software.jsonl",
    "Video_Games": "Video_Games.jsonl",
    "Cell_Phones_and_Accessories": "Cell_Phones_and_Accessories.jsonl",
    "Electronics": "Electronics.jsonl",
}

DATE_START = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
DATE_END = datetime(2023, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
START_MS = int(DATE_START.timestamp() * 1000)
END_MS = int(DATE_END.timestamp() * 1000)

RAW_SCHEMA = {
    "rating": pl.Float64,
    "title": pl.Utf8,
    "text": pl.Utf8,
    "asin": pl.Utf8,
    "parent_asin": pl.Utf8,
    "user_id": pl.Utf8,
    "timestamp": pl.Int64,
    "helpful_vote": pl.Int64,
    "verified_purchase": pl.Boolean,
}


def extract_category(category: str, force: bool = False) -> dict:
    filename = REVIEW_FILES[category]
    raw_path = RAW_DIR / filename
    out_path = OUT_DIR / f"{category}.parquet"

    if not raw_path.exists():
        raise FileNotFoundError(f"Missing raw file: {raw_path}")

    if out_path.exists() and not force:
        rows = pl.scan_parquet(out_path).select(pl.len()).collect().item()
        size_mb = out_path.stat().st_size / 1e6
        logger.info(
            f"[{category}] SKIP (exists): {rows:,} rows, {size_mb:.1f} MB  "
            f"(use --force to re-extract)"
        )
        return {"category": category, "rows": rows, "bytes": out_path.stat().st_size, "seconds": 0.0, "skipped": True}

    raw_mb = raw_path.stat().st_size / 1e6
    logger.info(f"[{category}] START  raw file: {raw_mb:,.0f} MB")
    t0 = time.perf_counter()

    lf = pl.scan_ndjson(raw_path, schema=RAW_SCHEMA)
    filtered = (
        lf.filter(
            (pl.col("verified_purchase") == True)  # noqa: E712
            & (pl.col("timestamp") >= START_MS)
            & (pl.col("timestamp") < END_MS)
        )
        .select(
            [
                pl.col("user_id"),
                pl.col("parent_asin"),
                pl.col("asin"),
                pl.col("timestamp"),
                pl.col("rating"),
                pl.col("helpful_vote"),
                pl.col("title"),
                pl.col("text"),
                pl.lit(category).alias("category_name"),
            ]
        )
    )

    # sink_parquet streams the output without loading the full frame.
    filtered.sink_parquet(out_path, compression="zstd", row_group_size=100_000)

    elapsed = time.perf_counter() - t0
    rows = pl.scan_parquet(out_path).select(pl.len()).collect().item()
    size_mb = out_path.stat().st_size / 1e6
    logger.info(
        f"[{category}] DONE   {rows:,} rows, {size_mb:.1f} MB, {elapsed:.1f}s"
    )
    return {
        "category": category,
        "rows": rows,
        "bytes": out_path.stat().st_size,
        "seconds": elapsed,
        "skipped": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract review text from raw JSONL")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even if per-category parquet already exists",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        choices=list(REVIEW_FILES.keys()),
        help="Only process a single category",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    categories = [args.only] if args.only else list(REVIEW_FILES.keys())
    results = []
    total_t0 = time.perf_counter()
    for category in categories:
        try:
            results.append(extract_category(category, force=args.force))
        except Exception as exc:
            logger.exception(f"[{category}] FAILED: {exc}")
            raise
    total_elapsed = time.perf_counter() - total_t0

    logger.info("=" * 60)
    logger.info("EXTRACTION SUMMARY")
    logger.info("=" * 60)
    total_rows = 0
    total_bytes = 0
    for r in results:
        total_rows += r["rows"]
        total_bytes += r["bytes"]
        tag = "SKIP" if r["skipped"] else "OK"
        logger.info(
            f"  [{tag}] {r['category']:30s} {r['rows']:>10,} rows  "
            f"{r['bytes']/1e6:>8.1f} MB  {r['seconds']:>6.1f}s"
        )
    logger.info(f"  TOTAL:                    {total_rows:>10,} rows  {total_bytes/1e6:>8.1f} MB  {total_elapsed:>6.1f}s")


if __name__ == "__main__":
    main()
