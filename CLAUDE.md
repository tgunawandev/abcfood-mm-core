# CLAUDE.md - abcfood-mm-core

This file provides context and instructions for AI assistants working with this codebase.

## Project Overview

**abcfood-mm-core** is the CORE business logic service for turning Mattermost into an operational command center. It exposes clean APIs for n8n and Mattermost to call.

### Key Principle: Separation of Concerns

| Component | Responsibility |
|-----------|----------------|
| **mm-core** (this service) | Business logic, validation, data access, audit logging |
| **n8n** | Orchestration, scheduling, message formatting, workflow |
| **Mattermost** | User interface, slash commands, interactive buttons |

**IMPORTANT**: This service returns **structured JSON only**. It NEVER formats Mattermost messages.

## Tech Stack

- **Language**: Python 3.11
- **Framework**: FastAPI
- **Dependencies**: Poetry
- **Databases**: PostgreSQL (audit logs), ClickHouse (analytics)
- **External**: Odoo XML-RPC
- **Logging**: structlog (JSON)
- **Testing**: pytest

## Project Structure

```
app/
├── main.py                 # FastAPI app entry point
├── api/v1/                 # API endpoints by feature
│   ├── approvals.py        # POST /approvals/*
│   ├── metrics.py          # GET /metrics/*
│   ├── digest.py           # GET /digest/*
│   ├── context.py          # GET /context/*
│   └── pending.py          # GET /pending/*
├── core/                   # Core infrastructure
│   ├── config.py           # Pydantic settings (env vars)
│   ├── security.py         # API key authentication
│   ├── logging.py          # Structured logging setup
│   └── exceptions.py       # Custom exception hierarchy
├── clients/                # External service clients
│   ├── postgres.py         # PostgreSQL for audit + Odoo data
│   ├── clickhouse.py       # ClickHouse for analytics
│   └── odoo.py             # Odoo XML-RPC for approvals
├── services/               # Business logic layer
│   ├── approval_service.py # Invoice/expense/leave approvals
│   ├── metrics_service.py  # Sales, overdue, customer risk
│   ├── digest_service.py   # Daily digest generation
│   ├── context_service.py  # Object context + pending items
│   └── audit_service.py    # Audit log writing
└── models/                 # Data models
    ├── schemas.py          # Pydantic request/response
    ├── enums.py            # Enumerations
    └── audit.py            # Audit log model
```

## Key APIs

### Approvals (State-changing)
```python
POST /api/v1/approvals/invoice/{id}?db={db}
POST /api/v1/approvals/expense/{id}?db={db}
POST /api/v1/approvals/leave/{id}?db={db}

# Request body
{
  "action": "approve" | "reject",
  "actor": "user@example.com",
  "actor_role": "manager",
  "reason": "optional"
}
```

### Metrics (Read-only)
```python
GET /api/v1/metrics/sales/today?db={db}
GET /api/v1/metrics/invoices/overdue?db={db}
GET /api/v1/metrics/customers/{id}/risk?db={db}
```

### Digest (For channel posting)
```python
GET /api/v1/digest/sales/daily?db={db}
GET /api/v1/digest/finance/daily?db={db}
```

### Context & Pending (For notifications)
```python
GET /api/v1/context/invoice/{id}?db={db}
GET /api/v1/pending/approvals?db={db}
GET /api/v1/pending/overdue?db={db}&threshold_days=14
```

## Database Architecture

### Odoo Servers (Multi-version Architecture)

**Odoo 16 (Main ERP)** - tln_db, ieg_db, tmi_db:
| Environment | Server |
|-------------|--------|
| Development | odoo-16-dev.abcfood.app |
| Production | tln.abcfood.app, ieg.abcfood.app, tmi.abcfood.app |

**Odoo 13 (HRIS)** - hris_db:
| Environment | Server |
|-------------|--------|
| Development | odoo-13-dev.abcfood.app |
| Production | TBD |

All servers use the same credential: `service_account`

### PostgreSQL (88.99.226.47)
- **Odoo DBs**: tln_db, ieg_db, tmi_db, hris_db (read queries for metrics)
- **Audit DB**: mm_audit (write audit logs)

### ClickHouse (138.199.213.219)
- **Analytics only**: Sales metrics, aggregations
- **No operational logs** - those go to PostgreSQL

## Configuration

All config via environment variables (see `.env.example`):

```bash
API_KEY=...              # Required for authentication

# PostgreSQL
PG_HOST=...              # PostgreSQL host
PG_PASSWORD=...          # PostgreSQL password

# Odoo 16 (Main ERP)
ODOO_HOST_TLN=...        # Odoo 16 host for tln_db
ODOO_HOST_IEG=...        # Odoo 16 host for ieg_db
ODOO_HOST_TMI=...        # Odoo 16 host for tmi_db

# Odoo 13 (HRIS)
ODOO_HOST_HRIS=...       # Odoo 13 host for hris_db

ODOO_USER=...            # Odoo XML-RPC user (service_account)
ODOO_PASSWORD=...        # Odoo XML-RPC password

# ClickHouse
CH_PASSWORD=...          # ClickHouse password

# Allowed databases
ALLOWED_ODOO_DBS=tln_db,ieg_db,tmi_db,hris_db
```

## Common Development Tasks

### Run locally
```bash
poetry install
poetry run uvicorn app.main:app --reload
```

### Run tests
```bash
poetry run pytest
```

### Build Docker
```bash
docker build -t mm-core .
docker run -p 8000:8000 --env-file .env mm-core
```

## Important Notes for AI Assistants

1. **Never format Mattermost messages** - return structured JSON for n8n to format
2. **All requests require API key** in `X-API-Key` header
3. **Database is per-request** - specified via `?db=` query param
4. **Audit everything** - all approval actions logged to PostgreSQL
5. **ClickHouse is read-only** - only for analytics queries
6. **Odoo XML-RPC for writes** - approvals go through Odoo API
7. **Multi-Odoo architecture** - Odoo 16 for ERP (tln, ieg, tmi), Odoo 13 for HRIS (hris_db)
8. **Version-aware client** - `settings.get_odoo_version(db_name)` returns 13 or 16

## Error Handling

Custom exceptions in `app/core/exceptions.py`:
- `NotFoundError` → 404
- `ValidationError` → 422
- `AuthenticationError` → 401
- `AuthorizationError` → 403
- `AlreadyApprovedError` → 409 (idempotency)
- `InvalidStateError` → 400
