"""API tests for health check and miscellaneous endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """GET / should return a healthy status."""
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "AI-First CMDB"


@pytest.mark.asyncio
async def test_docs_endpoint(client: AsyncClient):
    """Swagger UI should be accessible at /docs."""
    resp = await client.get("/docs")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_openapi_schema(client: AsyncClient):
    """OpenAPI JSON schema should be accessible."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["info"]["title"] == "AI-First CMDB"
