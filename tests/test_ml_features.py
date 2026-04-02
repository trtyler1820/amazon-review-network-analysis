"""Tests for ml.features — feature engineering from Graph objects."""

import pandas as pd
import pytest

from datetime import datetime, timedelta, timezone
from graph_logic.models import Graph, Review, User, Category, MAX_ENTRY_DATE
from ml.features import (
    build_retention_features,
    build_retention_features_all,
    build_user_features,
)
from tests.conftest import make_review, make_user, BASE_DATE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _small_graph() -> Graph:
    """
    Build a Graph with 5 users across 2 categories for testing.

    Users:
      u1: Electronics day 0, day 10 (retained), also Video_Games day 5
      u2: Electronics day 0 only (not retained, 1 review)
      u3: Electronics day 0, day 0+1hr (not retained, same day)
      u4: Video_Games day 0, day 20 (retained)
      u5: Electronics day 80 (observable but 1 review)
    """
    rows = [
        # u1 — retained in Electronics, cross-category
        {"user_id": "u1", "parent_asin": "P1", "asin": "A1", "category_name": "Electronics",
         "rating": 4.0, "helpful_vote": 2, "day": 0},
        {"user_id": "u1", "parent_asin": "P2", "asin": "A2", "category_name": "Video_Games",
         "rating": 3.0, "helpful_vote": 0, "day": 5},
        {"user_id": "u1", "parent_asin": "P3", "asin": "A3", "category_name": "Electronics",
         "rating": 5.0, "helpful_vote": 1, "day": 10},
        # u2 — single review
        {"user_id": "u2", "parent_asin": "P4", "asin": "A4", "category_name": "Electronics",
         "rating": 1.0, "helpful_vote": 0, "day": 0},
        # u3 — two reviews same day (not retained)
        {"user_id": "u3", "parent_asin": "P5", "asin": "A5", "category_name": "Electronics",
         "rating": 2.0, "helpful_vote": 0, "day": 0, "hour": 0},
        {"user_id": "u3", "parent_asin": "P6", "asin": "A6", "category_name": "Electronics",
         "rating": 3.0, "helpful_vote": 0, "day": 0, "hour": 3},
        # u4 — retained in Video_Games
        {"user_id": "u4", "parent_asin": "P7", "asin": "A7", "category_name": "Video_Games",
         "rating": 5.0, "helpful_vote": 5, "day": 0},
        {"user_id": "u4", "parent_asin": "P8", "asin": "A8", "category_name": "Video_Games",
         "rating": 4.0, "helpful_vote": 3, "day": 20},
        # u5 — observable, single review
        {"user_id": "u5", "parent_asin": "P9", "asin": "A9", "category_name": "Electronics",
         "rating": 3.0, "helpful_vote": 0, "day": 80},
    ]

    records = []
    for r in rows:
        dt = BASE_DATE + timedelta(days=r["day"], hours=r.get("hour", 0))
        records.append({
            "user_id": r["user_id"],
            "parent_asin": r["parent_asin"],
            "asin": r["asin"],
            "timestamp": int(dt.timestamp() * 1000),
            "date": dt,
            "rating": r["rating"],
            "verified_purchase": True,
            "category_name": r["category_name"],
            "helpful_vote": r["helpful_vote"],
        })

    df = pd.DataFrame(records)
    return Graph.from_dataframe(df)


# ---------------------------------------------------------------------------
# Retention feature tests
# ---------------------------------------------------------------------------

class TestBuildRetentionFeatures:

    def test_returns_expected_columns(self):
        g = _small_graph()
        df = build_retention_features(g, "Electronics", max_entry_date=None)
        expected = {
            "user_id", "category", "first_rating", "first_helpful_vote",
            "first_day_of_week", "first_hour_of_day", "prior_review_count",
            "prior_category_count", "prior_avg_rating", "is_first_ever_review",
            "category_size", "is_first_category", "days_since_first_ever",
            "first_review_month", "retained",
        }
        assert set(df.columns) == expected

    def test_only_observable_users(self):
        g = _small_graph()
        # With default MAX_ENTRY_DATE (2023-04-02), all our test users
        # started on BASE_DATE (2023-01-05) which is before cutoff
        df = build_retention_features(g, "Electronics", max_entry_date=None)
        assert len(df) == 4  # u1, u2, u3, u5 all in Electronics

    def test_retained_label_matches(self):
        g = _small_graph()
        df = build_retention_features(g, "Electronics", max_entry_date=None)
        u1_row = df[df["user_id"] == "u1"].iloc[0]
        assert u1_row["retained"] == True  # 2 reviews, 2 distinct days

        u2_row = df[df["user_id"] == "u2"].iloc[0]
        assert u2_row["retained"] == False  # 1 review

        u3_row = df[df["user_id"] == "u3"].iloc[0]
        assert u3_row["retained"] == False  # 2 reviews but same day

    def test_first_rating(self):
        g = _small_graph()
        df = build_retention_features(g, "Electronics", max_entry_date=None)
        u1_row = df[df["user_id"] == "u1"].iloc[0]
        assert u1_row["first_rating"] == 4.0

    def test_prior_review_count_cross_category(self):
        """u1's first Electronics review is day 0. u1 also has Video_Games day 5.
        But Video_Games day 5 is AFTER Electronics day 0, so prior count = 0."""
        g = _small_graph()
        df = build_retention_features(g, "Electronics", max_entry_date=None)
        u1_row = df[df["user_id"] == "u1"].iloc[0]
        assert u1_row["prior_review_count"] == 0

    def test_prior_review_count_has_prior(self):
        """u1's first Video_Games review is day 5. u1 has Electronics day 0 before that."""
        g = _small_graph()
        df = build_retention_features(g, "Video_Games", max_entry_date=None)
        u1_row = df[df["user_id"] == "u1"].iloc[0]
        assert u1_row["prior_review_count"] == 1
        assert u1_row["prior_category_count"] == 1

    def test_is_first_ever_review(self):
        g = _small_graph()
        df = build_retention_features(g, "Electronics", max_entry_date=None)
        u2_row = df[df["user_id"] == "u2"].iloc[0]
        assert u2_row["is_first_ever_review"] == 1

    def test_is_first_category(self):
        g = _small_graph()
        df = build_retention_features(g, "Electronics", max_entry_date=None)
        u1_row = df[df["user_id"] == "u1"].iloc[0]
        assert u1_row["is_first_category"] == 1  # Electronics day 0 is u1's first

    def test_days_since_first_ever(self):
        g = _small_graph()
        df = build_retention_features(g, "Video_Games", max_entry_date=None)
        u1_row = df[df["user_id"] == "u1"].iloc[0]
        assert u1_row["days_since_first_ever"] == 5  # first ever day 0, VG day 5

    def test_empty_category_returns_empty(self):
        g = _small_graph()
        df = build_retention_features(g, "Software", max_entry_date=None)
        assert df.empty

    def test_nonexistent_category_returns_empty(self):
        g = _small_graph()
        df = build_retention_features(g, "NoSuchCategory", max_entry_date=None)
        assert df.empty


class TestBuildRetentionFeaturesAll:

    def test_combines_categories(self):
        g = _small_graph()
        df = build_retention_features_all(g, max_entry_date=None)
        assert len(df) > 0
        # Should have one-hot category columns
        cat_cols = [c for c in df.columns if c.startswith("cat_")]
        assert len(cat_cols) == 2  # Electronics and Video_Games

    def test_no_raw_category_column(self):
        g = _small_graph()
        df = build_retention_features_all(g, max_entry_date=None)
        assert "category" not in df.columns


# ---------------------------------------------------------------------------
# User clustering feature tests
# ---------------------------------------------------------------------------

class TestBuildUserFeatures:

    def test_returns_expected_columns(self):
        g = _small_graph()
        df = build_user_features(g)
        expected = {
            "user_id", "total_review_count", "category_count", "avg_rating",
            "rating_std", "total_helpful_votes", "avg_helpful_votes",
            "active_days", "time_span_days", "reviews_per_active_day",
            "is_multi_category", "max_reviews_in_single_category",
            "category_concentration",
        }
        assert set(df.columns) == expected

    def test_total_review_count(self):
        g = _small_graph()
        df = build_user_features(g)
        u1_row = df[df["user_id"] == "u1"].iloc[0]
        assert u1_row["total_review_count"] == 3  # 2 Electronics + 1 VG

    def test_category_count(self):
        g = _small_graph()
        df = build_user_features(g)
        u1_row = df[df["user_id"] == "u1"].iloc[0]
        assert u1_row["category_count"] == 2

        u2_row = df[df["user_id"] == "u2"].iloc[0]
        assert u2_row["category_count"] == 1

    def test_time_span_days(self):
        g = _small_graph()
        df = build_user_features(g)
        u1_row = df[df["user_id"] == "u1"].iloc[0]
        assert u1_row["time_span_days"] == 10  # day 0 to day 10

        u2_row = df[df["user_id"] == "u2"].iloc[0]
        assert u2_row["time_span_days"] == 0  # single review

    def test_category_concentration(self):
        g = _small_graph()
        df = build_user_features(g)
        u2_row = df[df["user_id"] == "u2"].iloc[0]
        assert u2_row["category_concentration"] == 1.0  # all in one category

    def test_is_multi_category(self):
        g = _small_graph()
        df = build_user_features(g)
        u1_row = df[df["user_id"] == "u1"].iloc[0]
        assert u1_row["is_multi_category"] == 1

        u4_row = df[df["user_id"] == "u4"].iloc[0]
        assert u4_row["is_multi_category"] == 0

    def test_min_reviews_filter(self):
        g = _small_graph()
        df_all = build_user_features(g, min_reviews=1)
        df_multi = build_user_features(g, min_reviews=2)
        assert len(df_multi) < len(df_all)
        # u2 and u5 have 1 review each, should be filtered
        assert "u2" not in df_multi["user_id"].values
        assert "u5" not in df_multi["user_id"].values

    def test_rating_std_single_review(self):
        g = _small_graph()
        df = build_user_features(g)
        u2_row = df[df["user_id"] == "u2"].iloc[0]
        assert u2_row["rating_std"] == 0.0
