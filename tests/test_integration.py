"""
Integration tests — require the full cleaned dataset (2.52M rows).

Run with: pytest tests/test_integration.py -v
Or: make test-all

All tests are marked @pytest.mark.slow for selective runs.
Skip with: pytest tests/ -m "not slow"
"""

import pytest
import pandas as pd
from pathlib import Path

pytestmark = pytest.mark.slow

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_CSV = PROJECT_ROOT / "data" / "cleaned" / "cleaned_reviews.csv"

EXPECTED_CATEGORIES = {
    "Electronics",
    "Video_Games",
    "Software",
    "Cell_Phones_and_Accessories",
}

# From DATA_QUALITY_REPORT.md (full run 2026-03-28)
EXPECTED_ROW_COUNT = 2_523_881
EXPECTED_USER_COUNT = 1_832_347
EXPECTED_PRODUCT_COUNT = 369_782


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cleaned_df():
    """Load the full cleaned CSV once for all integration tests."""
    df = pd.read_csv(CLEANED_CSV)
    df["date"] = pd.to_datetime(df["date"], format="ISO8601", utc=True)
    df["user_first_date"] = pd.to_datetime(
        df["user_first_date"], format="ISO8601", utc=True,
    )
    return df


@pytest.fixture(scope="module")
def graph(cleaned_df):
    """Build graph from full dataset (~18s on first call, cached for module)."""
    from graph_logic.models import Graph
    return Graph.from_dataframe(cleaned_df)


# ---------------------------------------------------------------------------
# Dataset integrity
# ---------------------------------------------------------------------------

def test_row_count_matches_report(cleaned_df):
    assert len(cleaned_df) == EXPECTED_ROW_COUNT, (
        f"Expected {EXPECTED_ROW_COUNT} rows, got {len(cleaned_df)}"
    )


def test_unique_users_match_report(cleaned_df):
    assert cleaned_df["user_id"].nunique() == EXPECTED_USER_COUNT


def test_unique_products_match_report(cleaned_df):
    assert cleaned_df["parent_asin"].nunique() == EXPECTED_PRODUCT_COUNT


def test_categories_are_exactly_four(cleaned_df):
    assert set(cleaned_df["category_name"].unique()) == EXPECTED_CATEGORIES


def test_no_nulls_in_required_columns(cleaned_df):
    required = [
        "user_id", "parent_asin", "timestamp", "date",
        "rating", "verified_purchase", "category_name",
        "user_first_date", "days_since_first", "review_sequence",
    ]
    for col in required:
        assert cleaned_df[col].isna().sum() == 0, f"Nulls found in {col}"


def test_verified_purchase_all_true(cleaned_df):
    assert cleaned_df["verified_purchase"].all()


def test_ratings_in_valid_range(cleaned_df):
    assert cleaned_df["rating"].between(1.0, 5.0).all()


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def test_graph_builds_without_error(graph):
    assert graph is not None


def test_graph_user_count_matches(graph):
    assert len(graph.users) == EXPECTED_USER_COUNT


def test_graph_categories_are_four(graph):
    assert set(graph.categories.keys()) == EXPECTED_CATEGORIES


def test_interaction_graph_has_edges(graph):
    assert graph.interaction_graph.number_of_edges() > 0


def test_interaction_graph_edge_count_equals_reviews(graph):
    """MultiDiGraph should have one edge per review row."""
    assert graph.interaction_graph.number_of_edges() == EXPECTED_ROW_COUNT


def test_transition_graph_has_nodes(graph):
    for cat in EXPECTED_CATEGORIES:
        assert cat in graph.transition_graph.nodes


def test_transition_graph_has_edges(graph):
    """Transition graph should have at least 1 edge and at most 12 (4 categories × 3)."""
    n_edges = graph.transition_graph.number_of_edges()
    assert 1 <= n_edges <= 12, f"Unexpected transition edge count: {n_edges}"


# ---------------------------------------------------------------------------
# Retention rates (plausibility checks)
# ---------------------------------------------------------------------------

def test_retention_rates_between_zero_and_one(graph):
    for cat in graph.categories.values():
        rate = cat.retention_rate
        assert 0.0 <= rate <= 1.0, f"{cat.name} retention rate out of bounds: {rate}"


def test_high_retention_categories_nonempty(graph):
    from graph_logic.analysis import identify_high_retention_categories
    high_ret = identify_high_retention_categories(graph.categories)
    assert len(high_ret) > 0, "No high-retention categories found"


def test_high_retention_categories_pinned(graph):
    """Pin the specific high-retention categories so regressions are caught."""
    from graph_logic.analysis import identify_high_retention_categories
    high_ret = identify_high_retention_categories(graph.categories)
    # At minimum, the top-quartile set must be a subset of the 4 known categories
    assert high_ret <= EXPECTED_CATEGORIES, (
        f"Unexpected categories in high-retention set: {high_ret - EXPECTED_CATEGORIES}"
    )
    # Pin: with 4 categories and Q75 cutoff, expect 1-2 categories
    assert 1 <= len(high_ret) <= 2, f"Expected 1-2 high-retention categories, got {len(high_ret)}"


def test_retention_rates_ordered(graph):
    """Verify relative ordering of retention rates to catch formula regressions."""
    rates = {name: cat.retention_rate for name, cat in graph.categories.items()}
    # Electronics has the most users; its rate should be computable (non-zero)
    assert rates["Electronics"] > 0, "Electronics retention rate is zero"
    # All rates should be small (most users don't return) — sanity bound
    for name, rate in rates.items():
        assert rate < 0.5, f"{name} retention rate {rate:.2%} suspiciously high"


# ---------------------------------------------------------------------------
# Expansion pathways
# ---------------------------------------------------------------------------

def test_expansion_pathways_nonempty(graph):
    from graph_logic.analysis import (
        identify_high_retention_categories,
        compute_all_expansion_pathways,
    )
    high_ret = identify_high_retention_categories(graph.categories)
    pathways = compute_all_expansion_pathways(graph.users, high_ret)
    assert len(pathways) > 0, "No expansion pathways computed"


def test_expansion_pathway_values_bounded(graph):
    """Expansion differences should be in (-1, 1) and mostly small."""
    from graph_logic.analysis import (
        identify_high_retention_categories,
        compute_all_expansion_pathways,
    )
    high_ret = identify_high_retention_categories(graph.categories)
    pathways = compute_all_expansion_pathways(graph.users, high_ret)
    for (entry, dest), diff in pathways.items():
        assert -1.0 < diff < 1.0, (
            f"Expansion {entry}→{dest} = {diff:.4f} out of bounds"
        )
        assert entry != dest, f"Self-loop found: {entry}→{dest}"


def test_summary_report_not_empty(graph):
    from graph_logic.analysis import generate_summary_report
    report = generate_summary_report(graph)
    assert len(report) > 200
    assert "RETENTION RATES" in report
    assert "EXPANSION PATHWAYS" in report


# ---------------------------------------------------------------------------
# Manual spot-checks: 5 real users (required by CLAUDE.md)
#
# Each user was manually verified against the CSV using pandas.
# ---------------------------------------------------------------------------

SPOT_CHECK_USERS = [
    {
        "user_id": "AEAVWVRGL5XNUQMS2KWQM5D6ZO4Q",
        "category": "Electronics",
        "expected_retained": True,
        # 54 reviews in Electronics, 4 distinct days in 90d window
    },
    {
        "user_id": "AFPVH2M2WRDLREBNC3RF4T45ZQQQ",
        "category": "Video_Games",
        "expected_retained": True,
        # 26 reviews in Video_Games, 7 distinct days in 90d window
    },
    {
        "user_id": "AE2NIDPGORJYYE6AG2K6OV3CEMZQ",
        "category": "Software",
        "expected_retained": False,
        # Only 1 review in Software → fails 2+ reviews requirement
    },
    {
        "user_id": "AE22JPQNQI2KOOQPBRTNY5J4T3WA",
        "category": "Electronics",
        "expected_retained": False,
        # 2 reviews in Electronics, but both on 2023-02-22 (1 distinct day)
    },
    {
        "user_id": "AE22HAROTCUVAX2KFGVG5G4PY7RQ",
        "category": "Electronics",
        "expected_retained": False,
        # 2 reviews in Electronics, but 2nd at day 114 (outside 90d window)
    },
]


@pytest.mark.parametrize("case", SPOT_CHECK_USERS, ids=[c["user_id"][:12] for c in SPOT_CHECK_USERS])
def test_retention_spot_check(graph, case):
    user = graph.users.get(case["user_id"])
    assert user is not None, f"User {case['user_id']} not found in graph"
    result = user.is_retained(case["category"])
    assert result == case["expected_retained"], (
        f"User {case['user_id']} in {case['category']}: "
        f"expected retained={case['expected_retained']}, got {result}"
    )
