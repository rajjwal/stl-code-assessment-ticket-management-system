"""Natural language query handler.

Converts user questions into database queries via AI, executes them
deterministically against SQLite, then uses AI to format results
into human-readable answers.

Flow: question → AI parse → build SQLAlchemy query → execute → AI answer
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app import App
from app.models.device import Device
from app.models.user import User
from app.services.ai_service import generate_answer, parse_natural_language_query

logger = logging.getLogger(__name__)

# Map entity types to their ORM models and serialization helpers
ENTITY_MODELS = {
    "devices": Device,
    "users": User,
    "apps": App,
}


async def handle_question(
    question: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """Process a natural language question and return structured results.

    Returns:
        Dict with: answer (str), results (list), query_interpretation (str)
    """
    # Step 1: AI parses the question into structured filters
    query_spec = await parse_natural_language_query(question)

    if query_spec is None:
        return {
            "answer": "I'm sorry, the AI service is currently unavailable. Please try again later.",
            "results": [],
            "query_interpretation": "AI service unavailable",
        }

    entity_type = query_spec.get("entity_type", "devices")
    filters = query_spec.get("filters", {})
    aggregation = query_spec.get("aggregation")
    limit = query_spec.get("limit")

    interpretation = json.dumps(query_spec)

    # Step 2: Build and execute the database query
    model = ENTITY_MODELS.get(entity_type)
    if not model:
        return {
            "answer": f"Unknown entity type: {entity_type}",
            "results": [],
            "query_interpretation": interpretation,
        }

    query = select(model)
    query = _apply_filters(query, model, filters)

    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    rows = result.scalars().all()

    # Step 3: Serialize results
    results = [_serialize_row(row, entity_type) for row in rows]

    # Step 4: AI generates a human-readable answer
    answer = await generate_answer(question, results, query_spec)

    return {
        "answer": answer,
        "results": results,
        "query_interpretation": interpretation,
    }


def _apply_filters(query, model, filters: dict):
    """Apply parsed filters to a SQLAlchemy query.

    Supports operators: exact match, __contains, __gt, __lt.
    """
    for key, value in filters.items():
        if "__contains" in key:
            field_name = key.replace("__contains", "")
            column = getattr(model, field_name, None)
            if column is not None:
                query = query.where(column.ilike(f"%{value}%"))

        elif "__gt" in key:
            field_name = key.replace("__gt", "")
            column = getattr(model, field_name, None)
            if column is not None:
                query = query.where(column > value)

        elif "__lt" in key:
            field_name = key.replace("__lt", "")
            column = getattr(model, field_name, None)
            if column is not None:
                query = query.where(column < value)

        else:
            column = getattr(model, key, None)
            if column is not None:
                # Handle string status values — case-insensitive
                if isinstance(value, str):
                    query = query.where(column == value.lower())
                else:
                    query = query.where(column == value)

    return query


def _serialize_row(row: Any, entity_type: str) -> dict[str, Any]:
    """Convert an ORM model instance to a plain dict for the response."""
    if entity_type == "devices":
        return {
            "id": row.id,
            "hostname": row.hostname,
            "ip_address": row.ip_address,
            "os": row.os,
            "assigned_user_name": row.assigned_user_name,
            "location": row.location,
            "status": row.status,
            "device_type": row.device_type,
            "department": row.department,
        }
    elif entity_type == "users":
        groups = None
        if row.groups:
            try:
                groups = json.loads(row.groups)
            except (json.JSONDecodeError, TypeError):
                pass
        return {
            "id": row.id,
            "name": row.name,
            "email": row.email,
            "team": row.team,
            "groups": groups,
            "mfa_enabled": row.mfa_enabled,
            "last_login": row.last_login,
            "status": row.status,
        }
    elif entity_type == "apps":
        return {
            "id": row.id,
            "name": row.name,
            "vendor": row.vendor,
            "app_type": row.app_type,
            "category": row.category,
            "owner": row.owner,
            "sso_enabled": row.sso_enabled,
            "users_count": row.users_count,
        }
    else:
        return {"id": getattr(row, "id", None)}
