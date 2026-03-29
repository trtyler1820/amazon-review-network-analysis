"""
Shared pytest fixtures for the test suite.

Centralizes the make_review / make_user helpers that were previously
duplicated across test_models.py and test_analysis.py.
"""

from datetime import datetime, timedelta, timezone

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: integration tests requiring full dataset")

from graph_logic.models import Review, User


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


def make_user(user_id: str, reviews: list) -> User:
    """Create a User and add the provided Review objects."""
    user = User(user_id)
    for r in reviews:
        user.add_review(r)
    return user


@pytest.fixture
def base_date():
    return BASE_DATE


@pytest.fixture
def retained_user():
    """A user retained in Electronics (2 reviews, 2 distinct days, within 90d)."""
    return make_user("retained_u1", [
        make_review("retained_u1", "Electronics", day_offset=0),
        make_review("retained_u1", "Electronics", day_offset=15),
    ])


@pytest.fixture
def unretained_user():
    """A user NOT retained in Electronics (only 1 review)."""
    return make_user("unretained_u1", [
        make_review("unretained_u1", "Electronics", day_offset=0),
    ])
