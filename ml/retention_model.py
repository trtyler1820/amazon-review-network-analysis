"""Supervised retention prediction: logistic regression + random forest."""

from __future__ import annotations

from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
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
    y_prob = model.predict_proba(X_test_scaled)[:, 1]

    if model_type == "logistic_regression":
        importances = np.abs(model.coef_[0])
    else:
        importances = model.feature_importances_

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
