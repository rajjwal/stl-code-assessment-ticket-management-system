"""Post-ingestion relationship resolver.

Runs after all records are upserted to link CIs across data sources using
fuzzy string matching. Handles three relationship types:

1. Device → User: matches device.assigned_user_name against user.name
2. User → App: matches Okta user's apps list against app.name
3. App → App: matches integration names against known app names
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app import App
from app.models.device import Device
from app.models.user import User
from app.models.relationships import (
    app_integrations,
    user_app_assignments,
)
from app.utils.fuzzy_match import best_match

logger = logging.getLogger(__name__)


async def resolve_relationships(db: AsyncSession) -> dict:
    """Resolve all cross-source relationships after ingestion.

    Returns:
        Summary dict with counts of resolved relationships.
    """
    summary = {
        "device_user_links": 0,
        "user_app_links": 0,
        "app_integration_links": 0,
    }

    summary["device_user_links"] = await _resolve_device_user(db)
    summary["user_app_links"] = await _resolve_user_app(db)
    summary["app_integration_links"] = await _resolve_app_integrations(db)

    await db.commit()
    return summary


async def _resolve_device_user(db: AsyncSession) -> int:
    """Link devices to users by fuzzy matching assigned_user_name → user.name."""
    result = await db.execute(select(Device))
    devices = result.scalars().all()

    result = await db.execute(select(User))
    users = result.scalars().all()

    if not users:
        return 0

    user_names = [u.name for u in users]
    user_name_to_id = {u.name: u.id for u in users}
    links = 0

    for device in devices:
        if not device.assigned_user_name:
            continue

        matched_name = best_match(device.assigned_user_name, user_names)
        if matched_name and matched_name in user_name_to_id:
            device.assigned_user_id = user_name_to_id[matched_name]
            # Update the display name to the canonical form
            device.assigned_user_name = matched_name
            links += 1
            logger.debug(
                f"Linked device {device.id} → user {device.assigned_user_id} "
                f"('{device.assigned_user_name}' matched '{matched_name}')"
            )

    return links


async def _resolve_user_app(db: AsyncSession) -> int:
    """Link users to apps by fuzzy matching their apps list against app.name."""
    result = await db.execute(select(User))
    users = result.scalars().all()

    result = await db.execute(select(App))
    apps = result.scalars().all()

    if not apps:
        return 0

    app_names = [a.name for a in apps]
    app_name_to_id = {a.name: a.id for a in apps}
    links = 0

    # Clear existing assignments to rebuild from current data
    await db.execute(delete(user_app_assignments))

    for user in users:
        user_apps = _get_user_apps(user)
        if not user_apps:
            continue

        for app_name in user_apps:
            matched = best_match(app_name, app_names)
            if matched and matched in app_name_to_id:
                await db.execute(
                    user_app_assignments.insert().values(
                        user_id=user.id,
                        app_id=app_name_to_id[matched],
                    )
                )
                links += 1
                logger.debug(
                    f"Linked user {user.id} → app {app_name_to_id[matched]} "
                    f"('{app_name}' matched '{matched}')"
                )

    return links


async def _resolve_app_integrations(db: AsyncSession) -> int:
    """Link apps to their integration targets by fuzzy matching names."""
    result = await db.execute(select(App))
    apps = result.scalars().all()

    app_names = [a.name for a in apps]
    app_name_to_id = {a.name: a.id for a in apps}
    links = 0

    # Clear existing integrations to rebuild
    await db.execute(delete(app_integrations))

    for app in apps:
        integration_names = _get_app_integrations(app)
        if not integration_names:
            continue

        for int_name in integration_names:
            # Find if the integration target exists as a known app
            matched = best_match(int_name, app_names)
            target_id: Optional[str] = None
            if matched and matched in app_name_to_id:
                target_id = app_name_to_id[matched]

            await db.execute(
                app_integrations.insert().values(
                    source_app_id=app.id,
                    target_app_id=target_id,
                    target_app_name=int_name,
                )
            )
            links += 1

    return links


def _get_user_apps(user: User) -> list[str]:
    """Extract the apps list from a user's raw_data JSON."""
    if not user.raw_data:
        return []
    try:
        data = json.loads(user.raw_data)
        apps = data.get("apps", [])
        return apps if isinstance(apps, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _get_app_integrations(app: App) -> list[str]:
    """Extract integration names from an app's raw_data JSON."""
    if not app.raw_data:
        return []
    try:
        data = json.loads(app.raw_data)
        integrations = data.get("integrations", [])
        return integrations if isinstance(integrations, list) else []
    except (json.JSONDecodeError, TypeError):
        return []
