"""Unified CI lookup endpoint.

Searches across all CI types (devices, users, apps) by ID.
Returns the full CI with its relationships.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.app import App
from app.models.device import Device
from app.models.relationships import app_integrations
from app.models.user import User

router = APIRouter(tags=["ci"])


@router.get("/ci/{ci_id}")
async def get_ci(
    ci_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Fetch a configuration item by ID, searching across all CI types.

    Returns the full CI with relationships, or 404 if not found in any table.
    """
    # Search devices first
    result = await db.execute(
        select(Device).options(selectinload(Device.apps)).where(Device.id == ci_id)
    )
    device = result.scalar_one_or_none()
    if device:
        return _device_detail(device)

    # Search users
    result = await db.execute(
        select(User).options(selectinload(User.apps)).where(User.id == ci_id)
    )
    user = result.scalar_one_or_none()
    if user:
        return _user_detail(user)

    # Search apps
    result = await db.execute(select(App).where(App.id == ci_id))
    app = result.scalar_one_or_none()
    if app:
        return await _app_detail(db, app)

    raise HTTPException(status_code=404, detail=f"CI '{ci_id}' not found")


def _device_detail(device: Device) -> dict[str, Any]:
    """Build full device response with relationships."""
    return {
        "ci_type": "device",
        "id": device.id,
        "hostname": device.hostname,
        "ip_address": device.ip_address,
        "mac_address": device.mac_address,
        "os": device.os,
        "assigned_user_id": device.assigned_user_id,
        "assigned_user_name": device.assigned_user_name,
        "location": device.location,
        "status": device.status,
        "device_type": device.device_type,
        "serial_number": device.serial_number,
        "department": device.department,
        "encryption_status": device.encryption_status,
        "last_checkin": device.last_checkin,
        "assigned_apps": [a.name for a in device.apps] if device.apps else [],
    }


def _user_detail(user: User) -> dict[str, Any]:
    """Build full user response with relationships."""
    groups = None
    if user.groups:
        try:
            groups = json.loads(user.groups)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "ci_type": "user",
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "team": user.team,
        "groups": groups,
        "mfa_enabled": user.mfa_enabled,
        "last_login": user.last_login,
        "status": user.status,
        "employee_id": user.employee_id,
        "title": user.title,
        "apps": [a.name for a in user.apps] if user.apps else [],
    }


async def _app_detail(db: AsyncSession, app: App) -> dict[str, Any]:
    """Build full app response with integration details."""
    # Fetch integration names
    result = await db.execute(
        select(
            app_integrations.c.target_app_name,
            app_integrations.c.target_app_id,
        ).where(app_integrations.c.source_app_id == app.id)
    )
    integrations = [
        {"name": row[0], "resolved_id": row[1]} for row in result.fetchall()
    ]

    return {
        "ci_type": "app",
        "id": app.id,
        "name": app.name,
        "vendor": app.vendor,
        "app_type": app.app_type,
        "category": app.category,
        "deployment": app.deployment,
        "owner": app.owner,
        "users_count": app.users_count,
        "sso_enabled": app.sso_enabled,
        "annual_cost_usd": app.annual_cost_usd,
        "contract_renewal": app.contract_renewal,
        "server_location": app.server_location,
        "version": app.version,
        "integrations": integrations,
    }
