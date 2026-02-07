"""JSON format parser.

Handles two common JSON structures:
1. Top-level array of objects (e.g., sample_hardware.json, sample_okta.json)
2. Wrapper object containing an array (e.g., sample_app.json where records
   are under the "applications" key)
"""

from __future__ import annotations

import json

from app.services.parsers.base import BaseParser


class JSONParser(BaseParser):
    """Parses JSON files into a list of flat dictionaries."""

    def parse(self, content: bytes, filename: str) -> list[dict]:
        """Parse JSON bytes into records.

        Auto-detects whether the top-level structure is an array or an object.
        For objects, finds the first key whose value is a list of dicts.
        """
        data = json.loads(content.decode("utf-8-sig"))

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            # Search for the first key whose value is a list of dicts.
            # This handles wrapper formats like sample_app.json where
            # records live under "applications" alongside metadata keys.
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    return value

            raise ValueError(
                f"JSON object has no key containing a list of records. "
                f"Top-level keys: {list(data.keys())}"
            )

        raise ValueError(f"Unexpected JSON top-level type: {type(data).__name__}")
