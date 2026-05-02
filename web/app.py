"""
Amazon Reviews Analysis — Streamlit Dashboard (Phase 3)

Six pages:
  1. Overview           — landing page with top-line findings
  2. Review Synthesis   — RAG semantic search + LLM synthesis (Qdrant + Gemini)
  3. Expansion Pathways — transition heatmap
  4. User Segmentation  — user clustering (K-means, button-triggered)
  5. Category Detail    — overview (rankings, charts) + per-category drill-down
  6. Limitations        — methodology caveats

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

# Pre-computed artifacts written by scripts/precompute.py.
# When present, they bypass the 90-180s CSV → Graph build + expansion
# computation + ML pipeline, turning cold start into ~2-5s.
_PRECOMPUTED_DIR = os.path.join(_PROJECT_ROOT, "data", "precomputed")
_GRAPH_PKL = os.path.join(_PRECOMPUTED_DIR, "graph.pkl")
_EXPANSION_PKL = os.path.join(_PRECOMPUTED_DIR, "expansion.pkl")
_ML_PKL = os.path.join(_PRECOMPUTED_DIR, "ml.pkl")

import matplotlib
matplotlib.use("Agg")  # non-interactive backend; must precede pyplot import
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import streamlit as st

from graph_logic.analysis import (
    compute_all_expansion_pathways,
    identify_high_retention_categories,
)
from graph_logic.models import Graph, MAX_ENTRY_DATE, OBSERVATION_END
from web.theme import (
    COLOR_HIGH_RET,
    COLOR_STANDARD,
    COLORSCALE_AMBER,
    PALETTE,
)
from web.ui import (
    inject_global_styles,
    matplotlib_dark,
    mpl_color,
    render_divider,
    render_explainer_card,
    render_hero,
    render_page_header,
    render_sidebar_brand,
    render_sidebar_section_label,
    style_plotly,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Amazon Reviews Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject global CSS immediately after set_page_config so the dark palette,
# hero/page-header classes, and button/metric restyles are active for every
# page below.
inject_global_styles()

# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def load_graph() -> tuple[Graph, float, str]:
    """
    Load the Graph.

    Fast path: unpickle data/precomputed/graph.pkl (written by
    scripts/precompute.py). Cold path: rebuild from the cleaned CSV.

    Returns (graph, load_time_seconds, source) where source is
    "precomputed" or "csv".
    """
    import pickle

    t0 = time.perf_counter()
    if os.path.isfile(_GRAPH_PKL):
        with open(_GRAPH_PKL, "rb") as f:
            graph = pickle.load(f)
        return graph, time.perf_counter() - t0, "precomputed"

    df = pd.read_csv(DATA_PATH, dtype={"user_id": str, "category_name": str})
    df["date"] = pd.to_datetime(df["date"], format="ISO8601", utc=True)
    graph = Graph.from_dataframe(df)
    return graph, time.perf_counter() - t0, "csv"


@st.cache_resource(show_spinner=False)
def get_expansion_data(_graph: Graph) -> tuple[pd.DataFrame, pd.DataFrame, set]:
    """
    Transition count matrix, expansion difference matrix, and high-retention set.

    Fast path: read data/precomputed/expansion.pkl.
    Cold path: compute from the live Graph (preserves original behavior).
    """
    import pickle

    if os.path.isfile(_EXPANSION_PKL):
        with open(_EXPANSION_PKL, "rb") as f:
            payload = pickle.load(f)
        return payload["count_matrix"], payload["diff_matrix"], payload["high_ret"]

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
    User-clustering (K-means) results.

    Fast path: read data/precomputed/ml.pkl.
    Cold path: run the full pipeline (only triggered by the Run button).
    """
    import pickle

    if os.path.isfile(_ML_PKL):
        with open(_ML_PKL, "rb") as f:
            return pickle.load(f)

    from ml.clustering import (
        characterize_clusters,
        find_optimal_k,
        train_clustering,
    )
    from ml.features import build_user_features

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

    return {
        "user_feat_df": user_feat_df,
        "k_result": k_result,
        "cluster_result": cluster_result,
        "cluster_profiles": cluster_profiles,
    }


def _has_precomputed_artifacts() -> bool:
    """True if all three precomputed pickles exist on disk."""
    return all(os.path.isfile(p) for p in (_GRAPH_PKL, _EXPANSION_PKL, _ML_PKL))


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

render_sidebar_brand()
render_sidebar_section_label("Navigate")

_NAV_PAGES = [
    "Overview",
    "Review Synthesis",
    "User Segmentation",
    "Expansion Pathways",
    "Category Detail",
    "Limitations",
]

if "page" not in st.session_state:
    st.session_state["page"] = _NAV_PAGES[0]

# Anchor-card navigation from the "Where to go next" HTML blocks:
# clicking one sets `?goto=<page>`, which we route here, then clear the
# param so the URL stays clean and the click isn't re-fired on next rerun.
_goto = st.query_params.get("goto")
if _goto and _goto in _NAV_PAGES:
    st.session_state["page"] = _goto
    del st.query_params["goto"]
    st.rerun()

for _p in _NAV_PAGES:
    _is_active = (_p == st.session_state["page"])
    # Active page uses **markdown-bold** → <strong>, which the CSS
    # rule `button:has(strong)` lights up with the amber accent bar.
    _label = f"**{_p}**" if _is_active else _p
    if st.sidebar.button(_label, key=f"nav_{_p}", use_container_width=True):
        st.session_state["page"] = _p
        st.rerun()

page = st.session_state["page"]

# Load graph (shows status block on first run).
# If precomputed pickles are present, cold-start is a few seconds; otherwise
# we rebuild from CSV and that takes ~90-180 s (see scripts/precompute.py).
if "graph_loaded" not in st.session_state:
    _fast = _has_precomputed_artifacts()
    _init_label = (
        "Loading precomputed data..."
        if _fast
        else "Loading data... (first load takes 90-180 seconds)"
    )
    with st.status(_init_label, expanded=True) as status:
        if _fast:
            st.write("Reading precomputed graph pickle...")
        else:
            st.write("Reading cleaned_reviews.csv (2.5M rows)...")
        graph, load_time, source = load_graph()
        st.write(
            f"Graph ready ({source}: {len(graph.users):,} users, "
            f"{len(graph.categories)} categories)."
        )
        _count_matrix, _diff_matrix, high_ret = get_expansion_data(graph)
        st.write(f"Ready. Load time: {load_time:.1f}s")
        status.update(label="Data loaded.", state="complete", expanded=False)
    st.session_state["graph_loaded"] = True
else:
    graph, load_time, _source = load_graph()
    _count_matrix, _diff_matrix, high_ret = get_expansion_data(graph)

rankings_df = _build_rankings_df(graph, high_ret)

# ===========================================================================
# Page 0 — Overview (landing page)
# ===========================================================================

if page == "Overview":
    # --- Top-line numbers (computed first — also feeds the hero stat row) ---
    total_users = len(graph.users)
    total_observable = sum(c.observable_user_count() for c in graph.categories.values())
    total_entering = sum(c.entering_user_count for c in graph.categories.values())

    render_hero(
        title="Amazon Reviews Dashboard",
        eyebrow="Retention · Expansion · Semantics",
        subtitle=(
            "2.5M verified-purchase reviews across four categories — Electronics, "
            "Video Games, Software, Cell Phones & Accessories — analyzed for "
            "90-day retention and cross-category expansion pathways."
        ),
        stats=[
            (f"{total_users/1_000_000:.2f}M", "Unique users"),
            (f"{total_observable:,}", "Observable entries"),
            (f"{len(graph.categories)}", "Categories"),
            ("Jan–Jun 2023", "Window"),
        ],
    )

    # --- Explanation-first cards (live value lives in the hover tooltip) ---
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_explainer_card(
            "Unique Users",
            "Distinct verified reviewers observed across the four categories in the Jan–Jun 2023 window.",
            value=f"{total_users:,}",
            definition=(
                "Unique users = count of distinct user_id values after verified-purchase "
                "filtering and 2023-01-01 → 2023-06-30 date clipping."
            ),
        )
    with m2:
        render_explainer_card(
            "Observable Entries",
            "Category entries that can be measured for the full 90-day retention window before the dataset ends.",
            value=f"{total_observable:,}",
            definition=(
                "Sum of per-category entering users whose first review falls on or before "
                "2023-04-02 (so a full 90-day retention window can be observed)."
            ),
        )
    with m3:
        render_explainer_card(
            "Entry Events",
            "Total first-review events across categories — a user entering multiple categories contributes multiple events.",
            value=f"{total_entering:,}",
            definition=(
                "Sum of first-review events per category. Users can enter multiple categories, "
                "so this exceeds the unique-user count."
            ),
        )
    with m4:
        render_explainer_card(
            "Categories",
            "Product taxonomies under analysis: Electronics, Video Games, Software, and Cell Phones & Accessories.",
            value=f"{len(graph.categories)}",
            definition=(
                "Four categories chosen from the UCSD Amazon Reviews 2023 dataset. "
                "Findings are scoped to this set and do not generalize beyond it."
            ),
        )

    render_divider()

    # --- Retention finding ---
    st.subheader("Retention")
    high_ret_sorted = sorted(
        graph.categories.items(), key=lambda kv: kv[1].retention_rate, reverse=True
    )
    top_name, top_cat = high_ret_sorted[0]
    n_high = len(high_ret)

    st.markdown(
        f"**{n_high} of {len(graph.categories)} categories hit high-retention status.** "
        f"**{_fmt(top_name)}** leads at **{top_cat.retention_rate:.1%}** "
        f"({top_cat.observable_user_count():,} observable users)."
    )

    render_divider()

    # --- Expansion finding ---
    st.subheader("Expansion")
    st.caption(
        "ExpansionDifference(A → B) = P(reviewed B within 90d | first category = A) "
        "minus the same probability for users whose first category was not A. "
        "Reported in **percentage points (pp)** — absolute difference, not relative uplift."
    )
    _, diff_matrix, _ = get_expansion_data(graph)
    _stack = diff_matrix.stack(dropna=True)
    if _stack.empty:
        st.info("No expansion pathway data available.")
    else:
        (entry_cat, dest_cat), top_diff = _stack.idxmax(), _stack.max()
        if top_diff > 0:
            st.markdown(
                f"**Strongest pathway: {_fmt(entry_cat)} → {_fmt(dest_cat)}.** "
                f"Users whose first category is **{_fmt(entry_cat)}** reach **{_fmt(dest_cat)}** "
                f"within 90 days at a rate **{top_diff * 100:+.1f} pp** above the baseline "
                f"(the rate for users who started elsewhere)."
            )
        else:
            st.markdown(
                f"No above-baseline pathway was detected across the 4 categories.\n\n"
                f"The least-negative pathway is **{_fmt(entry_cat)} → {_fmt(dest_cat)}** at "
                f"**{top_diff * 100:+.1f} pp** relative to baseline."
            )

    render_divider()

    # --- Segmentation finding (only if ML already ran this session) ---
    st.subheader("User Segmentation")
    if "ml_ran" in st.session_state:
        ml = get_ml_results(graph)
        _profiles = ml["cluster_profiles"]
        _k = ml["k_result"]["best_k"]
        _largest = _profiles.sort_values("size", ascending=False).iloc[0]
        st.markdown(
            f"**{_k} behavioral segments identified.** Largest segment: "
            f"**{_largest['label']}** ({int(_largest['size']):,} users)."
        )
        _seg_bar = px.bar(
            _profiles.reset_index(),
            x="label",
            y="size",
            color="label",
            labels={"label": "Segment", "size": "User Count"},
        )
        style_plotly(_seg_bar, showlegend=False, height=260, margin=dict(t=10, b=10))
        st.plotly_chart(_seg_bar, use_container_width=True)
    else:
        st.info(
            "Click **User Segmentation** in the sidebar and run the analysis to see "
            "behavioral clusters (K-means). Segment breakdown will appear here after."
        )

    render_divider()

    # --- Where to go next (clickable cards) ---
    st.subheader("Where to go next")

    _nextgo = [
        (
            "Review Synthesis",
            "Ask a natural-language question across 100K reviews. "
            "Gemini 2.5 Flash synthesizes themes, summary, and supporting quotes.",
        ),
        (
            "Expansion Pathways",
            "A transition heatmap showing how users move between "
            "categories within 90 days of their first review.",
        ),
        (
            "Category Detail",
            "Drill into one category: rankings, inbound/outbound transitions, "
            "and expansion pathways into high-retention destinations.",
        ),
    ]
    # Pure-HTML anchor cards — we control the entire DOM, so text-align
    # behaves exactly as written and isn't subject to Streamlit-button
    # internal layout. Clicks land on `?goto=<page>` and are routed above.
    import html as _html
    _cards_html = '<div class="ar-nextgo-grid">' + "".join(
        (
            f'<a class="ar-nextgo-card" href="?goto={_html.escape(title)}" '
            f'target="_self">'
            f'<div class="ar-nextgo-card-title">{_html.escape(title)}</div>'
            f'<div class="ar-nextgo-card-body">{_html.escape(body)}</div>'
            f'<span class="ar-nextgo-card-arrow" aria-hidden="true">→</span>'
            f'</a>'
        )
        for title, body in _nextgo
    ) + "</div>"
    st.markdown(_cards_html, unsafe_allow_html=True)

    st.caption(
        "See the **Limitations** page for methodology caveats "
        "(right-censoring, top-quartile with N=4, sampling, etc.)."
    )

# ===========================================================================
# Page 1 — Review Synthesis (RAG + LLM synthesis)
# ===========================================================================

elif page == "Review Synthesis":
    render_page_header(
        title="Review Synthesis",
        eyebrow="RAG · Qdrant · Gemini 2.5 Flash",
        subtitle=(
            "Ask a natural-language question across the review corpus. "
            "Sentence-transformer embeddings retrieve the top 25 most similar reviews; "
            "Gemini 2.5 Flash synthesizes themes, a 4-sentence summary, and supporting excerpts."
        ),
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
            "Review retrieval will still work, but LLM synthesis will be skipped."
        )

    # ------------------------------------------------------------------
    # Sidebar filters (only shown on this page)
    # ------------------------------------------------------------------
    _all_cats = sorted(graph.categories.keys())
    st.sidebar.markdown("### Review Synthesis Filters")
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
                    "You are an qualitative researcher with 25 years of experience, summarizing Amazon product reviews for a data science audience. "
                    "You will receive up to 25 reviews retrieved by semantic similarity to a user query. "
                    "Your output must be in Markdown and contain exactly three sections:\n\n"
                    "## Key Themes\n"
                    "Up to 5 bullet points identifying the dominant themes across these reviews. "
                    "Each bullet should be specific and evidence-based.\n\n"
                    "## Executive Summary\n"
                    "Exactly 4 sentences summarizing the overall picture.\n\n"
                    "## Supporting Excerpts\n"
                    "Exactly 3 direct quotations from the reviews (cite as [N]) that best support the summary. "
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
                    render_divider()
                    st.subheader("Synthesis")
                    st.markdown(_synthesis)
            else:
                st.info(
                    "LLM synthesis skipped — no API key. Add `GEMINI_API_KEY` to `.env` to enable."
                )

            # ------------------------------------------------------------------
            # Raw review context (expandable)
            # ------------------------------------------------------------------
            render_divider()
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
# Page 2 — Expansion Pathways
# ===========================================================================

elif page == "Expansion Pathways":
    render_page_header(
        title="Expansion Pathways",
        eyebrow="Cross-category · 90-day window",
        subtitle=(
            "<strong>ExpansionDifference(A → B)</strong> = P(reviewed B within 90d | first category = A) "
            "minus P(reviewed B within 90d | first category ≠ A). "
            "Positive values indicate above-baseline expansion into high-retention destinations. "
            "Point estimates only — no confidence intervals. Users entering after 2023-04-02 are "
            "excluded (right-censoring); tied first-category timestamps are also excluded."
        ),
    )

    with st.spinner("Computing expansion pathways (first load only)..."):
        count_matrix, _diff_matrix, high_ret = get_expansion_data(graph)

    # --- Transition Heatmap (only view on this page) ---
    st.subheader("Category Transition Counts")
    st.markdown(
        "Number of **distinct users** who reviewed category A (row) and then later "
        "reviewed category B (column). Diagonal is masked (self-transitions)."
    )
    display_count = count_matrix.copy()
    display_count.index = [_fmt(c) for c in count_matrix.index]
    display_count.columns = [_fmt(c) for c in count_matrix.columns]

    fig_heat = px.imshow(
        display_count,
        text_auto=True,
        color_continuous_scale=COLORSCALE_AMBER,
        title="User Transition Counts (A → B)",
        labels={"x": "Destination", "y": "Source", "color": "Users"},
        aspect="auto",
    )
    style_plotly(fig_heat, height=450)
    st.plotly_chart(fig_heat, use_container_width=True)

    st.caption(
        "Source: Layer 2 (Category Transition Graph). Edge weight = distinct user count. "
        "Same-timestamp transitions are excluded (ambiguous direction)."
    )

# ===========================================================================
# Page 4 — Category Detail (overview + per-category drill-down)
# ===========================================================================

elif page == "Category Detail":
    render_page_header(
        title="Category Detail",
        eyebrow="Rankings · Transitions · Drill-down",
        subtitle=(
            "Retention rate = fraction of <em>observable</em> users retained "
            "(2+ reviews on 2+ distinct days within 90 days of first review). "
            "Users whose first review falls after 2023-04-02 are excluded from "
            "both numerator and denominator (right-censoring guard)."
        ),
    )

    # -------------------------------------------------------------------
    # Overview section (category rankings across all 4 categories)
    # -------------------------------------------------------------------
    st.subheader("Category Overview")

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
        color_discrete_map={True: COLOR_HIGH_RET, False: COLOR_STANDARD},
        text=sorted_df["Retention Rate"].apply(lambda v: f"{v:.1%}"),
        title="Retention Rate by Category",
        labels={"Retention Rate": "Retention Rate", "Category": ""},
    )
    fig_bar.update_traces(textposition="outside", marker_line_width=0)
    style_plotly(
        fig_bar,
        xaxis=dict(tickformat=".0%"),
        height=350,
        legend_title_text="High Retention",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    fig_scatter = px.scatter(
        rankings_df,
        x="Entering Users",
        y="Retention Rate",
        size="Observable Users",
        color="High Retention",
        text="Category",
        color_discrete_map={True: COLOR_HIGH_RET, False: COLOR_STANDARD},
        title="Retention Rate vs. User Volume",
        labels={"Entering Users": "Entering Users (all)", "Retention Rate": "Retention Rate"},
    )
    fig_scatter.update_traces(textposition="top center")
    style_plotly(fig_scatter, yaxis=dict(tickformat=".0%"), height=400)
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

    render_divider()

    # -------------------------------------------------------------------
    # Per-category drill-down
    # -------------------------------------------------------------------
    st.subheader("Per-Category Drill-Down")

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

    render_divider()

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
        render_divider()
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

    render_divider()
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
# Page 3 — User Segmentation
# ===========================================================================

elif page == "User Segmentation":
    render_page_header(
        title="User Segmentation",
        eyebrow="Unsupervised · K-means · 12 features",
        subtitle=(
            "Runs MiniBatchKMeans on standardized per-user features. "
            "<em>k</em> is chosen by silhouette score on a 200K subsample; the full user "
            "population is then labeled. Click a segment bar to drill into its profile."
        ),
    )

    st.info(
        "**Descriptive vs. Predictive**: Category rankings, retention rates, and expansion "
        "pathways (pages 1-4) are *descriptive* graph analysis derived from the review data. "
        "The clustering on this page is *unsupervised* — it learns behavioral patterns from "
        "review features without a labeled target."
    )

    run_ml = st.button("Run Segmentation Analysis", type="primary")

    if run_ml or "ml_ran" in st.session_state:
        st.session_state["ml_ran"] = True

        with st.spinner("Running clustering pipeline (first run: 30-90 seconds)..."):
            ml = get_ml_results(graph)

        user_feat_df = ml["user_feat_df"]
        k_result = ml["k_result"]
        cluster_result = ml["cluster_result"]
        cluster_profiles = ml["cluster_profiles"]

        # -------------------------------------------------------------------
        # Segment Sizes (interactive cluster bar chart)
        # -------------------------------------------------------------------
        st.markdown("### Segment Sizes — click a bar to explore that segment")
        fig_bar_cl = px.bar(
            cluster_profiles.reset_index(),
            x="label",
            y="size",
            color="label",
            title="User Segments",
            labels={"label": "Segment", "size": "User Count"},
        )
        fig_bar_cl.update_traces(marker_line_width=0)
        style_plotly(fig_bar_cl, showlegend=False, height=380)
        event = st.plotly_chart(
            fig_bar_cl, on_select="rerun", key="cluster_chart", use_container_width=True
        )

        # -------------------------------------------------------------------
        # User Segmentation (K-means) — elbow + silhouette diagnostics
        # -------------------------------------------------------------------
        st.subheader("User Segmentation (K-means)")
        st.caption(
            f"Best k = {k_result['best_k']} (chosen by silhouette score). "
            f"Total users clustered: {len(user_feat_df):,}. "
            "Clustering uses MiniBatchKMeans on all users; k search subsamples to 200K."
        )

        # Elbow + silhouette plots (matplotlib — themed dark)
        c1, c2 = st.columns(2)
        with c1:
            fig_elbow, ax_elbow = plt.subplots(figsize=(5, 3))
            from ml.clustering import plot_elbow, plot_silhouette
            plot_elbow(k_result, ax=ax_elbow)
            # Recolor the line drawn by plot_elbow to the amber accent before dark-retheming
            for _line in ax_elbow.get_lines():
                _line.set_color(PALETTE["accent"])
            matplotlib_dark(fig_elbow, ax_elbow)
            plt.tight_layout()
            st.pyplot(fig_elbow)
            plt.close(fig_elbow)
        with c2:
            fig_sil, ax_sil = plt.subplots(figsize=(5, 3))
            plot_silhouette(k_result, ax=ax_sil)
            for _line in ax_sil.get_lines():
                # The vline (best_k marker) is styled differently — keep its dashed style
                # but recolor. The main series line becomes amber too.
                if _line.get_linestyle() == "--":
                    _line.set_color(PALETTE["accent_bright"])
                else:
                    _line.set_color(PALETTE["accent"])
            matplotlib_dark(fig_sil, ax_sil)
            # Re-theme the "Best k =" legend added by plot_silhouette
            _leg = ax_sil.get_legend()
            if _leg is not None:
                _leg.get_frame().set_facecolor("#1a1a22")
                _leg.get_frame().set_edgecolor(mpl_color(PALETTE["border"]))
                for _t in _leg.get_texts():
                    _t.set_color(PALETTE["text"])
            plt.tight_layout()
            st.pyplot(fig_sil)
            plt.close(fig_sil)

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
            _hist_specs = [
                (d1, "total_review_count", "Review Count Distribution", 30),
                (d2, "avg_rating", "Avg Rating Distribution", 20),
                (d3, "time_span_days", "Active Span (days)", 30),
            ]
            for _col, _x, _title, _nbins in _hist_specs:
                _fig_h = px.histogram(
                    segment_df,
                    x=_x,
                    title=_title,
                    nbins=_nbins,
                    color_discrete_sequence=[PALETTE["accent"]],
                )
                _fig_h.update_traces(marker_line_width=0, opacity=0.9)
                style_plotly(_fig_h, showlegend=False, height=260)
                _col.plotly_chart(_fig_h, use_container_width=True)

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

    else:
        st.markdown(
            "Click **Run Segmentation Analysis** above to run user clustering. "
            "First run takes 30-90 seconds; subsequent loads are instant (cached)."
        )

# ===========================================================================
# Page 5 — Limitations
# ===========================================================================

elif page == "Limitations":
    render_page_header(
        title="Limitations",
        eyebrow="Methodology caveats",
        subtitle=(
            "Every number on this dashboard should be read in light of the scope "
            "constraints and interpretive choices documented below. "
            "Click any heading to expand."
        ),
    )

    # Page sentinel — lets styles.py scope the elevated expander styling to
    # this page only (via body:has()). Hidden so it doesn't take layout space.
    st.markdown(
        '<div class="ar-limitations-page" style="display:none"></div>',
        unsafe_allow_html=True,
    )

    _limitations = [
        (
            "90-day retention window",
            "Retention is defined as: *2+ reviews on 2+ distinct UTC days within 90 days "
            "of a user's first review in that category*. Longer-term loyalty patterns "
            "(e.g. annual repurchase cycles for software) are invisible to this definition.",
        ),
        (
            "Right-censoring cutoff (2023-04-02)",
            "The dataset ends 2023-07-01 UTC. Users whose first review in a category falls "
            "after **2023-04-02** cannot be observed for a full 90-day window, so they are "
            "excluded from both the numerator and denominator of retention rate. The "
            "per-category \"Right-Censored\" counts on the Category Detail page show how "
            "many users are dropped.",
        ),
        (
            "Top-quartile with N=4 is circular",
            "A category is labeled **high-retention** if its retention rate is in the top "
            "quartile of all 4 categories (and has at least 30 observable users). With "
            "N=4, the top quartile is the top 1 (or tied top 2) — so there is *always* at "
            "least one high-retention category by construction. Read \"high-retention\" as "
            "*\"stickiest among these four\"*, not as an absolute threshold.",
        ),
        (
            "Expansion differences are point estimates only",
            "`ExpansionDifference(A → B) = P(B | first = A) − P(B | first ≠ A)` is reported "
            "as a raw point estimate. There are no confidence intervals and no significance "
            "tests. Small positive/negative differences should not be over-interpreted.",
        ),
        (
            "Tied first-category timestamps excluded",
            "If a user's first reviews across multiple categories share the exact same "
            "timestamp, the user is excluded from expansion cohorts (their \"first "
            "category\" is ambiguous).",
        ),
        (
            "Review Synthesis runs on a stratified sample",
            "The deployed review-synthesis retrieval layer uses a **100K-point** Qdrant "
            "collection (25K per category), not the full 2.5M reviews. Rare phrases or "
            "long-tail products may be underrepresented. Embeddings are "
            "`all-MiniLM-L6-v2` (384-dim) — strong on general English but weak on domain "
            "jargon the model was not exposed to.",
        ),
        (
            "LLM synthesis is non-deterministic",
            "Gemini 2.5 Flash runs at temperature 0.3. Identical queries will produce "
            "similar but not byte-identical summaries. The LLM is also instructed to only "
            "cite the retrieved reviews — if it hallucinates content outside them, that "
            "is a failure mode, not an intended behavior.",
        ),
        (
            "K-means clustering uses heuristic segment labels",
            "`MiniBatchKMeans` chooses `k` by silhouette score on a 200K subsample. "
            "Cluster labels (e.g. \"Power reviewer\", \"One-and-done\") are heuristic "
            "names assigned after the fact based on profile thresholds in "
            "`ml/clustering.py` — they are interpretive, not ground-truth segments.",
        ),
        (
            "Dataset scope",
            "- **Categories**: Only 4 (Electronics, Video Games, Software, Cell Phones & "
            "Accessories). Findings do not generalize beyond these.\n"
            "- **verified_purchase = True** only. Unverified reviews are excluded.\n"
            "- **Date window**: Jan 1 – Jun 30, 2023. Seasonal or multi-year effects are "
            "not captured.",
        ),
    ]

    for _heading, _body in _limitations:
        with st.expander(_heading, expanded=False):
            st.markdown(_body)

    render_divider()
    st.markdown(
        "**Source.** Raw data from the "
        "[UCSD Amazon Reviews 2023](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023) "
        "dataset. See `docs/METRICS.md` and `docs/data_quality_report.md` in the repo for "
        "full definitions and filtering statistics."
    )
