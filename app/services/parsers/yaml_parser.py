"""YAML format parser.

Handles deeply nested YAML structures (like IT asset management exports)
by traversing to find the item list and flattening nested fields into
a flat dictionary suitable for downstream processing.
"""

from __future__ import annotations

import yaml

from app.services.parsers.base import BaseParser


class YAMLParser(BaseParser):
    """Parses YAML files and flattens nested structures into flat dicts."""

    def parse(self, content: bytes, filename: str) -> list[dict]:
        """Parse YAML bytes, find the record list, and flatten each record."""
        data = yaml.safe_load(content.decode("utf-8"))

        if isinstance(data, list):
            return [self._flatten_record(r) for r in data]

        if isinstance(data, dict):
            records = self._find_record_list(data)
            if records is not None:
                return [self._flatten_record(r) for r in records]
            raise ValueError("Could not find a list of records in YAML structure")

        raise ValueError(f"Unexpected YAML top-level type: {type(data).__name__}")

    def _find_record_list(self, data: dict, depth: int = 0) -> list | None:
        """Recursively search for the first list of dicts in the YAML tree.

        Traverses up to 3 levels deep to find arrays like
        inventory.devices or data.items.
        """
        if depth > 3:
            return None
        for value in data.values():
            if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                return value
            if isinstance(value, dict):
                result = self._find_record_list(value, depth + 1)
                if result is not None:
                    return result
        return None

    def _flatten_record(self, record: dict) -> dict:
        """Flatten a deeply nested YAML record into a flat dictionary.

        Applies domain-specific flattening rules for known nested structures
        (assigned_to, operating_system, network, security, status, hardware, location).
        Unknown nested dicts are skipped to avoid polluting the output.
        """
        flat = {}

        for key, value in record.items():
            if not isinstance(value, dict):
                flat[key] = value
                continue

            # Domain-specific flattening for known nested structures
            if key == "assigned_to":
                flat["assigned_to"] = value.get("name")
                if value.get("email"):
                    flat["assigned_to_email"] = value["email"]
                if value.get("employee_id"):
                    flat["employee_id"] = value["employee_id"]
                if value.get("department"):
                    flat["department"] = value["department"]
                if value.get("title"):
                    flat["title"] = value["title"]
                if value.get("team"):
                    flat["team"] = value["team"]

            elif key == "operating_system":
                # Combine name + version into a single OS string
                os_name = value.get("name", "")
                os_version = value.get("version", "")
                flat["os"] = f"{os_name} {os_version}".strip() if os_name else os_version

            elif key == "network":
                if value.get("primary_ip"):
                    flat["ip_address"] = value["primary_ip"]
                if value.get("mac_address"):
                    flat["mac_address"] = value["mac_address"]

            elif key == "security":
                if value.get("encryption_type"):
                    flat["encryption_status"] = value["encryption_type"]
                elif value.get("encryption_enabled"):
                    flat["encryption_status"] = "enabled"

            elif key == "status":
                if value.get("operational_status"):
                    flat["status"] = value["operational_status"]
                if value.get("last_checkin"):
                    flat["last_checkin"] = value["last_checkin"]

            elif key == "hardware":
                if value.get("serial_number"):
                    flat["serial_number"] = value["serial_number"]
                if value.get("manufacturer"):
                    flat["manufacturer"] = value["manufacturer"]
                if value.get("model"):
                    flat["model"] = value["model"]

            elif key == "location":
                if value.get("site"):
                    flat["location"] = value["site"]

            # Other nested dicts are intentionally skipped (compliance, etc.)
            # to avoid noise in the flattened output

        return flat
