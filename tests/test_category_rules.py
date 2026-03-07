"""Tests for pure helper functions in pipeline/ai/category_rules.py."""
import pytest

from pipeline.ai.category_rules import normalize_merchant, _matches_merchant


class TestNormalizeMerchant:
    """normalize_merchant() strips transaction-specific noise."""

    def test_basic(self):
        assert normalize_merchant("STARBUCKS") == "starbucks"

    def test_store_number(self):
        assert normalize_merchant("STARBUCKS #12345") == "starbucks"

    def test_date_suffix(self):
        assert normalize_merchant("NETFLIX 01/15 PURCHASE") == "netflix"

    def test_long_reference(self):
        assert normalize_merchant("AMAZON MKTPLACE 1234567890") == "amazon mktplace"

    def test_state_abbreviation(self):
        assert normalize_merchant("WALGREENS STORE CA") == "walgreens store"

    def test_trailing_amount(self):
        assert normalize_merchant("UBER EATS 12.99") == "uber eats"

    def test_empty_string(self):
        assert normalize_merchant("") == ""

    def test_none_like_empty(self):
        # None is falsy, returns early
        assert normalize_merchant(None) == ""

    def test_whitespace_collapse(self):
        assert normalize_merchant("  COSTCO   WHOLESALE   ") == "costco wholesale"

    def test_lowercase(self):
        assert normalize_merchant("MiXeD CaSe") == "mixed case"

    def test_on_at_in_suffix(self):
        assert normalize_merchant("PAYMENT ON 2024-01-15") == "payment"


class TestMatchesMerchant:
    """_matches_merchant() checks pattern against normalized merchant."""

    def test_exact_match(self):
        assert _matches_merchant("starbucks", "starbucks") is True

    def test_prefix_match(self):
        assert _matches_merchant("starbucks", "starbucks coffee") is True

    def test_word_boundary_match(self):
        assert _matches_merchant("starbucks", "the starbucks store") is True

    def test_substring_no_match(self):
        """Should NOT match if pattern is substring within a word."""
        assert _matches_merchant("at", "national") is False

    def test_empty_pattern(self):
        assert _matches_merchant("", "starbucks") is False

    def test_empty_merchant(self):
        assert _matches_merchant("starbucks", "") is False

    def test_both_empty(self):
        assert _matches_merchant("", "") is False

    def test_pattern_at_end(self):
        assert _matches_merchant("coffee", "morning coffee") is True

    def test_no_match(self):
        assert _matches_merchant("starbucks", "dunkin donuts") is False

    def test_case_sensitive(self):
        """normalize_merchant lowercases, so patterns should be lowercase too."""
        assert _matches_merchant("starbucks", "Starbucks") is False  # Case matters in _matches_merchant

    def test_special_characters(self):
        """Regex metacharacters in pattern should be escaped."""
        assert _matches_merchant("a+b", "a+b store") is True
