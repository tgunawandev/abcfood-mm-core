"""Odoo XML-RPC client for approval operations."""

import xmlrpc.client
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import OdooError
from app.core.logging import get_logger

logger = get_logger(__name__)


class OdooClient:
    """Odoo XML-RPC client for interacting with Odoo.

    This client handles authentication and provides methods for
    CRUD operations on Odoo models.
    """

    def __init__(self, db_name: str) -> None:
        """Initialize Odoo client.

        Args:
            db_name: Odoo database name (tln_db, ieg_db, tmi_db, hris_db)

        Multi-server architecture:
        - Odoo 16 (Main ERP):
            - tln_db -> tln.abcfood.app (prod) / odoo-16-dev.abcfood.app (dev)
            - ieg_db -> ieg.abcfood.app (prod) / odoo-16-dev.abcfood.app (dev)
            - tmi_db -> tmi.abcfood.app (prod) / odoo-16-dev.abcfood.app (dev)
        - Odoo 13 (HRIS):
            - hris_db -> odoo-13-dev.abcfood.app (dev) / TBD (prod)
        """
        self.settings = get_settings()
        if db_name not in self.settings.allowed_odoo_dbs:
            raise ValueError(f"Database {db_name} not in allowed list")

        self.db_name = db_name
        # Get the correct host and version for this database
        odoo_host = self.settings.get_odoo_host(db_name)
        self.odoo_version = self.settings.get_odoo_version(db_name)
        self.url = f"http://{odoo_host}:{self.settings.odoo_port}"
        self.username = self.settings.odoo_user
        self.password = self.settings.odoo_password
        self._uid: int | None = None

        logger.debug(
            "odoo_client_initialized",
            db=db_name,
            host=odoo_host,
            odoo_version=self.odoo_version,
            user=self.username,
        )

    @property
    def common(self) -> xmlrpc.client.ServerProxy:
        """Get common endpoint proxy."""
        return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")

    @property
    def models(self) -> xmlrpc.client.ServerProxy:
        """Get models endpoint proxy."""
        return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

    def authenticate(self) -> int:
        """Authenticate with Odoo and get user ID.

        Returns:
            User ID

        Raises:
            OdooError: If authentication fails
        """
        if self._uid is not None:
            return self._uid

        try:
            uid = self.common.authenticate(
                self.db_name,
                self.username,
                self.password,
                {},
            )
            if not uid:
                raise OdooError(
                    "Authentication failed",
                    {"db": self.db_name, "user": self.username},
                )
            self._uid = uid
            logger.debug("odoo_authenticated", db=self.db_name, uid=uid)
            return uid
        except xmlrpc.client.Fault as e:
            logger.error("odoo_auth_error", db=self.db_name, error=str(e))
            raise OdooError(f"Odoo authentication failed: {e}") from e

    def execute(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """Execute an Odoo method.

        Args:
            model: Odoo model name (e.g., 'account.move')
            method: Method name (e.g., 'read', 'write', 'action_post')
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Method result

        Raises:
            OdooError: If execution fails
        """
        uid = self.authenticate()
        args = args or []
        kwargs = kwargs or {}

        try:
            result = self.models.execute_kw(
                self.db_name,
                uid,
                self.password,
                model,
                method,
                args,
                kwargs,
            )
            return result
        except xmlrpc.client.Fault as e:
            logger.error(
                "odoo_execute_error",
                model=model,
                method=method,
                error=str(e),
            )
            raise OdooError(f"Odoo operation failed: {e}") from e

    def search(
        self,
        model: str,
        domain: list[Any],
        limit: int | None = None,
        offset: int = 0,
        order: str | None = None,
    ) -> list[int]:
        """Search for records.

        Args:
            model: Odoo model name
            domain: Search domain
            limit: Maximum records to return
            offset: Number of records to skip
            order: Sort order

        Returns:
            List of record IDs
        """
        kwargs: dict[str, Any] = {}
        if limit:
            kwargs["limit"] = limit
        if offset:
            kwargs["offset"] = offset
        if order:
            kwargs["order"] = order

        return self.execute(model, "search", [domain], kwargs)

    def read(
        self,
        model: str,
        ids: list[int],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Read records.

        Args:
            model: Odoo model name
            ids: Record IDs to read
            fields: Fields to read (all if None)

        Returns:
            List of record data
        """
        kwargs = {"fields": fields} if fields else {}
        return self.execute(model, "read", [ids], kwargs)

    def search_read(
        self,
        model: str,
        domain: list[Any],
        fields: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search and read records in one call.

        Args:
            model: Odoo model name
            domain: Search domain
            fields: Fields to read
            limit: Maximum records
            offset: Records to skip
            order: Sort order

        Returns:
            List of record data
        """
        kwargs: dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields
        if limit:
            kwargs["limit"] = limit
        if offset:
            kwargs["offset"] = offset
        if order:
            kwargs["order"] = order

        return self.execute(model, "search_read", [domain], kwargs)

    def write(
        self,
        model: str,
        ids: list[int],
        values: dict[str, Any],
    ) -> bool:
        """Update records.

        Args:
            model: Odoo model name
            ids: Record IDs to update
            values: Field values to set

        Returns:
            True if successful
        """
        return self.execute(model, "write", [ids, values])

    def call(
        self,
        model: str,
        method: str,
        ids: list[int],
    ) -> Any:
        """Call a method on records.

        Args:
            model: Odoo model name
            method: Method name
            ids: Record IDs

        Returns:
            Method result
        """
        return self.execute(model, method, [ids])

    def test_connection(self) -> bool:
        """Test Odoo connectivity.

        Returns:
            True if connection successful
        """
        try:
            version = self.common.version()
            logger.debug("odoo_connected", version=version.get("server_version"))
            return True
        except Exception as e:
            logger.warning("odoo_test_failed", error=str(e))
            return False

    # =========================================================================
    # Invoice Operations
    # =========================================================================

    def get_invoice(self, invoice_id: int) -> dict[str, Any] | None:
        """Get invoice details.

        Args:
            invoice_id: Invoice ID

        Returns:
            Invoice data or None
        """
        records = self.read(
            "account.move",
            [invoice_id],
            [
                "name",
                "state",
                "move_type",
                "amount_total",
                "amount_residual",
                "partner_id",
                "invoice_date",
                "invoice_date_due",
                "currency_id",
            ],
        )
        return records[0] if records else None

    def approve_invoice(self, invoice_id: int) -> dict[str, Any]:
        """Approve (post) an invoice.

        Args:
            invoice_id: Invoice ID

        Returns:
            Result with new state

        Raises:
            OdooError: If approval fails
        """
        # Check current state
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise OdooError(f"Invoice {invoice_id} not found", {"invoice_id": invoice_id})

        if invoice["state"] != "draft":
            raise OdooError(
                f"Invoice {invoice_id} is not in draft state",
                {"invoice_id": invoice_id, "current_state": invoice["state"]},
            )

        # Post the invoice (approve)
        self.call("account.move", "action_post", [invoice_id])

        # Fetch updated record
        updated = self.get_invoice(invoice_id)
        return {
            "invoice_id": invoice_id,
            "new_state": updated["state"] if updated else "unknown",
            "invoice_name": invoice["name"],
            "amount_total": invoice["amount_total"],
        }

    def reject_invoice(self, invoice_id: int, reason: str | None = None) -> dict[str, Any]:
        """Reject (cancel) an invoice.

        Args:
            invoice_id: Invoice ID
            reason: Rejection reason

        Returns:
            Result with new state
        """
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            raise OdooError(f"Invoice {invoice_id} not found", {"invoice_id": invoice_id})

        # Cancel the invoice
        self.call("account.move", "button_cancel", [invoice_id])

        # Optionally add rejection note
        if reason:
            self.execute(
                "mail.message",
                "create",
                [{
                    "model": "account.move",
                    "res_id": invoice_id,
                    "body": f"<p>Rejected: {reason}</p>",
                    "message_type": "comment",
                }],
            )

        updated = self.get_invoice(invoice_id)
        return {
            "invoice_id": invoice_id,
            "new_state": updated["state"] if updated else "unknown",
            "invoice_name": invoice["name"],
            "reason": reason,
        }

    # =========================================================================
    # Expense Operations
    # =========================================================================

    def get_expense(self, expense_id: int) -> dict[str, Any] | None:
        """Get expense details.

        Args:
            expense_id: Expense ID

        Returns:
            Expense data or None
        """
        records = self.read(
            "hr.expense",
            [expense_id],
            [
                "name",
                "state",
                "total_amount",
                "employee_id",
                "date",
                "description",
            ],
        )
        return records[0] if records else None

    def approve_expense(self, expense_id: int) -> dict[str, Any]:
        """Approve an expense.

        Args:
            expense_id: Expense ID

        Returns:
            Result with new state
        """
        expense = self.get_expense(expense_id)
        if not expense:
            raise OdooError(f"Expense {expense_id} not found", {"expense_id": expense_id})

        # Approve the expense
        self.call("hr.expense", "action_submit_expenses", [expense_id])
        self.call("hr.expense", "action_approve_expense_sheets", [expense_id])

        updated = self.get_expense(expense_id)
        return {
            "expense_id": expense_id,
            "new_state": updated["state"] if updated else "unknown",
            "expense_name": expense["name"],
            "total_amount": expense["total_amount"],
        }

    # =========================================================================
    # Leave Operations
    # =========================================================================

    def get_leave(self, leave_id: int) -> dict[str, Any] | None:
        """Get leave request details.

        Args:
            leave_id: Leave request ID

        Returns:
            Leave data or None
        """
        records = self.read(
            "hr.leave",
            [leave_id],
            [
                "display_name",
                "state",
                "employee_id",
                "date_from",
                "date_to",
                "number_of_days",
                "holiday_status_id",
            ],
        )
        return records[0] if records else None

    def approve_leave(self, leave_id: int) -> dict[str, Any]:
        """Approve a leave request.

        Args:
            leave_id: Leave request ID

        Returns:
            Result with new state
        """
        leave = self.get_leave(leave_id)
        if not leave:
            raise OdooError(f"Leave {leave_id} not found", {"leave_id": leave_id})

        # Approve the leave
        self.call("hr.leave", "action_approve", [leave_id])

        updated = self.get_leave(leave_id)
        return {
            "leave_id": leave_id,
            "new_state": updated["state"] if updated else "unknown",
            "leave_name": leave["display_name"],
            "number_of_days": leave["number_of_days"],
        }

    def reject_leave(self, leave_id: int, reason: str | None = None) -> dict[str, Any]:
        """Reject a leave request.

        Args:
            leave_id: Leave request ID
            reason: Rejection reason

        Returns:
            Result with new state
        """
        leave = self.get_leave(leave_id)
        if not leave:
            raise OdooError(f"Leave {leave_id} not found", {"leave_id": leave_id})

        # Reject the leave
        self.call("hr.leave", "action_refuse", [leave_id])

        updated = self.get_leave(leave_id)
        return {
            "leave_id": leave_id,
            "new_state": updated["state"] if updated else "unknown",
            "leave_name": leave["display_name"],
            "reason": reason,
        }


def get_odoo_client(db_name: str) -> OdooClient:
    """Get Odoo XML-RPC client for specific database."""
    return OdooClient(db_name)
