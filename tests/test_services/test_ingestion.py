"""Unit tests for the ingestion service — upsert logic and pipeline stages."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.user import User
from app.models.app import App
from app.services.ingestion import ingest_file, _merge_field


class TestMergeField:
    """Tests for the null-safe merge helper."""

    def test_new_value_overwrites(self):
        class Obj:
            x = "old"
        obj = Obj()
        _merge_field(obj, "x", "new")
        assert obj.x == "new"

    def test_none_does_not_overwrite(self):
        class Obj:
            x = "old"
        obj = Obj()
        _merge_field(obj, "x", None)
        assert obj.x == "old"

    def test_none_to_none_stays_none(self):
        class Obj:
            x = None
        obj = Obj()
        _merge_field(obj, "x", None)
        assert obj.x is None


class TestUpsertDevice:
    """Tests for device upsert via the full pipeline."""

    @pytest.mark.asyncio
    async def test_create_device(self, db_session: AsyncSession):
        """Ingesting hardware data creates device records."""
        content = json.dumps([
            {"device_id": "D-TEST-1", "hostname": "laptop-test", "os": "macOS",
             "ip_address": "10.0.0.1", "status": "active"}
        ]).encode()
        result = await ingest_file("test.json", content, db_session)
        assert result.records_created == 1

        device = await db_session.get(Device, "D-TEST-1")
        assert device is not None
        assert device.hostname == "laptop-test"
        assert device.os == "macOS"

    @pytest.mark.asyncio
    async def test_upsert_device_null_safe_merge(self, db_session: AsyncSession):
        """Re-ingesting with null fields should not erase existing data."""
        # First ingest with full data
        full = json.dumps([
            {"device_id": "D-MERGE", "hostname": "laptop-merge", "os": "macOS",
             "ip_address": "10.0.0.2", "location": "London", "status": "active"}
        ]).encode()
        await ingest_file("full.json", full, db_session)

        # Second ingest with sparser data (no location, no ip)
        sparse = json.dumps([
            {"device_id": "D-MERGE", "hostname": "laptop-merge", "os": "Ubuntu 22.04 LTS",
             "status": "active"}
        ]).encode()
        result = await ingest_file("sparse.json", sparse, db_session)
        assert result.records_updated == 1

        device = await db_session.get(Device, "D-MERGE")
        # OS should be updated (new non-null value)
        assert device.os == "Ubuntu 22.04 LTS"
        # Location should still be London (null didn't overwrite)
        assert device.location == "London"
        # IP should still be present
        assert device.ip_address == "10.0.0.2"


class TestUpsertUser:
    """Tests for user upsert via the full pipeline."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession):
        content = json.dumps([
            {"user_id": "u_test", "name": "Test User", "email": "test@test.com",
             "status": "active", "mfa_enabled": True,
             "groups": ["Engineering", "DevOps"]}
        ]).encode()
        result = await ingest_file("okta.json", content, db_session)
        assert result.records_created == 1

        user = await db_session.get(User, "u_test")
        assert user is not None
        assert user.name == "Test User"
        assert user.team == "Engineering"  # First group becomes team
        assert json.loads(user.groups) == ["Engineering", "DevOps"]

    @pytest.mark.asyncio
    async def test_upsert_user_null_safe_merge(self, db_session: AsyncSession):
        """Re-ingesting user should merge without erasing fields."""
        full = json.dumps([
            {"user_id": "u_merge", "name": "Merge User", "email": "merge@test.com",
             "status": "active", "mfa_enabled": True,
             "groups": ["Engineering"]}
        ]).encode()
        await ingest_file("okta1.json", full, db_session)

        sparse = json.dumps([
            {"user_id": "u_merge", "name": "Merge User", "status": "active",
             "mfa_enabled": False}
        ]).encode()
        result = await ingest_file("okta2.json", sparse, db_session)
        assert result.records_updated == 1

        user = await db_session.get(User, "u_merge")
        assert user.email == "merge@test.com"  # Not erased
        assert user.mfa_enabled is False  # Updated (boolean)


class TestUpsertApp:
    """Tests for app upsert via the full pipeline."""

    @pytest.mark.asyncio
    async def test_create_app(self, db_session: AsyncSession):
        content = json.dumps([
            {"app_id": "APP-TEST", "name": "TestApp", "app_type": "SaaS",
             "vendor": "TestVendor", "sso_enabled": True, "users_count": 50}
        ]).encode()
        result = await ingest_file("apps.json", content, db_session)
        assert result.records_created == 1

        app = await db_session.get(App, "APP-TEST")
        assert app is not None
        assert app.name == "TestApp"
        assert app.app_type == "SaaS"
        assert app.sso_enabled is True

    @pytest.mark.asyncio
    async def test_upsert_app_null_safe_merge(self, db_session: AsyncSession):
        """Re-ingesting app preserves existing fields."""
        full = json.dumps([
            {"app_id": "APP-MERGE", "name": "MergeApp", "vendor": "Vendor1",
             "app_type": "on-prem", "category": "Development",
             "sso_enabled": True, "users_count": 100, "annual_cost_usd": 50000}
        ]).encode()
        await ingest_file("apps1.json", full, db_session)

        sparse = json.dumps([
            {"app_id": "APP-MERGE", "name": "MergeApp", "app_type": "on-premise",
             "users_count": 120}
        ]).encode()
        result = await ingest_file("apps2.json", sparse, db_session)
        assert result.records_updated == 1

        app = await db_session.get(App, "APP-MERGE")
        assert app.vendor == "Vendor1"  # Not erased
        assert app.users_count == 120  # Updated
        assert app.annual_cost_usd == 50000  # Not erased


class TestIngestPipelineEdgeCases:
    """Tests for edge cases in the ingestion pipeline."""

    @pytest.mark.asyncio
    async def test_empty_file(self, db_session: AsyncSession):
        """Empty JSON array should succeed with 0 records."""
        result = await ingest_file("empty.json", b"[]", db_session)
        assert result.status == "success"
        assert result.records_processed == 0

    @pytest.mark.asyncio
    async def test_unrecognizable_format(self, db_session: AsyncSession):
        """Binary garbage should return failure."""
        result = await ingest_file("data.xyz", b"\x00\x01\x02", db_session)
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_missing_required_id(self, db_session: AsyncSession):
        """Records without an ID field should produce errors but not crash."""
        content = json.dumps([
            {"hostname": "no-id-device", "os": "macOS"}
        ]).encode()
        result = await ingest_file("hw.json", content, db_session)
        # Should still complete (with errors)
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_ingestion_log_created(self, db_session: AsyncSession):
        """Each ingestion should create a log entry."""
        from app.models.ingestion_log import IngestionLog

        content = json.dumps([
            {"device_id": "D-LOG", "hostname": "log-test", "status": "active"}
        ]).encode()
        await ingest_file("hw.json", content, db_session)

        result = await db_session.execute(select(IngestionLog))
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].filename == "hw.json"
        assert logs[0].file_format == "json"
        assert logs[0].records_count == 1
