"""Tests for ml.clustering — K-means user segmentation pipeline."""

import numpy as np
import pandas as pd
import pytest

from ml.clustering import (
    find_optimal_k,
    train_clustering,
    characterize_clusters,
)


def _synthetic_user_features(n: int = 300, random_state: int = 42) -> pd.DataFrame:
    """Create a synthetic user feature DataFrame with distinct clusters."""
    rng = np.random.default_rng(random_state)

    # Create 3 distinct groups
    group_size = n // 3

    # Group 1: one-and-done (low reviews, 1 category)
    g1 = pd.DataFrame({
        "total_review_count": rng.integers(1, 2, group_size),
        "category_count": np.ones(group_size, dtype=int),
        "avg_rating": rng.uniform(3, 5, group_size),
        "rating_std": np.zeros(group_size),
        "total_helpful_votes": rng.integers(0, 2, group_size),
        "avg_helpful_votes": rng.uniform(0, 1, group_size),
        "active_days": np.ones(group_size, dtype=int),
        "time_span_days": np.zeros(group_size, dtype=int),
        "reviews_per_active_day": np.ones(group_size, dtype=float),
        "is_multi_category": np.zeros(group_size, dtype=int),
        "max_reviews_in_single_category": rng.integers(1, 2, group_size),
        "category_concentration": np.ones(group_size, dtype=float),
    })

    # Group 2: casual (moderate reviews, 1 category)
    g2 = pd.DataFrame({
        "total_review_count": rng.integers(3, 8, group_size),
        "category_count": np.ones(group_size, dtype=int),
        "avg_rating": rng.uniform(2, 5, group_size),
        "rating_std": rng.uniform(0.5, 1.5, group_size),
        "total_helpful_votes": rng.integers(0, 10, group_size),
        "avg_helpful_votes": rng.uniform(0, 3, group_size),
        "active_days": rng.integers(2, 6, group_size),
        "time_span_days": rng.integers(10, 60, group_size),
        "reviews_per_active_day": rng.uniform(1, 2, group_size),
        "is_multi_category": np.zeros(group_size, dtype=int),
        "max_reviews_in_single_category": rng.integers(3, 8, group_size),
        "category_concentration": np.ones(group_size, dtype=float),
    })

    # Group 3: power reviewers (high reviews, multi-category)
    g3 = pd.DataFrame({
        "total_review_count": rng.integers(10, 30, group_size),
        "category_count": rng.integers(2, 4, group_size),
        "avg_rating": rng.uniform(3, 5, group_size),
        "rating_std": rng.uniform(0.5, 2, group_size),
        "total_helpful_votes": rng.integers(5, 50, group_size),
        "avg_helpful_votes": rng.uniform(1, 5, group_size),
        "active_days": rng.integers(5, 20, group_size),
        "time_span_days": rng.integers(30, 150, group_size),
        "reviews_per_active_day": rng.uniform(1, 3, group_size),
        "is_multi_category": np.ones(group_size, dtype=int),
        "max_reviews_in_single_category": rng.integers(5, 20, group_size),
        "category_concentration": rng.uniform(0.4, 0.8, group_size),
    })

    df = pd.concat([g1, g2, g3], ignore_index=True)
    df["user_id"] = [f"u{i}" for i in range(len(df))]
    return df


class TestFindOptimalK:

    def test_returns_expected_keys(self):
        df = _synthetic_user_features()
        result = find_optimal_k(df, k_range=range(2, 5))
        assert set(result.keys()) == {"k_range", "inertias", "silhouette_scores", "best_k"}

    def test_inertia_decreases(self):
        df = _synthetic_user_features()
        result = find_optimal_k(df, k_range=range(2, 6))
        inertias = result["inertias"]
        for i in range(len(inertias) - 1):
            assert inertias[i] >= inertias[i + 1]

    def test_silhouette_in_range(self):
        df = _synthetic_user_features()
        result = find_optimal_k(df, k_range=range(2, 5))
        for s in result["silhouette_scores"]:
            assert -1.0 <= s <= 1.0

    def test_best_k_in_range(self):
        df = _synthetic_user_features()
        result = find_optimal_k(df, k_range=range(2, 6))
        assert result["best_k"] in list(range(2, 6))


class TestTrainClustering:

    def test_returns_expected_keys(self):
        df = _synthetic_user_features()
        result = train_clustering(df, n_clusters=3)
        expected = {"model", "scaler", "feature_names", "labels",
                    "cluster_centers_original", "cluster_profiles"}
        assert set(result.keys()) == expected

    def test_labels_length(self):
        df = _synthetic_user_features()
        result = train_clustering(df, n_clusters=3)
        assert len(result["labels"]) == len(df)

    def test_cluster_profiles_shape(self):
        df = _synthetic_user_features()
        result = train_clustering(df, n_clusters=3)
        profiles = result["cluster_profiles"]
        assert len(profiles) == 3
        assert "size" in profiles.columns

    def test_all_labels_present(self):
        df = _synthetic_user_features()
        result = train_clustering(df, n_clusters=3)
        unique_labels = set(result["labels"])
        assert unique_labels == {0, 1, 2}


class TestCharacterizeClusters:

    def test_adds_label_column(self):
        df = _synthetic_user_features()
        result = train_clustering(df, n_clusters=3)
        profiles = characterize_clusters(result)
        assert "label" in profiles.columns
        assert len(profiles) == 3

    def test_labels_are_strings(self):
        df = _synthetic_user_features()
        result = train_clustering(df, n_clusters=3)
        profiles = characterize_clusters(result)
        for label in profiles["label"]:
            assert isinstance(label, str)
            assert len(label) > 0
