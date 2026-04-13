"""
Amazon Reviews Analysis — Streamlit Dashboard (Phase 3)

Six pages:
  1. Category Rankings   — retention rates, bar chart, scatter
  2. Category Filter     — slider/checkbox filtering
  3. Review Search       — RAG semantic search + LLM synthesis (Qdrant + OpenAI)
  4. Expansion Pathways  — heatmaps + network graph
  5. Category Detail     — per-category drill-down
  6. ML Insights         — user clustering + retention prediction (button-triggered)

Caveats surfaced throughout:
  - 90-day retention window
  - Right-censoring: users entering after 2023-04-02 excluded from denominators
  - Observability cutoff: data ends 2023-07-01 UTC
  - Expansion differences are raw point estimates (no confidence intervals)
"""

from __future__ import annotations

import os
import sys
import time

# ---------------------------------------------------------------------------
# Path setup — must come before any graph_logic / ml imports
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

DATA_PATH = os.path.join(_PROJECT_ROOT, "data", "cleaned", "cleaned_reviews.csv")

import matplotlib
matplotlib.use("Agg")  # non-interactive backend; must precede pyplot import
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from graph_logic.analysis import (
    compute_all_expansion_pathways,
    identify_high_retention_categories,
)
from graph_logic.models import Graph, MAX_ENTRY_DATE, OBSERVATION_END

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Amazon Reviews Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def load_graph() -> tuple[Graph, float]:
    """Load CSV and build Graph. Returns (graph, load_time_seconds)."""
    t0 = time.perf_counter()
    df = pd.read_csv(DATA_PATH, dtype={"user_id": str, "category_name": str})
    df["date"] = pd.to_datetime(df["date"], format="ISO8601", utc=True)
    graph = Graph.from_dataframe(df)
    elapsed = time.perf_counter() - t0
    return graph, elapsed


@st.cache_resource(show_spinner=False)
def get_expansion_data(_graph: Graph) -> tuple[pd.DataFrame, pd.DataFrame, set]:
    """
    Compute transition count matrix, expansion difference matrix, and
    high-retention category set. All heavy operations cached here.
    """
    high_ret = identify_high_retention_categories(_graph.categories)
    cats = list(_graph.categories.keys())

    # --- Transition count matrix (from Layer 2 edges) ---
    count_matrix = pd.DataFrame(0, index=cats, columns=cats, dtype=float)
    for src, dst, data in _graph.transition_graph.edges(data=True):
        count_matrix.loc[src, dst] = data.get("user_count", 0)
    # Mask diagonal — self-transitions are meaningless
    for c in cats:
        count_matrix.loc[c, c] = float("nan")

    # --- Expansion difference matrix ---
    pathways = compute_all_expansion_pathways(_graph.users, high_ret)
    diff_matrix = pd.DataFrame(float("nan"), index=cats, columns=cats)
    for (entry, dest), val in pathways.items():
        diff_matrix.loc[entry, dest] = val

    return count_matrix, diff_matrix, high_ret


@st.cache_resource(show_spinner=False)
def get_ml_results(_graph: Graph) -> dict:
    """
    Run ML pipeline: user clustering + retention prediction.
    Only called when user clicks the trigger button.
    """
    from ml.clustering import (
        characterize_clusters,
        find_optimal_k,
        plot_elbow,
        plot_silhouette,
        train_clustering,
    )
    from ml.features import build_retention_features_all, build_user_features
    from ml.retention_model import train_retention_model

    # -- User clustering --
    user_feat_df = build_user_features(_graph)
    k_result = find_optimal_k(user_feat_df)
    cluster_result = train_clustering(user_feat_df, n_clusters=k_result["best_k"])
    cluster_profiles = characterize_clusters(cluster_result)

    # Attach per-user cluster labels for drill-down
    user_feat_df = user_feat_df.copy()
    user_feat_df["cluster_label"] = cluster_result["labels"]
    label_map = dict(zip(cluster_profiles.index, cluster_profiles["label"]))
    user_feat_df["cluster_name"] = user_feat_df["cluster_label"].map(label_map)

    # -- Retention model --
    ret_feat_df = build_retention_features_all(_graph)
    if len(ret_feat_df) > 50_000:
        ret_feat_df = ret_feat_df.sample(50_000, random_state=42)
    ret_result = train_retention_model(ret_feat_df, model_type="random_forest")

    return {
        "user_feat_df": user_feat_df,
        "k_result": k_result,
        "cluster_result": cluster_result,
        "cluster_profiles": cluster_profiles,
        "ret_result": ret_result,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(name: str) -> str:
    """Format category name for display."""
    return name.replace("_", " ")


def _build_rankings_df(graph: Graph, high_ret: set) -> pd.DataFrame:
    rows = [
        {
            "Category": _fmt(name),
            "Category Key": name,
            "Retention Rate": cat.retention_rate,
            "Entering Users": cat.entering_user_count,
            "Observable Users": cat.observable_user_count(),
            "High Retention": name in high_ret,
        }
        for name, cat in graph.categories.items()
    ]
    return pd.DataFrame(rows).sort_values("Retention Rate", ascending=False)


# ---------------------------------------------------------------------------
# Sidebar + load
# ---------------------------------------------------------------------------

st.sidebar.title("Amazon Reviews Dashboard")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    [
        "Category Rankings",
        "Category Filter",
        "Review Search",
        "Expansion Pathways",
        "Category Detail",
        "ML Insights",
    ],
)

# Load graph (shows status block on first run)
if "graph_loaded" not in st.session_state:
    with st.status("Loading data... (first load takes 60-120 seconds)", expanded=True) as status:
        st.write("Reading cleaned_reviews.csv (2.5M rows)...")
        graph, load_time = load_graph()
        st.write("Graph built. Computing high-retention categories...")
        high_ret = identify_high_retention_categories(graph.categories)
        st.write(f"Ready. Load time: {load_time:.0f}s")
        status.update(label="Data loaded.", state="complete", expanded=False)
    st.session_state["graph_loaded"] = True
else:
    graph, load_time = load_graph()
    high_ret = identify_high_retention_categories(graph.categories)

# Sidebar status badge
st.sidebar.markdown(
    f"**Data:** {sum(cat.entering_user_count for cat in graph.categories.values()):,} user-category entries  \n"
    f"**Load time:** {load_time:.0f}s  \n"
    f"**Cutoff:** {MAX_ENTRY_DATE.date()} (90-day window)  \n"
    f"**Data ends:** {OBSERVATION_END.date()}"
)
st.sidebar.markdown("---")
st.sidebar.caption(
    "Retention window: 90 days from first review per category.  \n"
    "Right-censoring: users entering after 2023-04-02 excluded from denominators.  \n"
    "Expansion differences are raw point estimates — no confidence intervals."
)

rankings_df = _build_rankings_df(graph, high_ret)

# ===========================================================================
# Page 1 — Category Rankings
# ===========================================================================

if page == "Category Rankings":
    st.title("Category Rankings")
    st.caption(
        "Retention rate = fraction of **observable** users retained (2+ reviews on 2+ distinct days "
        "within 90 days of first review). Users whose first review falls after 2023-04-02 are "
        "excluded from both numerator and denominator (right-censoring guard)."
    )

    # Metric cards
    cols = st.columns(len(graph.categories))
    for i, (name, cat) in enumerate(
        sorted(graph.categories.items(), key=lambda kv: kv[1].retention_rate, reverse=True)
    ):
        badge = " (HIGH)" if name in high_ret else ""
        cols[i].metric(
            label=_fmt(name) + badge,
            value=f"{cat.retention_rate:.1%}",
            help=(
                f"Observable users: {cat.observable_user_count():,}  \n"
                f"Entering users: {cat.entering_user_count:,}  \n"
                f"Right-censored (excluded): {cat.entering_user_count - cat.observable_user_count():,}"
            ),
        )

    st.markdown("---")

    sort_by = st.selectbox(
        "Sort bars by",
        ["Retention Rate", "Entering Users", "Observable Users"],
    )
    sorted_df = rankings_df.sort_values(sort_by, ascending=True)

    fig_bar = px.bar(
        sorted_df,
        x="Retention Rate",
        y="Category",
        orientation="h",
        color="High Retention",
        color_discrete_map={True: "#2ecc71", False: "#3498db"},
        text=sorted_df["Retention Rate"].apply(lambda v: f"{v:.1%}"),
        title="Retention Rate by Category",
        labels={"Retention Rate": "Retention Rate", "Category": ""},
    )
    fig_bar.update_traces(textposition="outside")
    fig_bar.update_layout(xaxis_tickformat=".0%", height=350, legend_title="High Retention")
    st.plotly_chart(fig_bar, use_container_width=True)

    fig_scatter = px.scatter(
        rankings_df,
        x="Entering Users",
        y="Retention Rate",
        size="Observable Users",
        color="High Retention",
        text="Category",
        color_discrete_map={True: "#2ecc71", False: "#3498db"},
        title="Retention Rate vs. User Volume",
        labels={"Entering Users": "Entering Users (all)", "Retention Rate": "Retention Rate"},
    )
    fig_scatter.update_traces(textposition="top center")
    fig_scatter.update_layout(yaxis_tickformat=".0%", height=400)
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown("### Rankings Table")
    display_df = rankings_df.drop(columns=["Category Key"]).copy()
    display_df["Retention Rate"] = display_df["Retention Rate"].apply(lambda v: f"{v:.2%}")
    display_df["Entering Users"] = display_df["Entering Users"].apply(lambda v: f"{v:,}")
    display_df["Observable Users"] = display_df["Observable Users"].apply(lambda v: f"{v:,}")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    with st.expander("What does 'High Retention' mean?"):
        st.markdown(
            "A category is **high-retention** if its retention rate falls in the **top quartile** "
            "of all 4 category retention rates, AND it has at least 30 observable users.  \n\n"
            "With 4 categories, the top quartile is the top 1 (or tied top 2) by retention rate. "
            "High-retention categories are the **destination categories** in expansion pathway analysis."
        )

# ===========================================================================
# Page 2 — Category Filter
# ===========================================================================

elif page == "Category Filter":
    st.title("Category Filter")
    st.caption(
        "Use the controls below to narrow the category list by retention rate and user volume."
    )

    max_entering = int(rankings_df["Entering Users"].max())
    max_ret = float(rankings_df["Retention Rate"].max())

    st.sidebar.markdown("### Filters")
    min_retention = st.sidebar.slider(
        "Min Retention Rate", 0.0, max(max_ret, 0.01), 0.0, step=0.01, format="%.2f"
    )
    min_users = st.sidebar.slider(
        "Min Entering Users", 0, max_entering, 0, step=max(1, max_entering // 100)
    )
    show_high_only = st.sidebar.checkbox("High-Retention only")

    filtered = rankings_df[
        (rankings_df["Retention Rate"] >= min_retention)
        & (rankings_df["Entering Users"] >= min_users)
    ]
    if show_high_only:
        filtered = filtered[filtered["High Retention"]]

    n_total = len(rankings_df)
    n_match = len(filtered)
    st.info(f"{n_match} of {n_total} categories match the current filters.")

    if filtered.empty:
        st.warning(
            "No categories match the current filter settings. "
            "Try lowering the minimum retention rate or user count."
        )
    else:
        sorted_filtered = filtered.sort_values("Retention Rate", ascending=True)
        fig = px.bar(
            sorted_filtered,
            x="Retention Rate",
            y="Category",
            orientation="h",
            color="High Retention",
            color_discrete_map={True: "#2ecc71", False: "#3498db"},
            text=sorted_filtered["Retention Rate"].apply(lambda v: f"{v:.1%}"),
            title=f"Filtered Categories ({n_match} shown)",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(xaxis_tickformat=".0%", height=max(300, n_match * 80 + 100))
        st.plotly_chart(fig, use_container_width=True)

        display_df = filtered.drop(columns=["Category Key"]).copy()
        display_df["Retention Rate"] = display_df["Retention Rate"].apply(lambda v: f"{v:.2%}")
        display_df["Entering Users"] = display_df["Entering Users"].apply(lambda v: f"{v:,}")
        display_df["Observable Users"] = display_df["Observable Users"].apply(lambda v: f"{v:,}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# ===========================================================================
# Page 3 — Review Search (RAG + LLM synthesis)
# ===========================================================================

elif page == "Review Search":
    st.title("Review Search")
    st.caption(
        "Semantic search over 2.5M reviews using sentence embeddings and Qdrant. "
        "The top 25 most relevant results are passed to an LLM for theme synthesis. "
        "Results reflect reviews in the Jan–Jun 2023 observability window only."
    )

    # ------------------------------------------------------------------
    # Dependency checks (lazy — only evaluated when page is visited)
    # ------------------------------------------------------------------
    _missing_deps = []
    try:
        import google.generativeai as _genai
    except ImportError:
        _genai = None
        _missing_deps.append("google-generativeai")
    try:
        from dotenv import load_dotenv as _load_dotenv
    except ImportError:
        _load_dotenv = None
        _missing_deps.append("python-dotenv")

    if _missing_deps:
        st.error(
            f"Missing required packages: **{', '.join(_missing_deps)}**  \n\n"
            "Install them with:  \n"
            "```\npip install " + " ".join(_missing_deps) + "\n```"
        )
        st.stop()

    try:
        from qdrant_client import QdrantClient as _QdrantClient
        from qdrant_client.models import Filter as _QFilter, FieldCondition as _FieldCondition, MatchValue as _MatchValue, Range as _Range
    except ImportError:
        st.error(
            "Missing required package: **qdrant-client**  \n\n"
            "Install with:  \n"
            "```\npip install qdrant-client\n```"
        )
        st.stop()

    try:
        from sentence_transformers import SentenceTransformer as _SentenceTransformer
    except ImportError:
        st.error(
            "Missing required package: **sentence-transformers**  \n\n"
            "Install with:  \n"
            "```\npip install sentence-transformers\n```"
        )
        st.stop()

    # ------------------------------------------------------------------
    # Cached resource loaders
    # ------------------------------------------------------------------

    @st.cache_resource(show_spinner=False)
    def _load_qdrant_client() -> "_QdrantClient":
        qdrant_path = os.path.join(_PROJECT_ROOT, "data", "qdrant_sample")
        return _QdrantClient(path=str(qdrant_path))

    @st.cache_resource(show_spinner=False)
    def _load_embedding_model() -> "_SentenceTransformer":
        return _SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    # ------------------------------------------------------------------
    # API key resolution
    # ------------------------------------------------------------------
    _load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
    _gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

    if not _gemini_api_key:
        st.warning(
            "No Gemini API key found. Create a `.env` file in the project root with:  \n"
            "```\nGEMINI_API_KEY=your-key-here\n```  \n"
            "Semantic search will still work, but LLM synthesis will be skipped."
        )

    # ------------------------------------------------------------------
    # Sidebar filters (only shown on this page)
    # ------------------------------------------------------------------
    _all_cats = sorted(graph.categories.keys())
    st.sidebar.markdown("### Review Search Filters")
    _sel_cats = st.sidebar.multiselect(
        "Categories",
        options=_all_cats,
        default=_all_cats,
        format_func=_fmt,
    )
    _ret_radio = st.sidebar.radio(
        "Retention status",
        ["All", "Retained", "Churned"],
        horizontal=True,
    )
    _rating_range = st.sidebar.slider(
        "Rating range",
        min_value=1,
        max_value=5,
        value=(1, 5),
        step=1,
    )

    # ------------------------------------------------------------------
    # Query input + search button
    # ------------------------------------------------------------------
    _query_text = st.text_input(
        "Natural language query",
        placeholder='e.g. "battery life poor quality" or "fast shipping great value"',
    )

    _search_clicked = st.button("Search", type="primary")

    if _search_clicked and _query_text.strip():
        # Build Qdrant filter from sidebar selections
        _must_conditions = []

        # Category filter — only add if a strict subset is selected
        if _sel_cats and set(_sel_cats) != set(_all_cats):
            from qdrant_client.models import MatchAny as _MatchAny
            _must_conditions.append(
                _FieldCondition(key="category_name", match=_MatchAny(any=_sel_cats))
            )

        # Retention filter
        if _ret_radio == "Retained":
            _must_conditions.append(
                _FieldCondition(key="retained", match=_MatchValue(value=True))
            )
        elif _ret_radio == "Churned":
            _must_conditions.append(
                _FieldCondition(key="retained", match=_MatchValue(value=False))
            )

        # Rating range filter
        _low_rating, _high_rating = _rating_range
        if _low_rating > 1 or _high_rating < 5:
            _must_conditions.append(
                _FieldCondition(
                    key="rating",
                    range=_Range(gte=float(_low_rating), lte=float(_high_rating)),
                )
            )

        _qdrant_filter = _QFilter(must=_must_conditions) if _must_conditions else None

        with st.spinner("Embedding query and retrieving results..."):
            try:
                _embed_model = _load_embedding_model()
                _vector = _embed_model.encode(
                    _query_text.strip(), normalize_embeddings=True
                ).tolist()

                _qdrant_client = _load_qdrant_client()
                _search_kwargs = dict(
                    collection_name="reviews",
                    query=_vector,
                    limit=500,
                    with_payload=True,
                )
                if _qdrant_filter is not None:
                    _search_kwargs["query_filter"] = _qdrant_filter

                _hits = _qdrant_client.query_points(**_search_kwargs).points
            except Exception as _e:
                st.error(f"Search failed: {_e}")
                st.stop()

        if not _hits:
            st.warning(
                "No results returned. Try broadening the category/rating filters "
                "or rephrasing the query."
            )
        else:
            _top25 = _hits[:25]
            st.success(
                f"Retrieved {len(_hits):,} candidate reviews (showing top 25 for synthesis)."
            )

            # ------------------------------------------------------------------
            # LLM synthesis
            # ------------------------------------------------------------------
            if _gemini_api_key:
                # Build context block for the LLM
                _review_lines = []
                for _i, _hit in enumerate(_top25, 1):
                    _p = _hit.payload or {}
                    _title = (_p.get("title") or "").strip()
                    _text = (_p.get("text") or "").strip()
                    _rating = _p.get("rating", "?")
                    _cat = _fmt(_p.get("category_name", "?"))
                    _ret_flag = _p.get("retained")
                    _ret_str = "retained" if _ret_flag is True else ("churned" if _ret_flag is False else "unknown")
                    _review_lines.append(
                        f"[{_i}] Rating: {_rating}/5 | Category: {_cat} | User: {_ret_str}\n"
                        f"Title: {_title}\n"
                        f"Text: {_text[:400]}"
                    )
                _context_block = "\n\n".join(_review_lines)

                _system_prompt = (
                    "You are an analyst summarizing Amazon product reviews for a data science audience. "
                    "You will receive up to 25 reviews retrieved by semantic similarity to a user query. "
                    "Your output must be in Markdown and contain exactly three sections:\n\n"
                    "## Key Themes\n"
                    "Up to 4 bullet points identifying the dominant themes across these reviews. "
                    "Each bullet should be specific and evidence-based.\n\n"
                    "## Executive Summary\n"
                    "Exactly 3 sentences summarizing the overall picture.\n\n"
                    "## Supporting Excerpts\n"
                    "3 to 5 direct quotations from the reviews (cite as [N]) that best support the summary. "
                    "Quote verbatim — do not paraphrase.\n\n"
                    "Do not invent information not present in the reviews. "
                    "If the reviews are too sparse to identify clear themes, say so explicitly."
                )

                _user_msg = (
                    f"User query: \"{_query_text.strip()}\"\n\n"
                    f"Retrieved reviews:\n\n{_context_block}"
                )

                with st.spinner("Synthesizing with Gemini..."):
                    try:
                        _genai.configure(api_key=_gemini_api_key)
                        _model = _genai.GenerativeModel(
                            "gemini-2.5-flash",
                            system_instruction=_system_prompt,
                            generation_config=_genai.types.GenerationConfig(
                                temperature=0.3,
                                max_output_tokens=20480,
                            ),
                        )
                        _response = _model.generate_content(_user_msg)
                        _synthesis = _response.text
                    except Exception as _e:
                        _synthesis = None
                        st.error(f"LLM synthesis failed: {_e}")

                if _synthesis:
                    st.markdown("---")
                    st.subheader("Synthesis")
                    st.markdown(_synthesis)
            else:
                st.info(
                    "LLM synthesis skipped — no API key. Add `GEMINI_API_KEY` to `.env` to enable."
                )

            # ------------------------------------------------------------------
            # Raw review context (expandable)
            # ------------------------------------------------------------------
            st.markdown("---")
            with st.expander(f"Raw reviews used as context ({len(_top25)})"):
                for _i, _hit in enumerate(_top25, 1):
                    _p = _hit.payload or {}
                    _title = (_p.get("title") or "").strip() or "(no title)"
                    _text = (_p.get("text") or "").strip()
                    _rating = _p.get("rating", "?")
                    _cat = _fmt(_p.get("category_name", "?"))
                    _ret_flag = _p.get("retained")
                    _ret_str = (
                        "retained" if _ret_flag is True
                        else ("churned" if _ret_flag is False else "unknown")
                    )
                    _asin = _p.get("parent_asin", "?")
                    st.markdown(
                        f"**[{_i}]** {_title}  \n"
                        f"Product: `{_asin}` | Rating: {_rating}/5 | Category: {_cat} | Status: {_ret_str} "
                        f"| Score: {_hit.score:.4f}  \n"
                        f"{_text[:300]}{'...' if len(_text) > 300 else ''}"
                    )
                    st.markdown("---")

    elif _search_clicked:
        st.warning("Please enter a query before clicking Search.")

# ===========================================================================
# Page 4 — Expansion Pathways
# ===========================================================================

elif page == "Expansion Pathways":
    st.title("Expansion Pathways")
    st.caption(
        "**ExpansionDifference(A → B)** = P(reviewed B within 90d | first category = A) "
        "minus P(reviewed B within 90d | first category != A).  "
        "B must be a high-retention category. Positive = above-baseline pathway.  \n"
        "**Caveat**: These are raw point estimates with no confidence intervals. "
        "Users entering after 2023-04-02 are excluded (right-censoring). "
        "Users with tied first-category timestamps are excluded from both cohorts."
    )

    with st.spinner("Computing expansion pathways (first load only)..."):
        count_matrix, diff_matrix, high_ret = get_expansion_data(graph)

    view = st.radio(
        "View",
        ["Transition Heatmap", "Expansion Difference", "Network Graph"],
        horizontal=True,
    )

    cats = list(graph.categories.keys())

    # --- A: Transition Heatmap ---
    if view == "Transition Heatmap":
        st.subheader("Category Transition Counts")
        st.markdown(
            "Number of **distinct users** who reviewed category A (row) and then later "
            "reviewed category B (column). Diagonal is masked (self-transitions)."
        )
        # Rename axes for display
        display_count = count_matrix.copy()
        display_count.index = [_fmt(c) for c in count_matrix.index]
        display_count.columns = [_fmt(c) for c in count_matrix.columns]

        fig_heat = px.imshow(
            display_count,
            text_auto=True,
            color_continuous_scale="Blues",
            title="User Transition Counts (A → B)",
            labels={"x": "Destination", "y": "Source", "color": "Users"},
            aspect="auto",
        )
        fig_heat.update_layout(height=450)
        st.plotly_chart(fig_heat, use_container_width=True)

        st.caption(
            "Source: Layer 2 (Category Transition Graph). Edge weight = distinct user count. "
            "Same-timestamp transitions are excluded (ambiguous direction)."
        )

    # --- B: Expansion Difference ---
    elif view == "Expansion Difference":
        st.subheader("Expansion Difference Matrix")
        st.markdown(
            "Each cell = ExpansionDifference(row → column). Green = positive (above-baseline). "
            "Red = negative (below-baseline). Only high-retention destination categories are shown "
            "(columns with data). NaN = pair not computed (same category or insufficient cohort)."
        )
        # Drop columns that are all NaN (non-high-retention destinations)
        diff_display = diff_matrix.copy()
        diff_display = diff_display.loc[:, diff_display.notna().any()]
        diff_display.index = [_fmt(c) for c in diff_display.index]
        diff_display.columns = [_fmt(c) for c in diff_display.columns]

        fig_diff = px.imshow(
            diff_display,
            text_auto=".2%",
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            title="Expansion Difference (A → B)",
            labels={"x": "Destination (high-retention)", "y": "Entry Category", "color": "Diff"},
            aspect="auto",
        )
        fig_diff.update_layout(height=450)
        st.plotly_chart(fig_diff, use_container_width=True)

        # Ranked table of pathways
        st.subheader("Ranked Pathways")
        pathway_rows = []
        for entry in cats:
            for dest in cats:
                val = diff_matrix.loc[entry, dest]
                if not np.isnan(val):
                    pathway_rows.append(
                        {
                            "Entry Category": _fmt(entry),
                            "Destination (high-retention)": _fmt(dest),
                            "Expansion Difference": val,
                            "Direction": "Positive" if val > 0 else "Negative/Neutral",
                        }
                    )
        if pathway_rows:
            pw_df = pd.DataFrame(pathway_rows).sort_values(
                "Expansion Difference", ascending=False
            )
            pw_df["Expansion Difference"] = pw_df["Expansion Difference"].apply(
                lambda v: f"{v:+.2%}"
            )
            st.dataframe(pw_df, use_container_width=True, hide_index=True)
        else:
            st.info("No expansion pathway data available.")

    # --- C: Network Graph ---
    else:
        st.subheader("Category Transition Network")
        st.markdown(
            "Nodes = categories. Green = high-retention. "
            "Edge width proportional to user count. "
            "Arrows show direction of transition (source reviewed first)."
        )
        G = graph.transition_graph
        pos = nx.circular_layout(G)

        node_colors = ["#2ecc71" if n in high_ret else "#3498db" for n in G.nodes()]
        edge_weights = [G[u][v]["user_count"] for u, v in G.edges()]
        max_w = max(edge_weights) if edge_weights else 1
        edge_widths = [1 + 4 * (w / max_w) for w in edge_weights]

        fig_net, ax = plt.subplots(figsize=(8, 6))
        nx.draw_networkx(
            G,
            pos=pos,
            ax=ax,
            node_color=node_colors,
            node_size=1800,
            edge_color="#888888",
            width=edge_widths,
            arrows=True,
            arrowsize=20,
            font_size=8,
            font_color="white",
            font_weight="bold",
            labels={n: _fmt(n) for n in G.nodes()},
        )
        edge_labels = {(u, v): f"{G[u][v]['user_count']:,}" for u, v in G.edges()}
        nx.draw_networkx_edge_labels(G, pos=pos, edge_labels=edge_labels, ax=ax, font_size=7)
        ax.set_title("Category Transition Network", fontsize=13)
        ax.axis("off")
        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="#2ecc71", label="High-retention"),
            Patch(facecolor="#3498db", label="Standard"),
        ]
        ax.legend(handles=legend_elements, loc="upper right")
        plt.tight_layout()
        st.pyplot(fig_net)
        plt.close(fig_net)

        st.caption(
            f"High-retention categories: {', '.join(_fmt(c) for c in sorted(high_ret)) if high_ret else 'none'}. "
            "Edge labels = distinct user count."
        )

# ===========================================================================
# Page 4 — Category Detail
# ===========================================================================

elif page == "Category Detail":
    st.title("Category Detail")

    selected = st.selectbox(
        "Select category",
        list(graph.categories.keys()),
        format_func=_fmt,
    )
    cat = graph.categories[selected]

    # Metrics row
    entering = cat.entering_user_count
    observable = cat.observable_user_count()
    right_censored = entering - observable

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Retention Rate", f"{cat.retention_rate:.2%}")
    col2.metric(
        "Observable Users",
        f"{observable:,}",
        help=(
            "Users whose first review in this category falls on or before 2023-04-02. "
            "Only these users are included in retention rate calculations."
        ),
    )
    col3.metric("Entering Users", f"{entering:,}")
    col4.metric(
        "Right-Censored",
        f"{right_censored:,}",
        help=(
            "Users excluded from retention calculations because their first review in this "
            "category falls after 2023-04-02. They cannot be observed for a full 90-day window "
            "before the dataset ends (2023-07-01). This is expected, not data loss."
        ),
    )

    if selected in high_ret:
        st.success(
            f"{_fmt(selected)} is a **high-retention** category "
            f"(top quartile by retention rate, >= 30 observable users)."
        )
    else:
        st.info(f"{_fmt(selected)} is not in the high-retention set.")

    st.markdown("---")

    # Transition tables
    t_graph = graph.transition_graph
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Users Who Later Went To")
        successors = list(t_graph.successors(selected))
        if successors:
            succ_rows = [
                {
                    "Destination": _fmt(s),
                    "User Count": t_graph[selected][s]["user_count"],
                }
                for s in successors
            ]
            succ_df = pd.DataFrame(succ_rows).sort_values("User Count", ascending=False)
            st.dataframe(succ_df, use_container_width=True, hide_index=True)
        else:
            st.info("No outbound transitions recorded.")

    with col_b:
        st.subheader("Users Who Came From")
        predecessors = list(t_graph.predecessors(selected))
        if predecessors:
            pred_rows = [
                {
                    "Source": _fmt(p),
                    "User Count": t_graph[p][selected]["user_count"],
                }
                for p in predecessors
            ]
            pred_df = pd.DataFrame(pred_rows).sort_values("User Count", ascending=False)
            st.dataframe(pred_df, use_container_width=True, hide_index=True)
        else:
            st.info("No inbound transitions recorded.")

    # Expansion pathways INTO this category (only if high-retention)
    if selected in high_ret:
        st.markdown("---")
        st.subheader(f"Expansion Pathways Into {_fmt(selected)}")
        st.caption(
            "ExpansionDifference values for entry categories that lead to this "
            "high-retention destination. Positive = above-baseline pathway."
        )
        with st.spinner("Loading expansion data..."):
            _, diff_matrix, _ = get_expansion_data(graph)
        if selected in diff_matrix.columns:
            col_data = diff_matrix[selected].dropna().sort_values(ascending=False)
            if not col_data.empty:
                pathway_into = pd.DataFrame(
                    {
                        "Entry Category": [_fmt(idx) for idx in col_data.index],
                        "Expansion Difference": col_data.values,
                    }
                )
                pathway_into["Expansion Difference"] = pathway_into[
                    "Expansion Difference"
                ].apply(lambda v: f"{v:+.2%}")
                st.dataframe(pathway_into, use_container_width=True, hide_index=True)
            else:
                st.info("No expansion pathway data for this destination.")

    st.markdown("---")
    with st.expander("Metric Caveats"):
        st.markdown(
            f"""
**90-day retention window**: A user is retained in {_fmt(selected)} only if they post
2+ reviews on 2+ distinct UTC calendar days within 90 days of their first review in this category.

**Right-censoring**: {right_censored:,} users entered {_fmt(selected)} after 2023-04-02 and are
excluded from retention calculations. Their 90-day window extends past the data end date
(2023-07-01) so we cannot observe whether they were retained.

**Observability cutoff**: The dataset ends 2023-07-01 00:00:00 UTC. `MAX_ENTRY_DATE` =
{MAX_ENTRY_DATE.date()} (90 days before data end).

**Category-level semantics**: Retention is calculated independently per category. A user
can be retained in {_fmt(selected)} and not retained in another category, or vice versa.
"""
        )

# ===========================================================================
# Page 5 — ML Insights
# ===========================================================================

elif page == "ML Insights":
    st.title("ML Insights")
    st.caption(
        "This page runs user clustering (K-means) and retention prediction (Random Forest) "
        "on the full dataset. Results are cached after the first run."
    )

    st.info(
        "**Descriptive vs. Predictive**: Category rankings, retention rates, and expansion "
        "pathways (pages 1-4) are *descriptive* graph analysis derived from the review data. "
        "The models on this page are *predictive* — they learn patterns from features and "
        "generalize to unseen users. The ROC AUC here is a held-out test-set estimate."
    )

    run_ml = st.button("Run ML Analysis", type="primary")

    if run_ml or "ml_ran" in st.session_state:
        st.session_state["ml_ran"] = True

        with st.spinner("Running ML pipeline (first run: 30-90 seconds)..."):
            ml = get_ml_results(graph)

        user_feat_df = ml["user_feat_df"]
        k_result = ml["k_result"]
        cluster_result = ml["cluster_result"]
        cluster_profiles = ml["cluster_profiles"]
        ret_result = ml["ret_result"]

        tab_clusters, tab_retention = st.tabs(["User Clusters", "Retention Prediction"])

        # -------------------------------------------------------------------
        # Tab 1: User Clusters
        # -------------------------------------------------------------------
        with tab_clusters:
            st.subheader("User Segmentation (K-means)")
            st.caption(
                f"Best k = {k_result['best_k']} (chosen by silhouette score). "
                f"Total users clustered: {len(user_feat_df):,}. "
                "Clustering uses MiniBatchKMeans on all users; k search subsamples to 200K."
            )

            # Elbow + silhouette plots
            c1, c2 = st.columns(2)
            with c1:
                fig_elbow, ax_elbow = plt.subplots(figsize=(5, 3))
                from ml.clustering import plot_elbow, plot_silhouette
                plot_elbow(k_result, ax=ax_elbow)
                plt.tight_layout()
                st.pyplot(fig_elbow)
                plt.close(fig_elbow)
            with c2:
                fig_sil, ax_sil = plt.subplots(figsize=(5, 3))
                plot_silhouette(k_result, ax=ax_sil)
                plt.tight_layout()
                st.pyplot(fig_sil)
                plt.close(fig_sil)

            # Interactive cluster bar chart
            st.markdown("### Segment Sizes — click a bar to explore that segment")
            fig_bar_cl = px.bar(
                cluster_profiles.reset_index(),
                x="label",
                y="size",
                color="label",
                title="User Segments",
                labels={"label": "Segment", "size": "User Count"},
            )
            fig_bar_cl.update_layout(showlegend=False, height=380)
            event = st.plotly_chart(
                fig_bar_cl, on_select="rerun", key="cluster_chart", use_container_width=True
            )

            # Segment drill-down on click
            if event and event.selection and event.selection.points:
                clicked_label = event.selection.points[0]["x"]
                segment_df = user_feat_df[user_feat_df["cluster_name"] == clicked_label]

                st.subheader(f"Segment: {clicked_label}")
                sc1, sc2, sc3 = st.columns(3)
                sc1.metric("Users", f"{len(segment_df):,}")
                sc2.metric(
                    "Avg Reviews",
                    f"{segment_df['total_review_count'].mean():.1f}",
                )
                sc3.metric(
                    "Multi-Category",
                    f"{segment_df['is_multi_category'].mean():.0%}",
                )

                # Distribution plots
                d1, d2, d3 = st.columns(3)
                d1.plotly_chart(
                    px.histogram(
                        segment_df,
                        x="total_review_count",
                        title="Review Count Distribution",
                        nbins=30,
                    ),
                    use_container_width=True,
                )
                d2.plotly_chart(
                    px.histogram(
                        segment_df,
                        x="avg_rating",
                        title="Avg Rating Distribution",
                        nbins=20,
                    ),
                    use_container_width=True,
                )
                d3.plotly_chart(
                    px.histogram(
                        segment_df,
                        x="time_span_days",
                        title="Active Span (days)",
                        nbins=30,
                    ),
                    use_container_width=True,
                )

                # Segment vs population comparison
                st.subheader("vs. Overall Population")
                compare_cols = [
                    "total_review_count",
                    "avg_rating",
                    "category_count",
                    "time_span_days",
                    "is_multi_category",
                ]
                compare_df = pd.DataFrame(
                    {
                        "Feature": compare_cols,
                        "Segment Mean": [segment_df[c].mean() for c in compare_cols],
                        "Population Mean": [user_feat_df[c].mean() for c in compare_cols],
                    }
                )
                compare_df["Segment Mean"] = compare_df["Segment Mean"].round(3)
                compare_df["Population Mean"] = compare_df["Population Mean"].round(3)
                st.dataframe(compare_df, use_container_width=True, hide_index=True)
            else:
                st.caption("Click a bar above to explore that segment in detail.")

            # Cluster profiles table
            with st.expander("Full Cluster Profiles"):
                profile_display = cluster_profiles.copy().round(3)
                st.dataframe(profile_display, use_container_width=True)

        # -------------------------------------------------------------------
        # Tab 2: Retention Prediction
        # -------------------------------------------------------------------
        with tab_retention:
            st.subheader("Retention Prediction (Random Forest)")
            st.caption(
                "Target: will a user post 2+ reviews on 2+ distinct days within 90 days? "
                "Features are derived from the user's first review and prior history only "
                "(no look-ahead leakage). Users are split by user_id to prevent "
                "the same user appearing in both train and test."
            )

            auc = ret_result["roc_auc"]
            if np.isnan(auc):
                st.warning("ROC AUC could not be computed (test set may be single-class).")
            else:
                st.metric(
                    "ROC AUC (held-out test set)",
                    f"{auc:.3f}",
                    help=(
                        "Area under the ROC curve on the held-out test set. "
                        "0.5 = random, 1.0 = perfect. Expected range: 0.55-0.75 given "
                        "that retention is largely driven by user behavior not captured in features."
                    ),
                )

            mc1, mc2 = st.columns(2)
            with mc1:
                fig_roc, ax_roc = plt.subplots(figsize=(5, 4))
                from ml.retention_model import plot_roc_curve, plot_feature_importance
                if not np.isnan(auc):
                    plot_roc_curve(ret_result, ax=ax_roc)
                else:
                    ax_roc.text(0.5, 0.5, "ROC unavailable", ha="center", va="center")
                plt.tight_layout()
                st.pyplot(fig_roc)
                plt.close(fig_roc)

            with mc2:
                fig_imp, ax_imp = plt.subplots(figsize=(6, 4))
                plot_feature_importance(ret_result, ax=ax_imp, top_n=10)
                plt.tight_layout()
                st.pyplot(fig_imp)
                plt.close(fig_imp)

            with st.expander("Classification Report"):
                st.text(ret_result["classification_report"])

            with st.expander("Model Caveats"):
                st.markdown(
                    """
- **Sampled**: If the retention feature dataset exceeded 50,000 rows, a random 50K sample was used.
- **category_size leakage note**: The `category_size` feature counts all observable entrants,
  including those who entered after the user being scored. This is acceptable for retrospective
  analysis but would be look-ahead leakage in point-in-time deployment.
- **Right-censoring applies here too**: Only observable users (entering before 2023-04-02) are
  included in the feature set.
- **Four categories only**: Results reflect Amazon review behavior in Electronics, Video Games,
  Software, and Cell Phones & Accessories during Jan-Jun 2023.
"""
                )
    else:
        st.markdown(
            "Click **Run ML Analysis** above to run user clustering and retention prediction. "
            "First run takes 30-90 seconds; subsequent loads are instant (cached)."
        )
