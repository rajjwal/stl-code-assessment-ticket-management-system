"""Fuzzy string matching utility for cross-source entity resolution.

Uses stdlib difflib.SequenceMatcher to link entities across data sources
(e.g., "John D." in hardware CSV → "John Doe" in Okta). The matching
strategy is tiered: exact → case-insensitive → substring → ratio-based.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Optional


def best_match(
    needle: str,
    haystack: list[str],
    threshold: float = 0.6,
) -> Optional[str]:
    """Find the best fuzzy match for needle in haystack.

    Matching tiers (returns on first hit):
    1. Exact match
    2. Case-insensitive exact match
    3. Substring containment (either direction)
    4. Highest SequenceMatcher ratio above threshold

    Args:
        needle: The string to match.
        haystack: Candidate strings to match against.
        threshold: Minimum similarity ratio for fuzzy matches (0.0–1.0).

    Returns:
        The best matching string from haystack, or None if no match exceeds threshold.
    """
    if not needle or not haystack:
        return None

    needle_stripped = needle.strip()
    if not needle_stripped:
        return None

    needle_lower = needle_stripped.lower()

    # Tier 1: Exact match
    for candidate in haystack:
        if candidate.strip() == needle_stripped:
            return candidate

    # Tier 2: Case-insensitive exact match
    for candidate in haystack:
        if candidate.strip().lower() == needle_lower:
            return candidate

    # Tier 3: Substring containment (either direction)
    for candidate in haystack:
        candidate_lower = candidate.strip().lower()
        if needle_lower in candidate_lower or candidate_lower in needle_lower:
            return candidate

    # Tier 4: Ratio-based fuzzy match
    best_candidate = None
    best_ratio = threshold

    for candidate in haystack:
        ratio = SequenceMatcher(
            None, needle_lower, candidate.strip().lower()
        ).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_candidate = candidate

    return best_candidate
