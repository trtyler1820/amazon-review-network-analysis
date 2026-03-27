"""
Core OOP classes for Amazon Reviews graph analysis.

Two-layer graph:
  Layer 1 (interaction): nodes = users + products, edges = reviews
  Layer 2 (transition):  nodes = categories, edges = user transitions between categories

Per-category semantics:
  - user_first_date in the CSV is computed per (user_id, category_name) during cleaning.
  - User.first_category (the global entry category) is computed here by scanning all
    reviews across all categories and finding the category of the earliest review.
  - If a user has identical earliest timestamps in two or more categories, first_category
    returns None and that user is excluded from expansion pathway denominators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx
import pandas as pd


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------

@dataclass
class Review:
    """A single verified Amazon review."""

    user_id: str
    parent_asin: str
    asin: str
    timestamp: int          # original millisecond Unix timestamp
    date: datetime          # UTC-aware datetime
    rating: float           # 1.0–5.0
    verified_purchase: bool # always True in cleaned data
    category_name: str
    helpful_vote: int


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User:
    """
    Represents a single Amazon reviewer.

    reviews_by_category stores lists sorted by date ascending.
    All date arithmetic uses UTC-aware datetimes.
    """

    def __init__(self, user_id: str) -> None:
        self.user_id: str = user_id
        self.reviews_by_category: Dict[str, List[Review]] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_review(self, review: Review) -> None:
        """Append review to appropriate category bucket (unsorted; sort on access)."""
        cat = review.category_name
        if cat not in self.reviews_by_category:
            self.reviews_by_category[cat] = []
        self.reviews_by_category[cat].append(review)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def all_reviews(self) -> List[Review]:
        """All reviews across all categories, sorted by date ascending."""
        reviews: List[Review] = []
        for bucket in self.reviews_by_category.values():
            reviews.extend(bucket)
        return sorted(reviews, key=lambda r: r.date)

    def reviews_in(self, category: str) -> List[Review]:
        """Reviews in a specific category, sorted by date ascending."""
        bucket = self.reviews_by_category.get(category, [])
        return sorted(bucket, key=lambda r: r.date)

    # ------------------------------------------------------------------
    # First category (global entry point across all 4 categories)
    # ------------------------------------------------------------------

    @property
    def first_category(self) -> Optional[str]:
        """
        The category of the user's earliest review across all categories.

        Returns None if:
          - The user has no reviews at all.
          - Two or more categories share the same earliest timestamp (tie).

        Tie-broken users are excluded from expansion pathway denominators.
        """
        earliest_date: Optional[datetime] = None
        earliest_cats: Set[str] = set()

        for cat, bucket in self.reviews_by_category.items():
            if not bucket:
                continue
            cat_min = min(r.date for r in bucket)
            if earliest_date is None or cat_min < earliest_date:
                earliest_date = cat_min
                earliest_cats = {cat}
            elif cat_min == earliest_date:
                earliest_cats.add(cat)

        if not earliest_cats or len(earliest_cats) > 1:
            return None
        return next(iter(earliest_cats))

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def is_retained(self, category: str, window_days: int = 90) -> bool:
        """
        True if the user is retained in `category`.

        Retention requires, within `window_days` of the user's first review in
        that category:
          - 2 or more reviews
          - on at least 2 distinct calendar days (UTC)

        A user with only 1 review in the category is never retained.
        The window is inclusive: ts <= first_ts + window_days * 24h.
        """
        reviews = self.reviews_in(category)
        if len(reviews) < 2:
            return False

        first_date = reviews[0].date
        cutoff = first_date + timedelta(days=window_days)

        in_window = [r for r in reviews if r.date <= cutoff]
        if len(in_window) < 2:
            return False

        distinct_days: Set[Tuple[int, int, int]] = set()
        for r in in_window:
            utc_date = r.date.astimezone(timezone.utc)
            distinct_days.add((utc_date.year, utc_date.month, utc_date.day))

        return len(distinct_days) >= 2

    # ------------------------------------------------------------------
    # Expansion helper
    # ------------------------------------------------------------------

    def reviewed_category_within(
        self,
        category: str,
        after: datetime,
        within_days: int = 90,
    ) -> bool:
        """
        True if this user has at least one review in `category` such that
        after <= review.date <= after + within_days * 24h.

        Used for expansion pathway analysis: `after` is the user's global
        first-review date (entry point across all categories).
        """
        cutoff = after + timedelta(days=within_days)
        for r in self.reviews_by_category.get(category, []):
            if after <= r.date <= cutoff:
                return True
        return False

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        n = sum(len(b) for b in self.reviews_by_category.values())
        cats = list(self.reviews_by_category.keys())
        return f"User(id={self.user_id!r}, reviews={n}, categories={cats})"


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

class Category:
    """
    Represents one of the 4 product categories.

    `users` contains every user who has at least one review in this category.
    Retention is computed lazily via User.is_retained().
    """

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.users: Dict[str, User] = {}

    def add_user(self, user: User) -> None:
        """Register a user as having reviewed in this category."""
        self.users[user.user_id] = user

    @property
    def entering_user_count(self) -> int:
        """Number of users who reviewed in this category."""
        return len(self.users)

    @property
    def retention_rate(self) -> float:
        """
        Fraction of users retained in this category.

        Returns 0.0 if there are no users (avoids ZeroDivisionError).
        """
        if not self.users:
            return 0.0
        retained = sum(
            1 for u in self.users.values() if u.is_retained(self.name)
        )
        return retained / len(self.users)

    def __repr__(self) -> str:
        return (
            f"Category(name={self.name!r}, users={self.entering_user_count}, "
            f"retention={self.retention_rate:.2%})"
        )


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class Graph:
    """
    Two-layer directed graph over Amazon review data.

    Layer 1 — User-Product Interaction Graph (interaction_graph):
      Nodes: user IDs (type='user') and parent_asin strings (type='product')
      Edges: user → product, attrs: timestamp, rating, category_name, helpful_vote

    Layer 2 — Category Transition Graph (transition_graph):
      Nodes: category names
      Edges: category_A → category_B when a user reviewed A before B,
             attrs: user_count (number of users making this transition)

    Build via Graph.from_dataframe(df) using the cleaned CSV DataFrame.
    """

    def __init__(self) -> None:
        self.users: Dict[str, User] = {}
        self.categories: Dict[str, Category] = {}
        self.interaction_graph: nx.DiGraph = nx.DiGraph()
        self.transition_graph: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> "Graph":
        """
        Build a Graph from the cleaned_reviews DataFrame.

        Expected columns (subset required):
          user_id, parent_asin, asin, timestamp, date, rating,
          verified_purchase, category_name, helpful_vote

        The `date` column must be a UTC-aware datetime (pd.Timestamp or datetime).
        """
        graph = cls()

        # --- Build User and Category objects ---
        for row in df.itertuples(index=False):
            uid = row.user_id
            cat_name = row.category_name

            # Ensure UTC-aware datetime
            raw_date = row.date
            if isinstance(raw_date, pd.Timestamp):
                date_utc: datetime = raw_date.to_pydatetime()
                if date_utc.tzinfo is None:
                    date_utc = date_utc.replace(tzinfo=timezone.utc)
            else:
                date_utc = raw_date
                if date_utc.tzinfo is None:
                    date_utc = date_utc.replace(tzinfo=timezone.utc)

            review = Review(
                user_id=uid,
                parent_asin=row.parent_asin,
                asin=row.asin,
                timestamp=int(row.timestamp),
                date=date_utc,
                rating=float(row.rating),
                verified_purchase=bool(row.verified_purchase),
                category_name=cat_name,
                helpful_vote=int(row.helpful_vote),
            )

            if uid not in graph.users:
                graph.users[uid] = User(uid)
            graph.users[uid].add_review(review)

            if cat_name not in graph.categories:
                graph.categories[cat_name] = Category(cat_name)

        # Register each user with every category they reviewed
        for user in graph.users.values():
            for cat_name in user.reviews_by_category:
                graph.categories[cat_name].add_user(user)

        graph._build_interaction_layer()
        graph._build_transition_layer()

        return graph

    # ------------------------------------------------------------------
    # Layer builders
    # ------------------------------------------------------------------

    def _build_interaction_layer(self) -> None:
        """
        Layer 1: user → product edges for every review.

        Node attributes:
          - type: 'user' | 'product'
        Edge attributes:
          - timestamp, rating, category_name, helpful_vote
        """
        for user in self.users.values():
            self.interaction_graph.add_node(user.user_id, type="user")
            for review in user.all_reviews():
                if not self.interaction_graph.has_node(review.parent_asin):
                    self.interaction_graph.add_node(
                        review.parent_asin, type="product"
                    )
                self.interaction_graph.add_edge(
                    user.user_id,
                    review.parent_asin,
                    timestamp=review.timestamp,
                    rating=review.rating,
                    category_name=review.category_name,
                    helpful_vote=review.helpful_vote,
                )

    def _build_transition_layer(self) -> None:
        """
        Layer 2: category → category transition edges.

        An edge A → B exists when at least one user reviewed a product in
        category A and later reviewed a product in category B (chronologically).
        Edge weight = number of distinct users making that transition.
        """
        for cat in self.categories:
            self.transition_graph.add_node(cat)

        # Count transitions per (A, B) pair
        transition_counts: Dict[Tuple[str, str], int] = {}

        for user in self.users.values():
            reviews = user.all_reviews()
            seen_cats: List[str] = []
            for review in reviews:
                cat = review.category_name
                for prior_cat in seen_cats:
                    if prior_cat != cat:
                        key = (prior_cat, cat)
                        transition_counts[key] = transition_counts.get(key, 0) + 1
                if cat not in seen_cats:
                    seen_cats.append(cat)

        for (src, dst), count in transition_counts.items():
            self.transition_graph.add_edge(src, dst, user_count=count)

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Graph("
            f"users={len(self.users)}, "
            f"categories={list(self.categories.keys())}, "
            f"interaction_nodes={self.interaction_graph.number_of_nodes()}, "
            f"interaction_edges={self.interaction_graph.number_of_edges()}, "
            f"transition_edges={self.transition_graph.number_of_edges()}"
            f")"
        )
