"""Feature engineering: transforms Graph objects into sklearn-ready DataFrames.

Uses Polars for vectorized computation.
Returns pandas DataFrames for downstream sklearn compatibility.
"""

from __future__ import annotations

import pandas as pd
import polars as pl

from graph_logic.models import Graph


# ---------------------------------------------------------------------------
# Internal: Graph → Polars extraction (called once, reused across categories)
# ---------------------------------------------------------------------------

_EMPTY_SCHEMA = {
    "user_id": pl.Utf8,
    "category_name": pl.Utf8,
    "date": pl.Datetime("us", "UTC"),
    "rating": pl.Float64,
    "helpful_vote": pl.Int64,
}


def _graph_to_polars(graph: Graph) -> pl.DataFrame:
    """Flatten all reviews from a Graph into a Polars DataFrame."""
    user_ids, cat_names, dates, ratings, votes = [], [], [], [], []
    for user in graph.users.values():
        for reviews in user.reviews_by_category.values():
            for r in reviews:
                user_ids.append(r.user_id)
                cat_names.append(r.category_name)
                dates.append(r.date)
                ratings.append(r.rating)
                votes.append(r.helpful_vote)
    if not user_ids:
        return pl.DataFrame(schema=_EMPTY_SCHEMA)
    return pl.DataFrame({
        "user_id": user_ids,
        "category_name": cat_names,
        "date": dates,
        "rating": ratings,
        "helpful_vote": votes,
    })


# ---------------------------------------------------------------------------
# User clustering features (per user, global)
# ---------------------------------------------------------------------------

def build_user_features(
    graph: Graph,
    min_reviews: int = 1,
) -> pd.DataFrame:
    """
    Build feature matrix for user clustering / segmentation.

    Each row = one user. Features capture review behavior across all categories.
    """
    all_reviews = _graph_to_polars(graph)
    if all_reviews.is_empty():
        return pd.DataFrame()

    # Per-user per-category counts (for max_in_single + concentration)
    cat_stats = (
        all_reviews
        .group_by(["user_id", "category_name"])
        .agg(pl.len().alias("cat_count"))
        .group_by("user_id")
        .agg(pl.col("cat_count").max().alias("max_reviews_in_single_category"))
    )

    # Main per-user aggregation
    result = (
        all_reviews
        .with_columns(pl.col("date").dt.date().alias("review_day"))
        .group_by("user_id")
        .agg([
            pl.len().alias("total_review_count"),
            pl.col("category_name").n_unique().alias("category_count"),
            pl.col("rating").mean().alias("avg_rating"),
            pl.col("rating").std(ddof=0).alias("rating_std"),
            pl.col("helpful_vote").sum().alias("total_helpful_votes"),
            pl.col("helpful_vote").mean().alias("avg_helpful_votes"),
            pl.col("review_day").n_unique().alias("active_days"),
            ((pl.col("date").max() - pl.col("date").min()).dt.total_days())
            .alias("time_span_days"),
        ])
        .filter(pl.col("total_review_count") >= min_reviews)
        .join(cat_stats, on="user_id")
        .with_columns([
            pl.col("rating_std").fill_null(0.0),
            (pl.col("total_review_count").cast(pl.Float64) / pl.col("active_days"))
            .alias("reviews_per_active_day"),
            (pl.col("category_count") > 1).cast(pl.Int64).alias("is_multi_category"),
            (pl.col("max_reviews_in_single_category").cast(pl.Float64)
             / pl.col("total_review_count")).alias("category_concentration"),
        ])
        .select([
            "user_id", "total_review_count", "category_count", "avg_rating",
            "rating_std", "total_helpful_votes", "avg_helpful_votes",
            "active_days", "time_span_days", "reviews_per_active_day",
            "is_multi_category", "max_reviews_in_single_category",
            "category_concentration",
        ])
    )

    return result.to_pandas()
