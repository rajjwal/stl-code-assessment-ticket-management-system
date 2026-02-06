"""Application configuration item ORM model.

Represents SaaS and on-premise applications in the organization's portfolio.
Tracks ownership, cost, integrations, and SSO status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.relationships import (
    app_integrations,
    device_app_dependencies,
    user_app_assignments,
)


class App(Base):
    """An application configuration item in the CMDB."""

    __tablename__ = "apps"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    vendor: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    app_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # "SaaS" or "on-premise"
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deployment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    users_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sso_enabled: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    annual_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    contract_renewal: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    server_location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String, default=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        onupdate=lambda: datetime.now(timezone.utc).isoformat(),
    )

    # Many-to-many relationships
    users = relationship("User", secondary=user_app_assignments, back_populates="apps")
    devices = relationship("Device", secondary=device_app_dependencies, back_populates="apps")

    # Self-referential: apps this app integrates with (where target exists in CMDB)
    integrations = relationship(
        "App",
        secondary=app_integrations,
        primaryjoin=id == app_integrations.c.source_app_id,
        secondaryjoin=id == app_integrations.c.target_app_id,
        viewonly=True,
    )
