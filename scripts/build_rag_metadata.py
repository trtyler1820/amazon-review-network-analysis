#!/usr/bin/env python3
"""
Build RAG metadata (retention + first_category labels) from cleaned_reviews.csv.

Pure polars implementation of the logic in graph_logic/models.py so we can
attach behavioral labels to review text without instantiating the Graph class.

Outputs:
  - data/rag/user_category_metadata.parquet
      Columns: user_id, category_name, first_cat_date, window_review_count,
               distinct_days_in_window, retained, observable,
               first_category (the user's GLOBAL entry category, nullable on ties)

Parity rules with graph_logic/models.py:
  - Retention window: 90 days from first review in category (inclusive).
  - Retained iff >=2 reviews on >=2 distinct UTC calendar days within window.
  - Observable iff first_cat_date <= 2023-04-02 00:00:00 UTC
    (OBSERVATION_END 2023-07-01 minus 90-day window).
  - first_category is the category of the user's earliest review across ALL
    categories. If two or more categories share the same earliest timestamp,
    first_category is None (tie → excluded from expansion denominators).

Usage:
    python3 scripts/build_rag_metadata.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_CSV = PROJECT_ROOT / "data" / "cleaned" / "cleaned_reviews.csv"
OUT_DIR = PROJECT_ROOT / "data" / "rag"
OUT_FILE = OUT_DIR / "user_category_metadata.parquet"

OBSERVATION_END = datetime(2023, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
WINDOW_DAYS = 90
MAX_ENTRY_DATE = OBSERVATION_END - timedelta(days=WINDOW_DAYS)  # 2023-04-02 UTC


def load_cleaned() -> pl.DataFrame:
    logger.info(f"Loading {CLEANED_CSV}")
    df = pl.read_csv(
        CLEANED_CSV,
        columns=["user_id", "parent_asin", "timestamp", "date", "category_name"],
        schema_overrides={"timestamp": pl.Int64},
    )
    # The cleaned CSV has mixed-precision ISO strings (some rows have
    # microseconds, others don't). Parse with strict=False then cast to UTC.
    df = df.with_columns(
        pl.col("date")
        .str.to_datetime(time_unit="us", time_zone="UTC", strict=False)
        .alias("date")
    )
    null_dates = df["date"].null_count()
    if null_dates:
        raise ValueError(f"{null_dates} rows failed date parsing")
    logger.info(f"Loaded {df.height:,} rows")
    return df


def compute_user_category_metadata(df: pl.DataFrame) -> pl.DataFrame:
    """
    Per (user_id, category_name):
      - first_cat_date: min(date) in that category for that user
      - window_review_count: reviews in [first_cat_date, first_cat_date + 90d]
      - distinct_days_in_window: distinct UTC calendar days in that window
      - retained: window_review_count >= 2 AND distinct_days_in_window >= 2
      - observable: first_cat_date <= MAX_ENTRY_DATE
    """
    logger.info("Computing first_cat_date per (user, category)")
    first_dates = df.group_by(["user_id", "category_name"]).agg(
        pl.col("date").min().alias("first_cat_date")
    )

    logger.info("Joining first_cat_date back onto review rows")
    df_with_first = df.join(first_dates, on=["user_id", "category_name"])

    logger.info("Filtering to in-window reviews and aggregating")
    max_entry_literal = pl.lit(MAX_ENTRY_DATE).cast(pl.Datetime("us", "UTC"))

    in_window = df_with_first.filter(
        pl.col("date") <= pl.col("first_cat_date") + pl.duration(days=WINDOW_DAYS)
    )
    window_stats = in_window.group_by(["user_id", "category_name"]).agg(
        [
            pl.len().alias("window_review_count"),
            pl.col("date").dt.date().n_unique().alias("distinct_days_in_window"),
        ]
    )

    logger.info("Joining window stats and labeling retained/observable")
    metadata = (
        first_dates.join(window_stats, on=["user_id", "category_name"], how="left")
        .with_columns(
            [
                pl.col("window_review_count").fill_null(0),
                pl.col("distinct_days_in_window").fill_null(0),
            ]
        )
        .with_columns(
            [
                (
                    (pl.col("window_review_count") >= 2)
                    & (pl.col("distinct_days_in_window") >= 2)
                ).alias("retained"),
                (pl.col("first_cat_date") <= max_entry_literal).alias("observable"),
            ]
        )
    )

    return metadata


def compute_first_category(df: pl.DataFrame) -> pl.DataFrame:
    """
    Per user_id: the global entry category.
    Returns a frame with (user_id, first_category). first_category is null on ties.
    """
    logger.info("Computing global first_category per user")
    # Earliest date per user across all categories
    global_first = df.group_by("user_id").agg(
        pl.col("date").min().alias("global_first_date")
    )

    # Join back, find rows matching the earliest instant, then aggregate unique categories
    df_join = df.join(global_first, on="user_id")
    candidates = df_join.filter(pl.col("date") == pl.col("global_first_date"))
    unique_cats = candidates.group_by("user_id").agg(
        pl.col("category_name").unique().alias("cats_at_first")
    )
    first_cat = unique_cats.with_columns(
        pl.when(pl.col("cats_at_first").list.len() == 1)
        .then(pl.col("cats_at_first").list.first())
        .otherwise(None)
        .alias("first_category")
    ).select(["user_id", "first_category"])

    return first_cat


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_cleaned()

    meta = compute_user_category_metadata(df)
    first_cats = compute_first_category(df)

    logger.info("Merging first_category into metadata")
    meta = meta.join(first_cats, on="user_id", how="left")

    # Report
    total_rows = meta.height
    observable_users = meta.filter(pl.col("observable")).height
    retained_rows = meta.filter(pl.col("retained")).height
    observable_retained = meta.filter(
        pl.col("observable") & pl.col("retained")
    ).height
    null_first = meta.filter(pl.col("first_category").is_null()).height
    cats_breakdown = meta.group_by("category_name").agg(
        [
            pl.len().alias("users"),
            pl.col("observable").sum().alias("observable"),
            (pl.col("observable") & pl.col("retained"))
            .sum()
            .alias("observable_retained"),
        ]
    ).sort("category_name")

    logger.info(f"Total (user, category) rows: {total_rows:,}")
    logger.info(f"Observable rows: {observable_users:,}")
    logger.info(f"Retained (any): {retained_rows:,}")
    logger.info(f"Observable & retained: {observable_retained:,}")
    logger.info(f"Null first_category (ties or anomalies): {null_first:,}")
    logger.info("Per-category breakdown:")
    for row in cats_breakdown.iter_rows(named=True):
        observable = row["observable"]
        retained = row["observable_retained"]
        rate = (retained / observable * 100) if observable else 0.0
        logger.info(
            f"  {row['category_name']:30s} "
            f"users={row['users']:>8,}  "
            f"observable={observable:>8,}  "
            f"retained={retained:>7,}  "
            f"rate={rate:5.2f}%"
        )

    logger.info(f"Writing {OUT_FILE}")
    meta.write_parquet(OUT_FILE)
    logger.info(f"Done. {OUT_FILE.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
