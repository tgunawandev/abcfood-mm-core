"""Context API endpoints for actionable notifications."""

from fastapi import APIRouter, HTTPException, Path, status

from app.api.deps import ApiKeyDep, DbDep
from app.models.schemas import ObjectContext
from app.services.context_service import get_context_service

router = APIRouter(prefix="/context", tags=["context"])


@router.get("/invoice/{invoice_id}", response_model=ObjectContext)
async def get_invoice_context(
    invoice_id: int = Path(description="Invoice ID"),
    db: DbDep = ...,
    api_key: ApiKeyDep = ...,
) -> ObjectContext:
    """Get invoice context with available actions.

    Returns object details and available actions for n8n to build
    interactive notification buttons.

    Example n8n workflow:
    1. n8n detects new pending invoice
    2. n8n calls this endpoint to get context
    3. n8n builds Mattermost message with buttons:
       - [✓ Approve] [✗ Reject] [👁 View]
    4. User clicks button → n8n routes to approval endpoint
    """
    service = get_context_service(db)
    context = service.get_invoice_context(invoice_id)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found",
        )
    return context


@router.get("/expense/{expense_id}", response_model=ObjectContext)
async def get_expense_context(
    expense_id: int = Path(description="Expense ID"),
    db: DbDep = ...,
    api_key: ApiKeyDep = ...,
) -> ObjectContext:
    """Get expense context with available actions.

    Returns expense details and available actions for n8n to build
    interactive notification buttons.
    """
    service = get_context_service(db)
    context = service.get_expense_context(expense_id)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found",
        )
    return context


@router.get("/leave/{leave_id}", response_model=ObjectContext)
async def get_leave_context(
    leave_id: int = Path(description="Leave request ID"),
    db: DbDep = ...,
    api_key: ApiKeyDep = ...,
) -> ObjectContext:
    """Get leave request context with available actions.

    Returns leave request details and available actions for n8n to build
    interactive notification buttons.
    """
    service = get_context_service(db)
    context = service.get_leave_context(leave_id)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leave request {leave_id} not found",
        )
    return context
