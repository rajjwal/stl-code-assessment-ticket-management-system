"""Tests for format-specific parsers and the auto-detector.

Validates parsing of all 5 sample files plus edge cases.
"""

from __future__ import annotations

import json

import pytest

from app.services.parsers.csv_parser import CSVParser
from app.services.parsers.json_parser import JSONParser
from app.services.parsers.yaml_parser import YAMLParser
from app.services.parsers.detector import detect_format, detect_source_type


class TestCSVParser:
    """Tests for CSVParser."""

    def test_parse_hardware_csv(self, sample_hardware_csv):
        parser = CSVParser()
        records = parser.parse(sample_hardware_csv, "sample_hardware.csv")
        assert len(records) == 3
        assert records[0]["device_id"] == "C-19283"
        assert records[0]["hostname"] == "laptop-jdoe"
        assert records[0]["assigned_to"] == "John D."

    def test_field_names(self, sample_hardware_csv):
        parser = CSVParser()
        records = parser.parse(sample_hardware_csv, "sample_hardware.csv")
        expected_fields = {
            "device_id", "hostname", "assigned_to", "os", "ip_address",
            "mac_address", "last_checkin", "location", "encryption_status",
            "status", "device_type", "serial_number", "department",
        }
        assert set(records[0].keys()) == expected_fields

    def test_whitespace_stripping(self):
        """Values with extra whitespace should be stripped."""
        parser = CSVParser()
        csv_content = b"name, value \nAlice , hello "
        records = parser.parse(csv_content, "test.csv")
        assert records[0]["name"] == "Alice"
        assert records[0]["value"] == "hello"

    def test_empty_csv(self):
        """CSV with only headers and no data rows."""
        parser = CSVParser()
        records = parser.parse(b"col1,col2\n", "empty.csv")
        assert records == []

    def test_bom_handling(self):
        """UTF-8 BOM should be stripped transparently."""
        parser = CSVParser()
        bom_csv = b"\xef\xbb\xbfname,age\nAlice,30\n"
        records = parser.parse(bom_csv, "bom.csv")
        assert "name" in records[0]
        assert records[0]["name"] == "Alice"


class TestJSONParser:
    """Tests for JSONParser."""

    def test_parse_hardware_json(self, sample_hardware_json):
        """Top-level array format."""
        parser = JSONParser()
        records = parser.parse(sample_hardware_json, "sample_hardware.json")
        assert len(records) == 3
        assert records[0]["device_id"] == "C-19283"

    def test_parse_okta_json(self, sample_okta_json):
        """Top-level array format with user data."""
        parser = JSONParser()
        records = parser.parse(sample_okta_json, "sample_okta.json")
        assert len(records) == 9
        assert records[0]["user_id"] == "u_999"
        assert records[0]["mfa_enabled"] is True

    def test_parse_app_json(self, sample_app_json):
        """Wrapper object format — records under 'applications' key."""
        parser = JSONParser()
        records = parser.parse(sample_app_json, "sample_app.json")
        assert len(records) == 6
        assert records[0]["app_id"] == "APP-001"
        assert records[0]["name"] == "Slack"

    def test_no_record_list_raises(self):
        """JSON object with no list of dicts should raise ValueError."""
        parser = JSONParser()
        with pytest.raises(ValueError, match="no key containing a list"):
            parser.parse(b'{"key": "value"}', "test.json")

    def test_unexpected_type_raises(self):
        """Non-object/non-array JSON should raise ValueError."""
        parser = JSONParser()
        with pytest.raises(ValueError, match="Unexpected JSON"):
            parser.parse(b'"just a string"', "test.json")

    def test_malformed_json_raises(self):
        parser = JSONParser()
        with pytest.raises(Exception):
            parser.parse(b'{invalid json', "bad.json")


class TestYAMLParser:
    """Tests for YAMLParser with nested structure flattening."""

    def test_parse_hardware_yaml(self, sample_hardware_yaml):
        parser = YAMLParser()
        records = parser.parse(sample_hardware_yaml, "sample_hardware.yaml")
        assert len(records) == 3

    def test_yaml_flattens_assigned_to(self, sample_hardware_yaml):
        """Nested assigned_to.name should become flat assigned_to."""
        parser = YAMLParser()
        records = parser.parse(sample_hardware_yaml, "sample_hardware.yaml")
        assert records[0]["assigned_to"] == "John Doe"
        assert records[0].get("employee_id") == "EMP-2156"
        assert records[0].get("department") == "Engineering"

    def test_yaml_flattens_os(self, sample_hardware_yaml):
        """operating_system.name + version should combine into os."""
        parser = YAMLParser()
        records = parser.parse(sample_hardware_yaml, "sample_hardware.yaml")
        assert records[0]["os"] == "macOS Ventura 13.5"

    def test_yaml_flattens_network(self, sample_hardware_yaml):
        """network.primary_ip should become ip_address."""
        parser = YAMLParser()
        records = parser.parse(sample_hardware_yaml, "sample_hardware.yaml")
        assert records[0]["ip_address"] == "10.10.22.5"
        assert records[0]["mac_address"] == "AA:BB:CC:DD:11:22"

    def test_yaml_flattens_security(self, sample_hardware_yaml):
        """security.encryption_type should become encryption_status."""
        parser = YAMLParser()
        records = parser.parse(sample_hardware_yaml, "sample_hardware.yaml")
        assert records[0]["encryption_status"] == "FileVault 2"

    def test_yaml_flattens_status(self, sample_hardware_yaml):
        """status.operational_status should become status."""
        parser = YAMLParser()
        records = parser.parse(sample_hardware_yaml, "sample_hardware.yaml")
        assert records[0]["status"] == "deactivated"

    def test_yaml_flattens_location(self, sample_hardware_yaml):
        """location.site should become location."""
        parser = YAMLParser()
        records = parser.parse(sample_hardware_yaml, "sample_hardware.yaml")
        assert records[0]["location"] == "London"

    def test_yaml_preserves_flat_fields(self, sample_hardware_yaml):
        """device_id and hostname should pass through unchanged."""
        parser = YAMLParser()
        records = parser.parse(sample_hardware_yaml, "sample_hardware.yaml")
        assert records[0]["device_id"] == "C-19283"
        assert records[0]["hostname"] == "laptop-jdoe"

    def test_malformed_yaml_raises(self):
        parser = YAMLParser()
        with pytest.raises(Exception):
            parser.parse(b":\n  - :\n    invalid: [", "bad.yaml")


class TestDetector:
    """Tests for format and source type detection."""

    def test_detect_csv_format(self):
        assert detect_format(b"", "data.csv") == "csv"

    def test_detect_json_format(self):
        assert detect_format(b"", "data.json") == "json"

    def test_detect_yaml_format(self):
        assert detect_format(b"", "data.yaml") == "yaml"
        assert detect_format(b"", "data.yml") == "yaml"

    def test_detect_format_by_content(self):
        """When extension is ambiguous, try content sniffing."""
        json_content = b'[{"key": "val"}]'
        assert detect_format(json_content, "data.txt") == "json"

    def test_detect_format_unknown_raises(self):
        with pytest.raises(ValueError, match="Cannot determine format"):
            detect_format(b"random gibberish!@#$", "data.txt")

    def test_detect_hardware_source(self):
        records = [{"device_id": "D-1", "hostname": "test"}]
        assert detect_source_type(records) == "hardware"

    def test_detect_okta_source(self):
        records = [{"user_id": "u_1", "mfa_enabled": True}]
        assert detect_source_type(records) == "okta"

    def test_detect_app_source(self):
        records = [{"app_id": "APP-1", "vendor": "Test Inc"}]
        assert detect_source_type(records) == "app"

    def test_detect_empty_raises(self):
        with pytest.raises(ValueError, match="empty records"):
            detect_source_type([])

    def test_detect_unknown_raises(self):
        with pytest.raises(ValueError, match="Cannot determine source type"):
            detect_source_type([{"random_field": "value"}])
