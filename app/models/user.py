"""User configuration item ORM model.

Represents identity/access management users (primarily from Okta exports).
Tracks group memberships, MFA status, and app assignments.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.relationships import user_app_assignments


class User(Base):
    """A user configuration item in the CMDB."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    team: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Primary group/department
    groups: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of all groups
    mfa_enabled: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    last_login: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    employee_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # From YAML enrichment
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # From YAML enrichment
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String, default=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        onupdate=lambda: datetime.now(timezone.utc).isoformat(),
    )

    # Many-to-many relationship with apps via user_app_assignments
    apps = relationship("App", secondary=user_app_assignments, back_populates="users")
