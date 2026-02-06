"""Ingestion endpoint for uploading raw data files.

Accepts CSV, JSON, or YAML files containing hardware inventory,
Okta user exports, or application inventory data.
"""

from fastapi import APIRouter, UploadFile

from app.schemas.ingest import IngestResponse

router = APIRouter(tags=["ingestion"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_file(file: UploadFile) -> IngestResponse:
    """Upload a raw data file for ingestion into the CMDB.

    Supports CSV, JSON, and YAML formats. The source type (hardware, okta, app)
    is auto-detected from the file content.
    """
    # Stub — will be implemented in Phase 2
    return IngestResponse(
        status="not_implemented",
        filename=file.filename or "unknown",
    )
