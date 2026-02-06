"""Device configuration item ORM model.

Represents physical or virtual hardware assets (laptops, desktops, servers).
Uses text primary keys to preserve original source IDs (e.g., "C-19283")
for transparent cross-referencing across data sources.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.relationships import device_app_dependencies


class Device(Base):
    """A hardware device configuration item in the CMDB."""

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    hostname: Mapped[str] = mapped_column(String, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mac_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    os: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Soft FK to users.id — not enforced because devices may be ingested before users
    assigned_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    assigned_user_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    device_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    encryption_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_checkin: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Original JSON blob for auditability
    created_at: Mapped[str] = mapped_column(
        String, default=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        onupdate=lambda: datetime.now(timezone.utc).isoformat(),
    )

    # Many-to-many relationship with apps via device_app_dependencies
    apps = relationship("App", secondary=device_app_dependencies, back_populates="devices")
