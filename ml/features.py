"""Feature engineering: transforms Graph objects into sklearn-ready DataFrames."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from graph_logic.models import Graph, User, MAX_ENTRY_DATE


# ---------------------------------------------------------------------------
# Retention prediction features (per user-category pair)
# ---------------------------------------------------------------------------

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
    cat_obj = graph.categories.get(category)
    if cat_obj is None:
        return pd.DataFrame()

    records = []
    for user in cat_obj.users.values():
        if not user.is_observable(category, max_entry_date):
            continue

        cat_reviews = user.reviews_in(category)
        first = cat_reviews[0]

        all_revs = user.all_reviews()
        prior = [r for r in all_revs if r.date < first.date]
        prior_cats = {r.category_name for r in prior}
        prior_ratings = [r.rating for r in prior]

        records.append({
            "user_id": user.user_id,
            "category": category,
            "first_rating": first.rating,
            "first_helpful_vote": first.helpful_vote,
            "first_day_of_week": first.date.weekday(),
            "first_hour_of_day": first.date.hour,
            "prior_review_count": len(prior),
            "prior_category_count": len(prior_cats),
            "prior_avg_rating": float(np.mean(prior_ratings)) if prior_ratings else 0.0,
            "is_first_ever_review": 1 if len(prior) == 0 else 0,
            "category_size": cat_obj.observable_user_count(max_entry_date),
            "is_first_category": 1 if user.first_category == category else 0,
            "days_since_first_ever": (first.date - all_revs[0].date).days,
            "first_review_month": first.date.month,
            "retained": user.is_retained(category, max_entry_date=max_entry_date),
        })

    return pd.DataFrame(records)


def build_retention_features_all(
    graph: Graph,
    max_entry_date=MAX_ENTRY_DATE,
) -> pd.DataFrame:
    """
    Build retention features across all categories, with one-hot encoding
    for the category column.
    """
    frames = []
    for cat_name in graph.categories:
        df = build_retention_features(graph, cat_name, max_entry_date)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
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
    records = []
    for user in graph.users.values():
        all_revs = user.all_reviews()
        n = len(all_revs)
        if n < min_reviews:
            continue

        ratings = [r.rating for r in all_revs]
        helpful = [r.helpful_vote for r in all_revs]
        dates = [r.date.date() for r in all_revs]
        active_days = len(set(dates))
        time_span = (all_revs[-1].date - all_revs[0].date).days

        cat_counts = {cat: len(revs) for cat, revs in user.reviews_by_category.items()}
        max_in_single = max(cat_counts.values())

        records.append({
            "user_id": user.user_id,
            "total_review_count": n,
            "category_count": len(cat_counts),
            "avg_rating": float(np.mean(ratings)),
            "rating_std": float(np.std(ratings, ddof=0)) if n > 1 else 0.0,
            "total_helpful_votes": sum(helpful),
            "avg_helpful_votes": float(np.mean(helpful)),
            "active_days": active_days,
            "time_span_days": time_span,
            "reviews_per_active_day": n / active_days,
            "is_multi_category": 1 if len(cat_counts) > 1 else 0,
            "max_reviews_in_single_category": max_in_single,
            "category_concentration": max_in_single / n,
        })

    return pd.DataFrame(records)
