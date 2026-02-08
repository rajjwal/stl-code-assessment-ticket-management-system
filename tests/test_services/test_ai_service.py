"""Tests for AI service with mocked OpenRouter responses."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai_service import (
    _extract_json_from_response,
    extract_and_structure,
    enrich,
    generate_answer,
    parse_natural_language_query,
)


class TestExtractJsonFromResponse:
    """Tests for parsing JSON from AI response text."""

    def test_plain_json(self):
        result = _extract_json_from_response('[{"id": 1}]')
        assert result == [{"id": 1}]

    def test_json_with_code_fence(self):
        text = '```json\n[{"id": 1}]\n```'
        result = _extract_json_from_response(text)
        assert result == [{"id": 1}]

    def test_json_with_plain_fence(self):
        text = '```\n{"key": "value"}\n```'
        result = _extract_json_from_response(text)
        assert result == {"key": "value"}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _extract_json_from_response("not json at all")


class TestExtractAndStructure:
    """Tests for AI extraction with mocked responses."""

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        mock_response = json.dumps([
            {"device_id": "C-1", "hostname": "laptop-test", "os": "macOS", "status": "active"}
        ])

        with patch("app.services.ai_service._call_openrouter", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await extract_and_structure(
                [{"device_id": "C-1", "hostname": "laptop-test", "os": "macos"}],
                "hardware",
            )

        assert len(result) == 1
        assert result[0]["device_id"] == "C-1"

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_ai_failure(self):
        """When AI is unavailable, return input unchanged."""
        raw = [{"device_id": "C-1", "hostname": "test"}]

        with patch("app.services.ai_service._call_openrouter", new_callable=AsyncMock) as mock:
            mock.return_value = None
            result = await extract_and_structure(raw, "hardware")

        assert result == raw

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_bad_json(self):
        with patch("app.services.ai_service._call_openrouter", new_callable=AsyncMock) as mock:
            mock.return_value = "not valid json"
            raw = [{"device_id": "C-1"}]
            result = await extract_and_structure(raw, "hardware")

        assert result == raw

    @pytest.mark.asyncio
    async def test_unknown_source_type_passthrough(self):
        raw = [{"id": "1"}]
        result = await extract_and_structure(raw, "unknown_type")
        assert result == raw


class TestEnrich:
    """Tests for AI enrichment with mocked responses."""

    @pytest.mark.asyncio
    async def test_successful_enrichment(self):
        enriched_data = [{"device_id": "C-1", "hostname": "laptop-test", "device_type": "laptop"}]
        mock_response = json.dumps(enriched_data)

        with patch("app.services.ai_service._call_openrouter", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await enrich([{"device_id": "C-1", "hostname": "laptop-test"}], "hardware")

        assert result[0]["device_type"] == "laptop"

    @pytest.mark.asyncio
    async def test_wrong_record_count_uses_originals(self):
        """If AI returns different number of records, use originals."""
        with patch("app.services.ai_service._call_openrouter", new_callable=AsyncMock) as mock:
            mock.return_value = json.dumps([{"id": 1}])  # 1 record instead of 2
            originals = [{"id": 1}, {"id": 2}]
            result = await enrich(originals, "hardware")

        assert result == originals

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        with patch("app.services.ai_service._call_openrouter", new_callable=AsyncMock) as mock:
            mock.return_value = None
            originals = [{"device_id": "C-1"}]
            result = await enrich(originals, "hardware")

        assert result == originals


class TestParseNaturalLanguageQuery:
    """Tests for NL → structured query parsing."""

    @pytest.mark.asyncio
    async def test_successful_parse(self):
        query_spec = {
            "entity_type": "users",
            "filters": {"mfa_enabled": False},
            "sort_by": None,
            "aggregation": "list",
            "limit": None,
        }

        with patch("app.services.ai_service._call_openrouter", new_callable=AsyncMock) as mock:
            mock.return_value = json.dumps(query_spec)
            result = await parse_natural_language_query("Which users don't have MFA?")

        assert result is not None
        assert result["entity_type"] == "users"
        assert result["filters"]["mfa_enabled"] is False

    @pytest.mark.asyncio
    async def test_ai_unavailable_returns_none(self):
        with patch("app.services.ai_service._call_openrouter", new_callable=AsyncMock) as mock:
            mock.return_value = None
            result = await parse_natural_language_query("test question")

        assert result is None

    @pytest.mark.asyncio
    async def test_bad_json_returns_none(self):
        with patch("app.services.ai_service._call_openrouter", new_callable=AsyncMock) as mock:
            mock.return_value = "not json"
            result = await parse_natural_language_query("test question")

        assert result is None


class TestGenerateAnswer:
    """Tests for AI answer generation."""

    @pytest.mark.asyncio
    async def test_successful_answer(self):
        with patch("app.services.ai_service._call_openrouter", new_callable=AsyncMock) as mock:
            mock.return_value = "There are 3 users without MFA enabled."
            result = await generate_answer(
                "Which users don't have MFA?",
                [{"name": "User1"}, {"name": "User2"}, {"name": "User3"}],
                {"entity_type": "users", "filters": {"mfa_enabled": False}},
            )

        assert "3" in result or "users" in result.lower()

    @pytest.mark.asyncio
    async def test_fallback_answer_on_ai_failure(self):
        with patch("app.services.ai_service._call_openrouter", new_callable=AsyncMock) as mock:
            mock.return_value = None
            result = await generate_answer(
                "test", [{"id": 1}], {"entity_type": "users"}
            )

        assert "1" in result  # Should mention the count

    @pytest.mark.asyncio
    async def test_fallback_no_results(self):
        with patch("app.services.ai_service._call_openrouter", new_callable=AsyncMock) as mock:
            mock.return_value = None
            result = await generate_answer(
                "test", [], {"entity_type": "users"}
            )

        assert "no results" in result.lower() or "No results" in result
