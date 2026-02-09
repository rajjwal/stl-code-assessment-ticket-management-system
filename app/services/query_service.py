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
from app.models.relationships import device_app_dependencies, user_app_assignments
from app.models.user import User
from app.services.ai_service import generate_answer, parse_natural_language_query

logger = logging.getLogger(__name__)

# Map entity types to their ORM models and serialization helpers
ENTITY_MODELS = {
    "devices": Device,
    "users": User,
    "apps": App,
}

# Known join paths between entity types.
# Lambdas defer column resolution to call time (avoids circular import issues).
JOIN_PATHS = {
    ("devices", "users"): {
        "condition": lambda: Device.assigned_user_id == User.id,
    },
    ("devices", "apps"): {
        "secondary": device_app_dependencies,
    },
    ("users", "apps"): {
        "secondary": user_app_assignments,
    },
    ("apps", "users"): {
        "secondary": user_app_assignments,
    },
    ("apps", "devices"): {
        "secondary": device_app_dependencies,
    },
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

    # Cross-entity join: filter primary entity based on related entity properties
    join_spec = query_spec.get("join")
    if join_spec:
        query = _apply_join(query, entity_type, join_spec)
        query = query.distinct()

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


def _apply_join(query, primary_entity_type: str, join_spec: dict):
    """Apply a cross-entity join to the query.

    Looks up the join path from JOIN_PATHS, applies the join, then applies
    the join-side filters using the existing _apply_filters logic.

    If the join entity or path is unknown, logs a warning and returns
    the query unchanged (graceful degradation).
    """
    join_entity_type = join_spec.get("entity_type")
    join_model = ENTITY_MODELS.get(join_entity_type)
    join_filters = join_spec.get("filters", {})

    if not join_model:
        logger.warning(f"Unknown join entity type: {join_entity_type}")
        return query

    path_key = (primary_entity_type, join_entity_type)
    join_path = JOIN_PATHS.get(path_key)

    if not join_path:
        logger.warning(f"No join path defined for {path_key}")
        return query

    # Direct FK join vs M2M via junction table
    if "condition" in join_path:
        query = query.join(join_model, join_path["condition"]())
    elif "secondary" in join_path:
        secondary = join_path["secondary"]
        query = query.join(secondary).join(join_model)

    # Apply filters on the joined entity
    query = _apply_filters(query, join_model, join_filters)

    return query


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
                # Case-insensitive match for strings (handles "SaaS" vs "saas")
                if isinstance(value, str):
                    query = query.where(column.ilike(value))
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
