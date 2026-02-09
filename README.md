# AI-First CMDB — Configuration Management Database

An AI-powered Configuration Management Database (CMDB) backend service built with Python. Ingests raw and semi-structured IT infrastructure data, extracts and normalizes Configuration Items (Devices, Users, Apps), stores them with relationships, and uses AI for data enrichment and natural language queries.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Technology Choices & Justifications](#technology-choices--justifications)
- [Data Model](#data-model)
- [AI Integration](#ai-integration)
- [Setup Instructions](#setup-instructions)
- [Running Tests](#running-tests)
- [API Reference](#api-reference)
- [Sample Walkthrough](#sample-walkthrough)
- [Project Structure](#project-structure)
- [Assumptions & Limitations](#assumptions--limitations)

---

## Architecture Overview

```
                             ┌──────────────┐
                             │   Raw Data   │
                             │ CSV/JSON/YAML│
                             └──────┬───────┘
                                    │
                             POST /ingest
                                    │
                      ┌─────────────▼─────────────┐
                      │      Format Detector      │
                      │    (extension + sniff)    │
                      └─────────────┬─────────────┘
                                    │
                      ┌─────────────▼─────────────┐
                      │        Parser Layer       │
                      │     CSV / JSON / YAML     │
                      └─────────────┬─────────────┘
                                    │
                      ┌─────────────▼─────────────┐
                      │ Pre-Normalize (rule-based)│
                      │    (OS, status, dates)    │
                      └─────────────┬─────────────┘
                                    │
                      ┌─────────────▼─────────────┐
                      │   AI Extract & Structure  │
                      │     (via OpenRouter)      │
                      └─────────────┬─────────────┘
                                    │
                      ┌─────────────▼─────────────┐
                      │       AI Enrichment       │
                      │   (fill gaps, infer types)│
                      └─────────────┬─────────────┘
                                    │
                      ┌─────────────▼─────────────┐
                      │Post-Normalize (rule-based)│
                      │ (ensures AI output clean) │
                      └─────────────┬─────────────┘
                                    │
                      ┌─────────────▼─────────────┐
                      │      Upsert to SQLite     │
                      │     (null-safe merge)     │
                      └─────────────┬─────────────┘
                                    │
                      ┌─────────────▼─────────────┐
                      │  Relationship Resolver    │
                      │    (fuzzy FK matching)    │
                      └─────────────┴─────────────┘

        ┌──────────────┐  ┌───────────┐  ┌──────────┐  ┌─────────────┐
        │ GET /devices │  │ GET /users│  │ GET /apps│  │ GET /ci/{id}│
        └──────────────┘  └───────────┘  └──────────┘  └─────────────┘

                      ┌───────────────────────────┐
                      │         POST /ask         │
                      │     NL question → SQL     │
                      │    Execute → AI format    │
                      └───────────────────────────┘
```

The system follows a **pipeline architecture** for ingestion: each stage has a clear input/output contract (list of dicts), making stages independently testable and replaceable. If the AI service is unavailable, the pipeline degrades gracefully by skipping AI steps and storing rule-normalized data.

### Component Responsibilities

| Component | Role |
|-----------|------|
| **Parsers** | Convert raw bytes into flat dictionaries. CSV, JSON, and YAML each have format-specific logic (YAML flattening, JSON wrapper detection). |
| **Normalizer** | Deterministic rule-based cleanup: OS name canonicalization, status mapping, date formatting, IP validation. Runs before *and* after AI steps to ensure consistent output. |
| **AI Service** | OpenRouter API client with four focused methods: extract/structure, enrich, NL query parsing, and answer generation. Each uses a separate prompt optimized for its task. |
| **Relationship Resolver** | Fuzzy string matching to link CIs across data sources (e.g., "John D." in hardware CSV → "John Doe" in Okta). Uses a tiered matching strategy: exact → case-insensitive → substring containment → ratio-based. |
| **Query Service** | Converts natural language questions into structured DB filters via AI, executes the query deterministically against SQLite, then uses AI to format a human-readable answer. Supports both single-entity and cross-entity queries. |

---

## Technology Choices & Justifications

### FastAPI

- **Auto-generated OpenAPI/Swagger docs** — explore the API interactively at `/docs` without reading any documentation
- **Native async support** — non-blocking calls to OpenRouter API during ingestion and querying
- **Pydantic integration** — request/response validation is built-in, schemas double as data contracts
- **Type hints throughout** — improved code clarity and IDE support

### SQLite (via aiosqlite)

- **Zero configuration** — no database server to install, no connection strings to configure. Clone the repo and run.
- **Single-file portability** — the entire database is one file, easy to inspect with `sqlite3 cmdb.db`
- **Sufficient for demo scale** — the sample data has ~20 records total. SQLite handles millions of rows; this is not a bottleneck.
- **Tradeoff**: No concurrent write support. Acceptable for a single-user demo prototype; would switch to PostgreSQL for production multi-user workloads.

### SQLAlchemy 2.0 (async)

- **Declarative models** — table schemas are defined as Python classes, serving as living documentation
- **Relationship loading** — handles joins for many-to-many relationships (user↔app, device↔app, app↔app) cleanly with `selectinload` for async safety
- **Modern 2.0 API** — uses `Mapped[]` type annotations and `mapped_column()` instead of the legacy `Column()` pattern
- **Tradeoff**: Heavier than raw SQL for a prototype, but the relationship management alone justifies the overhead

### OpenRouter API

- **Single endpoint, many models** — access to hundreds of models without managing multiple API keys
- **Model choice: Llama 4 Maverick** — cost-effective with strong structured JSON output. Low temperature (0.1) for deterministic extraction.
- **Retry logic** — exponential backoff on 429/5xx errors with configurable max retries
- **Tradeoff**: External API dependency. Mitigated by graceful degradation — all ingestion works without AI, just with less enrichment.

### difflib.SequenceMatcher (fuzzy matching)

- **Standard library** — no extra dependencies
- **Tiered matching** — exact match → case-insensitive → substring containment → ratio-based, with configurable threshold (0.6 default)
- **Sufficient accuracy** — handles the matching cases in sample data ("John D." → "John Doe", "GitHub" → "GitHub Enterprise")
- **Tradeoff**: Less accurate than purpose-built libraries like `thefuzz` for highly noisy data. Acceptable for the demo data scale.

---

## Data Model

### Entity-Relationship Diagram

```
┌──────────────┐       ┌────────────────────┐       ┌──────────────┐
│   devices    │       │user_app_assignments│       │    users     │
├──────────────┤       ├────────────────────┤       ├──────────────┤
│ id (PK)      │       │ user_id (FK)       │       │ id (PK)      │
│ hostname     │       │ app_id (FK)        │       │ name         │
│ ip_address   │       └────────────────────┘       │ email        │
│ mac_address  │                                    │ team         │
│ os           │       ┌────────────────────┐       │ groups (JSON)│
│ assigned_user├──────→│ device_app_deps    │       │ mfa_enabled  │
│ location     │       ├────────────────────┤       │ last_login   │
│ status       │       │ device_id (FK)     │       │ status       │
│ device_type  │       │ app_id (FK)        │       │ raw_data     │
│ serial_number│       └────────────────────┘       └──────┬───────┘
│ department   │                                           │
│ raw_data     │       ┌────────────────────┐              │
└──────────────┘       │  app_integrations  │              │
                       ├────────────────────┤       ┌──────▼───────┐
                       │ source_app_id (FK) │       │    apps      │
                       │ target_app_id (FK) │       ├──────────────┤
                       │ target_app_name    │       │ id (PK)      │
                       └────────────────────┘       │ name         │
                                                    │ vendor       │
                                                    │ app_type     │
                                                    │ category     │
                                                    │ sso_enabled  │
                                                    │ users_count  │
                                                    │ raw_data     │
                                                    └──────────────┘
```

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Text primary keys** (e.g., "C-19283", "u_999") | Preserves original source IDs for transparent cross-referencing. No synthetic auto-increment IDs means no mapping table needed. |
| **`raw_data` column on every CI** | Stores the original ingested JSON blob. Critical for auditability — you can always trace what the AI enriched vs. what was in the source data. |
| **Soft foreign keys** (`assigned_user_id` is not a DB-enforced FK) | Ingestion order is unpredictable — devices may be ingested before users exist. Hard FKs would require strict ordering. The relationship resolver links them post-ingestion. |
| **Null-safe upsert merge** | When the same device appears in multiple files (JSON, CSV, YAML), re-ingestion updates fields but **null values never overwrite existing non-null values**. This ensures the richest data survives regardless of ingestion order. |
| **Junction tables for many-to-many** | `user_app_assignments`, `app_integrations`, `device_app_dependencies` are pure association tables — no extra columns beyond foreign keys. |
| **`app_integrations.target_app_name`** | Some integration targets (e.g., "Docker", "Kubernetes") may not exist as managed apps in the CMDB. `target_app_name` always stores the raw name; `target_app_id` is populated only when the target app is resolved. |
| **Pre-normalize AND post-normalize** | Rule-based normalizer runs before AI (to give AI clean input) and after AI (to ensure AI output conforms to our standards). Double normalization catches inconsistencies from any source. |

---

## AI Integration

AI is used for four distinct tasks, each with a separate focused prompt:

### 1. Data Extraction & Structuring

Converts raw parsed records into the normalized CI schema. The prompt includes the target schema definition and normalization rules (OS names, status values, date formats). The AI maps varied source field names to canonical schema fields.

**Example transformation:**
```
Input:  {"device_id": "C-19283", "hostname": "laptop-jdoe", "os": "macos", "status": "ACTIVE"}
Output: {"device_id": "C-19283", "hostname": "laptop-jdoe", "os": "macOS", "status": "active", "device_type": "laptop"}
```

### 2. Data Enrichment

A separate pass that fills gaps in partially-structured records. The prompt includes strict constraints:

**Allowed inferences:**
- Device type from hostname patterns ("laptop-jdoe" → "laptop", "server-prod" → "server")
- Department from team/group names
- Expanding abbreviated names when context is clear

**Prohibited fabrication:**
- Serial numbers, MAC addresses, IP addresses
- Specific dates or timestamps
- Email addresses or user IDs

### 3. Natural Language Queries

Converts questions into structured database filters. Supports both **single-entity queries** ("Which users don't have MFA?") and **cross-entity queries** ("Which devices belong to users without MFA?").

**Single-entity example:**
```json
{"entity_type": "users", "filters": {"mfa_enabled": false}, "join": null}
```

**Cross-entity example:**
```json
{
    "entity_type": "devices",
    "filters": {},
    "join": {"entity_type": "users", "join_type": "inner", "filters": {"mfa_enabled": false}}
}
```

Cross-entity queries work by joining related tables via a registry of known join paths (device→user via `assigned_user_id`, device↔app and user↔app via junction tables). The primary `entity_type` determines what gets returned; the `join` filters on related entities.

### 4. Answer Generation

Takes the query results and original question, and generates a human-readable answer. Falls back to a template-based answer if AI is unavailable (e.g., "Found 3 user(s) matching your query.").

### Graceful Degradation

If the OpenRouter API is unreachable or the API key is not configured:

| Feature | Behavior |
|---------|----------|
| **Ingestion** | Continues with rule-based normalization only. AI steps are skipped, errors logged. Data is still parsed and stored. |
| **GET endpoints** | Work normally — they query the database directly with no AI involvement. |
| **POST /ask** | Returns "AI service is currently unavailable" with empty results. |

---

## Setup Instructions

### Prerequisites

- Python 3.9+
- pip

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd stl-code-assessment-ticket-management-system

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and set your OPENROUTER_API_KEY
# (Optional — the system works without it, just without AI enrichment)

# 5. Start the server
uvicorn app.main:app --reload
```

The server starts at `http://localhost:8000`. Database tables are created automatically on first startup.

### Verify Installation

```bash
# Health check
curl http://localhost:8000/

# Expected response:
# {"status": "healthy", "service": "AI-First CMDB"}

# Interactive API docs
open http://localhost:8000/docs
```

---

## Running Tests

The test suite uses pytest with async support and achieves 88% code coverage across 204 tests. All tests use an in-memory SQLite database and mock AI API calls, so no external services are required.

```bash
# Run all tests (204 tests, ~1.5s)
pytest -v

# Run with coverage report
pytest --cov=app --cov-report=term-missing -v

# Run only unit tests (parsers, normalizer, fuzzy match, AI service, etc.)
pytest tests/test_services/ -v

# Run only API integration tests
pytest tests/test_api/ -v

# Run schema validation tests
pytest tests/test_models/ -v
```

### Test Categories

| Category | Tests | What's Covered |
|----------|-------|----------------|
| `test_services/test_parsers.py` | 24 | CSV, JSON, YAML parsing, format/source detection, edge cases |
| `test_services/test_normalizer.py` | 17 | OS normalization, status mapping, date parsing, IP validation |
| `test_services/test_fuzzy_match.py` | 15 | Tiered matching: exact, case-insensitive, substring, ratio |
| `test_services/test_relationship_resolver.py` | 8 | Device→User, User→App, App→App relationship linking |
| `test_services/test_ai_service.py` | 14 | AI extraction, enrichment, query parsing, answer generation (mocked) |
| `test_services/test_query_service.py` | 12 | NL query handling, filter operators, cross-entity joins, edge cases |
| `test_services/test_ingestion.py` | 11 | Upsert logic, null-safe merge, pipeline edge cases |
| `test_api/test_ingest.py` | 9 | File ingestion via HTTP, all formats, idempotency, AI enrichment |
| `test_api/test_devices.py` | 9 | Device listing, all filters, pagination, combined filters |
| `test_api/test_users.py` | 8 | User listing, filters, pagination, groups serialization |
| `test_api/test_apps.py` | 9 | App listing, filters, pagination, integrations |
| `test_api/test_ci.py` | 10 | Unified CI lookup, all entity types, relationships, 404 |
| `test_api/test_ask.py` | 5 | NL query endpoint, cross-entity queries, mocked AI, validation |
| `test_api/test_health.py` | 3 | Health check, docs endpoint, OpenAPI schema |
| `test_models/test_schemas.py` | 50 | Pydantic schema validation for all CI types |

---

## API Reference

### Health Check

```
GET /
```

```bash
curl http://localhost:8000/
```

Response:
```json
{"status": "healthy", "service": "AI-First CMDB"}
```

### Ingest Data

```
POST /ingest
Content-Type: multipart/form-data
```

Upload a raw data file (CSV, JSON, or YAML). Format and source type are auto-detected from file extension and content.

```bash
curl -X POST http://localhost:8000/ingest -F "file=@input_data/sample_hardware.json"
```

Response:
```json
{
    "status": "success",
    "filename": "sample_hardware.json",
    "file_format": "json",
    "source_type": "hardware",
    "records_processed": 3,
    "records_created": 3,
    "records_updated": 0,
    "errors": [],
    "ai_enrichments_applied": 2
}
```

Re-ingesting the same file is idempotent — existing records are updated (null-safe merge), not duplicated.

### List Devices

```
GET /devices?status=active&os=macOS&location=London&assigned_user=John&department=Engineering&limit=100&offset=0
```

All query parameters are optional. `os`, `location`, `assigned_user`, and `department` use case-insensitive partial matching.

```bash
curl "http://localhost:8000/devices?status=active"
```

Response:
```json
{
    "items": [
        {
            "id": "C-19283",
            "hostname": "laptop-jdoe",
            "ip_address": "10.10.22.5",
            "os": "macOS",
            "assigned_user_id": "u_999",
            "assigned_user_name": "John Doe",
            "location": "New York HQ",
            "status": "active",
            "device_type": "laptop"
        }
    ],
    "total": 2,
    "limit": 100,
    "offset": 0
}
```

### List Users

```
GET /users?status=active&team=Engineering&mfa_enabled=false&limit=100&offset=0
```

```bash
curl "http://localhost:8000/users?mfa_enabled=false"
```

Response:
```json
{
    "items": [
        {
            "id": "u_205",
            "name": "Carlos S.",
            "email": "carlos.s@company.com",
            "team": "Engineering",
            "groups": ["Engineering", "Cloud-Ops"],
            "mfa_enabled": false,
            "status": "active",
            "apps": ["Slack", "GitHub"]
        }
    ],
    "total": 3,
    "limit": 100,
    "offset": 0
}
```

### List Apps

```
GET /apps?app_type=SaaS&category=Development&sso_enabled=true&owner=Engineering&limit=100&offset=0
```

```bash
curl "http://localhost:8000/apps?app_type=SaaS"
```

Response:
```json
{
    "items": [
        {
            "id": "APP-001",
            "name": "Slack",
            "vendor": "Salesforce",
            "app_type": "SaaS",
            "category": "Collaboration",
            "owner": "IT",
            "users_count": 950,
            "sso_enabled": true,
            "integrations": ["GitHub", "Jira", "Google Workspace", "PagerDuty"]
        }
    ],
    "total": 3,
    "limit": 100,
    "offset": 0
}
```

### Get CI by ID

```
GET /ci/{ci_id}
```

Searches across all CI types (devices, users, apps). Returns full CI with relationships, or 404 if not found.

```bash
curl http://localhost:8000/ci/C-19283
```

Response:
```json
{
    "ci_type": "device",
    "id": "C-19283",
    "hostname": "laptop-jdoe",
    "ip_address": "10.10.22.5",
    "os": "macOS",
    "assigned_user_id": "u_999",
    "assigned_user_name": "John Doe",
    "location": "New York HQ",
    "status": "active",
    "device_type": "laptop",
    "assigned_apps": []
}
```

### Natural Language Query

```
POST /ask
Content-Type: application/json
```

Supports both single-entity and cross-entity questions:

```bash
# Single-entity query
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which users dont have MFA?"}'

# Cross-entity query
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which devices belong to users without MFA?"}'
```

Response:
```json
{
    "answer": "There are 3 users without MFA enabled: Carlos S., Michael Brown, and Alex Johnson.",
    "results": [
        {"id": "u_205", "name": "Carlos S.", "mfa_enabled": false, "status": "active"},
        {"id": "u_410", "name": "Michael Brown", "mfa_enabled": false, "status": "active"},
        {"id": "u_678", "name": "Alex Johnson", "mfa_enabled": false, "status": "suspended"}
    ],
    "query_interpretation": "{\"entity_type\": \"users\", \"filters\": {\"mfa_enabled\": false}}"
}
```

---

## Sample Walkthrough

Here's a complete walkthrough demonstrating the system end-to-end:

### 1. Start the Server

```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

### 2. Ingest All Sample Data

```bash
# Ingest hardware inventory (3 devices)
curl -X POST http://localhost:8000/ingest -F "file=@input_data/sample_hardware.json"
# → {"status": "success", "records_processed": 3, "records_created": 3, "ai_enrichments_applied": 2}

# Ingest hardware CSV (same 3 devices, different format)
curl -X POST http://localhost:8000/ingest -F "file=@input_data/sample_hardware.csv"
# → {"records_created": 0, "records_updated": 3} — idempotent merge

# Ingest hardware YAML (same 3 devices with nested structure)
curl -X POST http://localhost:8000/ingest -F "file=@input_data/sample_hardware.yaml"
# → {"records_created": 0, "records_updated": 3} — enriches with YAML-only fields

# Ingest Okta user directory (9 users)
curl -X POST http://localhost:8000/ingest -F "file=@input_data/sample_okta.json"
# → {"records_processed": 9, "records_created": 9}

# Ingest app inventory (6 apps)
curl -X POST http://localhost:8000/ingest -F "file=@input_data/sample_app.json"
# → {"records_processed": 6, "records_created": 6}
```

### 3. Query the Data

```bash
# List all active devices
curl "http://localhost:8000/devices?status=active"

# Find users without MFA
curl "http://localhost:8000/users?mfa_enabled=false"

# List SaaS apps
curl "http://localhost:8000/apps?app_type=SaaS"

# Look up a specific device (includes resolved relationships)
curl http://localhost:8000/ci/C-19283
# → assigned_user_id: "u_999", assigned_user_name: "John Doe"

# Look up a user (includes linked apps)
curl http://localhost:8000/ci/u_999
# → apps: ["Slack", "GitHub", "Salesforce CRM"]
```

### 4. Ask Natural Language Questions

```bash
# Which users don't have MFA?
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which users dont have MFA?"}'

# Cross-entity: devices belonging to users without MFA
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which devices belong to users without MFA?"}'

# Show all active devices
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me all active devices"}'

# Which apps are used by the Engineering team?
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which apps are used by the Engineering team?"}'
```

---

## Project Structure

```
app/
  main.py                    # FastAPI app, lifespan, router mounting, health check
  config.py                  # pydantic-settings: DB URL, OpenRouter API key, model config
  database.py                # Async SQLAlchemy engine, session factory, Base
  models/
    device.py                # Device ORM model
    user.py                  # User ORM model with M2M apps relationship
    app.py                   # App ORM model with M2M users/devices relationships
    relationships.py         # Junction tables (user_app, device_app, app_integrations)
    ingestion_log.py         # Audit log for each ingestion run
  schemas/
    device.py, user.py, app.py  # Pydantic response models
    ingest.py                   # IngestResponse schema
    ask.py                      # AskRequest/AskResponse schemas
  api/
    ingest.py                # POST /ingest — file upload + pipeline
    devices.py               # GET /devices — filtered listing with pagination
    users.py                 # GET /users — filtered listing with pagination
    apps.py                  # GET /apps — filtered listing with integrations
    ci.py                    # GET /ci/{id} — unified cross-type lookup
    ask.py                   # POST /ask — natural language query
  services/
    ingestion.py             # Pipeline orchestrator: detect → parse → normalize → AI → upsert
    ai_service.py            # OpenRouter client: extract, enrich, parse NL, generate answer
    normalizer.py            # Rule-based: OS names, status, dates, IPs
    relationship_resolver.py # Fuzzy FK resolution: device→user, user→app, app→app
    query_service.py         # NL question → structured query → execute → format answer
    parsers/
      base.py                # Abstract parser interface
      csv_parser.py          # CSV → list[dict] with BOM handling
      json_parser.py         # JSON → list[dict] with wrapper detection
      yaml_parser.py         # YAML → list[dict] with nested structure flattening
      detector.py            # Format detection (extension + sniff) and source type detection
  utils/
    fuzzy_match.py           # Tiered string matching with configurable threshold
tests/
  conftest.py                # Shared fixtures: in-memory DB, async client, sample data loaders
  test_models/               # Pydantic schema validation tests
  test_services/             # Unit tests for all service modules
  test_api/                  # API integration tests for all endpoints
input_data/                  # 5 sample data files (hardware JSON/CSV/YAML, Okta, apps)
```

---

## Assumptions & Limitations

- **Single-user prototype** — SQLite does not support concurrent writes. Suitable for demo/evaluation, not production multi-user workloads.
- **Small dataset scale** — AI processes all records in a single API call. For larger datasets, batching would be needed.
- **Name matching is fuzzy, not deterministic** — "John D." matching to "John Doe" relies on string similarity. Ambiguous names could produce incorrect matches.
- **No authentication** — API endpoints are open. A production system would need auth middleware.
- **No data versioning** — upserts overwrite previous values (null-safe). A production system might want an audit trail of field-level changes.
- **AI enrichment quality depends on model** — results vary by model choice and prompt design. The rule-based normalizer provides a reliable baseline regardless.
- **Cross-entity queries support one join** — queries can filter across two related entity types (e.g., "devices for users without MFA"). Multi-hop joins (three or more entities) are not currently supported.
