"""Approval API endpoints."""

from fastapi import APIRouter, Depends, Path

from app.api.deps import ApiKeyDep, DbDep
from app.models.schemas import ApprovalRequest, ApprovalResponse
from app.services.approval_service import get_approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/invoice/{invoice_id}", response_model=ApprovalResponse)
async def approve_invoice(
    invoice_id: int = Path(description="Invoice ID"),
    request: ApprovalRequest = ...,
    db: DbDep = ...,
    api_key: ApiKeyDep = ...,
) -> ApprovalResponse:
    """Approve or reject an invoice.

    This endpoint:
    1. Validates the request
    2. Updates the invoice state in Odoo
    3. Logs the action to audit table
    4. Returns structured response for n8n to format

    **Request body:**
    - `action`: "approve" or "reject"
    - `actor`: Email of user performing action
    - `actor_role`: Optional role of the actor
    - `reason`: Optional rejection reason
    - `source`: Source of action (default: "api")
    - `request_id`: Optional request ID for tracing
    """
    service = get_approval_service(db)
    return service.approve_invoice(invoice_id, request)


@router.post("/expense/{expense_id}", response_model=ApprovalResponse)
async def approve_expense(
    expense_id: int = Path(description="Expense ID"),
    request: ApprovalRequest = ...,
    db: DbDep = ...,
    api_key: ApiKeyDep = ...,
) -> ApprovalResponse:
    """Approve or reject an expense.

    This endpoint:
    1. Validates the request
    2. Updates the expense state in Odoo
    3. Logs the action to audit table
    4. Returns structured response for n8n to format
    """
    service = get_approval_service(db)
    return service.approve_expense(expense_id, request)


@router.post("/leave/{leave_id}", response_model=ApprovalResponse)
async def approve_leave(
    leave_id: int = Path(description="Leave request ID"),
    request: ApprovalRequest = ...,
    db: DbDep = ...,
    api_key: ApiKeyDep = ...,
) -> ApprovalResponse:
    """Approve or reject a leave request.

    This endpoint:
    1. Validates the request
    2. Updates the leave state in Odoo
    3. Logs the action to audit table
    4. Returns structured response for n8n to format
    """
    service = get_approval_service(db)
    return service.approve_leave(leave_id, request)
