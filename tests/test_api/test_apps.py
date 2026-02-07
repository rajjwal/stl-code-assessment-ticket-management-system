"""API integration tests for GET /apps endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_apps_empty(client: AsyncClient):
    resp = await client.get("/apps")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_apps_after_ingest(client: AsyncClient, sample_app_json: bytes):
    await client.post("/ingest", files={"file": ("apps.json", sample_app_json)})

    resp = await client.get("/apps")
    data = resp.json()
    assert data["total"] == 6


@pytest.mark.asyncio
async def test_filter_by_app_type_saas(client: AsyncClient, sample_app_json: bytes):
    await client.post("/ingest", files={"file": ("apps.json", sample_app_json)})

    resp = await client.get("/apps", params={"app_type": "SaaS"})
    data = resp.json()
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_filter_by_app_type_onprem(client: AsyncClient, sample_app_json: bytes):
    await client.post("/ingest", files={"file": ("apps.json", sample_app_json)})

    resp = await client.get("/apps", params={"app_type": "on-premise"})
    data = resp.json()
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_filter_by_sso(client: AsyncClient, sample_app_json: bytes):
    await client.post("/ingest", files={"file": ("apps.json", sample_app_json)})

    resp = await client.get("/apps", params={"sso_enabled": "true"})
    data = resp.json()
    assert data["total"] == 4


@pytest.mark.asyncio
async def test_filter_by_category(client: AsyncClient, sample_app_json: bytes):
    await client.post("/ingest", files={"file": ("apps.json", sample_app_json)})

    resp = await client.get("/apps", params={"category": "Development"})
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_apps_have_integrations(client: AsyncClient, sample_app_json: bytes):
    """After ingestion, apps should have integration names populated."""
    await client.post("/ingest", files={"file": ("apps.json", sample_app_json)})

    resp = await client.get("/apps")
    data = resp.json()
    slack = next(a for a in data["items"] if a["name"] == "Slack")
    assert slack["integrations"] is not None
    assert "GitHub" in slack["integrations"]
