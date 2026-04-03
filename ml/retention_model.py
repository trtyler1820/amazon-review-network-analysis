"""Supervised retention prediction: logistic regression + random forest."""

from __future__ import annotations

from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score, roc_curve
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.preprocessing import StandardScaler


# Columns that are not features
_NON_FEATURE_COLS = {"user_id", "retained"}


def train_retention_model(
    features_df: pd.DataFrame,
    model_type: str = "random_forest",
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """
    Train a retention classifier and return results.

    Parameters
    ----------
    features_df : DataFrame from build_retention_features / build_retention_features_all.
    model_type : 'random_forest' or 'logistic_regression'.
    test_size : fraction of data held out for testing.
    random_state : seed for reproducibility.

    Returns
    -------
    dict with keys: model, scaler, feature_names, X_train, X_test,
    y_train, y_test, y_pred, y_prob, classification_report, roc_auc,
    feature_importances.
    """
    feature_cols = [c for c in features_df.columns if c not in _NON_FEATURE_COLS]
    X = features_df[feature_cols].values
    y = features_df["retained"].astype(int).values
    feature_names = feature_cols

    # Guard: need both classes with enough examples to split
    unique_classes = np.unique(y)
    if len(unique_classes) < 2:
        raise ValueError(
            f"Cannot train: only one class present (label={unique_classes[0]}). "
            "Need both retained and non-retained users."
        )
    minority_count = min(np.sum(y == c) for c in unique_classes)
    min_test = max(1, int(np.ceil(len(y) * test_size)))
    if minority_count < 2 or len(y) < max(4, int(np.ceil(1 / test_size)) + 1):
        raise ValueError(
            f"Cannot train: too few examples (n={len(y)}, minority={minority_count}). "
            "Need enough data for a meaningful train/test split."
        )

    # Use group-aware split when user_id is present to prevent the same
    # user from appearing in both train and test (leakage).
    if "user_id" in features_df.columns:
        groups = features_df["user_id"].values
        gss = GroupShuffleSplit(
            n_splits=1, test_size=test_size, random_state=random_state,
        )
        train_idx, test_idx = next(gss.split(X, y, groups))
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, stratify=y, random_state=random_state,
        )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    if model_type == "logistic_regression":
        model = LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=random_state,
        )
    else:
        model = RandomForestClassifier(
            n_estimators=100,
            class_weight="balanced",
            random_state=random_state,
            n_jobs=-1,
        )

    model.fit(X_train_scaled, y_train)
    y_pred = model.predict(X_test_scaled)

    if model_type == "logistic_regression":
        importances = np.abs(model.coef_[0])
    else:
        importances = model.feature_importances_

    # Handle case where test set ends up single-class after split
    y_prob = model.predict_proba(X_test_scaled)[:, 1]
    if len(np.unique(y_test)) < 2:
        auc = float("nan")
    else:
        auc = roc_auc_score(y_test, y_prob)

    return {
        "model": model,
        "scaler": scaler,
        "feature_names": feature_names,
        "X_train": X_train_scaled,
        "X_test": X_test_scaled,
        "y_train": y_train,
        "y_test": y_test,
        "y_pred": y_pred,
        "y_prob": y_prob,
        "classification_report": classification_report(y_test, y_pred),
        "roc_auc": auc,
        "feature_importances": importances,
    }


def get_feature_importance(result: dict) -> pd.DataFrame:
    """Return a DataFrame of feature importances sorted descending."""
    return (
        pd.DataFrame({
            "feature": result["feature_names"],
            "importance": result["feature_importances"],
        })
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


def plot_roc_curve(result: dict, ax: Optional[plt.Axes] = None) -> None:
    """Plot ROC curve with AUC score."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6, 5))

    fpr, tpr, _ = roc_curve(result["y_test"], result["y_prob"])
    ax.plot(fpr, tpr, linewidth=2, label=f'AUC = {result["roc_auc"]:.3f}')
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)


def plot_feature_importance(
    result: dict,
    ax: Optional[plt.Axes] = None,
    top_n: int = 10,
) -> None:
    """Horizontal bar chart of top-N feature importances."""
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 5))

    imp_df = get_feature_importance(result).head(top_n).iloc[::-1]
    ax.barh(imp_df["feature"], imp_df["importance"], color="#3498db", edgecolor="white")
    ax.set_xlabel("Importance")
    ax.set_title(f"Top {top_n} Feature Importances")
    ax.grid(axis="x", alpha=0.3)
