"""Ingestion log ORM model for tracking data import operations.

Every call to POST /ingest creates a log entry recording what was ingested,
how many records were processed, and any errors encountered.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IngestionLog(Base):
    """Tracks each data ingestion operation for auditability."""

    __tablename__ = "ingestion_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    file_format: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # csv, json, yaml
    source_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # hardware, okta, app
    records_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # success, partial, failed
    ai_calls_made: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    errors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of error messages
    ingested_at: Mapped[str] = mapped_column(
        String, default=lambda: datetime.now(timezone.utc).isoformat()
    )
