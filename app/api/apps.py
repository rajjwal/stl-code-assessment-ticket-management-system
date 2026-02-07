"""App CI query endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.app import App
from app.models.relationships import app_integrations
from app.schemas.app import AppListResponse, AppResponse

router = APIRouter(tags=["apps"])


@router.get("/apps", response_model=AppListResponse)
async def list_apps(
    app_type: Optional[str] = None,
    category: Optional[str] = None,
    sso_enabled: Optional[bool] = None,
    owner: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> AppListResponse:
    """List application configuration items with optional filters."""
    query = select(App)

    if app_type:
        query = query.where(App.app_type.ilike(f"%{app_type}%"))
    if category:
        query = query.where(App.category.ilike(f"%{category}%"))
    if sso_enabled is not None:
        query = query.where(App.sso_enabled == sso_enabled)
    if owner:
        query = query.where(App.owner.ilike(f"%{owner}%"))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    apps = result.scalars().all()

    items = []
    for app in apps:
        integration_names = await _get_integration_names(db, app.id)
        items.append(_app_to_response(app, integration_names))

    return AppListResponse(items=items, total=total, limit=limit, offset=offset)


async def _get_integration_names(db: AsyncSession, app_id: str) -> list[str]:
    """Fetch integration target names for an app."""
    result = await db.execute(
        select(app_integrations.c.target_app_name).where(
            app_integrations.c.source_app_id == app_id
        )
    )
    return [row[0] for row in result.fetchall()]


def _app_to_response(
    app: App, integration_names: Optional[list[str]] = None
) -> AppResponse:
    """Convert an App ORM instance to a response schema."""
    return AppResponse(
        id=app.id,
        name=app.name,
        vendor=app.vendor,
        app_type=app.app_type,
        category=app.category,
        deployment=app.deployment,
        owner=app.owner,
        users_count=app.users_count,
        sso_enabled=app.sso_enabled,
        annual_cost_usd=app.annual_cost_usd,
        contract_renewal=app.contract_renewal,
        server_location=app.server_location,
        version=app.version,
        integrations=integration_names or None,
    )
