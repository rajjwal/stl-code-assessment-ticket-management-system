"""Tests for rule-based data normalizer."""

from __future__ import annotations

from app.services.normalizer import (
    normalize_os,
    normalize_status,
    normalize_date,
    validate_ip,
    normalize_record,
)


class TestOSNormalization:
    """Tests for OS name canonicalization."""

    def test_lowercase_macos(self):
        assert normalize_os("macos") == "macOS"

    def test_macos_ventura(self):
        assert normalize_os("macOS Ventura") == "macOS Ventura"

    def test_macos_ventura_with_version(self):
        """Version suffix should be preserved after canonical name."""
        assert normalize_os("macOS Ventura 13.5") == "macOS Ventura 13.5"

    def test_ubuntu_short(self):
        assert normalize_os("Ubuntu 22") == "Ubuntu 22.04 LTS"

    def test_ubuntu_full(self):
        assert normalize_os("Ubuntu 22.04 LTS") == "Ubuntu 22.04 LTS"

    def test_windows_alias(self):
        assert normalize_os("win11") == "Windows 11"
        assert normalize_os("win10") == "Windows 10"

    def test_unknown_os_passthrough(self):
        """Unknown OS names should pass through stripped but unchanged."""
        assert normalize_os("FreeBSD 13") == "FreeBSD 13"

    def test_none_passthrough(self):
        assert normalize_os(None) is None

    def test_empty_string(self):
        assert normalize_os("") is None

    def test_whitespace_stripping(self):
        assert normalize_os("  macOS  ") == "macOS"


class TestStatusNormalization:
    """Tests for status value mapping."""

    def test_active_lowercase(self):
        assert normalize_status("active") == "active"

    def test_active_uppercase(self):
        assert normalize_status("ACTIVE") == "active"

    def test_active_mixed(self):
        assert normalize_status("Active") == "active"

    def test_deactivated(self):
        assert normalize_status("deactivated") == "deactivated"

    def test_suspended(self):
        assert normalize_status("SUSPENDED") == "suspended"

    def test_alias_enabled(self):
        assert normalize_status("enabled") == "active"

    def test_alias_disabled(self):
        assert normalize_status("disabled") == "inactive"

    def test_none_passthrough(self):
        assert normalize_status(None) is None

    def test_unknown_passthrough(self):
        """Unknown status values pass through lowercased."""
        assert normalize_status("PENDING") == "pending"


class TestDateNormalization:
    """Tests for date parsing to ISO 8601."""

    def test_iso_format(self):
        result = normalize_date("2024-07-22T10:00:00Z")
        assert "2024-07-22" in result

    def test_date_only(self):
        result = normalize_date("2024-07-22")
        assert "2024-07-22" in result

    def test_invalid_date(self):
        assert normalize_date("not-a-date") is None

    def test_none_passthrough(self):
        assert normalize_date(None) is None

    def test_empty_string(self):
        assert normalize_date("") is None


class TestIPValidation:
    """Tests for IPv4 address validation."""

    def test_valid_ip(self):
        assert validate_ip("10.10.22.5") == "10.10.22.5"

    def test_valid_ip_with_whitespace(self):
        assert validate_ip("  10.10.22.5  ") == "10.10.22.5"

    def test_invalid_ip(self):
        assert validate_ip("not-an-ip") is None

    def test_out_of_range(self):
        assert validate_ip("999.999.999.999") is None

    def test_none_passthrough(self):
        assert validate_ip(None) is None


class TestNormalizeRecord:
    """Tests for full record normalization by source type."""

    def test_hardware_record(self):
        record = {
            "device_id": "D-1",
            "hostname": "  laptop-test  ",
            "os": "macos",
            "status": "ACTIVE",
            "ip_address": "10.0.0.1",
            "last_checkin": "2024-07-22T10:00:00Z",
        }
        result = normalize_record(record, "hardware")
        assert result["hostname"] == "laptop-test"
        assert result["os"] == "macOS"
        assert result["status"] == "active"
        assert result["ip_address"] == "10.0.0.1"

    def test_okta_record(self):
        record = {
            "user_id": "u_1",
            "name": "Test User",
            "status": "ACTIVE",
            "last_login": "2024-07-22T09:15:00Z",
        }
        result = normalize_record(record, "okta")
        assert result["status"] == "active"
        assert "2024-07-22" in result["last_login"]

    def test_app_record_saas(self):
        record = {"app_id": "A-1", "name": "Slack", "app_type": "SaaS"}
        result = normalize_record(record, "app")
        assert result["app_type"] == "SaaS"

    def test_app_record_onprem(self):
        record = {"app_id": "A-2", "name": "Jenkins", "app_type": "on-prem"}
        result = normalize_record(record, "app")
        assert result["app_type"] == "on-premise"

    def test_empty_string_becomes_none(self):
        """Empty strings after stripping should become None."""
        record = {"device_id": "D-1", "hostname": "test", "os": "  "}
        result = normalize_record(record, "hardware")
        assert result["os"] is None

    def test_invalid_ip_becomes_none(self):
        record = {"device_id": "D-1", "hostname": "test", "ip_address": "garbage"}
        result = normalize_record(record, "hardware")
        assert result["ip_address"] is None
