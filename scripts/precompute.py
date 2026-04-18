#!/usr/bin/env python3
"""
Pre-compute and serialize expensive dashboard artifacts.

Turns a cold ``streamlit run web/app.py`` startup from ~90–180 seconds into
~2–5 seconds. Run this ONCE after any data change or any edit to the
``graph_logic/`` or ``ml/`` modules:

    python3 scripts/precompute.py

Writes three pickle files to ``data/precomputed/``:

  graph.pkl     — Graph object (interaction_graph stripped; retention cache populated)
  expansion.pkl — dict: {high_ret: set, count_matrix: DataFrame, diff_matrix: DataFrame}
  ml.pkl        — dict: {user_feat_df, k_result, cluster_result, cluster_profiles}

The Streamlit app auto-detects these files and loads them. If any file is
missing, the corresponding loader falls back to live computation (preserves
existing behavior exactly). So the pickles are purely a speed optimization —
never a correctness dependency.

Size notes (approximate, 2.5M-row dataset):
  graph.pkl     ~250–500 MB
  expansion.pkl ~ a few KB
  ml.pkl        ~30–80 MB
"""

from __future__ import annotations

import os
import pickle
import sys
import time
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

import networkx as nx
import pandas as pd

from graph_logic.analysis import (
    compute_all_expansion_pathways,
    identify_high_retention_categories,
)
from graph_logic.models import Graph
from ml.clustering import characterize_clusters, find_optimal_k, train_clustering
from ml.features import build_user_features

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_PATH = Path(_PROJECT_ROOT) / "data" / "cleaned" / "cleaned_reviews.csv"
OUT_DIR = Path(_PROJECT_ROOT) / "data" / "precomputed"
GRAPH_PKL = OUT_DIR / "graph.pkl"
EXPANSION_PKL = OUT_DIR / "expansion.pkl"
ML_PKL = OUT_DIR / "ml.pkl"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _banner(msg: str) -> None:
    bar = "─" * 72
    print(f"\n{bar}\n{msg}\n{bar}")


def _size_mb(path: Path) -> str:
    n = path.stat().st_size
    return f"{n / (1024 * 1024):.1f} MB" if n >= 1024 * 1024 else f"{n / 1024:.1f} KB"


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


def _build_graph() -> Graph:
    _banner("Step 1 / 3 — Building Graph from CSV")
    t0 = time.perf_counter()
    print(f"Reading {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH, dtype={"user_id": str, "category_name": str})
    df["date"] = pd.to_datetime(df["date"], format="ISO8601", utc=True)
    print(f"  {len(df):,} rows loaded in {time.perf_counter() - t0:.1f}s.")

    t1 = time.perf_counter()
    graph = Graph.from_dataframe(df)
    print(
        f"  Graph built in {time.perf_counter() - t1:.1f}s: "
        f"{len(graph.users):,} users, "
        f"{len(graph.categories)} categories, "
        f"{graph.transition_graph.number_of_edges()} transition edges, "
        f"{graph.interaction_graph.number_of_edges():,} interaction edges."
    )
    return graph


def _prime_caches(graph: Graph) -> None:
    """
    Populate lazy caches on Category objects so that the unpickled Graph
    serves metric reads at O(1) instead of O(users).
    """
    t0 = time.perf_counter()
    for cat in graph.categories.values():
        _ = cat.retention_rate  # populates Category._retention_rate_cache
    print(f"  Retention caches primed in {time.perf_counter() - t0:.1f}s.")


def _strip_interaction_layer(graph: Graph) -> None:
    """
    Replace the large user-product interaction graph with an empty stub.
    The UI does not read from it (only tests do), so keeping it in the
    pickle would roughly double the file size for no runtime benefit.
    """
    removed_edges = graph.interaction_graph.number_of_edges()
    removed_nodes = graph.interaction_graph.number_of_nodes()
    graph.interaction_graph = nx.MultiDiGraph()
    print(
        f"  Interaction layer stripped: "
        f"{removed_nodes:,} nodes / {removed_edges:,} edges removed for pickle."
    )


def _save_graph(graph: Graph) -> None:
    t0 = time.perf_counter()
    with open(GRAPH_PKL, "wb") as f:
        pickle.dump(graph, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"  Wrote {GRAPH_PKL} ({_size_mb(GRAPH_PKL)}) in {time.perf_counter() - t0:.1f}s.")


def _compute_expansion(graph: Graph) -> dict:
    _banner("Step 2 / 3 — Computing expansion pathways")
    t0 = time.perf_counter()

    high_ret = identify_high_retention_categories(graph.categories)
    cats = list(graph.categories.keys())

    count_matrix = pd.DataFrame(0, index=cats, columns=cats, dtype=float)
    for src, dst, data in graph.transition_graph.edges(data=True):
        count_matrix.loc[src, dst] = data.get("user_count", 0)
    for c in cats:
        count_matrix.loc[c, c] = float("nan")

    pathways = compute_all_expansion_pathways(graph.users, high_ret)
    diff_matrix = pd.DataFrame(float("nan"), index=cats, columns=cats)
    for (entry, dest), val in pathways.items():
        diff_matrix.loc[entry, dest] = val

    payload = {
        "high_ret": high_ret,
        "count_matrix": count_matrix,
        "diff_matrix": diff_matrix,
    }
    print(
        f"  high-retention categories: "
        f"{sorted(high_ret) if high_ret else '(none)'}"
    )
    print(f"  Computed in {time.perf_counter() - t0:.1f}s.")
    return payload


def _save_expansion(payload: dict) -> None:
    t0 = time.perf_counter()
    with open(EXPANSION_PKL, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(
        f"  Wrote {EXPANSION_PKL} ({_size_mb(EXPANSION_PKL)}) "
        f"in {time.perf_counter() - t0:.1f}s."
    )


def _compute_ml(graph: Graph) -> dict:
    _banner("Step 3 / 3 — Running ML (user clustering)")
    t0 = time.perf_counter()

    user_feat_df = build_user_features(graph)
    print(
        f"  Features built: {len(user_feat_df):,} users × "
        f"{len(user_feat_df.columns)} columns "
        f"({time.perf_counter() - t0:.1f}s)."
    )

    t1 = time.perf_counter()
    k_result = find_optimal_k(user_feat_df)
    print(
        f"  k-search complete: best_k = {k_result['best_k']} "
        f"(evaluated k={list(k_result['k_range'])}, "
        f"{time.perf_counter() - t1:.1f}s)."
    )

    t1 = time.perf_counter()
    cluster_result = train_clustering(user_feat_df, n_clusters=k_result["best_k"])
    cluster_profiles = characterize_clusters(cluster_result)
    print(f"  Clustering fit + profiles in {time.perf_counter() - t1:.1f}s.")

    user_feat_df = user_feat_df.copy()
    user_feat_df["cluster_label"] = cluster_result["labels"]
    label_map = dict(zip(cluster_profiles.index, cluster_profiles["label"]))
    user_feat_df["cluster_name"] = user_feat_df["cluster_label"].map(label_map)

    return {
        "user_feat_df": user_feat_df,
        "k_result": k_result,
        "cluster_result": cluster_result,
        "cluster_profiles": cluster_profiles,
    }


def _save_ml(payload: dict) -> None:
    t0 = time.perf_counter()
    with open(ML_PKL, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"  Wrote {ML_PKL} ({_size_mb(ML_PKL)}) in {time.perf_counter() - t0:.1f}s.")


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t_total = time.perf_counter()

    if not DATA_PATH.is_file():
        raise SystemExit(
            f"ERROR: {DATA_PATH} not found. Run `python3 scripts/clean_data.py` first."
        )

    graph = _build_graph()

    # Expansion + ML must run BEFORE we strip the interaction graph, because
    # compute_all_expansion_pathways and build_user_features iterate user
    # review data — which lives on `graph.users`, not on interaction_graph —
    # but priming order keeps the invariant obvious if this is edited later.
    expansion = _compute_expansion(graph)
    ml = _compute_ml(graph)

    # Now that derived artifacts are captured, shrink the Graph for pickling.
    _prime_caches(graph)
    _strip_interaction_layer(graph)

    _save_graph(graph)
    _save_expansion(expansion)
    _save_ml(ml)

    _banner(f"Done. All artifacts written to {OUT_DIR}/.")
    print(f"Total wall time: {time.perf_counter() - t_total:.1f}s.")
    print(
        "Restart Streamlit to pick up the precomputed artifacts "
        "(clear cached data first if it's already running)."
    )


if __name__ == "__main__":
    main()
