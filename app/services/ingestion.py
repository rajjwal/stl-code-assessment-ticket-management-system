"""Ingestion pipeline orchestrator.

Coordinates the full ingestion flow: detect format → parse → pre-normalize →
AI extract → AI enrich → post-normalize → upsert to database → log result.

Each stage takes and returns list[dict], making stages independently
testable and the pipeline easy to extend. If AI is unavailable, the pipeline
degrades gracefully and uses rule-based normalization only.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.user import User
from app.models.app import App
from app.models.ingestion_log import IngestionLog
from app.schemas.ingest import IngestResponse
from app.services.parsers.csv_parser import CSVParser
from app.services.parsers.json_parser import JSONParser
from app.services.parsers.yaml_parser import YAMLParser
from app.services.parsers.detector import detect_format, detect_source_type
from app.services.normalizer import normalize_record
from app.services.relationship_resolver import resolve_relationships
from app.services.ai_service import extract_and_structure, enrich

logger = logging.getLogger(__name__)

PARSERS = {
    "csv": CSVParser(),
    "json": JSONParser(),
    "yaml": YAMLParser(),
}


async def ingest_file(
    filename: str,
    content: bytes,
    db: AsyncSession,
) -> IngestResponse:
    """Run the full ingestion pipeline for a single file.

    Pipeline stages:
    1. Detect format and source type
    2. Parse raw content into records
    3. Pre-normalize records (rule-based)
    4. AI extract and structure
    5. AI enrich
    6. Post-normalize (rule-based, ensures AI output is clean)
    7. Upsert to database
    8. Resolve relationships
    9. Log the ingestion

    Args:
        filename: Original filename for format detection.
        content: Raw file bytes.
        db: Async database session.

    Returns:
        IngestResponse summarizing what was ingested.
    """
    errors = []
    records_created = 0
    records_updated = 0

    # Step 1: Detect format
    try:
        file_format = detect_format(content, filename)
    except ValueError as e:
        return IngestResponse(
            status="failed",
            filename=filename,
            errors=[str(e)],
        )

    # Step 2: Parse
    parser = PARSERS.get(file_format)
    if not parser:
        return IngestResponse(
            status="failed",
            filename=filename,
            file_format=file_format,
            errors=[f"No parser available for format: {file_format}"],
        )

    try:
        records = parser.parse(content, filename)
    except (ValueError, Exception) as e:
        return IngestResponse(
            status="failed",
            filename=filename,
            file_format=file_format,
            errors=[f"Parse error: {e}"],
        )

    if not records:
        return IngestResponse(
            status="success",
            filename=filename,
            file_format=file_format,
            records_processed=0,
        )

    # Step 3: Detect source type
    try:
        source_type = detect_source_type(records)
    except ValueError as e:
        return IngestResponse(
            status="failed",
            filename=filename,
            file_format=file_format,
            errors=[str(e)],
        )

    # Step 4: Pre-normalize (rule-based)
    normalized = []
    for i, record in enumerate(records):
        try:
            normalized.append(normalize_record(record, source_type))
        except Exception as e:
            errors.append(f"Record {i}: normalization error: {e}")
            normalized.append(record)  # Keep original on error

    # Step 5: AI extract and structure (graceful degradation if unavailable)
    ai_calls = 0
    try:
        ai_extracted = await extract_and_structure(normalized, source_type)
        if ai_extracted is not normalized:
            ai_calls += 1
            normalized = ai_extracted
    except Exception as e:
        errors.append(f"AI extraction error (non-fatal): {e}")
        logger.warning(f"AI extraction failed, continuing with rule-based data: {e}")

    # Step 6: AI enrich (graceful degradation if unavailable)
    try:
        ai_enriched = await enrich(normalized, source_type)
        if ai_enriched is not normalized:
            ai_calls += 1
            normalized = ai_enriched
    except Exception as e:
        errors.append(f"AI enrichment error (non-fatal): {e}")
        logger.warning(f"AI enrichment failed, continuing with existing data: {e}")

    # Step 7: Post-normalize (ensures AI output conforms to our rules)
    post_normalized = []
    for i, record in enumerate(normalized):
        try:
            post_normalized.append(normalize_record(record, source_type))
        except Exception as e:
            errors.append(f"Record {i}: post-normalization error: {e}")
            post_normalized.append(record)
    normalized = post_normalized

    # Step 8: Upsert to database
    for i, record in enumerate(normalized):
        try:
            created = await _upsert_record(db, record, source_type)
            if created:
                records_created += 1
            else:
                records_updated += 1
        except Exception as e:
            errors.append(f"Record {i}: upsert error: {e}")
            logger.exception(f"Upsert failed for record {i} in {filename}")

    await db.commit()

    # Step 9: Resolve cross-source relationships (device→user, user→app, app→app)
    try:
        rel_summary = await resolve_relationships(db)
        logger.info(f"Relationships resolved: {rel_summary}")
    except Exception as e:
        errors.append(f"Relationship resolution error: {e}")
        logger.exception("Relationship resolution failed")

    # Step 10: Log ingestion
    log_entry = IngestionLog(
        filename=filename,
        file_format=file_format,
        source_type=source_type,
        records_count=len(records),
        status="success" if not errors else "partial",
        ai_calls_made=ai_calls,
        errors=json.dumps(errors) if errors else None,
    )
    db.add(log_entry)
    await db.commit()

    return IngestResponse(
        status="success" if not errors else "partial",
        filename=filename,
        file_format=file_format,
        source_type=source_type,
        records_processed=len(records),
        records_created=records_created,
        records_updated=records_updated,
        errors=errors,
        ai_enrichments_applied=ai_calls,
    )


async def _upsert_record(
    db: AsyncSession,
    record: dict,
    source_type: str,
) -> bool:
    """Insert or update a single record in the appropriate table.

    Uses null-safe merge: new non-null values overwrite existing values,
    but null values never overwrite existing non-null data. This ensures
    re-ingesting a sparser file doesn't erase richer data from a previous import.

    Returns:
        True if a new record was created, False if existing was updated.
    """
    if source_type == "hardware":
        return await _upsert_device(db, record)
    elif source_type == "okta":
        return await _upsert_user(db, record)
    elif source_type == "app":
        return await _upsert_app(db, record)
    else:
        raise ValueError(f"Unknown source type: {source_type}")


async def _upsert_device(db: AsyncSession, record: dict) -> bool:
    """Upsert a device record with null-safe merge."""
    device_id = record.get("device_id")
    if not device_id:
        raise ValueError("Device record missing 'device_id'")

    existing = await db.get(Device, device_id)
    raw_data = json.dumps(record)

    if existing is None:
        device = Device(
            id=device_id,
            hostname=record.get("hostname", "unknown"),
            ip_address=record.get("ip_address"),
            mac_address=record.get("mac_address"),
            os=record.get("os"),
            assigned_user_name=record.get("assigned_to"),
            location=record.get("location"),
            status=record.get("status"),
            device_type=record.get("device_type") or record.get("type"),
            serial_number=record.get("serial_number"),
            department=record.get("department"),
            encryption_status=record.get("encryption_status"),
            last_checkin=record.get("last_checkin"),
            raw_data=raw_data,
        )
        db.add(device)
        return True

    # Null-safe merge: only overwrite with non-null values
    _merge_field(existing, "hostname", record.get("hostname"))
    _merge_field(existing, "ip_address", record.get("ip_address"))
    _merge_field(existing, "mac_address", record.get("mac_address"))
    _merge_field(existing, "os", record.get("os"))
    _merge_field(existing, "assigned_user_name", record.get("assigned_to"))
    _merge_field(existing, "location", record.get("location"))
    _merge_field(existing, "status", record.get("status"))
    _merge_field(existing, "device_type", record.get("device_type") or record.get("type"))
    _merge_field(existing, "serial_number", record.get("serial_number"))
    _merge_field(existing, "department", record.get("department"))
    _merge_field(existing, "encryption_status", record.get("encryption_status"))
    _merge_field(existing, "last_checkin", record.get("last_checkin"))
    existing.raw_data = raw_data  # Always update raw_data to latest
    return False


async def _upsert_user(db: AsyncSession, record: dict) -> bool:
    """Upsert a user record with null-safe merge."""
    user_id = record.get("user_id")
    if not user_id:
        raise ValueError("User record missing 'user_id'")

    existing = await db.get(User, user_id)
    raw_data = json.dumps(record)

    # Store groups as JSON string
    groups_value = record.get("groups")
    if isinstance(groups_value, list):
        groups_str = json.dumps(groups_value)
    elif isinstance(groups_value, str):
        groups_str = groups_value
    else:
        groups_str = None

    # Use first group as primary team
    team = None
    if isinstance(groups_value, list) and groups_value:
        team = groups_value[0]

    if existing is None:
        user = User(
            id=user_id,
            name=record.get("name", "Unknown"),
            email=record.get("email"),
            team=team,
            groups=groups_str,
            mfa_enabled=record.get("mfa_enabled"),
            last_login=record.get("last_login"),
            status=record.get("status"),
            employee_id=record.get("employee_id"),
            title=record.get("title"),
            raw_data=raw_data,
        )
        db.add(user)
        return True

    _merge_field(existing, "name", record.get("name"))
    _merge_field(existing, "email", record.get("email"))
    _merge_field(existing, "team", team)
    _merge_field(existing, "groups", groups_str)
    if record.get("mfa_enabled") is not None:
        existing.mfa_enabled = record["mfa_enabled"]
    _merge_field(existing, "last_login", record.get("last_login"))
    _merge_field(existing, "status", record.get("status"))
    _merge_field(existing, "employee_id", record.get("employee_id"))
    _merge_field(existing, "title", record.get("title"))
    existing.raw_data = raw_data
    return False


async def _upsert_app(db: AsyncSession, record: dict) -> bool:
    """Upsert an app record with null-safe merge."""
    app_id = record.get("app_id")
    if not app_id:
        raise ValueError("App record missing 'app_id'")

    existing = await db.get(App, app_id)
    raw_data = json.dumps(record)

    if existing is None:
        app = App(
            id=app_id,
            name=record.get("name", "Unknown"),
            vendor=record.get("vendor"),
            app_type=record.get("app_type"),
            category=record.get("category"),
            deployment=record.get("deployment"),
            owner=record.get("owner"),
            users_count=record.get("users_count"),
            sso_enabled=record.get("sso_enabled"),
            annual_cost_usd=record.get("annual_cost_usd"),
            contract_renewal=record.get("contract_renewal"),
            server_location=record.get("server_location"),
            version=record.get("version"),
            raw_data=raw_data,
        )
        db.add(app)
        return True

    _merge_field(existing, "name", record.get("name"))
    _merge_field(existing, "vendor", record.get("vendor"))
    _merge_field(existing, "app_type", record.get("app_type"))
    _merge_field(existing, "category", record.get("category"))
    _merge_field(existing, "deployment", record.get("deployment"))
    _merge_field(existing, "owner", record.get("owner"))
    if record.get("users_count") is not None:
        existing.users_count = record["users_count"]
    if record.get("sso_enabled") is not None:
        existing.sso_enabled = record["sso_enabled"]
    if record.get("annual_cost_usd") is not None:
        existing.annual_cost_usd = record["annual_cost_usd"]
    _merge_field(existing, "contract_renewal", record.get("contract_renewal"))
    _merge_field(existing, "server_location", record.get("server_location"))
    _merge_field(existing, "version", record.get("version"))
    existing.raw_data = raw_data
    return False


def _merge_field(obj: object, field: str, new_value: object) -> None:
    """Set field on obj only if new_value is not None.

    This is the core of the null-safe merge strategy: new data enriches
    existing data but never erases it.
    """
    if new_value is not None:
        setattr(obj, field, new_value)
