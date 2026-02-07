"""CSV format parser.

Handles hardware inventory CSV exports with DictReader.
Strips BOM markers and normalizes field names.
"""

from __future__ import annotations

import csv
import io

from app.services.parsers.base import BaseParser


class CSVParser(BaseParser):
    """Parses CSV files into a list of flat dictionaries."""

    def parse(self, content: bytes, filename: str) -> list[dict]:
        """Parse CSV bytes into records.

        Handles UTF-8 BOM markers and strips whitespace from headers and values.
        """
        text = content.decode("utf-8-sig")  # utf-8-sig strips BOM if present
        reader = csv.DictReader(io.StringIO(text))
        records = []
        for row in reader:
            # Strip whitespace from keys and values
            clean = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}
            records.append(clean)
        return records
