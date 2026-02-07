"""Auto-detects file format and source type from content and filename.

Format detection uses file extension first, then content sniffing as fallback.
Source type detection inspects field names in the parsed data to classify
as hardware, okta (user), or application data.
"""

from __future__ import annotations

import csv
import io
import json

import yaml


def detect_format(content: bytes, filename: str) -> str:
    """Detect file format from extension and content sniffing.

    Returns:
        One of "csv", "json", "yaml".

    Raises:
        ValueError: If format cannot be determined.
    """
    lower = filename.lower()

    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith(".json"):
        return "json"
    if lower.endswith((".yaml", ".yml")):
        return "yaml"

    # Fallback: try parsing as each format
    text = content.decode("utf-8-sig").strip()

    if text.startswith(("{", "[")):
        try:
            json.loads(text)
            return "json"
        except json.JSONDecodeError:
            pass

    try:
        data = yaml.safe_load(text)
        if isinstance(data, (dict, list)):
            return "yaml"
    except yaml.YAMLError:
        pass

    try:
        dialect = csv.Sniffer().sniff(text[:4096])
        # Only accept common CSV delimiters to avoid false positives
        if dialect.delimiter in (",", ";", "\t", "|"):
            return "csv"
    except csv.Error:
        pass

    raise ValueError(f"Cannot determine format for file: {filename}")


def detect_source_type(records: list[dict]) -> str:
    """Detect the source type by inspecting field names in parsed records.

    Examines the keys of the first record to classify the data source.

    Returns:
        One of "hardware", "okta", "app".

    Raises:
        ValueError: If source type cannot be determined.
    """
    if not records:
        raise ValueError("Cannot detect source type from empty records")

    # Collect all keys across first few records for robustness
    all_keys = set()
    for record in records[:3]:
        all_keys.update(k.lower() for k in record.keys())

    # Hardware indicators: device-specific fields
    hardware_indicators = {"device_id", "hostname", "mac_address", "serial_number", "device_type"}
    if all_keys & hardware_indicators:
        return "hardware"

    # Okta/user indicators: identity-specific fields
    okta_indicators = {"user_id", "mfa_enabled", "last_login", "groups"}
    if all_keys & okta_indicators:
        return "okta"

    # App indicators: application-specific fields
    app_indicators = {"app_id", "vendor", "app_type", "sso_enabled", "deployment"}
    if all_keys & app_indicators:
        return "app"

    raise ValueError(
        f"Cannot determine source type from fields: {sorted(all_keys)}"
    )
