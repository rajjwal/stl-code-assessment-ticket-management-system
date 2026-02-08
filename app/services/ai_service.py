"""OpenRouter AI service for data extraction, enrichment, and NL queries.

Three focused methods, each with a separate prompt optimized for its task:
1. extract_and_structure — convert raw records into normalized CI schema
2. enrich — fill gaps in partially-structured records
3. parse_natural_language_query — convert NL question to structured filters
4. generate_answer — format query results into human-readable text

Uses httpx.AsyncClient with retry logic and graceful degradation.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Target schemas for AI extraction
DEVICE_SCHEMA = {
    "device_id": "string (required, e.g. 'C-19283')",
    "hostname": "string (required)",
    "ip_address": "string or null (valid IPv4)",
    "mac_address": "string or null",
    "os": "string or null (normalize: 'macos'→'macOS', 'win11'→'Windows 11', 'Ubuntu 22'→'Ubuntu 22.04 LTS')",
    "assigned_to": "string or null (person name)",
    "location": "string or null",
    "status": "string or null ('active', 'inactive', 'deactivated', 'suspended')",
    "device_type": "string or null ('laptop', 'desktop', 'server', 'workstation')",
    "serial_number": "string or null",
    "department": "string or null",
    "encryption_status": "string or null",
    "last_checkin": "string or null (ISO 8601 date)",
}

USER_SCHEMA = {
    "user_id": "string (required, e.g. 'u_999')",
    "name": "string (required, full name)",
    "email": "string or null",
    "groups": "list of strings or null",
    "apps": "list of strings or null (app names the user uses)",
    "mfa_enabled": "boolean or null",
    "last_login": "string or null (ISO 8601 date)",
    "status": "string or null ('active', 'inactive', 'deactivated', 'suspended')",
}

APP_SCHEMA = {
    "app_id": "string (required, e.g. 'APP-001')",
    "name": "string (required)",
    "vendor": "string or null",
    "app_type": "string or null ('SaaS' or 'on-premise')",
    "category": "string or null",
    "deployment": "string or null",
    "owner": "string or null",
    "users_count": "integer or null",
    "integrations": "list of strings or null",
    "sso_enabled": "boolean or null",
    "annual_cost_usd": "number or null",
    "contract_renewal": "string or null (ISO 8601 date)",
    "server_location": "string or null",
    "version": "string or null",
}

SCHEMAS = {"hardware": DEVICE_SCHEMA, "okta": USER_SCHEMA, "app": APP_SCHEMA}

# Available fields for NL query parsing
QUERYABLE_FIELDS = {
    "devices": {
        "id": "text", "hostname": "text", "ip_address": "text",
        "os": "text", "assigned_user_name": "text", "location": "text",
        "status": "text", "device_type": "text", "department": "text",
        "encryption_status": "text", "last_checkin": "date",
    },
    "users": {
        "id": "text", "name": "text", "email": "text", "team": "text",
        "mfa_enabled": "boolean", "last_login": "date", "status": "text",
        "title": "text",
    },
    "apps": {
        "id": "text", "name": "text", "vendor": "text", "app_type": "text",
        "category": "text", "owner": "text", "users_count": "integer",
        "sso_enabled": "boolean", "annual_cost_usd": "number",
        "server_location": "text", "version": "text",
    },
}

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 1


async def _call_openrouter(
    messages: list[dict[str, str]],
    max_tokens: Optional[int] = None,
) -> Optional[str]:
    """Make an API call to OpenRouter with retry on transient errors.

    Returns the response content string, or None if all retries fail.
    """
    if not settings.OPENROUTER_API_KEY:
        logger.warning("No OPENROUTER_API_KEY configured, skipping AI call")
        return None

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.AI_MODEL,
        "messages": messages,
        "temperature": settings.AI_TEMPERATURE,
        "max_tokens": max_tokens or settings.AI_MAX_TOKENS,
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]

            if response.status_code in (429, 500, 502, 503):
                logger.warning(
                    f"OpenRouter API returned {response.status_code}, "
                    f"attempt {attempt + 1}/{MAX_RETRIES + 1}"
                )
                if attempt < MAX_RETRIES:
                    import asyncio
                    await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                    continue

            logger.error(
                f"OpenRouter API error: {response.status_code} - {response.text}"
            )
            return None

        except httpx.TimeoutException:
            logger.warning(f"OpenRouter timeout, attempt {attempt + 1}/{MAX_RETRIES + 1}")
            if attempt < MAX_RETRIES:
                import asyncio
                await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                continue
            return None
        except Exception as e:
            logger.exception(f"OpenRouter call failed: {e}")
            return None

    return None


def _extract_json_from_response(text: str) -> Any:
    """Parse JSON from an AI response, handling markdown code fences."""
    cleaned = text.strip()
    # Strip markdown code fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (``` markers)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


async def extract_and_structure(
    raw_records: list[dict],
    source_type: str,
) -> list[dict]:
    """Use AI to extract and structure raw records into the target schema.

    Falls back to returning input unchanged if AI is unavailable.
    """
    schema = SCHEMAS.get(source_type)
    if not schema:
        return raw_records

    prompt = f"""You are a data extraction assistant for an IT Configuration Management Database (CMDB).

Given these raw records from a {source_type} data source, extract and structure each record
to match the target schema below. Apply these normalization rules:

- OS names: "macos" → "macOS", "win11" → "Windows 11", "win10" → "Windows 10", "Ubuntu 22" → "Ubuntu 22.04 LTS"
- Status values: normalize to lowercase ("ACTIVE" → "active", "SUSPENDED" → "suspended")
- App types: "on-prem" or "on-premise" → "on-premise"
- Dates: convert to ISO 8601 format
- Device types: infer from hostname if possible ("laptop-*" → "laptop", "server-*" → "server")
- Preserve all original field values where possible, only normalize formats

TARGET SCHEMA:
{json.dumps(schema, indent=2)}

RAW RECORDS:
{json.dumps(raw_records, indent=2)}

Return ONLY a JSON array of structured records matching the target schema. No explanation."""

    response = await _call_openrouter([
        {"role": "system", "content": "You output ONLY valid JSON arrays. No markdown, no explanation."},
        {"role": "user", "content": prompt},
    ])

    if response is None:
        logger.info("AI extraction unavailable, using raw records")
        return raw_records

    try:
        structured = _extract_json_from_response(response)
        if isinstance(structured, list) and len(structured) > 0:
            return structured
        logger.warning("AI extraction returned unexpected format, using raw records")
        return raw_records
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse AI extraction response: {e}")
        return raw_records


async def enrich(
    records: list[dict],
    source_type: str,
) -> list[dict]:
    """Use AI to fill gaps in partially-structured records.

    Only makes high-confidence inferences. Will NOT fabricate:
    - Serial numbers, MAC addresses, or IP addresses
    - Specific dates or timestamps
    - User emails or IDs
    """
    prompt = f"""You are a data enrichment assistant for an IT CMDB. Given these {source_type} records,
fill in missing fields ONLY where you can make high-confidence inferences from context.

RULES:
- You may infer device_type from hostname patterns (e.g., "laptop-jdoe" → "laptop", "server-prod" → "server")
- You may infer department from team/group names (e.g., "Engineering" group → department "Engineering")
- You may expand abbreviated names if context is clear (e.g., "John D." might stay as-is if ambiguous)
- You MUST NOT fabricate: serial numbers, MAC addresses, IP addresses, specific dates, email addresses
- You MUST NOT change existing non-null values
- Return ALL records, even if unchanged

RECORDS:
{json.dumps(records, indent=2)}

Return ONLY a JSON array of enriched records. No explanation."""

    response = await _call_openrouter([
        {"role": "system", "content": "You output ONLY valid JSON arrays. No markdown, no explanation."},
        {"role": "user", "content": prompt},
    ])

    if response is None:
        logger.info("AI enrichment unavailable, using existing records")
        return records

    try:
        enriched = _extract_json_from_response(response)
        if isinstance(enriched, list) and len(enriched) == len(records):
            return enriched
        logger.warning("AI enrichment returned wrong number of records, using originals")
        return records
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse AI enrichment response: {e}")
        return records


async def parse_natural_language_query(question: str) -> Optional[dict]:
    """Convert a natural language question into structured database filters.

    Returns a dict with: entity_type, filters, sort_by, aggregation, limit.
    """
    prompt = f"""You are a query parser for an IT CMDB database with three entity types: devices, users, apps.

Convert this natural language question into a structured JSON query.

AVAILABLE ENTITIES AND FIELDS:
{json.dumps(QUERYABLE_FIELDS, indent=2)}

FILTER OPERATORS:
- For exact match: {{"field": "value"}}
- For contains/partial match: {{"field__contains": "value"}}
- For boolean: {{"field": true}} or {{"field": false}}
- For greater than: {{"field__gt": "value"}}
- For less than: {{"field__lt": "value"}}

QUESTION: "{question}"

Return a JSON object with this structure:
{{
    "entity_type": "devices" | "users" | "apps",
    "filters": {{}},
    "sort_by": "field_name" or null,
    "aggregation": "count" | "list" | null,
    "limit": number or null
}}

Examples:
- "Which users don't have MFA?" → {{"entity_type": "users", "filters": {{"mfa_enabled": false}}, "sort_by": null, "aggregation": "list", "limit": null}}
- "How many SaaS apps?" → {{"entity_type": "apps", "filters": {{"app_type": "SaaS"}}, "sort_by": null, "aggregation": "count", "limit": null}}
- "Show active devices in London" → {{"entity_type": "devices", "filters": {{"status": "active", "location__contains": "London"}}, "sort_by": null, "aggregation": "list", "limit": null}}

Return ONLY the JSON object. No explanation."""

    response = await _call_openrouter([
        {"role": "system", "content": "You output ONLY valid JSON objects. No markdown, no explanation."},
        {"role": "user", "content": prompt},
    ])

    if response is None:
        return None

    try:
        parsed = _extract_json_from_response(response)
        if isinstance(parsed, dict) and "entity_type" in parsed:
            return parsed
        logger.warning("AI query parsing returned unexpected format")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse AI query response: {e}")
        return None


async def generate_answer(
    question: str,
    results: list[dict],
    query_interpretation: dict,
) -> str:
    """Format query results into a human-readable answer."""
    prompt = f"""You are a helpful IT asset management assistant. A user asked this question about their CMDB:

QUESTION: "{question}"

The query was interpreted as: {json.dumps(query_interpretation)}

RESULTS ({len(results)} records found):
{json.dumps(results[:20], indent=2)}

Provide a clear, concise answer to the user's question based on these results.
- If it's a count question, state the count clearly
- If it's a list question, summarize the key items
- If no results were found, say so clearly
- Keep the answer under 200 words
- Do not include raw JSON in your answer"""

    response = await _call_openrouter([
        {"role": "system", "content": "You are a helpful CMDB assistant. Give clear, concise answers."},
        {"role": "user", "content": prompt},
    ])

    if response is None:
        # Fallback: generate a basic answer without AI
        if not results:
            return f"No results found for your query about {query_interpretation.get('entity_type', 'items')}."
        return f"Found {len(results)} {query_interpretation.get('entity_type', 'item')}(s) matching your query."

    return response.strip()
