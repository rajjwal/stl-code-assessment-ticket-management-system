"""API integration tests for POST /ask endpoint."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ask_returns_200(client: AsyncClient, sample_okta_json: bytes):
    """POST /ask returns 200 even when AI is unavailable (graceful degradation)."""
    await client.post("/ingest", files={"file": ("okta.json", sample_okta_json)})

    with patch("app.services.query_service.parse_natural_language_query",
               new_callable=AsyncMock) as mock_parse, \
         patch("app.services.query_service.generate_answer",
               new_callable=AsyncMock) as mock_answer:
        mock_parse.return_value = {
            "entity_type": "users",
            "filters": {"mfa_enabled": False},
            "sort_by": None,
            "aggregation": "list",
            "limit": None,
        }
        mock_answer.return_value = "3 users without MFA."

        resp = await client.post("/ask", json={"question": "Which users don't have MFA?"})

    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "results" in data
    assert len(data["results"]) == 3


@pytest.mark.asyncio
async def test_ask_active_devices(
    client: AsyncClient, sample_hardware_json: bytes
):
    await client.post("/ingest", files={"file": ("hw.json", sample_hardware_json)})

    with patch("app.services.query_service.parse_natural_language_query",
               new_callable=AsyncMock) as mock_parse, \
         patch("app.services.query_service.generate_answer",
               new_callable=AsyncMock) as mock_answer:
        mock_parse.return_value = {
            "entity_type": "devices",
            "filters": {"status": "active"},
            "sort_by": None,
            "aggregation": "list",
            "limit": None,
        }
        mock_answer.return_value = "2 active devices found."

        resp = await client.post("/ask", json={"question": "Show all active devices"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 2


@pytest.mark.asyncio
async def test_ask_ai_unavailable(client: AsyncClient):
    """When AI is completely unavailable, return a helpful message."""
    with patch("app.services.query_service.parse_natural_language_query",
               new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = None

        resp = await client.post("/ask", json={"question": "test"})

    assert resp.status_code == 200
    data = resp.json()
    assert "unavailable" in data["answer"].lower()


@pytest.mark.asyncio
async def test_ask_empty_question_rejected(client: AsyncClient):
    """Empty question should be rejected by Pydantic validation."""
    # AskRequest requires a non-empty question field
    resp = await client.post("/ask", json={})
    assert resp.status_code == 422
