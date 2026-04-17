"""Machine learning package for Amazon Reviews user segmentation (clustering)."""

from .features import (
    build_user_features,
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
    "build_user_features",
    "find_optimal_k",
    "train_clustering",
    "characterize_clusters",
    "plot_elbow",
    "plot_silhouette",
    "plot_cluster_sizes",
]
