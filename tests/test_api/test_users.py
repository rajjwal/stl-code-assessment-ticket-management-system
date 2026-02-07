"""API integration tests for GET /users endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_users_empty(client: AsyncClient):
    resp = await client.get("/users")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_users_after_ingest(client: AsyncClient, sample_okta_json: bytes):
    await client.post("/ingest", files={"file": ("okta.json", sample_okta_json)})

    resp = await client.get("/users")
    data = resp.json()
    assert data["total"] == 9
    assert len(data["items"]) == 9


@pytest.mark.asyncio
async def test_filter_by_mfa_disabled(client: AsyncClient, sample_okta_json: bytes):
    """Three users have MFA disabled: Carlos S., Michael Brown, Alex Johnson."""
    await client.post("/ingest", files={"file": ("okta.json", sample_okta_json)})

    resp = await client.get("/users", params={"mfa_enabled": "false"})
    data = resp.json()
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_filter_by_status(client: AsyncClient, sample_okta_json: bytes):
    await client.post("/ingest", files={"file": ("okta.json", sample_okta_json)})

    resp = await client.get("/users", params={"status": "suspended"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Alex Johnson"


@pytest.mark.asyncio
async def test_filter_by_team(client: AsyncClient, sample_okta_json: bytes):
    await client.post("/ingest", files={"file": ("okta.json", sample_okta_json)})

    resp = await client.get("/users", params={"team": "Engineering"})
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_user_has_groups_as_list(client: AsyncClient, sample_okta_json: bytes):
    """Groups should be returned as a JSON list, not a string."""
    await client.post("/ingest", files={"file": ("okta.json", sample_okta_json)})

    resp = await client.get("/users")
    data = resp.json()
    for item in data["items"]:
        if item["groups"] is not None:
            assert isinstance(item["groups"], list)
