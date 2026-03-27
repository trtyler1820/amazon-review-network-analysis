"""
Retention and expansion pathway analysis functions.

All formulas follow docs/METRICS.md exactly.

Key definitions:
  - Retention: user posts 2+ reviews on 2+ distinct UTC calendar days
    within 90 days of their first review in that category.
  - High-retention category: top quartile by retention_rate,
    with at least `min_users` entering users.
  - ExpansionDifference(A→B): P(B within 90d | first=A) − P(B within 90d | first≠A)
    where B is a high-retention category and A ≠ B.
    Users whose first_category is None (timestamp tie) are excluded from both cohorts.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, Optional, Set, Tuple

from .models import Category, Graph, User


# ---------------------------------------------------------------------------
# High-retention category identification
# ---------------------------------------------------------------------------

def identify_high_retention_categories(
    categories: Dict[str, Category],
    min_users: int = 30,
) -> Set[str]:
    """
    Return the set of category names in the top quartile by retention rate,
    restricted to categories with at least `min_users` entering users.

    With only 4 categories the 75th percentile is computed over a 4-element
    array; numpy.percentile with interpolation='midpoint' is used so the
    cutoff is always one of the observed values (no synthetic interpolation).

    Tie behavior: if multiple categories share the same retention rate at the
    Q75 boundary, all tied categories are included.

    Returns an empty set if no category meets the min_users threshold.
    """
    eligible = {
        name: cat
        for name, cat in categories.items()
        if cat.entering_user_count >= min_users
    }
    if not eligible:
        return set()

    rates = [cat.retention_rate for cat in eligible.values()]
    q75 = float(np.percentile(rates, 75, method="midpoint"))

    return {name for name, cat in eligible.items() if cat.retention_rate >= q75}


# ---------------------------------------------------------------------------
# Expansion pathway calculations
# ---------------------------------------------------------------------------

def compute_expansion_difference(
    entry_category: str,
    dest_category: str,
    all_users: Dict[str, User],
    window_days: int = 90,
) -> Optional[float]:
    """
    Compute ExpansionDifference(entry_category → dest_category).

    Formula (from docs/METRICS.md):
      P(B | first=A)  = users with first_cat=A who reviewed B within 90d of entry
                        / users with first_cat=A
      P(B | first≠A) = users with first_cat≠A who reviewed B within 90d of entry
                        / users with first_cat≠A

      ExpansionDifference = P(B | first=A) − P(B | first≠A)

    The "within 90d of entry" window is measured from the user's first-ever
    review date across all categories (not the category-specific first date).

    Returns None if:
      - entry_category == dest_category
      - either cohort (A or not-A) has zero eligible users
    """
    if entry_category == dest_category:
        return None

    cohort_a: list[User] = []
    cohort_not_a: list[User] = []

    for user in all_users.values():
        fc = user.first_category
        if fc is None:
            continue  # timestamp tie — excluded from both cohorts
        if fc == entry_category:
            cohort_a.append(user)
        else:
            cohort_not_a.append(user)

    if not cohort_a or not cohort_not_a:
        return None

    def _expansion_rate(cohort: list[User]) -> float:
        count = 0
        for user in cohort:
            # Entry date = earliest review across all categories
            entry_date = min(
                min(r.date for r in bucket)
                for bucket in user.reviews_by_category.values()
                if bucket
            )
            if user.reviewed_category_within(dest_category, entry_date, window_days):
                count += 1
        return count / len(cohort)

    p_a = _expansion_rate(cohort_a)
    p_not_a = _expansion_rate(cohort_not_a)
    return p_a - p_not_a


def compute_all_expansion_pathways(
    all_users: Dict[str, User],
    high_retention_categories: Set[str],
    window_days: int = 90,
) -> Dict[Tuple[str, str], float]:
    """
    Compute ExpansionDifference for all (A, B) pairs where B is high-retention
    and A ≠ B.

    Returns a dict mapping (entry_category, dest_category) → expansion_difference.
    Pairs where compute_expansion_difference returns None are omitted.
    """
    # Collect all category names present across users
    all_cats: Set[str] = set()
    for user in all_users.values():
        all_cats.update(user.reviews_by_category.keys())

    results: Dict[Tuple[str, str], float] = {}
    for entry_cat in all_cats:
        for dest_cat in high_retention_categories:
            if entry_cat == dest_cat:
                continue
            diff = compute_expansion_difference(
                entry_cat, dest_cat, all_users, window_days
            )
            if diff is not None:
                results[(entry_cat, dest_cat)] = diff

    return results


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

def generate_summary_report(graph: Graph) -> str:
    """
    Generate a human-readable summary of retention rates and expansion pathways.

    Output sections:
      1. Category retention rates (sorted descending)
      2. High-retention categories
      3. Top expansion pathways (sorted by ExpansionDifference descending)
    """
    lines: list[str] = []

    # --- Section 1: Retention rates ---
    lines.append("=" * 60)
    lines.append("RETENTION RATES BY CATEGORY")
    lines.append("=" * 60)
    sorted_cats = sorted(
        graph.categories.items(),
        key=lambda kv: kv[1].retention_rate,
        reverse=True,
    )
    for name, cat in sorted_cats:
        lines.append(
            f"  {name:<35} {cat.retention_rate:>6.2%}  ({cat.entering_user_count} users)"
        )

    # --- Section 2: High-retention categories ---
    lines.append("")
    lines.append("=" * 60)
    lines.append("HIGH-RETENTION CATEGORIES (top quartile, ≥30 users)")
    lines.append("=" * 60)
    high_ret = identify_high_retention_categories(graph.categories)
    if high_ret:
        for name in sorted(high_ret):
            cat = graph.categories[name]
            lines.append(f"  * {name}  ({cat.retention_rate:.2%})")
    else:
        lines.append("  (none — no category meets the minimum user threshold)")

    # --- Section 3: Expansion pathways ---
    lines.append("")
    lines.append("=" * 60)
    lines.append("EXPANSION PATHWAYS  (A → B where B is high-retention)")
    lines.append("=" * 60)
    pathways = compute_all_expansion_pathways(graph.users, high_ret)
    if pathways:
        sorted_pathways = sorted(pathways.items(), key=lambda kv: kv[1], reverse=True)
        for (entry, dest), diff in sorted_pathways:
            direction = "+" if diff >= 0 else ""
            lines.append(
                f"  {entry:<35} → {dest:<35}  {direction}{diff:.2%}"
            )
    else:
        lines.append("  (no pathways computed — check high-retention set and cohort sizes)")

    lines.append("")
    return "\n".join(lines)
