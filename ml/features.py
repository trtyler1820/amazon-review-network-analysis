"""Feature engineering: transforms Graph objects into sklearn-ready DataFrames.

Uses Polars for vectorized computation and Joblib for parallel category
processing.  Returns pandas DataFrames for downstream sklearn compatibility.
"""

from __future__ import annotations

import pandas as pd
import polars as pl
from joblib import Parallel, delayed

from graph_logic.models import Graph, DEFAULT_WINDOW_DAYS, MAX_ENTRY_DATE


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
# Retention prediction features (per user-category pair)
# ---------------------------------------------------------------------------

def _build_retention_features_single(
    all_reviews: pl.DataFrame,
    category: str,
    max_entry_date,
) -> pd.DataFrame:
    """Vectorised retention feature engineering for one category."""
    cat_revs = all_reviews.filter(pl.col("category_name") == category)
    if cat_revs.is_empty():
        return pd.DataFrame()

    # First review per user in this category (sort_by guarantees earliest)
    first_in_cat = cat_revs.group_by("user_id").agg([
        pl.col("date").sort_by("date").first().alias("first_date"),
        pl.col("rating").sort_by("date").first().alias("first_rating"),
        pl.col("helpful_vote").sort_by("date").first().alias("first_helpful_vote"),
    ])

    # Observable filter
    if max_entry_date is not None:
        first_in_cat = first_in_cat.filter(pl.col("first_date") <= max_entry_date)
    if first_in_cat.is_empty():
        return pd.DataFrame()

    # NOTE: category_size counts all observable entrants, including those who
    # entered after the user being scored. This is appropriate for retrospective
    # analysis but would be look-ahead leakage in a point-in-time prediction
    # setting. For real-time deployment, replace with a cumulative count up to
    # each user's entry date.
    category_size = len(first_in_cat)

    # --- Retained: 2+ reviews on 2+ distinct UTC days within window ---
    retained = (
        cat_revs
        .join(first_in_cat.select("user_id", "first_date"), on="user_id")
        .filter(pl.col("date") <= pl.col("first_date") + pl.duration(days=DEFAULT_WINDOW_DAYS))
        .with_columns(pl.col("date").dt.date().alias("day"))
        .group_by("user_id")
        .agg([
            pl.len().alias("n"),
            pl.col("day").n_unique().alias("distinct_days"),
        ])
        .with_columns(
            ((pl.col("n") >= 2) & (pl.col("distinct_days") >= 2)).alias("retained")
        )
        .select("user_id", "retained")
    )

    # --- Global first review date per user ---
    global_first = (
        all_reviews.group_by("user_id")
        .agg(pl.col("date").min().alias("global_first_date"))
    )

    # --- First category per user (None on tie) ---
    user_min = all_reviews.group_by("user_id").agg(pl.col("date").min().alias("min_date"))
    first_cat = (
        all_reviews.join(user_min, on="user_id")
        .filter(pl.col("date") == pl.col("min_date"))
        .group_by("user_id")
        .agg([
            pl.col("category_name").n_unique().alias("n_ties"),
            pl.col("category_name").first().alias("fc"),
        ])
        .with_columns(
            pl.when(pl.col("n_ties") == 1).then(pl.col("fc"))
            .otherwise(pl.lit(None)).alias("first_category")
        )
        .select("user_id", "first_category")
    )

    # --- Prior reviews (any category, strictly before first-in-category date) ---
    prior = (
        all_reviews
        .join(first_in_cat.select("user_id", "first_date"), on="user_id")
        .filter(pl.col("date") < pl.col("first_date"))
        .group_by("user_id")
        .agg([
            pl.len().alias("prior_review_count"),
            pl.col("category_name").n_unique().alias("prior_category_count"),
            pl.col("rating").mean().alias("prior_avg_rating"),
        ])
    )

    # --- Assemble ---
    result = (
        first_in_cat
        .with_columns([
            # Polars weekday() is ISO 1-7; Python weekday() is 0-6
            (pl.col("first_date").dt.weekday() - 1).cast(pl.Int64).alias("first_day_of_week"),
            pl.col("first_date").dt.hour().cast(pl.Int64).alias("first_hour_of_day"),
            pl.col("first_date").dt.month().cast(pl.Int64).alias("first_review_month"),
            pl.lit(category_size).cast(pl.Int64).alias("category_size"),
            pl.lit(category).alias("category"),
        ])
        .join(retained, on="user_id", how="left")
        .join(prior, on="user_id", how="left")
        .join(global_first, on="user_id", how="left")
        .join(first_cat, on="user_id", how="left")
        .with_columns([
            pl.col("retained").fill_null(False),
            # is_first_ever must read the nullable prior_review_count BEFORE fill
            pl.col("prior_review_count").is_null().cast(pl.Int64).alias("is_first_ever_review"),
            pl.col("prior_review_count").fill_null(0).cast(pl.Int64),
            pl.col("prior_category_count").fill_null(0).cast(pl.Int64),
            pl.col("prior_avg_rating").fill_null(0.0),
            (pl.col("first_category") == pl.lit(category))
            .fill_null(False).cast(pl.Int64).alias("is_first_category"),
            (pl.col("first_date") - pl.col("global_first_date"))
            .dt.total_days().cast(pl.Int64).alias("days_since_first_ever"),
        ])
        .select([
            "user_id", "category", "first_rating", "first_helpful_vote",
            "first_day_of_week", "first_hour_of_day", "prior_review_count",
            "prior_category_count", "prior_avg_rating", "is_first_ever_review",
            "category_size", "is_first_category", "days_since_first_ever",
            "first_review_month", "retained",
        ])
    )

    return result.to_pandas()


def build_retention_features(
    graph: Graph,
    category: str,
    max_entry_date=MAX_ENTRY_DATE,
) -> pd.DataFrame:
    """
    Build feature matrix for retention prediction in a single category.

    Each row = one observable user in the category.
    Label column = 'retained' (bool).
    Features are derived from the user's first review in the category
    plus prior review history — no data leakage from the 90-day window.
    """
    all_reviews = _graph_to_polars(graph)
    if all_reviews.is_empty():
        return pd.DataFrame()
    return _build_retention_features_single(all_reviews, category, max_entry_date)


def build_retention_features_all(
    graph: Graph,
    max_entry_date=MAX_ENTRY_DATE,
) -> pd.DataFrame:
    """
    Build retention features across all categories, with one-hot encoding
    for the category column.

    Extracts reviews into Polars once, then uses Joblib to process
    categories in parallel threads.
    """
    all_reviews = _graph_to_polars(graph)
    if all_reviews.is_empty():
        return pd.DataFrame()

    categories = list(graph.categories.keys())
    if not categories:
        return pd.DataFrame()

    frames = Parallel(n_jobs=min(len(categories), 4), prefer="threads")(
        delayed(_build_retention_features_single)(all_reviews, cat, max_entry_date)
        for cat in categories
    )

    non_empty = [f for f in frames if not f.empty]
    if not non_empty:
        return pd.DataFrame()

    combined = pd.concat(non_empty, ignore_index=True)
    combined = pd.get_dummies(combined, columns=["category"], prefix="cat")
    return combined


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
