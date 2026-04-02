"""Machine learning package for Amazon Reviews retention prediction and user clustering."""

from .features import (
    build_retention_features,
    build_retention_features_all,
    build_user_features,
)
from .retention_model import (
    train_retention_model,
    get_feature_importance,
    plot_roc_curve,
    plot_feature_importance,
)
from .clustering import (
    find_optimal_k,
    train_clustering,
    characterize_clusters,
    plot_elbow,
    plot_silhouette,
    plot_cluster_sizes,
)

__all__ = [
    "build_retention_features",
    "build_retention_features_all",
    "build_user_features",
    "train_retention_model",
    "get_feature_importance",
    "plot_roc_curve",
    "plot_feature_importance",
    "find_optimal_k",
    "train_clustering",
    "characterize_clusters",
    "plot_elbow",
    "plot_silhouette",
    "plot_cluster_sizes",
]
