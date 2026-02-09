"""Tests for the query service with mocked AI."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app import App
from app.models.device import Device
from app.models.user import User
from app.services.query_service import handle_question


async def _seed_query_data(db: AsyncSession) -> None:
    """Insert test data for query service tests."""
    db.add(User(id="u_1", name="John Doe", email="john@test.com",
                mfa_enabled=True, status="active", team="Engineering"))
    db.add(User(id="u_2", name="Jane Smith", email="jane@test.com",
                mfa_enabled=False, status="active", team="Sales"))
    db.add(User(id="u_3", name="Bob Wilson", email="bob@test.com",
                mfa_enabled=False, status="suspended", team="Engineering"))

    db.add(Device(id="D-1", hostname="laptop-1", status="active",
                  os="macOS", location="London", assigned_user_id="u_1"))
    db.add(Device(id="D-2", hostname="server-1", status="active",
                  os="Ubuntu 22.04 LTS", location="New York", assigned_user_id="u_2"))
    db.add(Device(id="D-3", hostname="desktop-1", status="active",
                  os="Windows 11", location="London", assigned_user_id="u_3"))

    db.add(App(id="A-1", name="Slack", app_type="SaaS", sso_enabled=True))
    db.add(App(id="A-2", name="Jenkins", app_type="on-premise", sso_enabled=False))

    await db.commit()


class TestHandleQuestion:
    """Integration tests for the full question handling flow."""

    @pytest.mark.asyncio
    async def test_users_without_mfa(self, db_session: AsyncSession):
        await _seed_query_data(db_session)

        query_spec = {
            "entity_type": "users",
            "filters": {"mfa_enabled": False},
            "sort_by": None,
            "aggregation": "list",
            "limit": None,
        }

        with patch("app.services.query_service.parse_natural_language_query",
                    new_callable=AsyncMock) as mock_parse, \
             patch("app.services.query_service.generate_answer",
                    new_callable=AsyncMock) as mock_answer:
            mock_parse.return_value = query_spec
            mock_answer.return_value = "2 users without MFA: Jane Smith, Bob Wilson"

            result = await handle_question("Which users don't have MFA?", db_session)

        assert len(result["results"]) == 2
        names = [r["name"] for r in result["results"]]
        assert "Jane Smith" in names
        assert "Bob Wilson" in names

    @pytest.mark.asyncio
    async def test_active_devices_in_london(self, db_session: AsyncSession):
        await _seed_query_data(db_session)

        query_spec = {
            "entity_type": "devices",
            "filters": {"status": "active", "location__contains": "London"},
            "sort_by": None,
            "aggregation": "list",
            "limit": None,
        }

        with patch("app.services.query_service.parse_natural_language_query",
                    new_callable=AsyncMock) as mock_parse, \
             patch("app.services.query_service.generate_answer",
                    new_callable=AsyncMock) as mock_answer:
            mock_parse.return_value = query_spec
            mock_answer.return_value = "1 active device in London"

            result = await handle_question("Show active devices in London", db_session)

        assert len(result["results"]) == 2
        hostnames = {r["hostname"] for r in result["results"]}
        assert hostnames == {"laptop-1", "desktop-1"}

    @pytest.mark.asyncio
    async def test_saas_apps(self, db_session: AsyncSession):
        await _seed_query_data(db_session)

        query_spec = {
            "entity_type": "apps",
            "filters": {"app_type": "SaaS"},
            "sort_by": None,
            "aggregation": "count",
            "limit": None,
        }

        with patch("app.services.query_service.parse_natural_language_query",
                    new_callable=AsyncMock) as mock_parse, \
             patch("app.services.query_service.generate_answer",
                    new_callable=AsyncMock) as mock_answer:
            mock_parse.return_value = query_spec
            mock_answer.return_value = "1 SaaS app"

            result = await handle_question("How many SaaS apps?", db_session)

        # app_type is stored as "SaaS" — query uses lowercase comparison
        assert len(result["results"]) >= 1

    @pytest.mark.asyncio
    async def test_ai_unavailable(self, db_session: AsyncSession):
        """When AI can't parse the question, return helpful error."""
        await _seed_query_data(db_session)

        with patch("app.services.query_service.parse_natural_language_query",
                    new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = None

            result = await handle_question("test question", db_session)

        assert "unavailable" in result["answer"].lower()
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_unknown_entity_type(self, db_session: AsyncSession):
        await _seed_query_data(db_session)

        with patch("app.services.query_service.parse_natural_language_query",
                    new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = {
                "entity_type": "unknown",
                "filters": {},
            }

            result = await handle_question("test", db_session)

        assert "unknown" in result["answer"].lower()

    @pytest.mark.asyncio
    async def test_contains_filter(self, db_session: AsyncSession):
        """The __contains operator should do case-insensitive partial matching."""
        await _seed_query_data(db_session)

        query_spec = {
            "entity_type": "devices",
            "filters": {"hostname__contains": "laptop"},
            "sort_by": None,
            "aggregation": "list",
            "limit": None,
        }

        with patch("app.services.query_service.parse_natural_language_query",
                    new_callable=AsyncMock) as mock_parse, \
             patch("app.services.query_service.generate_answer",
                    new_callable=AsyncMock) as mock_answer:
            mock_parse.return_value = query_spec
            mock_answer.return_value = "1 device found"

            result = await handle_question("Find laptops", db_session)

        assert len(result["results"]) == 1
        assert result["results"][0]["hostname"] == "laptop-1"

    @pytest.mark.asyncio
    async def test_limit_applied(self, db_session: AsyncSession):
        """Query limit should restrict the number of results."""
        await _seed_query_data(db_session)

        query_spec = {
            "entity_type": "users",
            "filters": {},
            "sort_by": None,
            "aggregation": "list",
            "limit": 1,
        }

        with patch("app.services.query_service.parse_natural_language_query",
                    new_callable=AsyncMock) as mock_parse, \
             patch("app.services.query_service.generate_answer",
                    new_callable=AsyncMock) as mock_answer:
            mock_parse.return_value = query_spec
            mock_answer.return_value = "1 user"

            result = await handle_question("Show 1 user", db_session)

        assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_apps_query(self, db_session: AsyncSession):
        """Query for apps should serialize correctly."""
        await _seed_query_data(db_session)

        query_spec = {
            "entity_type": "apps",
            "filters": {"sso_enabled": True},
            "sort_by": None,
            "aggregation": "list",
            "limit": None,
        }

        with patch("app.services.query_service.parse_natural_language_query",
                    new_callable=AsyncMock) as mock_parse, \
             patch("app.services.query_service.generate_answer",
                    new_callable=AsyncMock) as mock_answer:
            mock_parse.return_value = query_spec
            mock_answer.return_value = "1 app with SSO"

            result = await handle_question("Apps with SSO?", db_session)

        assert len(result["results"]) == 1
        assert result["results"][0]["name"] == "Slack"
        assert result["results"][0]["sso_enabled"] is True

    @pytest.mark.asyncio
    async def test_devices_for_users_without_mfa(self, db_session: AsyncSession):
        """Cross-entity: devices whose assigned users lack MFA."""
        await _seed_query_data(db_session)

        query_spec = {
            "entity_type": "devices",
            "filters": {},
            "join": {
                "entity_type": "users",
                "join_type": "inner",
                "filters": {"mfa_enabled": False},
            },
            "sort_by": None,
            "aggregation": "list",
            "limit": None,
        }

        with patch("app.services.query_service.parse_natural_language_query",
                    new_callable=AsyncMock) as mock_parse, \
             patch("app.services.query_service.generate_answer",
                    new_callable=AsyncMock) as mock_answer:
            mock_parse.return_value = query_spec
            mock_answer.return_value = "2 devices belong to users without MFA"

            result = await handle_question(
                "Which devices belong to users without MFA?", db_session
            )

        assert len(result["results"]) == 2
        hostnames = {r["hostname"] for r in result["results"]}
        # D-2 → Jane (no MFA), D-3 → Bob (no MFA)
        assert hostnames == {"server-1", "desktop-1"}

    @pytest.mark.asyncio
    async def test_cross_entity_with_both_side_filters(self, db_session: AsyncSession):
        """Cross-entity with filters on both primary and joined entities."""
        await _seed_query_data(db_session)

        query_spec = {
            "entity_type": "devices",
            "filters": {"location__contains": "London"},
            "join": {
                "entity_type": "users",
                "join_type": "inner",
                "filters": {"mfa_enabled": False},
            },
            "sort_by": None,
            "aggregation": "list",
            "limit": None,
        }

        with patch("app.services.query_service.parse_natural_language_query",
                    new_callable=AsyncMock) as mock_parse, \
             patch("app.services.query_service.generate_answer",
                    new_callable=AsyncMock) as mock_answer:
            mock_parse.return_value = query_spec
            mock_answer.return_value = "1 device in London for users without MFA"

            result = await handle_question(
                "Devices in London for users without MFA?", db_session
            )

        # Only D-3 (London, assigned to Bob who has no MFA)
        assert len(result["results"]) == 1
        assert result["results"][0]["hostname"] == "desktop-1"

    @pytest.mark.asyncio
    async def test_no_join_backward_compatible(self, db_session: AsyncSession):
        """Queries without a join field work exactly as before."""
        await _seed_query_data(db_session)

        query_spec = {
            "entity_type": "devices",
            "filters": {"status": "active"},
            "sort_by": None,
            "aggregation": "list",
            "limit": None,
        }

        with patch("app.services.query_service.parse_natural_language_query",
                    new_callable=AsyncMock) as mock_parse, \
             patch("app.services.query_service.generate_answer",
                    new_callable=AsyncMock) as mock_answer:
            mock_parse.return_value = query_spec
            mock_answer.return_value = "3 active devices"

            result = await handle_question("Active devices?", db_session)

        assert len(result["results"]) == 3

    @pytest.mark.asyncio
    async def test_invalid_join_entity_graceful(self, db_session: AsyncSession):
        """An unrecognized join entity type should be ignored, not crash."""
        await _seed_query_data(db_session)

        query_spec = {
            "entity_type": "devices",
            "filters": {},
            "join": {
                "entity_type": "tickets",
                "join_type": "inner",
                "filters": {},
            },
            "sort_by": None,
            "aggregation": "list",
            "limit": None,
        }

        with patch("app.services.query_service.parse_natural_language_query",
                    new_callable=AsyncMock) as mock_parse, \
             patch("app.services.query_service.generate_answer",
                    new_callable=AsyncMock) as mock_answer:
            mock_parse.return_value = query_spec
            mock_answer.return_value = "All devices"

            result = await handle_question("test", db_session)

        # Should return all devices (join was silently ignored)
        assert len(result["results"]) == 3
