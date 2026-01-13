"""Context service for actionable notifications and pending items."""

from datetime import datetime
from typing import Any

from app.clients.odoo import get_odoo_client
from app.clients.postgres import get_odoo_client as get_postgres_client
from app.core.logging import get_logger
from app.models.enums import ObjectType, OdooDatabase, Priority
from app.models.schemas import ObjectContext, PendingItem, PendingItemsResponse
from app.utils.time import days_between, utc_now

logger = get_logger(__name__)


class ContextService:
    """Service for object context and pending items.

    Provides data for n8n to build actionable notifications
    with interactive buttons.
    """

    def __init__(self, db_name: str) -> None:
        """Initialize context service.

        Args:
            db_name: Odoo database name
        """
        self.db_name = db_name
        self._odoo = get_odoo_client(db_name)
        self._postgres = get_postgres_client(db_name)

    def get_invoice_context(self, invoice_id: int) -> ObjectContext | None:
        """Get invoice context with available actions.

        Args:
            invoice_id: Invoice ID

        Returns:
            Object context or None if not found
        """
        try:
            invoice = self._odoo.get_invoice(invoice_id)
            if not invoice:
                return None

            state = invoice.get("state", "")

            # Determine available actions based on state
            actions = []
            if state == "draft":
                actions = ["approve", "reject", "view"]
            elif state == "posted":
                actions = ["view"]
            elif state == "cancel":
                actions = ["view"]

            # Parse partner name
            partner = invoice.get("partner_id")
            partner_name = partner[1] if isinstance(partner, list) else "Unknown"

            # Parse due date
            due_date = invoice.get("invoice_date_due")
            if isinstance(due_date, str):
                due_date = datetime.fromisoformat(due_date)

            days_overdue = 0
            if due_date and state == "posted":
                days_overdue = max(0, days_between(due_date))

            return ObjectContext(
                object_type=ObjectType.INVOICE,
                object_id=str(invoice_id),
                display_name=invoice.get("name", f"Invoice {invoice_id}"),
                state=state,
                amount=float(invoice.get("amount_total", 0)),
                partner=partner_name,
                due_date=due_date,
                days_overdue=days_overdue,
                available_actions=actions,
                requires_role="manager" if state == "draft" else None,
                additional_info={
                    "amount_residual": invoice.get("amount_residual", 0),
                    "move_type": invoice.get("move_type", ""),
                },
            )

        except Exception as e:
            logger.error(
                "invoice_context_error",
                invoice_id=invoice_id,
                error=str(e),
            )
            return None

    def get_expense_context(self, expense_id: int) -> ObjectContext | None:
        """Get expense context with available actions.

        Args:
            expense_id: Expense ID

        Returns:
            Object context or None if not found
        """
        try:
            expense = self._odoo.get_expense(expense_id)
            if not expense:
                return None

            state = expense.get("state", "")

            actions = []
            if state in ("draft", "reported"):
                actions = ["approve", "reject", "view"]
            else:
                actions = ["view"]

            employee = expense.get("employee_id")
            employee_name = employee[1] if isinstance(employee, list) else "Unknown"

            return ObjectContext(
                object_type=ObjectType.EXPENSE,
                object_id=str(expense_id),
                display_name=expense.get("name", f"Expense {expense_id}"),
                state=state,
                amount=float(expense.get("total_amount", 0)),
                partner=employee_name,
                available_actions=actions,
                requires_role="manager" if state in ("draft", "reported") else None,
                additional_info={
                    "description": expense.get("description", ""),
                },
            )

        except Exception as e:
            logger.error("expense_context_error", expense_id=expense_id, error=str(e))
            return None

    def get_leave_context(self, leave_id: int) -> ObjectContext | None:
        """Get leave context with available actions.

        Args:
            leave_id: Leave request ID

        Returns:
            Object context or None if not found
        """
        try:
            leave = self._odoo.get_leave(leave_id)
            if not leave:
                return None

            state = leave.get("state", "")

            actions = []
            if state in ("confirm",):
                actions = ["approve", "reject", "view"]
            else:
                actions = ["view"]

            employee = leave.get("employee_id")
            employee_name = employee[1] if isinstance(employee, list) else "Unknown"

            leave_type = leave.get("holiday_status_id")
            leave_type_name = leave_type[1] if isinstance(leave_type, list) else "Leave"

            return ObjectContext(
                object_type=ObjectType.LEAVE,
                object_id=str(leave_id),
                display_name=leave.get("display_name", f"Leave {leave_id}"),
                state=state,
                partner=employee_name,
                available_actions=actions,
                requires_role="manager" if state == "confirm" else None,
                additional_info={
                    "leave_type": leave_type_name,
                    "number_of_days": leave.get("number_of_days", 0),
                    "date_from": str(leave.get("date_from", "")),
                    "date_to": str(leave.get("date_to", "")),
                },
            )

        except Exception as e:
            logger.error("leave_context_error", leave_id=leave_id, error=str(e))
            return None

    def get_pending_approvals(
        self,
        actor: str | None = None,
    ) -> PendingItemsResponse:
        """Get pending items awaiting approval.

        Args:
            actor: Filter by assigned approver

        Returns:
            List of pending items
        """
        items: list[PendingItem] = []

        try:
            # Get pending invoices
            pending_invoices = self._postgres.get_pending_invoices("draft")
            for inv in pending_invoices[:20]:  # Limit to 20
                create_date = inv.get("create_date")
                if isinstance(create_date, str):
                    create_date = datetime.fromisoformat(create_date)
                elif create_date is None:
                    create_date = utc_now()

                days_pending = days_between(create_date)
                priority = self._calculate_priority(
                    days_pending, float(inv.get("amount_total", 0))
                )

                items.append(
                    PendingItem(
                        object_type=ObjectType.INVOICE,
                        object_id=str(inv["id"]),
                        display_name=inv.get("name", f"Invoice {inv['id']}"),
                        amount=float(inv.get("amount_total", 0)),
                        waiting_since=create_date,
                        days_pending=days_pending,
                        priority=priority,
                    )
                )

            return PendingItemsResponse(
                db=OdooDatabase(self.db_name),
                count=len(items),
                items=items,
            )

        except Exception as e:
            logger.error("pending_approvals_error", db=self.db_name, error=str(e))
            return PendingItemsResponse(
                db=OdooDatabase(self.db_name),
                count=0,
                items=[],
            )

    def get_overdue_items(
        self,
        threshold_days: int = 14,
    ) -> PendingItemsResponse:
        """Get overdue items above threshold.

        Args:
            threshold_days: Minimum days overdue

        Returns:
            List of overdue items
        """
        items: list[PendingItem] = []

        try:
            overdue_invoices = self._postgres.get_overdue_invoices(threshold_days)

            for inv in overdue_invoices[:20]:
                due_date = inv.get("invoice_date_due")
                if isinstance(due_date, str):
                    due_date = datetime.fromisoformat(due_date)
                elif due_date is None:
                    due_date = utc_now()

                days_overdue = int(inv.get("days_overdue", 0))
                priority = self._calculate_overdue_priority(
                    days_overdue, float(inv.get("amount_residual", 0))
                )

                items.append(
                    PendingItem(
                        object_type=ObjectType.INVOICE,
                        object_id=str(inv["id"]),
                        display_name=inv.get("name", f"Invoice {inv['id']}"),
                        amount=float(inv.get("amount_residual", 0)),
                        waiting_since=due_date,
                        days_pending=days_overdue,
                        priority=priority,
                    )
                )

            return PendingItemsResponse(
                db=OdooDatabase(self.db_name),
                count=len(items),
                items=items,
            )

        except Exception as e:
            logger.error("overdue_items_error", db=self.db_name, error=str(e))
            return PendingItemsResponse(
                db=OdooDatabase(self.db_name),
                count=0,
                items=[],
            )

    def _calculate_priority(self, days_pending: int, amount: float) -> Priority:
        """Calculate priority based on pending days and amount."""
        if days_pending > 7 or amount > 100_000_000:  # 100M IDR
            return Priority.HIGH
        elif days_pending > 3 or amount > 50_000_000:  # 50M IDR
            return Priority.MEDIUM
        else:
            return Priority.LOW

    def _calculate_overdue_priority(self, days_overdue: int, amount: float) -> Priority:
        """Calculate priority for overdue items."""
        if days_overdue > 30 or amount > 100_000_000:
            return Priority.CRITICAL
        elif days_overdue > 14 or amount > 50_000_000:
            return Priority.HIGH
        elif days_overdue > 7:
            return Priority.MEDIUM
        else:
            return Priority.LOW


def get_context_service(db_name: str) -> ContextService:
    """Get context service instance for specific database."""
    return ContextService(db_name)
