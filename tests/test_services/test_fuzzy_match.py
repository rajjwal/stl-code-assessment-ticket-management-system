"""Tests for fuzzy string matching utility."""

from __future__ import annotations

from app.utils.fuzzy_match import best_match


class TestExactMatch:
    """Tier 1: exact string matching."""

    def test_exact_match(self):
        assert best_match("Sarah Chen", ["Sarah Chen", "John Doe"]) == "Sarah Chen"

    def test_exact_match_first_occurrence(self):
        assert best_match("Slack", ["Slack", "GitHub"]) == "Slack"


class TestCaseInsensitiveMatch:
    """Tier 2: case-insensitive matching."""

    def test_case_insensitive(self):
        assert best_match("john doe", ["John Doe", "Jane Doe"]) == "John Doe"

    def test_uppercase_needle(self):
        assert best_match("SLACK", ["Slack", "GitHub"]) == "Slack"


class TestSubstringMatch:
    """Tier 3: substring containment matching."""

    def test_needle_in_candidate(self):
        """'GitHub' is a substring of 'GitHub Enterprise'."""
        assert best_match("GitHub", ["GitHub Enterprise", "Slack"]) == "GitHub Enterprise"

    def test_candidate_in_needle(self):
        """'Slack' is a substring of 'Slack App'."""
        assert best_match("Slack App", ["Slack", "GitHub"]) == "Slack"


class TestFuzzyRatioMatch:
    """Tier 4: ratio-based fuzzy matching."""

    def test_john_d_matches_john_doe(self):
        """Abbreviated name should match full name."""
        result = best_match("John D.", ["John Doe", "Jane Doe", "Carlos S."])
        assert result == "John Doe"

    def test_carlos_s_matches_carlos_santos(self):
        result = best_match("Carlos S.", ["Carlos Santos", "Sarah Chen"])
        assert result == "Carlos Santos"


class TestNoMatch:
    """Cases where no match should be found."""

    def test_random_name_no_match(self):
        result = best_match("Random Person", ["John Doe", "Jane Doe"])
        assert result is None

    def test_empty_haystack(self):
        assert best_match("John", []) is None

    def test_empty_needle(self):
        assert best_match("", ["John Doe"]) is None

    def test_none_needle(self):
        assert best_match(None, ["John Doe"]) is None

    def test_none_haystack(self):
        assert best_match("John", None) is None


class TestThreshold:
    """Custom threshold behavior."""

    def test_high_threshold_rejects_weak_match(self):
        result = best_match("X", ["ABCDEFG"], threshold=0.9)
        assert result is None

    def test_low_threshold_accepts_weak_match(self):
        result = best_match("John", ["Johan"], threshold=0.5)
        assert result == "Johan"


class TestWhitespace:
    """Whitespace handling."""

    def test_stripped_matching(self):
        assert best_match("  Slack  ", ["Slack"]) == "Slack"

    def test_whitespace_only_returns_none(self):
        assert best_match("   ", ["Slack"]) is None
