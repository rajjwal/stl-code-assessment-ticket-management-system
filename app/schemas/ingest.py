"""Pydantic schemas for the data ingestion endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class IngestResponse(BaseModel):
    """Response returned after ingesting a data file."""

    status: str  # "success", "partial", "failed"
    filename: str
    file_format: str | None = None  # "csv", "json", "yaml"
    source_type: str | None = None  # "hardware", "okta", "app"
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    errors: list[str] = []
    ai_enrichments_applied: int = 0
