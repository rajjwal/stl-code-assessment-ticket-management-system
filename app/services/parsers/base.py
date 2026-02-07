"""Abstract base class for all data parsers.

Each parser converts raw file bytes into a list of flat dictionaries,
regardless of the source format (CSV, JSON, YAML).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseParser(ABC):
    """Interface that all format-specific parsers must implement."""

    @abstractmethod
    def parse(self, content: bytes, filename: str) -> list[dict]:
        """Parse raw file content into a list of flat dictionaries.

        Args:
            content: Raw file bytes.
            filename: Original filename (used for format hints).

        Returns:
            List of dictionaries, one per record.

        Raises:
            ValueError: If content cannot be parsed.
        """
        ...
