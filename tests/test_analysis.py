"""
Unit tests for graph_logic/analysis.py.

All tests use synthetic fixtures built from controlled User objects.
The worked example from the plan (E→VG: 40% − 20% = 20%) is explicitly tested.
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import Dict

from graph_logic.models import Review, User, Category
from graph_logic.analysis import (
    identify_high_retention_categories,
    compute_expansion_difference,
    compute_all_expansion_pathways,
    generate_summary_report,
    Graph,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

BASE_DATE = datetime(2023, 1, 5, 0, 0, 0, tzinfo=timezone.utc)


def make_review(
    user_id: str,
    category: str,
    day_offset: int,
    parent_asin: str = "P1",
) -> Review:
    date = BASE_DATE + timedelta(days=day_offset)
    return Review(
        user_id=user_id,
        parent_asin=parent_asin,
        asin=parent_asin + "_v",
        timestamp=int(date.timestamp() * 1000),
        date=date,
        rating=5.0,
        verified_purchase=True,
        category_name=category,
        helpful_vote=0,
    )


def build_user(user_id: str, reviews: list) -> User:
    u = User(user_id)
    for r in reviews:
        u.add_review(r)
    return u


def make_retained_user(uid: str, cat: str) -> User:
    """User with 2 reviews on 2 distinct days → retained."""
    return build_user(uid, [
        make_review(uid, cat, day_offset=0),
        make_review(uid, cat, day_offset=15),
    ])


def make_unretained_user(uid: str, cat: str) -> User:
    """User with 1 review → not retained."""
    return build_user(uid, [
        make_review(uid, cat, day_offset=0),
    ])


def make_category_with_retention(
    name: str, retained_count: int, unretained_count: int
) -> Category:
    """Build a Category object populated with synthetic users."""
    cat = Category(name)
    for i in range(retained_count):
        u = make_retained_user(f"{name}_ret_{i}", name)
        cat.add_user(u)
    for i in range(unretained_count):
        u = make_unretained_user(f"{name}_unr_{i}", name)
        cat.add_user(u)
    return cat


# ---------------------------------------------------------------------------
# identify_high_retention_categories
# ---------------------------------------------------------------------------

class TestIdentifyHighRetentionCategories:
    def test_top_quartile_with_four_categories(self):
        # Retention rates: E=50%, VG=30%, SW=20%, CP=10%
        # np.percentile([10,20,30,50], 75, method="midpoint")
        #   = (rates[2] + rates[3]) / 2 = (30+50)/2 = 40
        # Only Electronics (50%) >= 40% → sole top-quartile category
        cats = {
            "Electronics": make_category_with_retention("Electronics", 5, 5),       # 50%
            "Video_Games": make_category_with_retention("Video_Games", 3, 7),        # 30%
            "Software": make_category_with_retention("Software", 2, 8),              # 20%
            "Cell_Phones": make_category_with_retention("Cell_Phones", 1, 9),        # 10%
        }
        result = identify_high_retention_categories(cats, min_users=10)
        assert "Electronics" in result
        assert "Video_Games" not in result
        assert "Software" not in result
        assert "Cell_Phones" not in result

    def test_min_users_filter(self):
        # Software has only 5 users (< 30 threshold); Electronics has exactly 30
        cats = {
            "Electronics": make_category_with_retention("Electronics", 24, 6),      # 80%, 30 users
            "Software": make_category_with_retention("Software", 3, 2),              # 60%, 5 users
        }
        result = identify_high_retention_categories(cats, min_users=30)
        # Software excluded due to min_users; Electronics is the only eligible → in result
        assert "Electronics" in result
        assert "Software" not in result

    def test_no_eligible_categories(self):
        # All categories below min_users threshold
        cats = {
            "Electronics": make_category_with_retention("Electronics", 1, 1),
        }
        result = identify_high_retention_categories(cats, min_users=30)
        assert result == set()

    def test_empty_categories(self):
        result = identify_high_retention_categories({}, min_users=30)
        assert result == set()

    def test_all_same_retention_rate(self):
        # All 4 categories have exactly the same rate → all qualify (all at Q75)
        cats = {
            "A": make_category_with_retention("A", 5, 5),
            "B": make_category_with_retention("B", 5, 5),
            "C": make_category_with_retention("C", 5, 5),
            "D": make_category_with_retention("D", 5, 5),
        }
        result = identify_high_retention_categories(cats, min_users=10)
        assert result == {"A", "B", "C", "D"}

    def test_min_users_uses_observable_count(self):
        """min_users threshold should use observable_user_count, not entering_user_count."""
        from graph_logic.models import MAX_ENTRY_DATE, Category
        late_offset = (MAX_ENTRY_DATE - BASE_DATE).days + 5

        # Category with 5 observable users + 30 unobservable late users
        cat = Category("Test")
        for i in range(5):
            cat.add_user(make_retained_user(f"obs_{i}", "Test"))
        for i in range(30):
            u = build_user(f"late_{i}", [
                make_review(f"late_{i}", "Test", day_offset=late_offset),
                make_review(f"late_{i}", "Test", day_offset=late_offset + 10),
            ])
            cat.add_user(u)

        # entering_user_count = 35, but observable = 5
        assert cat.entering_user_count == 35
        assert cat.observable_user_count() == 5

        # With min_users=10, this category should NOT qualify (only 5 observable)
        result = identify_high_retention_categories({"Test": cat}, min_users=10)
        assert result == set()


# ---------------------------------------------------------------------------
# compute_expansion_difference
# ---------------------------------------------------------------------------

class TestComputeExpansionDifference:
    def _build_user_pool(self) -> Dict[str, User]:
        """
        Worked example from plan:
          - 10 users with first_cat = "Electronics"
              4 of them reviewed "Video_Games" within 90d → P(VG|first=E) = 40%
          - 40 users with first_cat != "Electronics"
              8 of them reviewed "Video_Games" within 90d → P(VG|first≠E) = 20%
        ExpansionDifference(Electronics → Video_Games) = +20%
        """
        users: Dict[str, User] = {}

        # 10 Electronics-first users
        for i in range(10):
            uid = f"e_user_{i}"
            u = User(uid)
            u.add_review(make_review(uid, "Electronics", day_offset=0, parent_asin=f"E_P{i}"))
            if i < 4:
                # Also reviewed Video_Games within 90 days
                u.add_review(make_review(uid, "Video_Games", day_offset=30, parent_asin=f"VG_P{i}"))
            users[uid] = u

        # 40 non-Electronics-first users (Software-first)
        for i in range(40):
            uid = f"s_user_{i}"
            u = User(uid)
            u.add_review(make_review(uid, "Software", day_offset=0, parent_asin=f"SW_P{i}"))
            if i < 8:
                # Also reviewed Video_Games within 90 days
                u.add_review(make_review(uid, "Video_Games", day_offset=20, parent_asin=f"VG_SW_P{i}"))
            users[uid] = u

        return users

    def test_worked_example(self):
        users = self._build_user_pool()
        diff = compute_expansion_difference("Electronics", "Video_Games", users)
        assert diff is not None
        assert abs(diff - 0.20) < 1e-9

    def test_same_category_returns_none(self):
        users = self._build_user_pool()
        result = compute_expansion_difference("Electronics", "Electronics", users)
        assert result is None

    def test_empty_entry_cohort_returns_none(self):
        # No users with first_cat = "Cell_Phones"
        users = self._build_user_pool()
        result = compute_expansion_difference("Cell_Phones", "Video_Games", users)
        assert result is None

    def test_tie_users_excluded(self):
        # User with tie in first_category (first_category returns None) should be skipped
        users: Dict[str, User] = {}

        # Normal Electronics-first user
        uid_e = "e_user"
        u_e = User(uid_e)
        u_e.add_review(make_review(uid_e, "Electronics", day_offset=0))
        u_e.add_review(make_review(uid_e, "Video_Games", day_offset=5))
        users[uid_e] = u_e

        # Tie user (same timestamp in two categories)
        tie_date = BASE_DATE
        uid_tie = "tie_user"
        u_tie = User(uid_tie)
        r1 = Review(
            user_id=uid_tie, parent_asin="TP1", asin="TA1",
            timestamp=int(tie_date.timestamp() * 1000), date=tie_date,
            rating=5.0, verified_purchase=True, category_name="Electronics", helpful_vote=0
        )
        r2 = Review(
            user_id=uid_tie, parent_asin="TP2", asin="TA2",
            timestamp=int(tie_date.timestamp() * 1000), date=tie_date,
            rating=4.0, verified_purchase=True, category_name="Software", helpful_vote=0
        )
        u_tie.add_review(r1)
        u_tie.add_review(r2)
        users[uid_tie] = u_tie

        # Software-first baseline user (no VG)
        uid_s = "s_user"
        u_s = User(uid_s)
        u_s.add_review(make_review(uid_s, "Software", day_offset=0))
        users[uid_s] = u_s

        # Electronics cohort: 1 user, 1 reviewed VG → P(VG|E) = 1.0
        # Software cohort: 1 user, 0 reviewed VG → P(VG|S) = 0.0
        # diff = 1.0 - 0.0 = 1.0 (tie user excluded)
        diff = compute_expansion_difference("Electronics", "Video_Games", users)
        assert diff is not None
        assert abs(diff - 1.0) < 1e-9


    def test_right_censored_users_excluded_from_cohorts(self):
        """Users entering after MAX_ENTRY_DATE should be excluded from expansion."""
        from graph_logic.models import MAX_ENTRY_DATE
        late_offset = (MAX_ENTRY_DATE - BASE_DATE).days + 5

        users: Dict[str, User] = {}

        # Normal Electronics-first user (within window)
        uid_e = "e_user"
        u_e = User(uid_e)
        u_e.add_review(make_review(uid_e, "Electronics", day_offset=0))
        u_e.add_review(make_review(uid_e, "Video_Games", day_offset=5))
        users[uid_e] = u_e

        # Late entrant — should be excluded
        uid_late = "late_user"
        u_late = User(uid_late)
        u_late.add_review(make_review(uid_late, "Software", day_offset=late_offset))
        u_late.add_review(make_review(uid_late, "Video_Games", day_offset=late_offset + 10))
        users[uid_late] = u_late

        # Without the late user, only e_user exists: cohort_a=1 (E), cohort_not_a=0 → None
        diff = compute_expansion_difference("Electronics", "Video_Games", users)
        assert diff is None  # no not-A cohort after censoring

    def test_min_cohort_size_enforced(self):
        """If a cohort is smaller than min_cohort_size, return None."""
        users: Dict[str, User] = {}
        uid = "u1"
        u = User(uid)
        u.add_review(make_review(uid, "Electronics", day_offset=0))
        users[uid] = u

        uid2 = "u2"
        u2 = User(uid2)
        u2.add_review(make_review(uid2, "Software", day_offset=0))
        users[uid2] = u2

        # cohort_a=1 (Electronics), cohort_not_a=1 (Software), min_cohort=100 → None
        diff = compute_expansion_difference(
            "Electronics", "Video_Games", users, min_cohort_size=100,
        )
        assert diff is None


class TestComputeAllExpansionPathways:
    def test_returns_only_high_retention_destinations(self):
        # Set Video_Games as the only high-retention category
        users: Dict[str, User] = {}

        uid = "u1"
        u = User(uid)
        u.add_review(make_review(uid, "Electronics", day_offset=0))
        u.add_review(make_review(uid, "Video_Games", day_offset=10))
        users[uid] = u

        uid2 = "u2"
        u2 = User(uid2)
        u2.add_review(make_review(uid2, "Software", day_offset=0))
        users[uid2] = u2

        high_ret = {"Video_Games"}
        result = compute_all_expansion_pathways(users, high_ret)

        # All destination categories in result must be Video_Games
        for (entry, dest) in result:
            assert dest in high_ret
            assert entry != dest

    def test_no_self_loops(self):
        users: Dict[str, User] = {}
        uid = "u1"
        u = User(uid)
        u.add_review(make_review(uid, "Electronics", day_offset=0))
        users[uid] = u

        result = compute_all_expansion_pathways(users, {"Electronics"})
        for (entry, dest) in result:
            assert entry != dest

    def test_empty_high_retention_set(self):
        users: Dict[str, User] = {}
        uid = "u1"
        u = User(uid)
        u.add_review(make_review(uid, "Electronics", day_offset=0))
        users[uid] = u

        result = compute_all_expansion_pathways(users, set())
        assert result == {}


# ---------------------------------------------------------------------------
# generate_summary_report
# ---------------------------------------------------------------------------

class TestGenerateSummaryReport:
    def _make_graph(self):
        import pandas as pd
        rows = []
        for i in range(5):
            uid = f"u{i}"
            # All users: Electronics, first review day 0, second review day 10
            rows.append({
                "user_id": uid, "parent_asin": "P1", "asin": "A1",
                "timestamp": int(BASE_DATE.timestamp() * 1000),
                "date": BASE_DATE,
                "rating": 5.0, "verified_purchase": True,
                "category_name": "Electronics", "helpful_vote": 0,
            })
            rows.append({
                "user_id": uid, "parent_asin": "P2", "asin": "A2",
                "timestamp": int((BASE_DATE + timedelta(days=10)).timestamp() * 1000),
                "date": BASE_DATE + timedelta(days=10),
                "rating": 4.0, "verified_purchase": True,
                "category_name": "Electronics", "helpful_vote": 0,
            })
        df = pd.DataFrame(rows)
        return Graph.from_dataframe(df)

    def test_report_is_string(self):
        g = self._make_graph()
        report = generate_summary_report(g)
        assert isinstance(report, str)

    def test_report_contains_retention_section(self):
        g = self._make_graph()
        report = generate_summary_report(g)
        assert "RETENTION RATES" in report

    def test_report_contains_expansion_section(self):
        g = self._make_graph()
        report = generate_summary_report(g)
        assert "EXPANSION PATHWAYS" in report

    def test_report_contains_category_name(self):
        g = self._make_graph()
        report = generate_summary_report(g)
        assert "Electronics" in report

    def test_report_shows_observable_users(self):
        g = self._make_graph()
        report = generate_summary_report(g)
        assert "observable users" in report
