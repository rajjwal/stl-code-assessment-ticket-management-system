"""API integration tests for POST /ingest endpoint, including AI-enhanced flow."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ingest_hardware_json(client: AsyncClient, sample_hardware_json: bytes):
    resp = await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["records_processed"] == 3
    assert data["records_created"] == 3


@pytest.mark.asyncio
async def test_ingest_okta_json(client: AsyncClient, sample_okta_json: bytes):
    resp = await client.post("/ingest", files={"file": ("okta.json", sample_okta_json)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["records_processed"] == 9


@pytest.mark.asyncio
async def test_ingest_app_json(client: AsyncClient, sample_app_json: bytes):
    resp = await client.post("/ingest", files={"file": ("apps.json", sample_app_json)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["records_processed"] == 6


@pytest.mark.asyncio
async def test_ingest_csv(client: AsyncClient, sample_hardware_csv: bytes):
    resp = await client.post("/ingest", files={"file": ("hw.csv", sample_hardware_csv)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["file_format"] == "csv"


@pytest.mark.asyncio
async def test_ingest_yaml(client: AsyncClient, sample_hardware_yaml: bytes):
    resp = await client.post("/ingest", files={"file": ("hw.yaml", sample_hardware_yaml)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["file_format"] == "yaml"


@pytest.mark.asyncio
async def test_ingest_idempotent(client: AsyncClient, sample_hardware_json: bytes):
    """Re-ingesting the same file should update, not duplicate."""
    resp1 = await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})
    assert resp1.json()["records_created"] == 3

    resp2 = await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})
    data2 = resp2.json()
    assert data2["records_created"] == 0
    assert data2["records_updated"] == 3


@pytest.mark.asyncio
async def test_ingest_invalid_format(client: AsyncClient):
    """Unrecognizable content should return a failure."""
    resp = await client.post(
        "/ingest",
        files={"file": ("data.xyz", b"totally random binary content \x00\x01\x02")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"


@pytest.mark.asyncio
async def test_ingest_with_ai_enrichment(client: AsyncClient, sample_hardware_json: bytes):
    """When AI is available, records should be enriched (mocked)."""
    enriched = [
        {"device_id": "C-19283", "hostname": "laptop-jdoe", "os": "macOS",
         "device_type": "laptop", "status": "active", "ip_address": "10.10.22.5",
         "assigned_to": "John D.", "location": "New York HQ",
         "last_checkin": "2024-06-12T14:30:00Z"},
        {"device_id": "D-10005", "hostname": "laptop-devops", "os": "Ubuntu 22.04 LTS",
         "device_type": "laptop", "status": "active", "ip_address": "10.10.22.45",
         "assigned_to": "Sarah Chen"},
        {"device_id": "HW-2024-003", "hostname": "macbook-cto-01", "os": "macOS",
         "device_type": "laptop", "status": "inactive", "assigned_to": "Jane Doe",
         "location": "New York HQ"},
    ]

    with patch("app.services.ingestion.extract_and_structure",
               new_callable=AsyncMock) as mock_extract, \
         patch("app.services.ingestion.enrich",
               new_callable=AsyncMock) as mock_enrich:
        mock_extract.return_value = enriched
        # Must be a different list object so identity check (is not) works
        mock_enrich.return_value = [dict(r) for r in enriched]

        resp = await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    data = resp.json()
    assert data["status"] == "success"
    assert data["ai_enrichments_applied"] == 2  # extract + enrich

    # Verify device_type was enriched
    dev_resp = await client.get("/ci/C-19283")
    dev_data = dev_resp.json()
    assert dev_data["device_type"] == "laptop"


@pytest.mark.asyncio
async def test_ingest_ai_failure_graceful(client: AsyncClient, sample_hardware_json: bytes):
    """When AI fails, ingestion should still succeed with rule-based data."""
    with patch("app.services.ingestion.extract_and_structure",
               new_callable=AsyncMock) as mock_extract, \
         patch("app.services.ingestion.enrich",
               new_callable=AsyncMock) as mock_enrich:
        mock_extract.side_effect = Exception("API timeout")
        mock_enrich.side_effect = Exception("API timeout")

        resp = await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    data = resp.json()
    # Should still succeed (with errors noted)
    assert data["records_processed"] == 3
    assert data["records_created"] == 3
