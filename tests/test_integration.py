"""
Integration tests — require the full cleaned dataset (2.52M rows).

These tests are skipped until the full pipeline run completes tonight:
  python3 scripts/clean_data.py

To activate: remove the @pytest.mark.skip decorators and run:
  pytest tests/test_integration.py -v

What each test validates:
  - Row/user/product counts match DATA_QUALITY_REPORT.md after full run
  - Graph builds without errors on 2.52M rows
  - Category retention rates are within plausible bounds
  - Expansion pathways produce non-empty results
  - Manual spot-check: 5 real users' retention math (required by CLAUDE.md)
"""

import pytest
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_CSV = PROJECT_ROOT / "data" / "cleaned" / "cleaned_reviews.csv"

SKIP_REASON = (
    "Full dataset not yet available. "
    "Run `python3 scripts/clean_data.py` first, then remove @pytest.mark.skip."
)

EXPECTED_CATEGORIES = {
    "Electronics",
    "Video_Games",
    "Software",
    "Cell_Phones_and_Accessories",
}

# From DATA_QUALITY_REPORT.md (full run) — update after tonight's run if counts differ
EXPECTED_ROW_COUNT = 2_516_345
EXPECTED_USER_COUNT = 1_827_354
EXPECTED_PRODUCT_COUNT = 369_157


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cleaned_df():
    """Load the full cleaned CSV once for all integration tests."""
    return pd.read_csv(
        CLEANED_CSV,
        parse_dates=["date", "user_first_date"],
    )


@pytest.fixture(scope="module")
def graph(cleaned_df):
    from graph_logic.models import Graph
    return Graph.from_dataframe(cleaned_df)


# ---------------------------------------------------------------------------
# Dataset integrity
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason=SKIP_REASON)
def test_row_count_matches_report(cleaned_df):
    assert len(cleaned_df) == EXPECTED_ROW_COUNT, (
        f"Expected {EXPECTED_ROW_COUNT} rows, got {len(cleaned_df)}"
    )


@pytest.mark.skip(reason=SKIP_REASON)
def test_unique_users_match_report(cleaned_df):
    assert cleaned_df["user_id"].nunique() == EXPECTED_USER_COUNT


@pytest.mark.skip(reason=SKIP_REASON)
def test_unique_products_match_report(cleaned_df):
    assert cleaned_df["parent_asin"].nunique() == EXPECTED_PRODUCT_COUNT


@pytest.mark.skip(reason=SKIP_REASON)
def test_categories_are_exactly_four(cleaned_df):
    assert set(cleaned_df["category_name"].unique()) == EXPECTED_CATEGORIES


@pytest.mark.skip(reason=SKIP_REASON)
def test_no_nulls_in_required_columns(cleaned_df):
    required = [
        "user_id", "parent_asin", "timestamp", "date",
        "rating", "verified_purchase", "category_name",
        "user_first_date", "days_since_first", "review_sequence",
    ]
    for col in required:
        assert cleaned_df[col].isna().sum() == 0, f"Nulls found in {col}"


@pytest.mark.skip(reason=SKIP_REASON)
def test_verified_purchase_all_true(cleaned_df):
    assert cleaned_df["verified_purchase"].all()


@pytest.mark.skip(reason=SKIP_REASON)
def test_ratings_in_valid_range(cleaned_df):
    assert cleaned_df["rating"].between(1.0, 5.0).all()


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason=SKIP_REASON)
def test_graph_builds_without_error(graph):
    assert graph is not None


@pytest.mark.skip(reason=SKIP_REASON)
def test_graph_user_count_matches(graph):
    assert len(graph.users) == EXPECTED_USER_COUNT


@pytest.mark.skip(reason=SKIP_REASON)
def test_graph_categories_are_four(graph):
    assert set(graph.categories.keys()) == EXPECTED_CATEGORIES


@pytest.mark.skip(reason=SKIP_REASON)
def test_interaction_graph_has_edges(graph):
    assert graph.interaction_graph.number_of_edges() > 0


@pytest.mark.skip(reason=SKIP_REASON)
def test_transition_graph_has_nodes(graph):
    for cat in EXPECTED_CATEGORIES:
        assert cat in graph.transition_graph.nodes


# ---------------------------------------------------------------------------
# Retention rates (plausibility checks)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason=SKIP_REASON)
def test_retention_rates_between_zero_and_one(graph):
    for cat in graph.categories.values():
        rate = cat.retention_rate
        assert 0.0 <= rate <= 1.0, f"{cat.name} retention rate out of bounds: {rate}"


@pytest.mark.skip(reason=SKIP_REASON)
def test_high_retention_categories_nonempty(graph):
    from graph_logic.analysis import identify_high_retention_categories
    high_ret = identify_high_retention_categories(graph.categories)
    assert len(high_ret) > 0, "No high-retention categories found — check min_users threshold"


# ---------------------------------------------------------------------------
# Expansion pathways
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason=SKIP_REASON)
def test_expansion_pathways_nonempty(graph):
    from graph_logic.analysis import (
        identify_high_retention_categories,
        compute_all_expansion_pathways,
    )
    high_ret = identify_high_retention_categories(graph.categories)
    pathways = compute_all_expansion_pathways(graph.users, high_ret)
    assert len(pathways) > 0, "No expansion pathways computed"


# ---------------------------------------------------------------------------
# Manual spot-checks: 5 real users (required by CLAUDE.md)
# Populate SPOT_CHECK_USERS after the full run with actual user IDs from the CSV.
# ---------------------------------------------------------------------------

SPOT_CHECK_USERS: list = []
# Example format (fill in after full run):
# SPOT_CHECK_USERS = [
#     {
#         "user_id": "AEVPPTMG43C6GWSR7I2UGRQN7WFQ",
#         "category": "Electronics",
#         "expected_retained": True,
#     },
# ]


@pytest.mark.skip(reason=SKIP_REASON)
@pytest.mark.parametrize("case", SPOT_CHECK_USERS)
def test_retention_spot_check(graph, case):
    user = graph.users.get(case["user_id"])
    assert user is not None, f"User {case['user_id']} not found in graph"
    result = user.is_retained(case["category"])
    assert result == case["expected_retained"], (
        f"User {case['user_id']} in {case['category']}: "
        f"expected retained={case['expected_retained']}, got {result}"
    )
