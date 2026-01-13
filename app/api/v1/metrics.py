"""Metrics API endpoints for ChatOps queries."""

from fastapi import APIRouter, Path, Query

from app.api.deps import ApiKeyDep, DbDep
from app.models.schemas import CustomerRisk, OverdueInvoicesResponse, SalesSummary
from app.services.metrics_service import get_metrics_service

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/sales/today", response_model=SalesSummary)
async def get_sales_today(
    db: DbDep,
    api_key: ApiKeyDep,
) -> SalesSummary:
    """Get today's sales summary.

    Returns:
    - Total revenue
    - Order count
    - Average order value
    - Comparison with yesterday

    Example n8n usage:
    ```
    /sales today → "📊 Sales Today: Rp 150,000,000 (45 orders, +12% vs yesterday)"
    ```
    """
    service = get_metrics_service(db)
    return service.get_sales_today()


@router.get("/sales/mtd", response_model=SalesSummary)
async def get_sales_mtd(
    db: DbDep,
    api_key: ApiKeyDep,
) -> SalesSummary:
    """Get month-to-date sales summary.

    Returns sales metrics for the current month.
    """
    service = get_metrics_service(db)
    return service.get_sales_mtd()


@router.get("/invoices/overdue", response_model=OverdueInvoicesResponse)
async def get_overdue_invoices(
    db: DbDep,
    api_key: ApiKeyDep,
    threshold_days: int = Query(
        default=0,
        ge=0,
        description="Minimum days overdue to include",
    ),
) -> OverdueInvoicesResponse:
    """Get list of overdue invoices.

    Returns:
    - Count of overdue invoices
    - Total overdue amount
    - List of invoices with details

    Example n8n usage:
    ```
    /invoice overdue → "⚠️ 5 invoices overdue (Rp 75,000,000)"
    ```
    """
    service = get_metrics_service(db)
    return service.get_overdue_invoices(threshold_days)


@router.get("/customers/{customer_id}/risk", response_model=CustomerRisk | None)
async def get_customer_risk(
    customer_id: int = Path(description="Customer ID"),
    db: DbDep = ...,
    api_key: ApiKeyDep = ...,
) -> CustomerRisk | None:
    """Get customer risk snapshot.

    Returns:
    - Total receivable
    - Total overdue
    - Overdue count
    - Risk score (low/medium/high)

    Example n8n usage:
    ```
    /customer risk @PT ABC → "🔴 High Risk: Rp 50M overdue (3 invoices)"
    ```
    """
    service = get_metrics_service(db)
    return service.get_customer_risk(customer_id)
