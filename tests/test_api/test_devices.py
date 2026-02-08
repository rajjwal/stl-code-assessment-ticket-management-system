"""API integration tests for GET /devices endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_devices_empty(client: AsyncClient):
    """Empty database returns empty list."""
    resp = await client.get("/devices")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_devices_after_ingest(client: AsyncClient, sample_hardware_json: bytes):
    """After ingesting hardware data, devices are returned."""
    await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    resp = await client.get("/devices")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_filter_by_status(client: AsyncClient, sample_hardware_json: bytes):
    await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    resp = await client.get("/devices", params={"status": "active"})
    data = resp.json()
    assert data["total"] == 2
    for item in data["items"]:
        assert item["status"] == "active"


@pytest.mark.asyncio
async def test_filter_by_os(client: AsyncClient, sample_hardware_json: bytes):
    await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    resp = await client.get("/devices", params={"os": "macOS"})
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert "macOS" in item["os"]


@pytest.mark.asyncio
async def test_filter_by_location(client: AsyncClient, sample_hardware_json: bytes):
    await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    resp = await client.get("/devices", params={"location": "New York"})
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_pagination(client: AsyncClient, sample_hardware_json: bytes):
    await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    resp = await client.get("/devices", params={"limit": 1, "offset": 0})
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] == 3

    resp2 = await client.get("/devices", params={"limit": 1, "offset": 1})
    data2 = resp2.json()
    assert len(data2["items"]) == 1
    assert data2["items"][0]["id"] != data["items"][0]["id"]


@pytest.mark.asyncio
async def test_filter_by_assigned_user(client: AsyncClient, sample_hardware_json: bytes):
    await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    resp = await client.get("/devices", params={"assigned_user": "John"})
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert "john" in (item.get("assigned_user_name") or "").lower()


@pytest.mark.asyncio
async def test_filter_by_department(client: AsyncClient, sample_hardware_json: bytes):
    """Department filter should work even if no devices have department set."""
    await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    resp = await client.get("/devices", params={"department": "Engineering"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_combined_filters(client: AsyncClient, sample_hardware_json: bytes):
    """Multiple filters should be applied together (AND logic)."""
    await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    resp = await client.get("/devices", params={"status": "active", "os": "macOS"})
    data = resp.json()
    for item in data["items"]:
        assert item["status"] == "active"
        assert "macOS" in item["os"]
