"""Unsupervised user clustering with K-means."""

from __future__ import annotations

from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


def find_optimal_k(
    features_df: pd.DataFrame,
    k_range: range = range(2, 9),
    random_state: int = 42,
    max_sample: int = 200_000,
) -> dict:
    """
    Evaluate K-means for each k in k_range using inertia and silhouette score.

    If the dataset exceeds max_sample rows, a random subsample is used for
    the silhouette/elbow search to keep runtime manageable.

    Returns dict with keys: k_range, inertias, silhouette_scores, best_k.
    """
    feature_cols = [c for c in features_df.columns if c != "user_id"]
    X = features_df[feature_cols].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Subsample for speed if needed
    if len(X_scaled) > max_sample:
        rng = np.random.default_rng(random_state)
        idx = rng.choice(len(X_scaled), size=max_sample, replace=False)
        X_search = X_scaled[idx]
    else:
        X_search = X_scaled

    inertias = []
    sil_scores = []

    for k in k_range:
        km = MiniBatchKMeans(
            n_clusters=k, n_init=10, random_state=random_state, batch_size=10_000,
        )
        labels = km.fit_predict(X_search)
        inertias.append(km.inertia_)
        sil_scores.append(silhouette_score(X_search, labels, sample_size=min(10_000, len(X_search))))

    best_k = list(k_range)[int(np.argmax(sil_scores))]

    return {
        "k_range": list(k_range),
        "inertias": inertias,
        "silhouette_scores": sil_scores,
        "best_k": best_k,
    }


def train_clustering(
    features_df: pd.DataFrame,
    n_clusters: int = 4,
    random_state: int = 42,
) -> dict:
    """
    Fit K-means and return results.

    Returns dict with keys: model, scaler, feature_names, labels,
    cluster_centers_original, cluster_profiles.
    """
    feature_cols = [c for c in features_df.columns if c != "user_id"]
    X = features_df[feature_cols].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = MiniBatchKMeans(
        n_clusters=n_clusters, n_init=10, random_state=random_state, batch_size=10_000,
    )
    labels = model.fit_predict(X_scaled)

    # Inverse-transform centers back to original scale for interpretation
    centers_original = scaler.inverse_transform(model.cluster_centers_)

    profiles = pd.DataFrame(centers_original, columns=feature_cols)
    profiles.index.name = "cluster"
    profiles["size"] = pd.Series(labels).value_counts().sort_index().values

    return {
        "model": model,
        "scaler": scaler,
        "feature_names": feature_cols,
        "labels": labels,
        "cluster_centers_original": centers_original,
        "cluster_profiles": profiles,
    }


def characterize_clusters(result: dict) -> pd.DataFrame:
    """
    Assign human-readable labels to clusters based on their profiles.

    Labels are assigned by sorting clusters on key distinguishing features.
    """
    profiles = result["cluster_profiles"].copy()
    labels = []

    for _, row in profiles.iterrows():
        if row["total_review_count"] <= 1.3:
            labels.append("One-and-done")
        elif row["is_multi_category"] > 0.4:
            if row["total_review_count"] > 8:
                labels.append("Power explorer")
            else:
                labels.append("Category explorer")
        elif row["total_review_count"] > 8:
            labels.append("Power reviewer")
        elif row["time_span_days"] > 30:
            labels.append("Loyal returner")
        else:
            labels.append("Casual reviewer")

    profiles["label"] = labels
    return profiles


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_elbow(result: dict, ax: Optional[plt.Axes] = None) -> None:
    """Elbow plot: k vs inertia."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6, 4))
    ax.plot(result["k_range"], result["inertias"], "o-", linewidth=2)
    ax.set_xlabel("k (number of clusters)")
    ax.set_ylabel("Inertia")
    ax.set_title("Elbow Plot")
    ax.grid(alpha=0.3)


def plot_silhouette(result: dict, ax: Optional[plt.Axes] = None) -> None:
    """Silhouette score vs k."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6, 4))
    ax.plot(result["k_range"], result["silhouette_scores"], "o-", linewidth=2, color="#2ecc71")
    ax.set_xlabel("k (number of clusters)")
    ax.set_ylabel("Silhouette Score")
    ax.set_title("Silhouette Analysis")
    ax.grid(alpha=0.3)
    best = result["best_k"]
    best_idx = result["k_range"].index(best)
    ax.axvline(best, color="red", linestyle="--", alpha=0.6, label=f"Best k = {best}")
    ax.legend()


def plot_cluster_sizes(result: dict, ax: Optional[plt.Axes] = None) -> None:
    """Bar chart of cluster sizes."""
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 4))
    profiles = result["cluster_profiles"]
    clusters = range(len(profiles))
    sizes = profiles["size"].values
    ax.bar(clusters, sizes, color="#3498db", edgecolor="white")
    ax.set_xlabel("Cluster")
    ax.set_ylabel("Number of Users")
    ax.set_title("Cluster Sizes")
    ax.set_xticks(list(clusters))
    ax.grid(axis="y", alpha=0.3)
