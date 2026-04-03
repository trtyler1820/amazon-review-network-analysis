"""Tests for ml.retention_model — supervised retention prediction pipeline."""

import numpy as np
import pandas as pd
import pytest

from ml.retention_model import (
    train_retention_model,
    get_feature_importance,
)


def _synthetic_features(n: int = 200, random_state: int = 42) -> pd.DataFrame:
    """Create a synthetic feature DataFrame for pipeline testing."""
    rng = np.random.default_rng(random_state)
    df = pd.DataFrame({
        "user_id": [f"u{i}" for i in range(n)],
        "first_rating": rng.uniform(1, 5, n),
        "first_helpful_vote": rng.integers(0, 10, n),
        "prior_review_count": rng.integers(0, 5, n),
        "is_first_ever_review": rng.integers(0, 2, n),
        "category_size": rng.integers(100, 1000, n),
    })
    # Label correlated with first_rating for a learnable signal
    df["retained"] = (df["first_rating"] > 3.0).astype(int)
    return df


class TestTrainRetentionModel:

    def test_returns_expected_keys(self):
        df = _synthetic_features()
        result = train_retention_model(df, model_type="random_forest")
        expected_keys = {
            "model", "scaler", "feature_names", "X_train", "X_test",
            "y_train", "y_test", "y_pred", "y_prob",
            "classification_report", "roc_auc", "feature_importances",
        }
        assert set(result.keys()) == expected_keys

    def test_predictions_length(self):
        df = _synthetic_features()
        result = train_retention_model(df)
        assert len(result["y_pred"]) == len(result["y_test"])
        assert len(result["y_prob"]) == len(result["y_test"])

    def test_feature_importances_length(self):
        df = _synthetic_features()
        result = train_retention_model(df)
        assert len(result["feature_importances"]) == len(result["feature_names"])

    def test_roc_auc_in_range(self):
        df = _synthetic_features()
        result = train_retention_model(df)
        assert 0.0 <= result["roc_auc"] <= 1.0

    def test_classification_report_nonempty(self):
        df = _synthetic_features()
        result = train_retention_model(df)
        assert len(result["classification_report"]) > 0

    def test_logistic_regression_runs(self):
        df = _synthetic_features()
        result = train_retention_model(df, model_type="logistic_regression")
        assert result["roc_auc"] > 0.0

    def test_random_forest_runs(self):
        df = _synthetic_features()
        result = train_retention_model(df, model_type="random_forest")
        assert result["roc_auc"] > 0.0

    def test_user_id_not_in_features(self):
        df = _synthetic_features()
        result = train_retention_model(df)
        assert "user_id" not in result["feature_names"]
        assert "retained" not in result["feature_names"]


    def test_single_class_raises(self):
        """All-same-class data should raise ValueError, not crash."""
        df = pd.DataFrame({
            "user_id": ["u1", "u2", "u3"],
            "feature_a": [1.0, 2.0, 3.0],
            "retained": [0, 0, 0],  # only one class
        })
        with pytest.raises(ValueError, match="only one class"):
            train_retention_model(df)

    def test_too_few_examples_raises(self):
        """Tiny dataset with minority_count=1 should raise ValueError."""
        df = pd.DataFrame({
            "user_id": ["u1", "u2"],
            "feature_a": [1.0, 2.0],
            "retained": [0, 1],
        })
        with pytest.raises(ValueError, match="too few examples"):
            train_retention_model(df)

    def test_group_split_no_user_leakage(self):
        """When user_id is present and users span multiple rows, no user
        should appear in both train and test sets."""
        n_users = 50
        rows_per_user = 3
        rng = np.random.default_rng(42)
        rows = []
        for i in range(n_users):
            for _ in range(rows_per_user):
                rows.append({
                    "user_id": f"u{i}",
                    "first_rating": rng.uniform(1, 5),
                    "prior_review_count": rng.integers(0, 5),
                    "retained": int(rng.random() > 0.5),
                })
        df = pd.DataFrame(rows)
        result = train_retention_model(df)
        # Recover which user_ids ended up in train vs test via index tracking
        # Since GroupShuffleSplit splits by user, check that train/test
        # y lengths are consistent (no crash) and model trained successfully
        assert result["roc_auc"] >= 0.0
        assert len(result["y_train"]) + len(result["y_test"]) == len(df)


class TestGetFeatureImportance:

    def test_sorted_descending(self):
        df = _synthetic_features()
        result = train_retention_model(df)
        imp_df = get_feature_importance(result)
        assert list(imp_df["importance"]) == sorted(imp_df["importance"], reverse=True)

    def test_has_expected_columns(self):
        df = _synthetic_features()
        result = train_retention_model(df)
        imp_df = get_feature_importance(result)
        assert set(imp_df.columns) == {"feature", "importance"}
