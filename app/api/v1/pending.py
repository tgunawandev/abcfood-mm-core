"""Pending items API endpoints for proactive alerts."""

from fastapi import APIRouter, Query

from app.api.deps import ApiKeyDep, DbDep
from app.models.schemas import PendingItemsResponse
from app.services.context_service import get_context_service

router = APIRouter(prefix="/pending", tags=["pending"])


@router.get("/approvals", response_model=PendingItemsResponse)
async def get_pending_approvals(
    db: DbDep,
    api_key: ApiKeyDep,
    actor: str | None = Query(
        default=None,
        description="Filter by assigned approver email",
    ),
) -> PendingItemsResponse:
    """Get items awaiting approval.

    n8n polls this endpoint periodically to trigger notifications
    for items that need attention.

    Example n8n workflow:
    1. n8n cron triggers every hour
    2. n8n calls this endpoint
    3. For each pending item with priority >= high:
       - n8n gets context (GET /context/{type}/{id})
       - n8n sends notification with action buttons
    4. Prevents notification spam by tracking sent notifications

    Returns:
    - Count of pending items
    - List with priority levels (low, medium, high, critical)
    """
    service = get_context_service(db)
    return service.get_pending_approvals(actor)


@router.get("/overdue", response_model=PendingItemsResponse)
async def get_overdue_items(
    db: DbDep,
    api_key: ApiKeyDep,
    threshold_days: int = Query(
        default=14,
        ge=0,
        description="Minimum days overdue to include",
    ),
) -> PendingItemsResponse:
    """Get overdue items above threshold.

    n8n polls this endpoint to trigger actionable notifications
    for overdue invoices that need follow-up.

    Example n8n workflow:
    1. n8n cron triggers daily
    2. n8n calls this endpoint with threshold_days=14
    3. For critical priority items:
       - n8n sends notification with actions:
         [📞 Call Customer] [📧 Send Reminder] [👁 View Invoice]
    4. n8n tracks which items have been notified

    Returns items with priority based on:
    - Days overdue (>30 = critical, >14 = high)
    - Amount (>100M = critical, >50M = high)
    """
    service = get_context_service(db)
    return service.get_overdue_items(threshold_days)
