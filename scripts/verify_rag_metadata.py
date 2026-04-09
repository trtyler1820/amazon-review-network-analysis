#!/usr/bin/env python3
"""
Parity check: confirm polars-computed metadata in
data/rag/user_category_metadata.parquet matches graph_logic/models.py
on a sampled set of users.

Samples N users from the cleaned data, builds a small Graph from ONLY
those users' reviews (so every review of those users is present across
all categories), then compares:
  - retained per (user, category)
  - observable per (user, category)
  - first_category per user

Exits non-zero on any mismatch.
"""

from __future__ import annotations

import logging
import random
import sys
from pathlib import Path

import pandas as pd
import polars as pl

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from graph_logic.models import Graph  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CLEANED_CSV = PROJECT_ROOT / "data" / "cleaned" / "cleaned_reviews.csv"
META_PARQUET = PROJECT_ROOT / "data" / "rag" / "user_category_metadata.parquet"
SAMPLE_USERS = 500
RNG_SEED = 42


def main() -> None:
    logger.info(f"Loading {META_PARQUET}")
    meta = pl.read_parquet(META_PARQUET)

    logger.info(f"Loading {CLEANED_CSV} (polars, then slicing to sample users)")
    df_pl = pl.read_csv(
        CLEANED_CSV,
        schema_overrides={"timestamp": pl.Int64},
    ).with_columns(
        pl.col("date")
        .str.to_datetime(time_unit="us", time_zone="UTC", strict=False)
        .alias("date")
    )

    all_users = df_pl["user_id"].unique().to_list()
    random.seed(RNG_SEED)
    sample = random.sample(all_users, SAMPLE_USERS)
    logger.info(f"Sampled {len(sample)} users")

    sample_df_pl = df_pl.filter(pl.col("user_id").is_in(sample))
    logger.info(f"Sample has {sample_df_pl.height} reviews")

    # Build Graph from the sample (graph_logic expects pandas)
    sample_df_pd = sample_df_pl.to_pandas()
    # Ensure UTC-aware datetimes (pandas conversion can go naive if not careful)
    sample_df_pd["date"] = pd.to_datetime(
        sample_df_pd["date"], utc=True, format="ISO8601"
    )
    logger.info("Building Graph from sample")
    graph = Graph.from_dataframe(sample_df_pd)

    # Build the ground-truth dict from the Graph
    truth_user_cat = {}  # (user_id, category) -> (retained, observable)
    truth_first_cat = {}  # user_id -> first_category
    for uid, user in graph.users.items():
        truth_first_cat[uid] = user.first_category
        for cat in user.reviews_by_category:
            truth_user_cat[(uid, cat)] = (
                user.is_retained(cat),
                user.is_observable(cat),
            )

    # Compare against metadata parquet (filtered to sample)
    sample_meta = meta.filter(pl.col("user_id").is_in(sample))
    logger.info(f"Metadata rows for sample: {sample_meta.height}")

    mismatches_retained = 0
    mismatches_observable = 0
    mismatches_first_cat = 0
    missing_in_meta = 0

    seen_keys = set()
    for row in sample_meta.iter_rows(named=True):
        key = (row["user_id"], row["category_name"])
        seen_keys.add(key)
        truth = truth_user_cat.get(key)
        if truth is None:
            missing_in_meta += 1
            continue
        truth_retained, truth_observable = truth
        # Graph.is_retained() returns False for unobservable users (observable
        # check is baked in). Polars metadata keeps the flags independent.
        # Compare Graph.is_retained vs (polars.retained AND polars.observable).
        polars_retained_observable = row["retained"] and row["observable"]
        if polars_retained_observable != truth_retained:
            mismatches_retained += 1
            if mismatches_retained <= 3:
                logger.warning(
                    f"RETAINED mismatch {key}: "
                    f"polars(retained&observable)={polars_retained_observable} "
                    f"graph={truth_retained}"
                )
        if row["observable"] != truth_observable:
            mismatches_observable += 1
            if mismatches_observable <= 3:
                logger.warning(
                    f"OBSERVABLE mismatch {key}: "
                    f"polars={row['observable']} graph={truth_observable}"
                )

    # Any keys in the Graph that are missing from metadata?
    missing_in_polars = 0
    for key in truth_user_cat:
        if key not in seen_keys:
            missing_in_polars += 1

    # First category
    first_cat_meta = (
        sample_meta.group_by("user_id")
        .agg(pl.col("first_category").first())
        .to_dicts()
    )
    for rec in first_cat_meta:
        uid = rec["user_id"]
        expected = truth_first_cat.get(uid)
        actual = rec["first_category"]
        if expected != actual:
            mismatches_first_cat += 1
            if mismatches_first_cat <= 3:
                logger.warning(
                    f"FIRST_CAT mismatch {uid}: polars={actual} graph={expected}"
                )

    logger.info("=" * 60)
    logger.info("PARITY RESULTS")
    logger.info("=" * 60)
    logger.info(f"Sample users: {SAMPLE_USERS}")
    logger.info(f"Graph (user,cat) pairs: {len(truth_user_cat)}")
    logger.info(f"Metadata (user,cat) pairs for sample: {sample_meta.height}")
    logger.info(f"Retained mismatches:    {mismatches_retained}")
    logger.info(f"Observable mismatches:  {mismatches_observable}")
    logger.info(f"First-category mismatches: {mismatches_first_cat}")
    logger.info(f"(user,cat) in graph but missing in metadata: {missing_in_polars}")
    logger.info(f"(user,cat) in metadata but missing in graph: {missing_in_meta}")

    total_mismatches = (
        mismatches_retained
        + mismatches_observable
        + mismatches_first_cat
        + missing_in_polars
        + missing_in_meta
    )
    if total_mismatches == 0:
        logger.info("✓ FULL PARITY")
        sys.exit(0)
    else:
        logger.error(f"✗ {total_mismatches} TOTAL mismatches")
        sys.exit(1)


if __name__ == "__main__":
    main()
