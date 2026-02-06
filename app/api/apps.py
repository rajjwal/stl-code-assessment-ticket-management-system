"""App CI query endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.app import AppListResponse

router = APIRouter(tags=["apps"])


@router.get("/apps", response_model=AppListResponse)
async def list_apps(
    app_type: str | None = None,
    category: str | None = None,
    sso_enabled: bool | None = None,
    owner: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AppListResponse:
    """List application configuration items with optional filters."""
    # Stub — will be implemented in Phase 3
    return AppListResponse(items=[], total=0, limit=limit, offset=offset)
