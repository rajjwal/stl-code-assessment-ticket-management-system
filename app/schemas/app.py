"""Pydantic schemas for App CI API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel


class AppResponse(BaseModel):
    """Response schema for a single application configuration item."""

    ci_type: str = "app"
    id: str
    name: str
    vendor: str | None = None
    app_type: str | None = None
    category: str | None = None
    deployment: str | None = None
    owner: str | None = None
    users_count: int | None = None
    sso_enabled: bool | None = None
    annual_cost_usd: float | None = None
    contract_renewal: str | None = None
    server_location: str | None = None
    version: str | None = None
    # Related entities
    integrations: list[str] | None = None

    model_config = {"from_attributes": True}


class AppListResponse(BaseModel):
    """Paginated list of applications."""

    items: list[AppResponse]
    total: int
    limit: int
    offset: int
