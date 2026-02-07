"""Device CI query endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.device import Device
from app.schemas.device import DeviceListResponse, DeviceResponse

router = APIRouter(tags=["devices"])


@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    status: Optional[str] = None,
    os: Optional[str] = None,
    location: Optional[str] = None,
    assigned_user: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> DeviceListResponse:
    """List device configuration items with optional filters."""
    query = select(Device)

    if status:
        query = query.where(Device.status == status.lower())
    if os:
        query = query.where(Device.os.ilike(f"%{os}%"))
    if location:
        query = query.where(Device.location.ilike(f"%{location}%"))
    if assigned_user:
        query = query.where(Device.assigned_user_name.ilike(f"%{assigned_user}%"))
    if department:
        query = query.where(Device.department.ilike(f"%{department}%"))

    # Count total matching records (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination and eager-load apps relationship for async safety
    query = query.options(selectinload(Device.apps)).offset(offset).limit(limit)
    result = await db.execute(query)
    devices = result.scalars().all()

    items = [
        DeviceResponse(
            id=d.id,
            hostname=d.hostname,
            ip_address=d.ip_address,
            mac_address=d.mac_address,
            os=d.os,
            assigned_user_id=d.assigned_user_id,
            assigned_user_name=d.assigned_user_name,
            location=d.location,
            status=d.status,
            device_type=d.device_type,
            serial_number=d.serial_number,
            department=d.department,
            encryption_status=d.encryption_status,
            last_checkin=d.last_checkin,
            assigned_apps=[a.name for a in d.apps] if d.apps else None,
        )
        for d in devices
    ]

    return DeviceListResponse(items=items, total=total, limit=limit, offset=offset)
