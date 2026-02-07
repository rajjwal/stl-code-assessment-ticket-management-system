"""Tests for cross-source relationship resolution."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app import App
from app.models.device import Device
from app.models.relationships import app_integrations, user_app_assignments
from app.models.user import User
from app.services.relationship_resolver import resolve_relationships


async def _seed_test_data(db: AsyncSession) -> None:
    """Insert minimal test data for relationship resolution tests."""
    # Users
    db.add(User(id="u_999", name="John Doe", email="john@test.com",
                raw_data=json.dumps({"apps": ["GitHub", "Slack"]})))
    db.add(User(id="u_110", name="Jane Doe", email="jane@test.com",
                raw_data=json.dumps({"apps": ["GitHub", "Salesforce"]})))
    db.add(User(id="u_301", name="Sarah Chen", email="sarah@test.com",
                raw_data=json.dumps({"apps": ["AWS Console"]})))

    # Devices
    db.add(Device(id="C-19283", hostname="laptop-jdoe",
                  assigned_user_name="John D.", status="active"))
    db.add(Device(id="D-10005", hostname="laptop-devops",
                  assigned_user_name="Sarah Chen", status="active"))
    db.add(Device(id="HW-2024-003", hostname="macbook-cto-01",
                  assigned_user_name="Jane Doe", status="inactive"))

    # Apps
    db.add(App(id="APP-001", name="Slack",
               raw_data=json.dumps({"integrations": ["GitHub", "Jira"]})))
    db.add(App(id="APP-002", name="GitHub Enterprise",
               raw_data=json.dumps({"integrations": ["Slack", "Jira"]})))
    db.add(App(id="APP-003", name="Salesforce CRM",
               raw_data=json.dumps({"integrations": ["Slack"]})))

    await db.commit()


class TestDeviceUserResolution:
    """Device → User relationship tests."""

    @pytest.mark.asyncio
    async def test_john_d_matches_john_doe(self, db_session: AsyncSession):
        await _seed_test_data(db_session)
        await resolve_relationships(db_session)

        device = await db_session.get(Device, "C-19283")
        assert device.assigned_user_id == "u_999"
        assert device.assigned_user_name == "John Doe"

    @pytest.mark.asyncio
    async def test_exact_name_match(self, db_session: AsyncSession):
        await _seed_test_data(db_session)
        await resolve_relationships(db_session)

        device = await db_session.get(Device, "D-10005")
        assert device.assigned_user_id == "u_301"

    @pytest.mark.asyncio
    async def test_jane_doe_matched(self, db_session: AsyncSession):
        await _seed_test_data(db_session)
        await resolve_relationships(db_session)

        device = await db_session.get(Device, "HW-2024-003")
        assert device.assigned_user_id == "u_110"


class TestUserAppResolution:
    """User → App relationship tests."""

    @pytest.mark.asyncio
    async def test_user_github_linked(self, db_session: AsyncSession):
        """'GitHub' in user apps list should match 'GitHub Enterprise'."""
        await _seed_test_data(db_session)
        await resolve_relationships(db_session)

        result = await db_session.execute(
            select(user_app_assignments).where(
                user_app_assignments.c.user_id == "u_999"
            )
        )
        app_ids = [row.app_id for row in result.fetchall()]
        assert "APP-002" in app_ids  # GitHub → GitHub Enterprise
        assert "APP-001" in app_ids  # Slack

    @pytest.mark.asyncio
    async def test_user_salesforce_linked(self, db_session: AsyncSession):
        await _seed_test_data(db_session)
        await resolve_relationships(db_session)

        result = await db_session.execute(
            select(user_app_assignments).where(
                user_app_assignments.c.user_id == "u_110"
            )
        )
        app_ids = [row.app_id for row in result.fetchall()]
        assert "APP-003" in app_ids  # Salesforce → Salesforce CRM

    @pytest.mark.asyncio
    async def test_unmatched_app_not_linked(self, db_session: AsyncSession):
        """'AWS Console' doesn't match any app, so no link created."""
        await _seed_test_data(db_session)
        await resolve_relationships(db_session)

        result = await db_session.execute(
            select(user_app_assignments).where(
                user_app_assignments.c.user_id == "u_301"
            )
        )
        assert result.fetchall() == []


class TestAppIntegrationResolution:
    """App → App integration resolution tests."""

    @pytest.mark.asyncio
    async def test_slack_github_integration(self, db_session: AsyncSession):
        """Slack integrates with GitHub → should resolve to APP-002."""
        await _seed_test_data(db_session)
        await resolve_relationships(db_session)

        result = await db_session.execute(
            select(app_integrations).where(
                app_integrations.c.source_app_id == "APP-001"
            )
        )
        rows = result.fetchall()
        integration_names = [r.target_app_name for r in rows]
        assert "GitHub" in integration_names
        assert "Jira" in integration_names

        # GitHub should be resolved to APP-002
        github_row = next(r for r in rows if r.target_app_name == "GitHub")
        assert github_row.target_app_id == "APP-002"

        # Jira is unresolved (not in our apps)
        jira_row = next(r for r in rows if r.target_app_name == "Jira")
        assert jira_row.target_app_id is None

    @pytest.mark.asyncio
    async def test_resolve_summary_counts(self, db_session: AsyncSession):
        await _seed_test_data(db_session)
        summary = await resolve_relationships(db_session)

        assert summary["device_user_links"] == 3
        assert summary["user_app_links"] > 0
        assert summary["app_integration_links"] > 0
