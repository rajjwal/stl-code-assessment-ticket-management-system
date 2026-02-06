"""Pydantic schemas for User CI API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel


class UserResponse(BaseModel):
    """Response schema for a single user configuration item."""

    ci_type: str = "user"
    id: str
    name: str
    email: str | None = None
    team: str | None = None
    groups: list[str] | None = None
    mfa_enabled: bool | None = None
    last_login: str | None = None
    status: str | None = None
    employee_id: str | None = None
    title: str | None = None
    # Related entities
    apps: list[str] | None = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Paginated list of users."""

    items: list[UserResponse]
    total: int
    limit: int
    offset: int
