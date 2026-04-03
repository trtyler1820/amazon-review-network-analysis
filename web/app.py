"""
Amazon Reviews Analysis Dashboard — Phase 3 Streamlit app.

Surfaces retention, expansion pathway, and ML insights derived from the
graph_logic and ml packages. Does not redefine any backend metrics.

Run from project root:
    streamlit run web/app.py
"""

from __future__ import annotations

import os
import sys

# ── path setup ────────────────────────────────────────────────────────────────
# Ensure project root is importable before any graph_logic / ml imports.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

DATA_PATH = os.path.join(_ROOT, "data", "cleaned", "cleaned_reviews.csv")

# ── stdlib / third-party ──────────────────────────────────────────────────────
import math
import warnings

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import plotly.express as px
import streamlit as st

# ── project imports ───────────────────────────────────────────────────────────
from graph_logic.models import Graph, MAX_ENTRY_DATE, OBSERVATION_END
from graph_logic.analysis import (
    identify_high_retention_categories,
    compute_all_expansion_pathways,
    generate_summary_report,
)
from ml.features import build_user_features, build_retention_features_all
from ml.retention_model import (
    train_retention_model,
    plot_roc_curve,
    plot_feature_importance,
)
from ml.clustering import (
    find_optimal_k,
    train_clustering,
    characterize_clusters,
    plot_elbow,
    plot_silhouette,
    plot_cluster_sizes,
)

# ── constants ─────────────────────────────────────────────────────────────────
_CAVEAT = (
    "**Data caveats**: "
    "Retention uses a strict 90-day window. "
    f"Right-censoring cutoff: users whose first review in a category falls after "
    f"**{MAX_ENTRY_DATE.strftime('%B %d, %Y')} UTC** are excluded from both the numerator "
    "and denominator of all retention and expansion calculations. "
    f"Dataset ends **{OBSERVATION_END.strftime('%B %d, %Y')} UTC** (exclusive). "
    "Expansion differences are raw point estimates — no confidence intervals."
)

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Amazon Reviews Dashboard",
    page_icon=None,
    layout="wide",
)


# ── cached loaders ────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def load_graph() -> Graph:
    """Load cleaned CSV and build Graph object. Cached for session lifetime."""
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"Cleaned data file not found at:\n{DATA_PATH}\n"
            "Run `python3 scripts/clean_data.py` from the project root first."
        )
    df = pd.read_csv(DATA_PATH, dtype={"user_id": str, "category_name": str})
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return Graph.from_dataframe(df)


@st.cache_resource(show_spinner=False)
def get_rankings(_graph: Graph) -> tuple[pd.DataFrame, set]:
    """
    Build the category rankings table and high-retention set.

    Underscore prefix on _graph prevents Streamlit from trying to hash the
    Graph object when checking the cache.
    """
    cats = _graph.categories
    high_ret = identify_high_retention_categories(cats)

    rows = []
    for name, cat in cats.items():
        rows.append({
            "Category": name.replace("_", " "),
            "Category Key": name,
            "Retention Rate": cat.retention_rate,
            "Entering Users": cat.entering_user_count,
            "Observable Users": cat.observable_user_count(),
            "Right-Censored": cat.entering_user_count - cat.observable_user_count(),
            "High Retention": name in high_ret,
        })

    df = pd.DataFrame(rows).sort_values("Retention Rate", ascending=False).reset_index(drop=True)
    return df, high_ret


@st.cache_resource(show_spinner=False)
def get_expansion_data(
    _graph: Graph,
    high_ret_frozen: frozenset,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Compute count matrix, expansion-difference matrix, and raw pathway dict.

    high_ret_frozen must be a frozenset (hashable) for Streamlit cache key.
    """
    high_ret = set(high_ret_frozen)
    cats = list(_graph.categories.keys())

    # Transition count matrix (user counts from transition_graph edges)
    count_matrix = pd.DataFrame(0.0, index=cats, columns=cats)
    for src, dst, data in _graph.transition_graph.edges(data=True):
        count_matrix.loc[src, dst] = float(data.get("user_count", 0))
    for c in cats:
        count_matrix.loc[c, c] = float("nan")  # mask diagonal

    # Expansion difference matrix
    pathways = compute_all_expansion_pathways(_graph.users, high_ret)
    diff_matrix = pd.DataFrame(float("nan"), index=cats, columns=cats)
    for (entry, dest), val in pathways.items():
        diff_matrix.loc[entry, dest] = val

    return count_matrix, diff_matrix, pathways


@st.cache_resource(show_spinner=False)
def get_ml_results(_graph: Graph) -> dict:
    """
    Build features and train clustering + retention models.

    Sampling: retention model capped at 50,000 rows to keep runtime
    manageable for a course-project demo.
    """
    user_feat_df = build_user_features(_graph)
    k_result = find_optimal_k(user_feat_df)
    cluster_result = train_clustering(user_feat_df, n_clusters=k_result["best_k"])
    cluster_profiles = characterize_clusters(cluster_result)

    ret_feat_df = build_retention_features_all(_graph)
    if len(ret_feat_df) > 50_000:
        ret_feat_df = ret_feat_df.sample(50_000, random_state=42)
    ret_result = train_retention_model(ret_feat_df, model_type="random_forest")

    return {
        "k_result": k_result,
        "cluster_result": cluster_result,
        "cluster_profiles": cluster_profiles,
        "ret_result": ret_result,
    }


# ── sidebar + data loading ────────────────────────────────────────────────────

st.sidebar.title("Amazon Reviews Dashboard")
st.sidebar.caption("SI 511 + SI 507 Course Project")

page = st.sidebar.radio(
    "Navigate",
    [
        "Category Rankings",
        "Category Filter",
        "Expansion Pathways",
        "Category Detail",
        "ML Insights",
    ],
)

st.sidebar.divider()

with st.sidebar:
    with st.status("Loading data...", expanded=False) as _status:
        try:
            graph = load_graph()
            _status.update(
                label=f"Data loaded ({len(graph.users):,} users)",
                state="complete",
            )
        except FileNotFoundError as exc:
            _status.update(label="Data file not found", state="error")
            st.error(str(exc))
            st.stop()

# Always needed on every page
rankings_df, high_ret = get_rankings(graph)

# ── sidebar caveat panel ──────────────────────────────────────────────────────
with st.sidebar.expander("Metric caveats", expanded=False):
    st.markdown(
        f"- **90-day retention window** (strict, UTC)\n"
        f"- **Right-censoring cutoff**: {MAX_ENTRY_DATE.strftime('%Y-%m-%d')} UTC\n"
        f"  Users entering after this date are excluded from all denominators\n"
        f"- **Observability end**: {OBSERVATION_END.strftime('%Y-%m-%d')} UTC\n"
        f"- **Graph analysis**: descriptive (observed transitions)\n"
        f"- **ML outputs**: predictive; trained on a 50k-row sample"
    )


# =============================================================================
# Page 1 — Category Rankings
# =============================================================================

if page == "Category Rankings":
    st.title("Category Rankings")
    st.info(_CAVEAT)

    sort_by = st.selectbox(
        "Sort by",
        ["Retention Rate", "Entering Users", "Observable Users"],
    )
    display_df = rankings_df.sort_values(
        sort_by, ascending=(sort_by != "Retention Rate")
    ).reset_index(drop=True)

    # Metric cards
    cols = st.columns(len(display_df))
    for i, (_, row) in enumerate(display_df.iterrows()):
        cols[i].metric(
            label=row["Category"],
            value=f"{row['Retention Rate']:.1%}",
            help=(
                f"{row['Entering Users']:,} entering users | "
                f"{row['Observable Users']:,} observable | "
                f"{row['Right-Censored']:,} right-censored"
            ),
        )
        if row["High Retention"]:
            cols[i].caption("High-retention")

    st.divider()

    # Horizontal bar chart
    fig_bar = px.bar(
        display_df,
        x="Retention Rate",
        y="Category",
        orientation="h",
        color="High Retention",
        color_discrete_map={True: "#2ecc71", False: "#3498db"},
        title="Retention Rate by Category",
        text_auto=".1%",
    )
    fig_bar.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_bar, use_container_width=True)

    # Scatter: volume vs retention
    fig_scatter = px.scatter(
        display_df,
        x="Entering Users",
        y="Retention Rate",
        size="Observable Users",
        color="Category",
        title="Volume vs Retention Rate",
        hover_data=["Observable Users", "Right-Censored"],
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.subheader("Raw Data")
    st.dataframe(
        display_df.drop(columns=["Category Key"]),
        use_container_width=True,
    )
    st.caption(
        "Observable Users = entering users whose first review was on or before "
        f"{MAX_ENTRY_DATE.strftime('%Y-%m-%d')} UTC. "
        "Right-Censored = entering users excluded from retention denominator."
    )


# =============================================================================
# Page 2 — Category Filter
# =============================================================================

elif page == "Category Filter":
    st.title("Category Filter")
    st.info(_CAVEAT)

    max_entering = int(rankings_df["Entering Users"].max())

    min_retention = st.sidebar.slider(
        "Min Retention Rate",
        min_value=0.0,
        max_value=1.0,
        value=0.0,
        step=0.01,
        format="%.0f%%",
    )
    min_users = st.sidebar.slider(
        "Min Entering Users",
        min_value=0,
        max_value=max_entering,
        value=0,
        step=max(1, max_entering // 100),
    )
    show_high_only = st.sidebar.checkbox("High-Retention categories only")

    filtered = rankings_df[
        (rankings_df["Retention Rate"] >= min_retention)
        & (rankings_df["Entering Users"] >= min_users)
    ]
    if show_high_only:
        filtered = filtered[filtered["High Retention"]]

    st.info(f"{len(filtered)} of {len(rankings_df)} categories match filters")

    if len(filtered) == 0:
        st.warning("No categories match the current filters — try widening your criteria.")
    else:
        fig = px.bar(
            filtered,
            x="Retention Rate",
            y="Category",
            orientation="h",
            color="High Retention",
            color_discrete_map={True: "#2ecc71", False: "#3498db"},
            title="Filtered Categories — Retention Rate",
            text_auto=".1%",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Raw Data"):
            st.dataframe(filtered.drop(columns=["Category Key"]), use_container_width=True)


# =============================================================================
# Page 3 — Expansion Pathways
# =============================================================================

elif page == "Expansion Pathways":
    st.title("Expansion Pathways")
    st.info(_CAVEAT)
    st.caption(
        "Expansion Difference = P(B within 90d | first category = A) "
        "minus P(B within 90d | first category != A). "
        "Destination B is always a high-retention category. "
        "Values are raw point estimates with no confidence intervals."
    )

    with st.spinner("Computing expansion pathways (first load only)..."):
        count_matrix, diff_matrix, pathways = get_expansion_data(
            graph, frozenset(high_ret)
        )

    view = st.radio(
        "View",
        ["Transition Heatmap", "Expansion Difference", "Network Graph"],
        horizontal=True,
    )

    label_map = {c: c.replace("_", " ") for c in count_matrix.index}

    if view == "Transition Heatmap":
        display_cm = count_matrix.rename(index=label_map, columns=label_map)
        fig = px.imshow(
            display_cm,
            text_auto=True,
            color_continuous_scale="Blues",
            labels={"color": "Users"},
            title="Category Transition Counts (distinct users per transition)",
        )
        fig.update_xaxes(title="Destination Category")
        fig.update_yaxes(title="Origin Category")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Diagonal is masked — self-transitions are undefined. "
            "Cell value = distinct users observed transitioning from row to column category."
        )

    elif view == "Expansion Difference":
        display_dm = diff_matrix.rename(index=label_map, columns=label_map)
        fig = px.imshow(
            display_dm,
            text_auto=".2%",
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            title="Expansion Difference: P(B | first=A) - P(B | first!=A)",
        )
        fig.update_xaxes(title="Destination (B, must be high-retention)")
        fig.update_yaxes(title="Entry Category (A)")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Green = above-baseline expansion. Red = below-baseline. "
            "Gray cells = not applicable (diagonal, or B is not high-retention, "
            "or cohort too small)."
        )

        # Ranked table
        pathway_rows = [
            {
                "Entry": e.replace("_", " "),
                "Destination": d.replace("_", " "),
                "Expansion Diff": f"{v:+.2%}",
                "Direction": "Positive" if v > 0 else "Negative",
            }
            for (e, d), v in sorted(pathways.items(), key=lambda kv: kv[1], reverse=True)
        ]
        if pathway_rows:
            st.subheader("All Pathways — Ranked")
            st.dataframe(pd.DataFrame(pathway_rows), use_container_width=True)
        else:
            st.warning(
                "No expansion pathways computed. "
                "This happens when no category qualifies as high-retention "
                "(needs >= 30 observable users and top-quartile retention)."
            )

    else:  # Network Graph
        if count_matrix.shape[0] == 0:
            st.warning("No transition data available to render.")
        else:
            fig_net, ax = plt.subplots(figsize=(8, 6))
            pos = nx.spring_layout(graph.transition_graph, seed=42)
            edge_weights = [
                d["user_count"]
                for _, _, d in graph.transition_graph.edges(data=True)
            ]
            max_w = max(edge_weights) if edge_weights else 1
            norm_widths = [4 * w / max_w for w in edge_weights]
            node_colors = [
                "#2ecc71" if n in high_ret else "#3498db"
                for n in graph.transition_graph.nodes()
            ]
            nx.draw_networkx(
                graph.transition_graph,
                pos=pos,
                ax=ax,
                node_color=node_colors,
                node_size=2500,
                width=norm_widths,
                edge_color="#888",
                arrows=True,
                arrowsize=20,
                labels={n: n.replace("_", "\n") for n in graph.transition_graph.nodes()},
                font_size=8,
            )
            ax.set_title(
                "Category Transition Network\n"
                "(green = high-retention, edge width proportional to user count)"
            )
            ax.axis("off")
            st.pyplot(fig_net)
            plt.close(fig_net)
            st.caption(
                "Edges represent distinct users observed transitioning between categories "
                "within the dataset window. Arrow direction = earlier -> later category."
            )


# =============================================================================
# Page 4 — Category Detail
# =============================================================================

elif page == "Category Detail":
    st.title("Category Detail")

    with st.spinner("Loading expansion data..."):
        count_matrix, diff_matrix, pathways = get_expansion_data(
            graph, frozenset(high_ret)
        )

    selected = st.selectbox(
        "Select a category",
        options=list(graph.categories.keys()),
        format_func=lambda x: x.replace("_", " "),
    )

    cat = graph.categories[selected]
    censored = cat.entering_user_count - cat.observable_user_count()

    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Retention Rate", f"{cat.retention_rate:.1%}")
    col2.metric(
        "Observable Users",
        f"{cat.observable_user_count():,}",
        help="Users whose first review was on or before the right-censoring cutoff.",
    )
    col3.metric("Entering Users", f"{cat.entering_user_count:,}")
    col4.metric(
        "Right-Censored",
        f"{censored:,}",
        help=(
            f"Users whose first review in this category fell after "
            f"{MAX_ENTRY_DATE.strftime('%Y-%m-%d')} UTC. "
            "Excluded from the retention denominator to avoid right-censoring bias."
        ),
    )

    if selected in high_ret:
        st.success(
            f"{selected.replace('_', ' ')} is a High-Retention category "
            "(top quartile, >= 30 observable users)."
        )
    else:
        st.info(
            f"{selected.replace('_', ' ')} is NOT in the top-quartile retention set. "
            "It will not appear as a destination in expansion pathway analysis."
        )

    st.info(_CAVEAT)
    st.divider()

    # Transitions out / in
    col_out, col_in = st.columns(2)

    with col_out:
        st.subheader("Users Who Later Reviewed")
        out_edges = []
        for dst in graph.transition_graph.successors(selected):
            uc = graph.transition_graph[selected][dst].get("user_count", 0)
            out_edges.append({"Destination": dst.replace("_", " "), "Users": uc})
        if out_edges:
            out_df = pd.DataFrame(out_edges).sort_values("Users", ascending=False)
            st.dataframe(out_df, use_container_width=True)
        else:
            st.caption("No outgoing transitions recorded for this category.")

    with col_in:
        st.subheader("Users Who Came From")
        in_edges = []
        for src in graph.transition_graph.predecessors(selected):
            uc = graph.transition_graph[src][selected].get("user_count", 0)
            in_edges.append({"Source": src.replace("_", " "), "Users": uc})
        if in_edges:
            in_df = pd.DataFrame(in_edges).sort_values("Users", ascending=False)
            st.dataframe(in_df, use_container_width=True)
        else:
            st.caption("No incoming transitions recorded for this category.")

    # Expansion pathways INTO this category (only meaningful if it is high-retention)
    if selected in high_ret:
        st.divider()
        st.subheader(f"Expansion Pathways INTO {selected.replace('_', ' ')}")
        st.caption(
            "Expansion Difference measures how much more likely users entering via each "
            "source category are to review this (high-retention) category within 90 days, "
            "compared to the baseline of all other users."
        )
        into_rows = []
        for e in diff_matrix.index:
            if e == selected:
                continue
            val = diff_matrix.loc[e, selected]
            if not (isinstance(val, float) and math.isnan(val)):
                into_rows.append({
                    "Entry Category": e.replace("_", " "),
                    "Expansion Diff": f"{val:+.2%}",
                    "Value": val,
                    "Direction": "Positive" if val > 0 else "Negative",
                })
        if into_rows:
            into_df = pd.DataFrame(into_rows).sort_values("Value", ascending=False)
            st.dataframe(into_df.drop(columns=["Value"]), use_container_width=True)
        else:
            st.caption("No expansion pathway data available for this category.")
    else:
        st.divider()
        st.caption(
            f"{selected.replace('_', ' ')} is not a high-retention category, so it does "
            "not appear as a destination (B) in expansion pathway analysis. "
            "Expansion pathways are only computed toward high-retention destinations."
        )


# =============================================================================
# Page 5 — ML Insights
# =============================================================================

elif page == "ML Insights":
    st.title("ML Insights (Advanced)")

    st.info(
        "These are **predictive** outputs from the ML layer, distinct from the "
        "descriptive graph analysis on the other pages. "
        "Clustering uses K-means on user features. "
        "Retention prediction uses a Random Forest classifier trained on features "
        "derived at the time of each user's first review in a category "
        "(no look-ahead into the 90-day window)."
    )
    st.warning(
        "ML training is compute-intensive. The retention model is trained on a "
        "50,000-user sample. Results are cached after the first run."
    )

    # Use session state to control when computation runs
    if "ml_done" not in st.session_state:
        st.session_state.ml_done = False

    if st.button("Run ML Analysis", type="primary", disabled=st.session_state.ml_done):
        with st.spinner("Building features and training models... (1-3 minutes on full dataset)"):
            try:
                get_ml_results(graph)   # populates cache
                st.session_state.ml_done = True
                st.rerun()
            except Exception as exc:
                st.error(f"ML training failed: {exc}")

    if st.session_state.ml_done:
        try:
            ml = get_ml_results(graph)  # instant cache hit
        except Exception as exc:
            st.error(f"Could not load ML results: {exc}")
            st.stop()

        tab_clust, tab_ret = st.tabs(["User Clusters", "Retention Prediction"])

        # ── clustering tab ──────────────────────────────────────────────────
        with tab_clust:
            st.caption(
                "K-means clustering on user-level features (review count, category breadth, "
                "rating patterns, etc.). Best k is chosen by highest silhouette score."
            )
            col1, col2 = st.columns(2)
            with col1:
                fig, ax = plt.subplots()
                plot_elbow(ml["k_result"], ax=ax)
                st.pyplot(fig)
                plt.close(fig)
            with col2:
                fig, ax = plt.subplots()
                plot_silhouette(ml["k_result"], ax=ax)
                st.pyplot(fig)
                plt.close(fig)

            best_k = ml["k_result"]["best_k"]
            st.subheader(f"Cluster Profiles (k = {best_k})")
            st.caption(
                "Cluster centers are shown in original (unscaled) feature space "
                "for interpretability. 'size' = number of users assigned to each cluster."
            )
            st.dataframe(ml["cluster_profiles"], use_container_width=True)

            fig, ax = plt.subplots()
            plot_cluster_sizes(ml["cluster_result"], ax=ax)
            st.pyplot(fig)
            plt.close(fig)

        # ── retention prediction tab ────────────────────────────────────────
        with tab_ret:
            st.caption(
                "Random Forest classifier trained to predict whether a user will be "
                "retained in a category (2+ reviews on 2+ distinct days within 90 days). "
                "Features are engineered at the user's first-review date — "
                "no data from inside the 90-day window is used as a feature. "
                "A group-aware train/test split prevents the same user from appearing "
                "in both sets."
            )

            roc_auc = ml["ret_result"]["roc_auc"]
            if roc_auc is not None and not (isinstance(roc_auc, float) and math.isnan(roc_auc)):
                st.metric("ROC AUC", f"{roc_auc:.3f}")
            else:
                st.warning(
                    "ROC AUC unavailable — the test split contained only one class. "
                    "This can happen with very imbalanced data or a small sample."
                )

            col1, col2 = st.columns(2)
            with col1:
                try:
                    fig, ax = plt.subplots()
                    plot_roc_curve(ml["ret_result"], ax=ax)
                    st.pyplot(fig)
                    plt.close(fig)
                except Exception as exc:
                    st.warning(f"ROC curve unavailable: {exc}")
            with col2:
                fig, ax = plt.subplots()
                plot_feature_importance(ml["ret_result"], ax=ax, top_n=10)
                st.pyplot(fig)
                plt.close(fig)

            with st.expander("Classification Report"):
                st.text(ml["ret_result"]["classification_report"])

    else:
        st.caption("Click 'Run ML Analysis' above to start.")
