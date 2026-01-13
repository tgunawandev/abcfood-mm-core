"""Digest API endpoints for Live Business Pulse."""

from fastapi import APIRouter

from app.api.deps import ApiKeyDep, DbDep
from app.models.schemas import DigestResponse
from app.services.digest_service import get_digest_service

router = APIRouter(prefix="/digest", tags=["digest"])


@router.get("/sales/daily", response_model=DigestResponse)
async def get_sales_daily_digest(
    db: DbDep,
    api_key: ApiKeyDep,
) -> DigestResponse:
    """Get daily sales digest for channel posting.

    Called by n8n on schedule (e.g., 08:00 daily) to generate
    channel summaries for the sales team.

    Returns structured data for n8n to format and post to Mattermost:
    - Total revenue and order count
    - Top selling products
    - Comparison with previous day
    - Alerts (if any issues)

    Example n8n workflow:
    1. n8n cron triggers at 08:00
    2. n8n calls this endpoint
    3. n8n formats response into rich markdown
    4. n8n posts to #sales-{company} channel
    """
    service = get_digest_service(db)
    return service.get_sales_daily()


@router.get("/finance/daily", response_model=DigestResponse)
async def get_finance_daily_digest(
    db: DbDep,
    api_key: ApiKeyDep,
) -> DigestResponse:
    """Get daily finance digest for channel posting.

    Provides finance team with:
    - Receivables/payables summary
    - Overdue amounts
    - Critical alerts for severely overdue items

    Posted to #finance-{company} channel daily.
    """
    service = get_digest_service(db)
    return service.get_finance_daily()


@router.get("/ops/daily", response_model=DigestResponse)
async def get_ops_daily_digest(
    db: DbDep,
    api_key: ApiKeyDep,
) -> DigestResponse:
    """Get daily operations digest for channel posting.

    Provides operations team with:
    - Pending orders count
    - Pending deliveries
    - Low stock alerts

    Posted to #ops-{company} channel daily.
    """
    service = get_digest_service(db)
    return service.get_ops_daily()
