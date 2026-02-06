"""User CI query endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.user import UserListResponse

router = APIRouter(tags=["users"])


@router.get("/users", response_model=UserListResponse)
async def list_users(
    status: str | None = None,
    team: str | None = None,
    mfa_enabled: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> UserListResponse:
    """List user configuration items with optional filters."""
    # Stub — will be implemented in Phase 3
    return UserListResponse(items=[], total=0, limit=limit, offset=offset)
