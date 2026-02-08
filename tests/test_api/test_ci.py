"""API integration tests for GET /ci/{ci_id} endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ci_not_found(client: AsyncClient):
    resp = await client.get("/ci/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_device_by_id(client: AsyncClient, sample_hardware_json: bytes):
    await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    resp = await client.get("/ci/C-19283")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ci_type"] == "device"
    assert data["id"] == "C-19283"
    assert data["hostname"] == "laptop-jdoe"


@pytest.mark.asyncio
async def test_get_user_by_id(client: AsyncClient, sample_okta_json: bytes):
    await client.post("/ingest", files={"file": ("okta.json", sample_okta_json)})

    resp = await client.get("/ci/u_999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ci_type"] == "user"
    assert data["name"] == "John Doe"


@pytest.mark.asyncio
async def test_get_app_by_id(client: AsyncClient, sample_app_json: bytes):
    await client.post("/ingest", files={"file": ("apps.json", sample_app_json)})

    resp = await client.get("/ci/APP-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ci_type"] == "app"
    assert data["name"] == "Slack"


@pytest.mark.asyncio
async def test_device_has_assigned_user_after_relationship_resolution(
    client: AsyncClient,
    sample_hardware_json: bytes,
    sample_okta_json: bytes,
):
    """After ingesting both hardware and okta, device should have assigned_user_id."""
    await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})
    await client.post("/ingest", files={"file": ("okta.json", sample_okta_json)})

    resp = await client.get("/ci/C-19283")
    data = resp.json()
    assert data["assigned_user_id"] == "u_999"
    assert data["assigned_user_name"] == "John Doe"


@pytest.mark.asyncio
async def test_user_has_apps_after_relationship_resolution(
    client: AsyncClient,
    sample_okta_json: bytes,
    sample_app_json: bytes,
):
    """After ingesting okta and app data, user should have linked apps."""
    await client.post("/ingest", files={"file": ("okta.json", sample_okta_json)})
    await client.post("/ingest", files={"file": ("apps.json", sample_app_json)})

    resp = await client.get("/ci/u_999")
    data = resp.json()
    assert len(data["apps"]) >= 1


@pytest.mark.asyncio
async def test_app_has_integrations_with_resolution(
    client: AsyncClient,
    sample_app_json: bytes,
):
    """App integrations should show resolved IDs where possible."""
    await client.post("/ingest", files={"file": ("apps.json", sample_app_json)})

    resp = await client.get("/ci/APP-001")
    data = resp.json()
    assert len(data["integrations"]) > 0

    # GitHub integration should be resolved to APP-002
    github_int = next(
        (i for i in data["integrations"] if i["name"] == "GitHub"), None
    )
    assert github_int is not None
    assert github_int["resolved_id"] == "APP-002"


@pytest.mark.asyncio
async def test_get_user_has_all_fields(client: AsyncClient, sample_okta_json: bytes):
    """User CI detail should include all expected fields."""
    await client.post("/ingest", files={"file": ("okta.json", sample_okta_json)})

    resp = await client.get("/ci/u_999")
    data = resp.json()
    assert data["ci_type"] == "user"
    assert "email" in data
    assert "team" in data
    assert "mfa_enabled" in data
    assert "groups" in data
    assert "status" in data
    assert "apps" in data


@pytest.mark.asyncio
async def test_get_app_has_all_fields(client: AsyncClient, sample_app_json: bytes):
    """App CI detail should include all expected fields."""
    await client.post("/ingest", files={"file": ("apps.json", sample_app_json)})

    resp = await client.get("/ci/APP-001")
    data = resp.json()
    assert data["ci_type"] == "app"
    assert "vendor" in data
    assert "app_type" in data
    assert "sso_enabled" in data
    assert "integrations" in data
    assert "users_count" in data


@pytest.mark.asyncio
async def test_get_device_has_all_fields(client: AsyncClient, sample_hardware_json: bytes):
    """Device CI detail should include all expected fields."""
    await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    resp = await client.get("/ci/C-19283")
    data = resp.json()
    assert data["ci_type"] == "device"
    assert "hostname" in data
    assert "ip_address" in data
    assert "os" in data
    assert "status" in data
    assert "assigned_apps" in data
    assert "location" in data
