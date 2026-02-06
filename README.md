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
- [Assumptions & Limitations](#assumptions--limitations)

---

## Architecture Overview

```
                         ┌──────────────┐
                         │  Raw Data    │
                         │ CSV/JSON/YAML│
                         └──────┬───────┘
                                │
                         POST /ingest
                                │
                    ┌───────────▼───────────┐
                    │   Format Detector     │
                    │  (extension + sniff)  │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Parser Layer        │
                    │  CSV / JSON / YAML    │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Rule-Based Normalizer│
                    │  (OS, status, dates)  │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   AI Extraction &     │
                    │   Enrichment          │
                    │   (via OpenRouter)    │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Upsert to SQLite     │
                    │  (null-safe merge)    │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ Relationship Resolver │
                    │ (fuzzy FK matching)   │
                    └───────────────────────┘

  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │GET /devices│ │GET /users│  │GET /apps │  │GET /ci/id│
  └──────────┘  └──────────┘  └──────────┘  └──────────┘

                    ┌───────────────────────┐
                    │     POST /ask         │
                    │  NL Question          │
                    │    → AI parse to SQL  │
                    │    → Execute query    │
                    │    → AI format answer │
                    └───────────────────────┘
```

The system follows a **pipeline architecture** for ingestion: each stage has a clear input/output contract (list of dicts), making stages independently testable and replaceable. If the AI service is unavailable, the pipeline degrades gracefully by skipping AI steps and storing rule-normalized data.

### Component Responsibilities

| Component | Role |
|-----------|------|
| **Parsers** | Convert raw bytes into flat dictionaries. CSV, JSON, and YAML each have format-specific logic (YAML flattening, JSON wrapper detection). |
| **Normalizer** | Deterministic rule-based cleanup: OS name canonicalization, status mapping, date formatting, IP validation. Runs before *and* after AI steps. |
| **AI Service** | OpenRouter API client with three focused methods: extract/structure, enrich, and NL query parsing. Each uses a separate prompt optimized for its task. |
| **Relationship Resolver** | Fuzzy string matching to link CIs across data sources (e.g., "John D." in hardware CSV → "John Doe" in Okta). |
| **Query Service** | Converts natural language questions into structured DB filters via AI, executes the query, then uses AI to format a human-readable answer. |

---

## Technology Choices & Justifications

### FastAPI

- **Auto-generated OpenAPI/Swagger docs** — evaluators can explore the API interactively at `/docs` without reading any documentation
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
- **Relationship loading** — handles joins for many-to-many relationships (user↔app, device↔app, app↔app) cleanly
- **Modern 2.0 API** — uses `Mapped[]` type annotations and `mapped_column()` instead of the legacy `Column()` pattern
- **Tradeoff**: Heavier than raw SQL for a prototype, but the relationship management alone justifies the overhead

### OpenRouter API

- **Single endpoint, many models** — access to hundreds of models without managing multiple API keys
- **Model choice: Llama 4 Maverick** — cost-effective with strong structured JSON output. Low temperature (0.1) for deterministic extraction.
- **Tradeoff**: External API dependency. Mitigated by graceful degradation — all ingestion works without AI, just with less enrichment.

### difflib.SequenceMatcher (fuzzy matching)

- **Standard library** — no extra dependencies
- **Sufficient accuracy** — handles the matching cases in sample data ("John D." → "John Doe", "GitHub" → "GitHub Enterprise")
- **Tradeoff**: Less accurate than purpose-built libraries like `thefuzz` for highly noisy data. Acceptable for the demo data scale.

---

## Data Model

### Entity-Relationship Diagram

```
┌──────────────┐       ┌────────────────────┐       ┌──────────────┐
│   devices    │       │ user_app_assignments│       │    users     │
├──────────────┤       ├───────��────────────┤       ├──────────────┤
│ id (PK)      │       │ user_id (FK)       │       │ id (PK)      │
│ hostname     │       │ app_id (FK)        │       │ name         │
│ ip_address   │       └────────────────────┘       │ email        │
│ mac_address  │                                     │ team         │
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

---

## AI Integration

AI is used for three distinct tasks, each with a separate focused prompt:

### 1. Data Extraction & Structuring
Converts raw parsed records into the normalized CI schema. Handles OS name normalization ("macos" → "macOS"), device type inference from hostname patterns ("laptop-*" → laptop), and field mapping from varied source schemas.

### 2. Data Enrichment
A separate pass that fills gaps in partially-structured records. Only makes high-confidence inferences — will NOT fabricate serial numbers, MAC addresses, or specific dates. Can infer device types, departments, and expand abbreviated names when context supports it.

### 3. Natural Language Queries
Converts questions like "Which users don't have MFA?" into structured database filters (`{entity_type: "users", filters: {mfa_enabled: false}}`). The query executes deterministically against SQLite, then AI formats the results into a human-readable answer.

### Graceful Degradation
If the OpenRouter API is unreachable:
- **Ingestion** continues with rule-based normalization only (no AI enrichment)
- **GET endpoints** work normally (they query the database directly)
- **POST /ask** returns an error message explaining AI is unavailable

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

```bash
# Run all tests
pytest -v

# Run with coverage report
pytest --cov=app --cov-report=term-missing -v

# Run only unit tests
pytest tests/test_services/ -v

# Run only API integration tests
pytest tests/test_api/ -v

# Run end-to-end tests (requires OPENROUTER_API_KEY)
pytest -m e2e -v
```

---

## API Reference

### Health Check

```
GET /
```

```bash
curl http://localhost:8000/
# {"status": "healthy", "service": "AI-First CMDB"}
```

### Ingest Data

```
POST /ingest
Content-Type: multipart/form-data
```

Upload a raw data file (CSV, JSON, or YAML). Format and source type are auto-detected.

```bash
curl -X POST http://localhost:8000/ingest -F "file=@input_data/sample_hardware.json"
curl -X POST http://localhost:8000/ingest -F "file=@input_data/sample_okta.json"
curl -X POST http://localhost:8000/ingest -F "file=@input_data/sample_app.json"
```

### List Devices

```
GET /devices?status=active&os=macOS&location=London&department=Engineering&limit=100&offset=0
```

All query parameters are optional.

```bash
curl http://localhost:8000/devices
curl "http://localhost:8000/devices?status=active"
```

### List Users

```
GET /users?status=active&team=Engineering&mfa_enabled=false&limit=100&offset=0
```

```bash
curl http://localhost:8000/users
curl "http://localhost:8000/users?mfa_enabled=false"
```

### List Apps

```
GET /apps?app_type=SaaS&category=Development&sso_enabled=true&owner=Engineering&limit=100&offset=0
```

```bash
curl http://localhost:8000/apps
curl "http://localhost:8000/apps?app_type=SaaS"
```

### Get CI by ID

```
GET /ci/{ci_id}
```

Searches across all CI types (devices, users, apps). Returns full CI with relationships.

```bash
curl http://localhost:8000/ci/C-19283
curl http://localhost:8000/ci/u_999
curl http://localhost:8000/ci/APP-001
```

### Natural Language Query

```
POST /ask
Content-Type: application/json
```

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which users dont have MFA?"}'
```

---

## Assumptions & Limitations

- **Single-user prototype** — SQLite does not support concurrent writes. Suitable for demo/evaluation, not production multi-user workloads.
- **Small dataset scale** — AI processes all records in a single API call. For larger datasets, batching would be needed.
- **Name matching is fuzzy, not deterministic** — "John D." matching to "John Doe" relies on string similarity. Ambiguous names could produce incorrect matches.
- **No authentication** — API endpoints are open. A production system would need auth middleware.
- **No data versioning** — upserts overwrite previous values. A production system might want an audit trail of field-level changes.
- **AI enrichment quality depends on model** — results vary by model choice and prompt design. The rule-based normalizer provides a reliable baseline regardless.
