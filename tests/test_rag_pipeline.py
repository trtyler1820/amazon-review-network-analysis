"""
Tests for RAG pipeline components: payload formatting, stratified sampling,
and embedding dimension validation.
"""

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.index_qdrant import payload_from_row, EMBED_DIM, PAYLOAD_COLS


# -----------------------------------------------------------------------
# payload_from_row
# -----------------------------------------------------------------------

class TestPayloadFromRow:
    """Tests for the Qdrant payload builder."""

    def _base_row(self, **overrides):
        row = {
            "user_id": "U001",
            "parent_asin": "B09XYZ",
            "category_name": "Electronics",
            "rating": 4.0,
            "date": "2023-03-15T00:00:00",
            "retained": True,
            "observable": True,
            "first_category": "Electronics",
            "title": "Great product",
            "text": "Works perfectly fine.",
        }
        row.update(overrides)
        return row

    def test_all_fields_present(self):
        payload = payload_from_row(self._base_row())
        expected_keys = {
            "user_id", "parent_asin", "category_name", "rating",
            "date", "retained", "observable", "first_category",
            "title", "text",
        }
        assert set(payload.keys()) == expected_keys

    def test_values_pass_through(self):
        payload = payload_from_row(self._base_row())
        assert payload["user_id"] == "U001"
        assert payload["parent_asin"] == "B09XYZ"
        assert payload["category_name"] == "Electronics"
        assert payload["title"] == "Great product"
        assert payload["text"] == "Works perfectly fine."

    def test_rating_is_float(self):
        payload = payload_from_row(self._base_row(rating=5))
        assert isinstance(payload["rating"], float)
        assert payload["rating"] == 5.0

    def test_rating_none_stays_none(self):
        payload = payload_from_row(self._base_row(rating=None))
        assert payload["rating"] is None

    def test_retained_is_bool(self):
        payload = payload_from_row(self._base_row(retained=1))
        assert payload["retained"] is True

    def test_retained_none_stays_none(self):
        payload = payload_from_row(self._base_row(retained=None))
        assert payload["retained"] is None

    def test_observable_is_bool(self):
        payload = payload_from_row(self._base_row(observable=0))
        assert payload["observable"] is False

    def test_date_string_passes_through(self):
        payload = payload_from_row(self._base_row(date="2023-03-15T00:00:00"))
        assert payload["date"] == "2023-03-15T00:00:00"

    def test_date_datetime_converted_to_iso(self):
        dt = datetime(2023, 3, 15, 12, 30, 0, tzinfo=timezone.utc)
        payload = payload_from_row(self._base_row(date=dt))
        assert isinstance(payload["date"], str)
        assert "2023-03-15" in payload["date"]

    def test_date_none_stays_none(self):
        payload = payload_from_row(self._base_row(date=None))
        assert payload["date"] is None


# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------

class TestPipelineConstants:
    """Verify pipeline constants match expected values."""

    def test_embedding_dimension(self):
        assert EMBED_DIM == 384

    def test_payload_columns_count(self):
        assert len(PAYLOAD_COLS) == 10

    def test_payload_columns_include_essentials(self):
        for col in ("user_id", "parent_asin", "category_name", "rating",
                     "retained", "text", "title"):
            assert col in PAYLOAD_COLS, f"{col} missing from PAYLOAD_COLS"


# -----------------------------------------------------------------------
# Stratified sampling (via polars, mirrors index_qdrant logic)
# -----------------------------------------------------------------------

class TestStratifiedSampling:
    """Test that stratified sampling produces correct category distribution."""

    @pytest.fixture
    def sample_df(self):
        import polars as pl
        rows = []
        cats = ["Electronics", "Video_Games", "Software", "Cell_Phones_and_Accessories"]
        sizes = [200, 100, 30, 150]
        for cat, size in zip(cats, sizes):
            for i in range(size):
                rows.append({
                    "point_id": len(rows),
                    "category_name": cat,
                    "embedding": [0.0] * 384,
                    "user_id": f"u{len(rows)}",
                    "parent_asin": f"P{len(rows)}",
                    "rating": 4.0,
                    "date": "2023-03-15",
                    "retained": True,
                    "observable": True,
                    "first_category": cat,
                    "title": "title",
                    "text": "text",
                })
        return pl.DataFrame(rows)

    def test_equal_allocation(self, sample_df):
        import polars as pl
        target = 100
        cats = sample_df["category_name"].unique().to_list()
        n_per_cat = target // len(cats)  # 25

        sampled_frames = []
        for cat in sorted(cats):
            cat_df = sample_df.filter(pl.col("category_name") == cat)
            n = min(n_per_cat, cat_df.height)
            sampled_frames.append(cat_df.sample(n=n, seed=42))
        result = pl.concat(sampled_frames)

        assert result.height == 100

    def test_category_counts_equal(self, sample_df):
        import polars as pl
        target = 100
        cats = sample_df["category_name"].unique().to_list()
        n_per_cat = target // len(cats)

        sampled_frames = []
        for cat in sorted(cats):
            cat_df = sample_df.filter(pl.col("category_name") == cat)
            n = min(n_per_cat, cat_df.height)
            sampled_frames.append(cat_df.sample(n=n, seed=42))
        result = pl.concat(sampled_frames)

        counts = result.group_by("category_name").agg(pl.len().alias("count"))
        for row in counts.to_dicts():
            assert row["count"] == 25

    def test_small_category_capped(self, sample_df):
        """When a category has fewer rows than n_per_cat, take all of them."""
        import polars as pl
        target = 200
        cats = sample_df["category_name"].unique().to_list()
        n_per_cat = target // len(cats)  # 50

        sampled_frames = []
        for cat in sorted(cats):
            cat_df = sample_df.filter(pl.col("category_name") == cat)
            n = min(n_per_cat, cat_df.height)
            sampled_frames.append(cat_df.sample(n=n, seed=42))
        result = pl.concat(sampled_frames)

        # Software only has 30 rows, so it should be capped at 30
        software_count = result.filter(
            pl.col("category_name") == "Software"
        ).height
        assert software_count == 30

    def test_deterministic_with_seed(self, sample_df):
        import polars as pl
        target = 100
        cats = sorted(sample_df["category_name"].unique().to_list())
        n_per_cat = target // len(cats)

        def do_sample():
            frames = []
            for cat in cats:
                cat_df = sample_df.filter(pl.col("category_name") == cat)
                n = min(n_per_cat, cat_df.height)
                frames.append(cat_df.sample(n=n, seed=42))
            return pl.concat(frames)

        r1 = do_sample()
        r2 = do_sample()
        assert r1["point_id"].to_list() == r2["point_id"].to_list()
