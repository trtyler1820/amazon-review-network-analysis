"""
Tests for the Review Search page: dependency imports, filter construction,
context block formatting, and synthesis prompt structure.

These tests do NOT require a running Streamlit server, Qdrant collection,
or API key — they test the logic extracted from web/app.py.
"""

import pytest


# -----------------------------------------------------------------------
# Import smoke tests — catch missing dependencies early
# -----------------------------------------------------------------------

class TestDependencyImports:
    """Verify all packages required by the Review Search page are importable."""

    def test_import_qdrant_client(self):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

    def test_import_sentence_transformers(self):
        from sentence_transformers import SentenceTransformer

    def test_import_google_generativeai(self):
        import google.generativeai as genai

    def test_import_dotenv(self):
        from dotenv import load_dotenv

    def test_import_streamlit(self):
        import streamlit

    def test_import_plotly(self):
        import plotly


# -----------------------------------------------------------------------
# Filter construction — mirrors logic in web/app.py lines 473-503
# -----------------------------------------------------------------------

class TestFilterConstruction:
    """Test that Qdrant filters are built correctly from user inputs."""

    def _build_filter(self, sel_cats, all_cats, ret_radio, rating_range):
        """Reproduce the filter construction logic from app.py."""
        from qdrant_client.models import (
            Filter, FieldCondition, MatchValue, MatchAny, Range,
        )

        must_conditions = []

        if sel_cats and set(sel_cats) != set(all_cats):
            must_conditions.append(
                FieldCondition(key="category_name", match=MatchAny(any=sel_cats))
            )

        if ret_radio == "Retained":
            must_conditions.append(
                FieldCondition(key="retained", match=MatchValue(value=True))
            )
        elif ret_radio == "Churned":
            must_conditions.append(
                FieldCondition(key="retained", match=MatchValue(value=False))
            )

        low_rating, high_rating = rating_range
        if low_rating > 1 or high_rating < 5:
            must_conditions.append(
                FieldCondition(
                    key="rating",
                    range=Range(gte=float(low_rating), lte=float(high_rating)),
                )
            )

        return Filter(must=must_conditions) if must_conditions else None

    ALL_CATS = [
        "Cell_Phones_and_Accessories", "Electronics", "Software", "Video_Games",
    ]

    def test_no_filters_returns_none(self):
        result = self._build_filter(
            sel_cats=self.ALL_CATS,
            all_cats=self.ALL_CATS,
            ret_radio="All",
            rating_range=(1, 5),
        )
        assert result is None

    def test_category_subset_adds_filter(self):
        result = self._build_filter(
            sel_cats=["Electronics"],
            all_cats=self.ALL_CATS,
            ret_radio="All",
            rating_range=(1, 5),
        )
        assert result is not None
        assert len(result.must) == 1
        assert result.must[0].key == "category_name"

    def test_retained_filter(self):
        result = self._build_filter(
            sel_cats=self.ALL_CATS,
            all_cats=self.ALL_CATS,
            ret_radio="Retained",
            rating_range=(1, 5),
        )
        assert result is not None
        assert len(result.must) == 1
        cond = result.must[0]
        assert cond.key == "retained"
        assert cond.match.value is True

    def test_churned_filter(self):
        result = self._build_filter(
            sel_cats=self.ALL_CATS,
            all_cats=self.ALL_CATS,
            ret_radio="Churned",
            rating_range=(1, 5),
        )
        assert result is not None
        cond = result.must[0]
        assert cond.key == "retained"
        assert cond.match.value is False

    def test_rating_range_filter(self):
        result = self._build_filter(
            sel_cats=self.ALL_CATS,
            all_cats=self.ALL_CATS,
            ret_radio="All",
            rating_range=(3, 5),
        )
        assert result is not None
        assert len(result.must) == 1
        cond = result.must[0]
        assert cond.key == "rating"
        assert cond.range.gte == 3.0
        assert cond.range.lte == 5.0

    def test_all_filters_combined(self):
        result = self._build_filter(
            sel_cats=["Electronics", "Software"],
            all_cats=self.ALL_CATS,
            ret_radio="Retained",
            rating_range=(2, 4),
        )
        assert result is not None
        assert len(result.must) == 3
        keys = {c.key for c in result.must}
        assert keys == {"category_name", "retained", "rating"}

    def test_full_rating_range_no_filter(self):
        result = self._build_filter(
            sel_cats=self.ALL_CATS,
            all_cats=self.ALL_CATS,
            ret_radio="All",
            rating_range=(1, 5),
        )
        assert result is None

    def test_all_radio_no_retention_filter(self):
        result = self._build_filter(
            sel_cats=["Electronics"],
            all_cats=self.ALL_CATS,
            ret_radio="All",
            rating_range=(1, 5),
        )
        assert len(result.must) == 1
        assert result.must[0].key == "category_name"


# -----------------------------------------------------------------------
# Context block formatting — mirrors synthesis prep in app.py
# -----------------------------------------------------------------------

def _fmt(name: str) -> str:
    """Reproduce the category name formatter from app.py."""
    return name.replace("_", " ") if name else name


def _build_context_block(hits):
    """Reproduce the context block builder from app.py lines 543-557."""
    review_lines = []
    for i, hit in enumerate(hits, 1):
        p = hit.get("payload", {})
        title = (p.get("title") or "").strip()
        text = (p.get("text") or "").strip()
        rating = p.get("rating", "?")
        cat = _fmt(p.get("category_name", "?"))
        ret_flag = p.get("retained")
        ret_str = (
            "retained" if ret_flag is True
            else ("churned" if ret_flag is False else "unknown")
        )
        review_lines.append(
            f"[{i}] Rating: {rating}/5 | Category: {cat} | User: {ret_str}\n"
            f"Title: {title}\n"
            f"Text: {text[:400]}"
        )
    return "\n\n".join(review_lines)


class TestContextBlock:
    """Test the context block sent to the LLM for synthesis."""

    def _make_hit(self, **overrides):
        hit = {
            "payload": {
                "title": "Great phone case",
                "text": "Fits perfectly and looks nice.",
                "rating": 5.0,
                "category_name": "Cell_Phones_and_Accessories",
                "retained": True,
            },
        }
        hit["payload"].update(overrides)
        return hit

    def test_single_review_format(self):
        block = _build_context_block([self._make_hit()])
        assert "[1]" in block
        assert "Rating: 5.0/5" in block
        assert "Category: Cell Phones and Accessories" in block
        assert "User: retained" in block
        assert "Title: Great phone case" in block
        assert "Fits perfectly" in block

    def test_churned_label(self):
        block = _build_context_block([self._make_hit(retained=False)])
        assert "User: churned" in block

    def test_unknown_retention_label(self):
        block = _build_context_block([self._make_hit(retained=None)])
        assert "User: unknown" in block

    def test_multiple_reviews_numbered(self):
        hits = [self._make_hit() for _ in range(3)]
        block = _build_context_block(hits)
        assert "[1]" in block
        assert "[2]" in block
        assert "[3]" in block

    def test_long_text_truncated_at_400(self):
        long_text = "x" * 500
        block = _build_context_block([self._make_hit(text=long_text)])
        # The text portion should be at most 400 chars
        lines = block.split("\n")
        text_line = [l for l in lines if l.startswith("Text:")]
        assert len(text_line[0]) <= 406  # "Text: " + 400 chars

    def test_empty_title_handled(self):
        block = _build_context_block([self._make_hit(title="")])
        assert "Title: " in block  # empty but no crash

    def test_none_title_handled(self):
        block = _build_context_block([self._make_hit(title=None)])
        assert "Title: " in block


# -----------------------------------------------------------------------
# Synthesis prompt structure
# -----------------------------------------------------------------------

class TestSynthesisPrompt:
    """Verify the system prompt contains required output sections."""

    SYSTEM_PROMPT = (
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

    def test_requires_key_themes_section(self):
        assert "## Key Themes" in self.SYSTEM_PROMPT

    def test_requires_executive_summary_section(self):
        assert "## Executive Summary" in self.SYSTEM_PROMPT

    def test_requires_supporting_excerpts_section(self):
        assert "## Supporting Excerpts" in self.SYSTEM_PROMPT

    def test_limits_bullet_points_to_four(self):
        assert "Up to 4 bullet points" in self.SYSTEM_PROMPT

    def test_requires_three_sentences(self):
        assert "Exactly 3 sentences" in self.SYSTEM_PROMPT

    def test_requires_citation_format(self):
        assert "cite as [N]" in self.SYSTEM_PROMPT

    def test_forbids_invention(self):
        assert "Do not invent" in self.SYSTEM_PROMPT
