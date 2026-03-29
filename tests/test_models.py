"""
Unit tests for graph_logic/models.py.

All tests use synthetic fixtures — no real data required.
make_review() is the primary fixture factory.
"""

import pytest
from datetime import datetime, timedelta, timezone

from graph_logic.models import Review, User, Category, Graph


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

BASE_DATE = datetime(2023, 1, 5, 12, 0, 0, tzinfo=timezone.utc)


def make_review(
    user_id: str = "user1",
    category: str = "Electronics",
    day_offset: int = 0,
    hour_offset: int = 0,
    parent_asin: str = "PASIN001",
    asin: str = "ASIN001",
    rating: float = 5.0,
) -> Review:
    """Create a Review with date = BASE_DATE + day_offset days + hour_offset hours."""
    date = BASE_DATE + timedelta(days=day_offset, hours=hour_offset)
    return Review(
        user_id=user_id,
        parent_asin=parent_asin,
        asin=asin,
        timestamp=int(date.timestamp() * 1000),
        date=date,
        rating=rating,
        verified_purchase=True,
        category_name=category,
        helpful_vote=0,
    )


def make_user_with_reviews(user_id: str, reviews: list) -> User:
    """Create a User and add the provided Review objects."""
    user = User(user_id)
    for r in reviews:
        user.add_review(r)
    return user


# ---------------------------------------------------------------------------
# Review dataclass
# ---------------------------------------------------------------------------

class TestReview:
    def test_fields_stored(self):
        r = make_review(user_id="u1", category="Electronics", day_offset=3)
        assert r.user_id == "u1"
        assert r.category_name == "Electronics"
        assert r.verified_purchase is True
        assert r.date == BASE_DATE + timedelta(days=3)

    def test_timestamp_is_int(self):
        r = make_review()
        assert isinstance(r.timestamp, int)


# ---------------------------------------------------------------------------
# User — add_review / all_reviews / reviews_in
# ---------------------------------------------------------------------------

class TestUserReviewAccess:
    def test_add_review_single(self):
        user = User("u1")
        r = make_review(user_id="u1", category="Electronics")
        user.add_review(r)
        assert len(user.reviews_by_category["Electronics"]) == 1

    def test_add_reviews_multiple_categories(self):
        user = User("u1")
        user.add_review(make_review(category="Electronics"))
        user.add_review(make_review(category="Video_Games"))
        assert set(user.reviews_by_category.keys()) == {"Electronics", "Video_Games"}

    def test_all_reviews_sorted(self):
        user = User("u1")
        user.add_review(make_review(category="Electronics", day_offset=5))
        user.add_review(make_review(category="Electronics", day_offset=1))
        user.add_review(make_review(category="Video_Games", day_offset=3))
        dates = [r.date for r in user.all_reviews()]
        assert dates == sorted(dates)

    def test_reviews_in_filters_category(self):
        user = User("u1")
        user.add_review(make_review(category="Electronics", day_offset=0))
        user.add_review(make_review(category="Video_Games", day_offset=1))
        assert len(user.reviews_in("Electronics")) == 1
        assert len(user.reviews_in("Video_Games")) == 1
        assert user.reviews_in("Software") == []

    def test_reviews_in_sorted(self):
        user = User("u1")
        user.add_review(make_review(category="Electronics", day_offset=10))
        user.add_review(make_review(category="Electronics", day_offset=2))
        dates = [r.date for r in user.reviews_in("Electronics")]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# User — first_category
# ---------------------------------------------------------------------------

class TestUserFirstCategory:
    def test_single_category(self):
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=0),
        ])
        assert user.first_category == "Electronics"

    def test_two_categories_clear_winner(self):
        # Electronics first (day 0), Video_Games later (day 5)
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=0),
            make_review(category="Video_Games", day_offset=5),
        ])
        assert user.first_category == "Electronics"

    def test_two_categories_clear_winner_reversed(self):
        # Video_Games first (day 0), Electronics later (day 3)
        user = make_user_with_reviews("u1", [
            make_review(category="Video_Games", day_offset=0),
            make_review(category="Electronics", day_offset=3),
        ])
        assert user.first_category == "Video_Games"

    def test_tie_returns_none(self):
        # Both categories share the same earliest timestamp — tie
        tie_date = BASE_DATE  # same date for both
        r1 = Review(
            user_id="u1", parent_asin="P1", asin="A1",
            timestamp=int(tie_date.timestamp() * 1000), date=tie_date,
            rating=5.0, verified_purchase=True,
            category_name="Electronics", helpful_vote=0,
        )
        r2 = Review(
            user_id="u1", parent_asin="P2", asin="A2",
            timestamp=int(tie_date.timestamp() * 1000), date=tie_date,
            rating=4.0, verified_purchase=True,
            category_name="Video_Games", helpful_vote=0,
        )
        user = make_user_with_reviews("u1", [r1, r2])
        assert user.first_category is None

    def test_no_reviews_returns_none(self):
        user = User("u1")
        assert user.first_category is None


# ---------------------------------------------------------------------------
# User — is_retained
# ---------------------------------------------------------------------------

class TestUserIsRetained:
    def test_retained_two_reviews_two_days(self):
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=0),
            make_review(category="Electronics", day_offset=10),
        ])
        assert user.is_retained("Electronics") is True

    def test_not_retained_single_review(self):
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=0),
        ])
        assert user.is_retained("Electronics") is False

    def test_not_retained_two_reviews_same_day(self):
        # Two reviews on the same calendar day — only 1 distinct day
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=0, hour_offset=0),
            make_review(category="Electronics", day_offset=0, hour_offset=4),
        ])
        assert user.is_retained("Electronics") is False

    def test_not_retained_second_review_day_91(self):
        # Second review is 1 day outside the window
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=0),
            make_review(category="Electronics", day_offset=91),
        ])
        assert user.is_retained("Electronics") is False

    def test_retained_second_review_exactly_day_90(self):
        # Exactly 90 days is inclusive
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=0),
            make_review(category="Electronics", day_offset=90),
        ])
        assert user.is_retained("Electronics") is True

    def test_retained_three_reviews_one_day_then_one_more(self):
        # Day 0: 3 reviews (count as 1 distinct day), Day 15: 1 review → retained
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=0, hour_offset=0),
            make_review(category="Electronics", day_offset=0, hour_offset=2),
            make_review(category="Electronics", day_offset=0, hour_offset=5),
            make_review(category="Electronics", day_offset=15),
        ])
        assert user.is_retained("Electronics") is True

    def test_per_category_semantics(self):
        # Retained in Electronics but not in Video_Games
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=0),
            make_review(category="Electronics", day_offset=15),
            make_review(category="Video_Games", day_offset=0),
            # No second Video_Games review within window
        ])
        assert user.is_retained("Electronics") is True
        assert user.is_retained("Video_Games") is False

    def test_not_retained_unknown_category(self):
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=0),
        ])
        assert user.is_retained("Software") is False

    def test_not_retained_reviews_only_after_window(self):
        # First review day 0, second review day 91 — only first is in window
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=0),
            make_review(category="Electronics", day_offset=91),
        ])
        assert user.is_retained("Electronics") is False

    def test_right_censored_user_excluded(self):
        # User enters after MAX_ENTRY_DATE → not retained (unobservable)
        from graph_logic.models import MAX_ENTRY_DATE
        late_offset = (MAX_ENTRY_DATE - BASE_DATE).days + 5  # 5 days past cutoff
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=late_offset),
            make_review(category="Electronics", day_offset=late_offset + 10),
        ])
        # With default max_entry_date, this user is excluded
        assert user.is_retained("Electronics") is False
        # With censoring disabled, this user IS retained
        assert user.is_retained("Electronics", max_entry_date=None) is True

    def test_user_before_censoring_cutoff_included(self):
        # User enters before MAX_ENTRY_DATE → normal retention logic applies
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=0),
            make_review(category="Electronics", day_offset=10),
        ])
        assert user.is_retained("Electronics") is True


# ---------------------------------------------------------------------------
# User — reviewed_category_within
# ---------------------------------------------------------------------------

class TestUserReviewedCategoryWithin:
    def test_true_when_review_in_window(self):
        user = make_user_with_reviews("u1", [
            make_review(category="Video_Games", day_offset=5),
        ])
        assert user.reviewed_category_within("Video_Games", BASE_DATE, 90) is True

    def test_false_when_no_review_in_category(self):
        user = make_user_with_reviews("u1", [
            make_review(category="Electronics", day_offset=5),
        ])
        assert user.reviewed_category_within("Video_Games", BASE_DATE, 90) is False

    def test_false_when_review_outside_window(self):
        user = make_user_with_reviews("u1", [
            make_review(category="Video_Games", day_offset=95),
        ])
        assert user.reviewed_category_within("Video_Games", BASE_DATE, 90) is False

    def test_true_at_exact_boundary(self):
        user = make_user_with_reviews("u1", [
            make_review(category="Video_Games", day_offset=90),
        ])
        assert user.reviewed_category_within("Video_Games", BASE_DATE, 90) is True

    def test_false_before_after_date(self):
        # Review is before `after` — should not count
        review_date = BASE_DATE - timedelta(days=1)
        r = Review(
            user_id="u1", parent_asin="P1", asin="A1",
            timestamp=int(review_date.timestamp() * 1000), date=review_date,
            rating=5.0, verified_purchase=True,
            category_name="Video_Games", helpful_vote=0,
        )
        user = make_user_with_reviews("u1", [r])
        assert user.reviewed_category_within("Video_Games", BASE_DATE, 90) is False


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

class TestCategory:
    def _make_retained_user(self, uid: str, cat: str = "Electronics") -> User:
        return make_user_with_reviews(uid, [
            make_review(user_id=uid, category=cat, day_offset=0),
            make_review(user_id=uid, category=cat, day_offset=10),
        ])

    def _make_unretained_user(self, uid: str, cat: str = "Electronics") -> User:
        return make_user_with_reviews(uid, [
            make_review(user_id=uid, category=cat, day_offset=0),
        ])

    def test_entering_user_count(self):
        cat = Category("Electronics")
        cat.add_user(User("u1"))
        cat.add_user(User("u2"))
        assert cat.entering_user_count == 2

    def test_retention_rate_two_of_three(self):
        cat = Category("Electronics")
        cat.add_user(self._make_retained_user("u1"))
        cat.add_user(self._make_retained_user("u2"))
        cat.add_user(self._make_unretained_user("u3"))
        assert abs(cat.retention_rate - 2 / 3) < 1e-9

    def test_retention_rate_zero_users(self):
        cat = Category("Electronics")
        assert cat.retention_rate == 0.0

    def test_retention_rate_all_retained(self):
        cat = Category("Electronics")
        cat.add_user(self._make_retained_user("u1"))
        cat.add_user(self._make_retained_user("u2"))
        assert cat.retention_rate == 1.0

    def test_retention_rate_none_retained(self):
        cat = Category("Electronics")
        cat.add_user(self._make_unretained_user("u1"))
        cat.add_user(self._make_unretained_user("u2"))
        assert cat.retention_rate == 0.0

    def test_observable_user_count_excludes_late_entrants(self):
        from graph_logic.models import MAX_ENTRY_DATE
        late_offset = (MAX_ENTRY_DATE - BASE_DATE).days + 5
        cat = Category("Electronics")
        # Observable user (enters within window)
        cat.add_user(self._make_retained_user("u1"))
        # Late user (enters after MAX_ENTRY_DATE)
        cat.add_user(make_user_with_reviews("u_late", [
            make_review(user_id="u_late", category="Electronics", day_offset=late_offset),
            make_review(user_id="u_late", category="Electronics", day_offset=late_offset + 10),
        ]))
        assert cat.entering_user_count == 2
        assert cat.observable_user_count() == 1

    def test_observable_user_count_none_disables_filter(self):
        cat = Category("Electronics")
        cat.add_user(self._make_retained_user("u1"))
        assert cat.observable_user_count(max_entry_date=None) == 1

    def test_retention_rate_excludes_unobservable_from_denominator(self):
        from graph_logic.models import MAX_ENTRY_DATE
        late_offset = (MAX_ENTRY_DATE - BASE_DATE).days + 5
        cat = Category("Electronics")
        # 1 retained observable user
        cat.add_user(self._make_retained_user("u1"))
        # 1 unobservable user (should NOT count in denominator)
        cat.add_user(make_user_with_reviews("u_late", [
            make_review(user_id="u_late", category="Electronics", day_offset=late_offset),
            make_review(user_id="u_late", category="Electronics", day_offset=late_offset + 10),
        ]))
        # Retention = 1/1 (not 1/2), because late user is excluded
        assert cat.retention_rate == 1.0

    def test_is_observable(self):
        from graph_logic.models import MAX_ENTRY_DATE
        late_offset = (MAX_ENTRY_DATE - BASE_DATE).days + 5
        # Observable
        u1 = make_user_with_reviews("u1", [
            make_review(user_id="u1", category="Electronics", day_offset=0),
        ])
        assert u1.is_observable("Electronics") is True
        # Not observable (late entry)
        u2 = make_user_with_reviews("u2", [
            make_review(user_id="u2", category="Electronics", day_offset=late_offset),
        ])
        assert u2.is_observable("Electronics") is False
        # Not observable (no reviews in category)
        assert u1.is_observable("Video_Games") is False

    def test_repr_does_not_crash(self):
        cat = Category("Electronics")
        assert "Electronics" in repr(cat)


# ---------------------------------------------------------------------------
# Graph — basic construction from small DataFrame
# ---------------------------------------------------------------------------

class TestGraphFromDataframe:
    def _make_df(self):
        import pandas as pd

        rows = [
            {
                "user_id": "u1",
                "parent_asin": "P1",
                "asin": "A1",
                "timestamp": int(BASE_DATE.timestamp() * 1000),
                "date": BASE_DATE,
                "rating": 5.0,
                "verified_purchase": True,
                "category_name": "Electronics",
                "helpful_vote": 0,
            },
            {
                "user_id": "u1",
                "parent_asin": "P2",
                "asin": "A2",
                "timestamp": int((BASE_DATE + timedelta(days=10)).timestamp() * 1000),
                "date": BASE_DATE + timedelta(days=10),
                "rating": 4.0,
                "verified_purchase": True,
                "category_name": "Electronics",
                "helpful_vote": 2,
            },
            {
                "user_id": "u2",
                "parent_asin": "P3",
                "asin": "A3",
                "timestamp": int((BASE_DATE + timedelta(days=5)).timestamp() * 1000),
                "date": BASE_DATE + timedelta(days=5),
                "rating": 3.0,
                "verified_purchase": True,
                "category_name": "Video_Games",
                "helpful_vote": 1,
            },
        ]
        return pd.DataFrame(rows)

    def test_users_loaded(self):
        df = self._make_df()
        g = Graph.from_dataframe(df)
        assert set(g.users.keys()) == {"u1", "u2"}

    def test_categories_loaded(self):
        df = self._make_df()
        g = Graph.from_dataframe(df)
        assert set(g.categories.keys()) == {"Electronics", "Video_Games"}

    def test_interaction_graph_nodes(self):
        df = self._make_df()
        g = Graph.from_dataframe(df)
        assert "u1" in g.interaction_graph.nodes
        assert "P1" in g.interaction_graph.nodes

    def test_interaction_graph_edges(self):
        df = self._make_df()
        g = Graph.from_dataframe(df)
        assert g.interaction_graph.has_edge("u1", "P1")
        assert g.interaction_graph.has_edge("u1", "P2")
        assert g.interaction_graph.has_edge("u2", "P3")

    def test_transition_graph_nodes(self):
        df = self._make_df()
        g = Graph.from_dataframe(df)
        assert "Electronics" in g.transition_graph.nodes
        assert "Video_Games" in g.transition_graph.nodes

    def test_transition_graph_counts_distinct_users(self):
        """User reviewing A→B→A→B should count as 1 user for (A,B) transition."""
        import pandas as pd
        rows = []
        for day, cat in [(0, "Electronics"), (5, "Video_Games"),
                         (10, "Electronics"), (15, "Video_Games")]:
            rows.append({
                "user_id": "u1", "parent_asin": f"P_{cat}_{day}",
                "asin": f"A_{cat}_{day}",
                "timestamp": int((BASE_DATE + timedelta(days=day)).timestamp() * 1000),
                "date": BASE_DATE + timedelta(days=day),
                "rating": 5.0, "verified_purchase": True,
                "category_name": cat, "helpful_vote": 0,
            })
        g = Graph.from_dataframe(pd.DataFrame(rows))
        edge_data = g.transition_graph.get_edge_data("Electronics", "Video_Games")
        assert edge_data is not None
        assert edge_data["user_count"] == 1  # distinct user, not event count

    def test_multigraph_preserves_duplicate_edges(self):
        """User reviewing the same product twice should produce 2 edges."""
        import pandas as pd
        rows = [
            {
                "user_id": "u1", "parent_asin": "P1", "asin": "A1",
                "timestamp": int(BASE_DATE.timestamp() * 1000),
                "date": BASE_DATE,
                "rating": 5.0, "verified_purchase": True,
                "category_name": "Electronics", "helpful_vote": 0,
            },
            {
                "user_id": "u1", "parent_asin": "P1", "asin": "A1",
                "timestamp": int((BASE_DATE + timedelta(days=10)).timestamp() * 1000),
                "date": BASE_DATE + timedelta(days=10),
                "rating": 3.0, "verified_purchase": True,
                "category_name": "Electronics", "helpful_vote": 1,
            },
        ]
        g = Graph.from_dataframe(pd.DataFrame(rows))
        # MultiDiGraph: 2 parallel edges from u1 → P1
        assert g.interaction_graph.number_of_edges() == 2

    def test_repr_does_not_crash(self):
        df = self._make_df()
        g = Graph.from_dataframe(df)
        assert "Graph(" in repr(g)
