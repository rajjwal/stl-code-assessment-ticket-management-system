"""Pydantic schemas for Device CI API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel


class DeviceResponse(BaseModel):
    """Response schema for a single device configuration item."""

    ci_type: str = "device"
    id: str
    hostname: str
    ip_address: str | None = None
    mac_address: str | None = None
    os: str | None = None
    assigned_user_id: str | None = None
    assigned_user_name: str | None = None
    location: str | None = None
    status: str | None = None
    device_type: str | None = None
    serial_number: str | None = None
    department: str | None = None
    encryption_status: str | None = None
    last_checkin: str | None = None
    # Related entities (populated when fetching full details)
    assigned_apps: list[str] | None = None

    model_config = {"from_attributes": True}


class DeviceListResponse(BaseModel):
    """Paginated list of devices."""

    items: list[DeviceResponse]
    total: int
    limit: int
    offset: int
