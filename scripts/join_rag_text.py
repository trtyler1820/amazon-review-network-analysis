#!/usr/bin/env python3
"""
Stage 1b of RAG pipeline: join extracted review text with cleaned-CSV key
set and behavioral metadata.

Inputs:
  - data/rag/raw_text/{category}.parquet              (from extract_review_text.py)
  - data/cleaned/cleaned_reviews.csv                   (dedup key + derived columns)
  - data/rag/user_category_metadata.parquet            (from build_rag_metadata.py)

Output:
  - data/rag/reviews_with_text.parquet
    Final columns:
      user_id, parent_asin, asin, timestamp, date, rating, verified_purchase,
      category_name, helpful_vote, user_first_date, days_since_first,
      review_sequence, title, text, retained, observable, first_category

Logic:
  1. Concat per-category text parquets.
  2. Drop duplicates on (user_id, parent_asin, timestamp) — matches clean_data.py.
  3. Inner-join against cleaned_reviews.csv on the dedup key. Inner-join
     acts as a sanity filter: any row that survived raw filters but didn't
     end up in the cleaned CSV is dropped; any cleaned row missing a text
     match is surfaced as an anomaly.
  4. Left-join user_category_metadata on (user_id, category_name) to attach
     behavioral labels.
  5. Assert final row count equals the cleaned CSV row count (2,523,881).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import polars as pl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_TEXT_DIR = PROJECT_ROOT / "data" / "rag" / "raw_text"
META_PARQUET = PROJECT_ROOT / "data" / "rag" / "user_category_metadata.parquet"
CLEANED_CSV = PROJECT_ROOT / "data" / "cleaned" / "cleaned_reviews.csv"
OUT_PATH = PROJECT_ROOT / "data" / "rag" / "reviews_with_text.parquet"

EXPECTED_ROWS = 2_523_881


def main() -> None:
    text_files = sorted(RAW_TEXT_DIR.glob("*.parquet"))
    if not text_files:
        logger.error(f"No per-category parquets found in {RAW_TEXT_DIR}")
        sys.exit(1)

    logger.info(f"Loading {len(text_files)} per-category parquets")
    text_df = pl.concat([pl.read_parquet(p) for p in text_files], how="vertical")
    logger.info(f"Raw concatenated rows: {text_df.height:,}")

    logger.info("Deduplicating on (user_id, parent_asin, timestamp)")
    before = text_df.height
    text_df = text_df.unique(
        subset=["user_id", "parent_asin", "timestamp"], keep="first"
    )
    logger.info(f"After dedup: {text_df.height:,} (-{before - text_df.height:,})")

    logger.info(f"Loading cleaned CSV key + derived columns: {CLEANED_CSV}")
    cleaned = pl.read_csv(
        CLEANED_CSV,
        columns=[
            "user_id",
            "parent_asin",
            "timestamp",
            "date",
            "verified_purchase",
            "user_first_date",
            "days_since_first",
            "review_sequence",
        ],
        schema_overrides={
            "timestamp": pl.Int64,
            "days_since_first": pl.Int64,
            "review_sequence": pl.Int64,
        },
    ).with_columns(
        [
            pl.col("date")
            .str.to_datetime(time_unit="us", time_zone="UTC", strict=False)
            .alias("date"),
            pl.col("user_first_date")
            .str.to_datetime(time_unit="us", time_zone="UTC", strict=False)
            .alias("user_first_date"),
        ]
    )
    logger.info(f"Cleaned CSV rows: {cleaned.height:,}")

    logger.info("Inner join text ⟕ cleaned on (user_id, parent_asin, timestamp)")
    joined = text_df.join(
        cleaned,
        on=["user_id", "parent_asin", "timestamp"],
        how="inner",
    )
    logger.info(f"After inner join: {joined.height:,}")

    # Detect anomalies
    missing_from_text = cleaned.height - joined.height
    if missing_from_text > 0:
        logger.warning(
            f"{missing_from_text:,} cleaned rows had no text match"
        )
    extra_text = text_df.height - joined.height
    if extra_text > 0:
        logger.warning(
            f"{extra_text:,} extracted rows did not match cleaned CSV"
        )

    logger.info(f"Loading metadata: {META_PARQUET}")
    meta = pl.read_parquet(META_PARQUET).select(
        [
            "user_id",
            "category_name",
            "retained",
            "observable",
            "first_category",
        ]
    )

    logger.info("Left join metadata on (user_id, category_name)")
    joined = joined.join(
        meta,
        on=["user_id", "category_name"],
        how="left",
    )

    null_retained = joined["retained"].null_count()
    if null_retained:
        logger.warning(f"{null_retained:,} rows have null 'retained' after join")

    # Final column order
    final_cols = [
        "user_id",
        "parent_asin",
        "asin",
        "timestamp",
        "date",
        "rating",
        "verified_purchase",
        "category_name",
        "helpful_vote",
        "user_first_date",
        "days_since_first",
        "review_sequence",
        "title",
        "text",
        "retained",
        "observable",
        "first_category",
    ]
    missing = [c for c in final_cols if c not in joined.columns]
    if missing:
        logger.error(f"Missing columns after join: {missing}")
        sys.exit(1)
    joined = joined.select(final_cols)

    # Sanity: row count parity
    if joined.height != EXPECTED_ROWS:
        logger.error(
            f"Row count {joined.height:,} != expected {EXPECTED_ROWS:,}"
        )
        sys.exit(1)

    # Report
    logger.info("=" * 60)
    logger.info("FINAL STATS")
    logger.info("=" * 60)
    logger.info(f"Total rows:           {joined.height:,}")
    by_cat = (
        joined.group_by("category_name")
        .agg(
            [
                pl.len().alias("rows"),
                pl.col("retained").sum().alias("retained_true"),
                pl.col("observable").sum().alias("observable_true"),
                (pl.col("retained") & pl.col("observable")).sum().alias("retained_obs"),
                pl.col("text").str.len_chars().mean().alias("avg_text_chars"),
            ]
        )
        .sort("category_name")
    )
    for row in by_cat.iter_rows(named=True):
        logger.info(
            f"  {row['category_name']:30s} "
            f"rows={row['rows']:>9,}  "
            f"retained={row['retained_true']:>8,}  "
            f"observable={row['observable_true']:>9,}  "
            f"ret&obs={row['retained_obs']:>7,}  "
            f"avg_text={row['avg_text_chars']:>6.0f}c"
        )
    first_cat_nulls = joined["first_category"].null_count()
    logger.info(f"Rows with null first_category (global tie): {first_cat_nulls:,}")
    logger.info(f"Text char p50: {joined['text'].str.len_chars().quantile(0.5):.0f}")
    logger.info(f"Text char p95: {joined['text'].str.len_chars().quantile(0.95):.0f}")

    logger.info(f"Writing {OUT_PATH}")
    joined.write_parquet(OUT_PATH, compression="zstd")
    size_mb = OUT_PATH.stat().st_size / 1e6
    logger.info(f"Done. {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
