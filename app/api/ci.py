"""Unified CI lookup endpoint.

Searches across all CI types (devices, users, apps) by ID.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["ci"])


@router.get("/ci/{ci_id}")
async def get_ci(ci_id: str) -> dict[str, Any]:
    """Fetch a configuration item by ID, searching across all CI types.

    Returns the full CI with relationships, or 404 if not found in any table.
    """
    # Stub — will be implemented in Phase 3
    raise HTTPException(status_code=404, detail=f"CI '{ci_id}' not found")
