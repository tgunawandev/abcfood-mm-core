"""Approval service for handling invoice, expense, and leave approvals."""

from datetime import datetime
from typing import Any

from app.clients.odoo import get_odoo_client
from app.core.exceptions import (
    AlreadyApprovedError,
    InvalidStateError,
    NotFoundError,
    OdooError,
)
from app.core.logging import get_logger
from app.models.enums import ApprovalAction, ApprovalResult, ObjectType
from app.models.schemas import ApprovalRequest, ApprovalResponse
from app.services.audit_service import get_audit_service
from app.utils.time import utc_now

logger = get_logger(__name__)


class ApprovalService:
    """Service for handling approvals of various object types."""

    def __init__(self, db_name: str) -> None:
        """Initialize approval service.

        Args:
            db_name: Odoo database name
        """
        self.db_name = db_name
        self._odoo = get_odoo_client(db_name)
        self._audit = get_audit_service()

    def approve_invoice(
        self,
        invoice_id: int,
        request: ApprovalRequest,
    ) -> ApprovalResponse:
        """Approve or reject an invoice.

        Args:
            invoice_id: Invoice ID
            request: Approval request

        Returns:
            Approval response

        Raises:
            NotFoundError: If invoice not found
            InvalidStateError: If invoice in invalid state
            AlreadyApprovedError: If already approved
        """
        object_id = str(invoice_id)
        action = request.action.value

        try:
            # Get current invoice state
            invoice = self._odoo.get_invoice(invoice_id)
            if not invoice:
                raise NotFoundError(
                    f"Invoice {invoice_id} not found",
                    {"invoice_id": invoice_id, "db": self.db_name},
                )

            # Check current state
            current_state = invoice["state"]
            if current_state == "posted" and request.action == ApprovalAction.APPROVE:
                raise AlreadyApprovedError(
                    f"Invoice {invoice_id} is already approved",
                    {"invoice_id": invoice_id, "current_state": current_state},
                )

            if current_state not in ("draft",) and request.action == ApprovalAction.APPROVE:
                raise InvalidStateError(
                    f"Invoice {invoice_id} cannot be approved in state {current_state}",
                    {"invoice_id": invoice_id, "current_state": current_state},
                )

            # Perform action
            if request.action == ApprovalAction.APPROVE:
                result = self._odoo.approve_invoice(invoice_id)
                new_state = result["new_state"]
            else:
                result = self._odoo.reject_invoice(invoice_id, request.reason)
                new_state = result["new_state"]

            # Log audit
            self._audit.log_approval(
                action=action,
                actor=request.actor,
                db_name=self.db_name,
                object_type=ObjectType.INVOICE,
                object_id=object_id,
                result=ApprovalResult.SUCCESS,
                actor_role=request.actor_role,
                object_data=invoice,
                source=request.source,
                request_id=request.request_id,
                metadata={"reason": request.reason} if request.reason else None,
            )

            # Build summary
            partner_name = invoice.get("partner_id", [0, "Unknown"])[1] if isinstance(
                invoice.get("partner_id"), list
            ) else "Unknown"
            amount = invoice.get("amount_total", 0)
            summary = f"Invoice {invoice['name']} {action}d ({partner_name}, Rp {amount:,.0f})"

            return ApprovalResponse(
                success=True,
                object_type=ObjectType.INVOICE,
                object_id=object_id,
                action=request.action,
                new_state=new_state,
                actor=request.actor,
                timestamp=utc_now(),
                summary=summary,
                result=ApprovalResult.SUCCESS,
            )

        except (NotFoundError, InvalidStateError, AlreadyApprovedError):
            raise

        except OdooError as e:
            # Log failed audit
            self._audit.log_approval(
                action=action,
                actor=request.actor,
                db_name=self.db_name,
                object_type=ObjectType.INVOICE,
                object_id=object_id,
                result=ApprovalResult.FAILED,
                actor_role=request.actor_role,
                error_message=str(e),
                source=request.source,
                request_id=request.request_id,
            )
            raise

    def approve_expense(
        self,
        expense_id: int,
        request: ApprovalRequest,
    ) -> ApprovalResponse:
        """Approve or reject an expense.

        Args:
            expense_id: Expense ID
            request: Approval request

        Returns:
            Approval response
        """
        object_id = str(expense_id)
        action = request.action.value

        try:
            expense = self._odoo.get_expense(expense_id)
            if not expense:
                raise NotFoundError(
                    f"Expense {expense_id} not found",
                    {"expense_id": expense_id, "db": self.db_name},
                )

            if request.action == ApprovalAction.APPROVE:
                result = self._odoo.approve_expense(expense_id)
                new_state = result["new_state"]
            else:
                # For reject, we'd need to implement reject_expense in OdooClient
                new_state = "refused"

            # Log audit
            self._audit.log_approval(
                action=action,
                actor=request.actor,
                db_name=self.db_name,
                object_type=ObjectType.EXPENSE,
                object_id=object_id,
                result=ApprovalResult.SUCCESS,
                actor_role=request.actor_role,
                object_data=expense,
                source=request.source,
                request_id=request.request_id,
            )

            amount = expense.get("total_amount", 0)
            summary = f"Expense {expense['name']} {action}d (Rp {amount:,.0f})"

            return ApprovalResponse(
                success=True,
                object_type=ObjectType.EXPENSE,
                object_id=object_id,
                action=request.action,
                new_state=new_state,
                actor=request.actor,
                timestamp=utc_now(),
                summary=summary,
                result=ApprovalResult.SUCCESS,
            )

        except (NotFoundError, InvalidStateError, AlreadyApprovedError):
            raise

        except OdooError as e:
            self._audit.log_approval(
                action=action,
                actor=request.actor,
                db_name=self.db_name,
                object_type=ObjectType.EXPENSE,
                object_id=object_id,
                result=ApprovalResult.FAILED,
                error_message=str(e),
                source=request.source,
                request_id=request.request_id,
            )
            raise

    def approve_leave(
        self,
        leave_id: int,
        request: ApprovalRequest,
    ) -> ApprovalResponse:
        """Approve or reject a leave request.

        Args:
            leave_id: Leave request ID
            request: Approval request

        Returns:
            Approval response
        """
        object_id = str(leave_id)
        action = request.action.value

        try:
            leave = self._odoo.get_leave(leave_id)
            if not leave:
                raise NotFoundError(
                    f"Leave request {leave_id} not found",
                    {"leave_id": leave_id, "db": self.db_name},
                )

            if request.action == ApprovalAction.APPROVE:
                result = self._odoo.approve_leave(leave_id)
                new_state = result["new_state"]
            else:
                result = self._odoo.reject_leave(leave_id, request.reason)
                new_state = result["new_state"]

            # Log audit
            self._audit.log_approval(
                action=action,
                actor=request.actor,
                db_name=self.db_name,
                object_type=ObjectType.LEAVE,
                object_id=object_id,
                result=ApprovalResult.SUCCESS,
                actor_role=request.actor_role,
                object_data=leave,
                source=request.source,
                request_id=request.request_id,
            )

            days = leave.get("number_of_days", 0)
            summary = f"Leave {leave['display_name']} {action}d ({days} days)"

            return ApprovalResponse(
                success=True,
                object_type=ObjectType.LEAVE,
                object_id=object_id,
                action=request.action,
                new_state=new_state,
                actor=request.actor,
                timestamp=utc_now(),
                summary=summary,
                result=ApprovalResult.SUCCESS,
            )

        except (NotFoundError, InvalidStateError, AlreadyApprovedError):
            raise

        except OdooError as e:
            self._audit.log_approval(
                action=action,
                actor=request.actor,
                db_name=self.db_name,
                object_type=ObjectType.LEAVE,
                object_id=object_id,
                result=ApprovalResult.FAILED,
                error_message=str(e),
                source=request.source,
                request_id=request.request_id,
            )
            raise


def get_approval_service(db_name: str) -> ApprovalService:
    """Get approval service instance for specific database."""
    return ApprovalService(db_name)
