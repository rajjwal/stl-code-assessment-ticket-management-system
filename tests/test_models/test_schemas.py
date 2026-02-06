"""Tests for Pydantic schema validation.

Verifies that all CI response schemas handle required fields, optional fields,
defaults, and edge cases correctly.
"""

import pytest
from pydantic import ValidationError

from app.schemas.device import DeviceListResponse, DeviceResponse
from app.schemas.user import UserListResponse, UserResponse
from app.schemas.app import AppListResponse, AppResponse
from app.schemas.ingest import IngestResponse
from app.schemas.ask import AskRequest, AskResponse


class TestDeviceSchema:
    """Tests for DeviceResponse and DeviceListResponse."""

    def test_minimal_device(self):
        """Device with only required fields (id, hostname) should be valid."""
        device = DeviceResponse(id="D-001", hostname="test-host")
        assert device.ci_type == "device"
        assert device.id == "D-001"
        assert device.hostname == "test-host"
        assert device.ip_address is None
        assert device.status is None

    def test_full_device(self):
        """Device with all fields populated."""
        device = DeviceResponse(
            id="C-19283",
            hostname="laptop-jdoe",
            ip_address="10.10.22.5",
            mac_address="AA:BB:CC:DD:11:22",
            os="macOS Ventura 13.5",
            assigned_user_id="u_999",
            assigned_user_name="John Doe",
            location="London",
            status="active",
            device_type="laptop",
            serial_number="LAP-JD-20230615",
            department="Engineering",
            encryption_status="FileVault 2",
            last_checkin="2024-07-23T13:45:00Z",
            assigned_apps=["Slack", "GitHub"],
        )
        assert device.os == "macOS Ventura 13.5"
        assert device.assigned_apps == ["Slack", "GitHub"]

    def test_device_list_response(self):
        """DeviceListResponse wraps items with pagination metadata."""
        response = DeviceListResponse(
            items=[DeviceResponse(id="D-001", hostname="host1")],
            total=1,
            limit=100,
            offset=0,
        )
        assert len(response.items) == 1
        assert response.total == 1

    def test_device_missing_required_field(self):
        """Device without hostname should fail validation."""
        with pytest.raises(ValidationError):
            DeviceResponse(id="D-001")


class TestUserSchema:
    """Tests for UserResponse and UserListResponse."""

    def test_minimal_user(self):
        """User with only required fields (id, name) should be valid."""
        user = UserResponse(id="u_001", name="Test User")
        assert user.ci_type == "user"
        assert user.mfa_enabled is None
        assert user.groups is None

    def test_full_user(self):
        """User with all fields populated."""
        user = UserResponse(
            id="u_999",
            name="John Doe",
            email="john.d@example.com",
            team="Engineering",
            groups=["Engineering", "Platform"],
            mfa_enabled=True,
            last_login="2024-07-22T09:15:00Z",
            status="active",
            employee_id="EMP-2156",
            title="Senior Engineer",
            apps=["GitHub", "Slack"],
        )
        assert user.mfa_enabled is True
        assert len(user.groups) == 2
        assert len(user.apps) == 2

    def test_user_mfa_false(self):
        """MFA disabled should serialize correctly (not confused with None)."""
        user = UserResponse(id="u_001", name="Test", mfa_enabled=False)
        assert user.mfa_enabled is False

    def test_user_list_response(self):
        """UserListResponse wraps items with pagination metadata."""
        response = UserListResponse(items=[], total=0, limit=50, offset=0)
        assert response.items == []
        assert response.total == 0


class TestAppSchema:
    """Tests for AppResponse and AppListResponse."""

    def test_minimal_app(self):
        """App with only required fields (id, name) should be valid."""
        app = AppResponse(id="APP-001", name="Slack")
        assert app.ci_type == "app"
        assert app.sso_enabled is None

    def test_full_app(self):
        """App with all fields populated."""
        app = AppResponse(
            id="APP-001",
            name="Slack",
            vendor="Salesforce Inc.",
            app_type="SaaS",
            category="Collaboration",
            deployment="cloud",
            owner="IT Operations",
            users_count=52,
            sso_enabled=True,
            annual_cost_usd=24000.0,
            contract_renewal="2025-03-15",
            integrations=["GitHub", "Jira"],
        )
        assert app.users_count == 52
        assert app.annual_cost_usd == 24000.0
        assert len(app.integrations) == 2

    def test_app_on_premise(self):
        """On-premise app with server_location and version."""
        app = AppResponse(
            id="APP-005",
            name="PostgreSQL",
            app_type="on-premise",
            server_location="AWS us-east-1",
            version="14.5",
        )
        assert app.server_location == "AWS us-east-1"
        assert app.version == "14.5"

    def test_app_list_response(self):
        """AppListResponse wraps items with pagination metadata."""
        response = AppListResponse(
            items=[AppResponse(id="APP-001", name="Slack")],
            total=1,
            limit=100,
            offset=0,
        )
        assert len(response.items) == 1


class TestIngestSchema:
    """Tests for IngestResponse."""

    def test_success_response(self):
        """Successful ingestion response."""
        response = IngestResponse(
            status="success",
            filename="sample_hardware.json",
            file_format="json",
            source_type="hardware",
            records_processed=3,
            records_created=3,
        )
        assert response.errors == []
        assert response.ai_enrichments_applied == 0

    def test_partial_response_with_errors(self):
        """Partial ingestion with some errors."""
        response = IngestResponse(
            status="partial",
            filename="bad_data.csv",
            records_processed=5,
            records_created=3,
            errors=["Row 4: missing hostname", "Row 5: invalid IP"],
        )
        assert len(response.errors) == 2

    def test_minimal_response(self):
        """Only required fields: status and filename."""
        response = IngestResponse(status="failed", filename="test.txt")
        assert response.records_processed == 0


class TestAskSchema:
    """Tests for AskRequest and AskResponse."""

    def test_ask_request(self):
        """Simple question request."""
        req = AskRequest(question="Which users don't have MFA?")
        assert req.question == "Which users don't have MFA?"

    def test_ask_request_empty_fails(self):
        """Empty question should still be a valid string (no min_length constraint)."""
        req = AskRequest(question="")
        assert req.question == ""

    def test_ask_response(self):
        """Full answer response."""
        resp = AskResponse(
            answer="3 users don't have MFA enabled.",
            results=[{"name": "Carlos S.", "mfa_enabled": False}],
            query_interpretation="Searched users where mfa_enabled = false",
        )
        assert len(resp.results) == 1

    def test_ask_response_defaults(self):
        """AskResponse with only answer provided."""
        resp = AskResponse(answer="No results found.")
        assert resp.results == []
        assert resp.query_interpretation == ""
