"""Device CI query endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.device import DeviceListResponse

router = APIRouter(tags=["devices"])


@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    status: str | None = None,
    os: str | None = None,
    location: str | None = None,
    department: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> DeviceListResponse:
    """List device configuration items with optional filters."""
    # Stub — will be implemented in Phase 3
    return DeviceListResponse(items=[], total=0, limit=limit, offset=offset)
