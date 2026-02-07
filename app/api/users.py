"""User CI query endpoints."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserListResponse, UserResponse

router = APIRouter(tags=["users"])


@router.get("/users", response_model=UserListResponse)
async def list_users(
    status: Optional[str] = None,
    team: Optional[str] = None,
    mfa_enabled: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """List user configuration items with optional filters."""
    query = select(User)

    if status:
        query = query.where(User.status == status.lower())
    if team:
        query = query.where(User.team.ilike(f"%{team}%"))
    if mfa_enabled is not None:
        query = query.where(User.mfa_enabled == mfa_enabled)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.options(selectinload(User.apps)).offset(offset).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    items = [_user_to_response(u) for u in users]

    return UserListResponse(items=items, total=total, limit=limit, offset=offset)


def _user_to_response(user: User) -> UserResponse:
    """Convert a User ORM instance to a response schema."""
    # Parse groups JSON string back to list
    groups = None
    if user.groups:
        try:
            groups = json.loads(user.groups)
        except (json.JSONDecodeError, TypeError):
            groups = None

    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        team=user.team,
        groups=groups,
        mfa_enabled=user.mfa_enabled,
        last_login=user.last_login,
        status=user.status,
        employee_id=user.employee_id,
        title=user.title,
        apps=[a.name for a in user.apps] if user.apps else None,
    )
