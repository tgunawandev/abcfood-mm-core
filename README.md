# ABCFood MM Core

Core business logic service for Mattermost command center. This service is the **BRAIN** that handles approvals, ChatOps queries, and audit logging.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      MATTERMOST                                 │
│                    (Chat Interface)                             │
│     User types: /sales today   |   Clicks [Approve] button     │
└───────────────────────┬─────────────────────┬───────────────────┘
                        │                     │
                        ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                         n8n                                     │
│                    (Orchestrator)                               │
│  • Receives slash commands & button clicks                      │
│  • Routes to mm-core APIs                                       │
│  • Formats responses for Mattermost                             │
│  • Schedules digests & polls for pending items                  │
└───────────────────────┬─────────────────────┬───────────────────┘
                        │                     │
                        ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MM-CORE (This Service)                       │
│                       (Brain)                                   │
│  • Business logic & validation                                  │
│  • Approval workflows                                           │
│  • Metrics queries                                              │
│  • Audit logging                                                │
└───────────┬───────────────────┬───────────────────┬─────────────┘
            │                   │                   │
            ▼                   ▼                   ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │    Odoo       │   │  PostgreSQL   │   │  ClickHouse   │
    │  (XML-RPC)    │   │ (Audit Logs)  │   │ (Analytics)   │
    │               │   │               │   │               │
    │ tln_db        │   │ mm_audit_logs │   │ Sales metrics │
    │ ieg_db        │   │               │   │ Reports       │
    │ tmi_db        │   │               │   │               │
    └───────────────┘   └───────────────┘   └───────────────┘
```

## Key Principles

1. **mm-core is the BRAIN** - All business logic, validation, and rules live here
2. **n8n is the ORCHESTRATOR** - Workflow, scheduling, and message formatting
3. **Mattermost is the UI** - User interaction only
4. **Structured JSON only** - mm-core never formats Mattermost messages

## API Endpoints

### Health
- `GET /api/v1/health` - Health check
- `GET /api/v1/ready` - Readiness (DB connectivity)

### Approvals (Killer Feature #1)
- `POST /api/v1/approvals/invoice/{id}?db={db}` - Approve/reject invoice
- `POST /api/v1/approvals/expense/{id}?db={db}` - Approve/reject expense
- `POST /api/v1/approvals/leave/{id}?db={db}` - Approve/reject leave

### Metrics (Killer Feature #2 - ChatOps)
- `GET /api/v1/metrics/sales/today?db={db}` - Today's sales
- `GET /api/v1/metrics/sales/mtd?db={db}` - Month-to-date sales
- `GET /api/v1/metrics/invoices/overdue?db={db}` - Overdue invoices
- `GET /api/v1/metrics/customers/{id}/risk?db={db}` - Customer risk

### Digest (Killer Feature #3 - Live Pulse)
- `GET /api/v1/digest/sales/daily?db={db}` - Daily sales digest
- `GET /api/v1/digest/finance/daily?db={db}` - Daily finance digest
- `GET /api/v1/digest/ops/daily?db={db}` - Daily ops digest

### Context (Killer Feature #4 - Actionable Notifications)
- `GET /api/v1/context/invoice/{id}?db={db}` - Invoice context + actions
- `GET /api/v1/context/expense/{id}?db={db}` - Expense context + actions
- `GET /api/v1/context/leave/{id}?db={db}` - Leave context + actions

### Pending (Killer Feature #4 - Proactive Alerts)
- `GET /api/v1/pending/approvals?db={db}` - Items awaiting approval
- `GET /api/v1/pending/overdue?db={db}` - Overdue items

## Quick Start

### Local Development

```bash
# Clone and setup
cd ~/projects/abcfood-mm-core

# Install dependencies
poetry install

# Copy environment
cp .env.example .env
# Edit .env with your credentials

# Run development server
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Access docs
open http://localhost:8000/docs
```

### Docker

```bash
# Build
docker build -t abcfood-mm-core .

# Run
docker run -d \
  --name mm-core \
  -p 8000:8000 \
  --env-file .env \
  abcfood-mm-core

# Or with docker-compose
docker-compose up -d
```

## n8n Integration Examples

### Slash Command: /sales today

```
n8n Webhook receives: /sales today
           ↓
n8n calls: GET http://mm-core:8000/api/v1/metrics/sales/today?db=tln_db
           Headers: X-API-Key: <api-key>
           ↓
mm-core returns:
{
  "db": "tln_db",
  "period": "today",
  "total_revenue": 150000000,
  "order_count": 45,
  "avg_order_value": 3333333,
  "comparison_previous": "+12%"
}
           ↓
n8n formats: "📊 **Sales Today (TLN)**
              Revenue: Rp 150,000,000
              Orders: 45
              Avg: Rp 3,333,333
              vs Yesterday: +12%"
           ↓
n8n posts to Mattermost channel
```

### Approval Flow

```
n8n polls: GET /api/v1/pending/approvals?db=tln_db
           ↓
mm-core returns: [{ id: 123, type: "invoice", amount: 15M, priority: "high" }]
           ↓
n8n gets context: GET /api/v1/context/invoice/123?db=tln_db
           ↓
n8n builds message with buttons: [✓ Approve] [✗ Reject] [👁 View]
           ↓
n8n sends to approver's DM
           ↓
User clicks [✓ Approve]
           ↓
n8n receives action → POST /api/v1/approvals/invoice/123?db=tln_db
           ↓
mm-core validates, updates Odoo, logs audit
           ↓
n8n updates message: "✅ Invoice INV/2026/001 approved by @user"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEY` | API authentication key | required |
| `PG_HOST` | PostgreSQL host | 116.203.191.172 |
| `PG_PASSWORD` | PostgreSQL password | required |
| `PG_AUDIT_DB` | Audit database name | mm_audit |
| `ODOO_HOST` | Odoo host | 116.203.191.172 |
| `ODOO_USER` | Odoo username | required |
| `ODOO_PASSWORD` | Odoo password | required |
| `CH_HOST` | ClickHouse host | 138.199.213.219 |
| `CH_PASSWORD` | ClickHouse password | required |

## Project Structure

```
abcfood-mm-core/
├── app/
│   ├── main.py              # FastAPI application
│   ├── api/v1/              # API endpoints
│   │   ├── approvals.py     # Approval endpoints
│   │   ├── metrics.py       # ChatOps queries
│   │   ├── digest.py        # Live pulse digests
│   │   ├── context.py       # Actionable notifications
│   │   └── pending.py       # Proactive alerts
│   ├── core/                # Core infrastructure
│   │   ├── config.py        # Pydantic settings
│   │   ├── security.py      # API key auth
│   │   ├── logging.py       # Structured logging
│   │   └── exceptions.py    # Exception hierarchy
│   ├── clients/             # External service clients
│   │   ├── postgres.py      # PostgreSQL (audit + data)
│   │   ├── clickhouse.py    # ClickHouse (analytics)
│   │   └── odoo.py          # Odoo XML-RPC
│   ├── services/            # Business logic
│   │   ├── approval_service.py
│   │   ├── metrics_service.py
│   │   ├── digest_service.py
│   │   ├── context_service.py
│   │   └── audit_service.py
│   └── models/              # Pydantic models
│       ├── schemas.py       # Request/response models
│       ├── enums.py         # Enumerations
│       └── audit.py         # Audit log model
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Non-Goals

This service does NOT handle:
- UI rendering (n8n + Mattermost)
- Scheduling/cron (n8n)
- Retries/error recovery (n8n)
- Workflow branching (n8n)
- Mattermost message formatting (n8n)

## Related Projects

- `kodemeio-platform-ops/apps/airflow/` - Production deployment configs
- `abcfood-airflow-etl/` - ETL jobs that sync data to ClickHouse
