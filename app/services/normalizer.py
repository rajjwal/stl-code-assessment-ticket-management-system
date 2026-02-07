"""Rule-based data normalizer for deterministic field cleanup.

Runs before and after AI steps to ensure consistent formatting.
Handles OS name canonicalization, status mapping, date parsing,
IP validation, and whitespace stripping.
"""

from __future__ import annotations

import re
from datetime import datetime

from dateutil import parser as dateutil_parser

# Canonical OS name mappings — keys are lowercase patterns
OS_NORMALIZATION_MAP = {
    "macos ventura": "macOS Ventura",
    "macos sonoma": "macOS Sonoma",
    "macos monterey": "macOS Monterey",
    "macos": "macOS",
    "ubuntu 22.04": "Ubuntu 22.04 LTS",
    "ubuntu 22": "Ubuntu 22.04 LTS",
    "ubuntu 20.04": "Ubuntu 20.04 LTS",
    "ubuntu": "Ubuntu",
    "windows 11": "Windows 11",
    "windows 10": "Windows 10",
    "win11": "Windows 11",
    "win10": "Windows 10",
}

# Valid canonical status values
VALID_STATUSES = {"active", "inactive", "deactivated", "suspended"}

# Simple IPv4 regex
IPV4_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)


def normalize_os(os_value: str | None) -> str | None:
    """Normalize OS names to canonical forms.

    Uses longest-match-first strategy: "macOS Ventura 13.5" matches
    "macos ventura" before "macos".
    """
    if not os_value or not os_value.strip():
        return None

    lower = os_value.strip().lower()

    # Try longest matches first to avoid "macos" matching before "macos ventura"
    for pattern in sorted(OS_NORMALIZATION_MAP.keys(), key=len, reverse=True):
        if lower.startswith(pattern):
            canonical = OS_NORMALIZATION_MAP[pattern]
            suffix = os_value.strip()[len(pattern):].strip()
            # Avoid duplicating words already in the canonical form
            # e.g., "Ubuntu 22.04 LTS" matches "ubuntu 22" → canonical "Ubuntu 22.04 LTS"
            # suffix would be ".04 LTS" but canonical already ends with "LTS"
            if suffix and not canonical.endswith(suffix):
                return f"{canonical} {suffix}"
            return canonical

    return os_value.strip()


def normalize_status(status: str | None) -> str | None:
    """Map status values to canonical lowercase set."""
    if not status:
        return status

    lower = status.strip().lower()

    if lower in VALID_STATUSES:
        return lower

    # Common aliases
    aliases = {
        "enabled": "active",
        "disabled": "inactive",
        "decommissioned": "deactivated",
    }
    return aliases.get(lower, lower)


def normalize_date(date_str: str | None) -> str | None:
    """Parse various date formats into ISO 8601 strings.

    Returns None for unparseable values rather than failing.
    """
    if not date_str or not date_str.strip():
        return None

    try:
        parsed = dateutil_parser.parse(date_str)
        return parsed.isoformat()
    except (ValueError, TypeError):
        return None


def validate_ip(ip: str | None) -> str | None:
    """Validate IPv4 address format. Returns None for invalid addresses."""
    if not ip:
        return ip

    ip = ip.strip()
    if IPV4_PATTERN.match(ip):
        return ip
    return None


def normalize_record(record: dict, source_type: str) -> dict:
    """Apply all normalizations to a single record.

    Args:
        record: Flat dictionary of field values.
        source_type: One of "hardware", "okta", "app" — determines which fields to normalize.

    Returns:
        New dictionary with normalized values.
    """
    normalized = {}

    for key, value in record.items():
        # Strip whitespace from all string values
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                value = None
        normalized[key] = value

    # Source-specific normalization
    if source_type == "hardware":
        if "os" in normalized:
            normalized["os"] = normalize_os(normalized["os"])
        if "status" in normalized:
            normalized["status"] = normalize_status(normalized["status"])
        if "ip_address" in normalized:
            normalized["ip_address"] = validate_ip(normalized["ip_address"])
        if "last_checkin" in normalized:
            normalized["last_checkin"] = normalize_date(normalized["last_checkin"])

    elif source_type == "okta":
        if "status" in normalized:
            normalized["status"] = normalize_status(normalized["status"])
        if "last_login" in normalized:
            normalized["last_login"] = normalize_date(normalized["last_login"])

    elif source_type == "app":
        # Normalize app_type to consistent casing
        if "app_type" in normalized and normalized["app_type"]:
            at = normalized["app_type"].lower()
            if at in ("saas", "cloud"):
                normalized["app_type"] = "SaaS"
            elif at in ("on-premise", "on-prem", "on_premise"):
                normalized["app_type"] = "on-premise"

    return normalized
