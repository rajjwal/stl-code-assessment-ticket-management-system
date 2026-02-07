"""Ingestion endpoint for uploading raw data files.

Accepts CSV, JSON, or YAML files containing hardware inventory,
Okta user exports, or application inventory data.
"""

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ingest import IngestResponse
from app.services.ingestion import ingest_file as run_ingestion

router = APIRouter(tags=["ingestion"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Upload a raw data file for ingestion into the CMDB.

    Supports CSV, JSON, and YAML formats. The source type (hardware, okta, app)
    is auto-detected from the file content.
    """
    content = await file.read()
    filename = file.filename or "unknown"
    return await run_ingestion(filename, content, db)
