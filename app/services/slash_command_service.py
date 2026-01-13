"""Slash command routing and handling service."""

import re
from datetime import datetime
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import SlashCommandError
from app.core.logging import get_logger
from app.models.schemas import (
    MattermostAttachment,
    MattermostField,
    SlashCommandRequest,
    SlashCommandResponse,
)

logger = get_logger(__name__)


class SlashCommandService:
    """Service for handling Mattermost slash commands."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize slash command service."""
        self.settings = settings or get_settings()

    async def handle_command(self, request: SlashCommandRequest) -> SlashCommandResponse:
        """Route and handle a slash command.

        Args:
            request: Slash command request from Mattermost

        Returns:
            SlashCommandResponse for Mattermost
        """
        command = request.command.lower().strip("/")
        text = request.text.strip()

        logger.info(
            "slash_command_received",
            command=command,
            text=text,
            user_id=request.user_id,
            user_name=request.user_name,
            channel_id=request.channel_id,
        )

        try:
            # Route to appropriate handler
            if command == "erp":
                return await self._handle_erp(text, request)
            elif command == "hr":
                return await self._handle_hr(text, request)
            elif command == "frappe":
                return await self._handle_frappe(text, request)
            elif command == "metabase":
                return await self._handle_metabase(text, request)
            elif command == "access":
                return await self._handle_access(text, request)
            else:
                return self._error_response(f"Unknown command: /{command}")

        except SlashCommandError as e:
            logger.error("slash_command_error", command=command, error=str(e))
            return self._error_response(str(e))
        except Exception as e:
            logger.exception("slash_command_exception", command=command, error=str(e))
            return self._error_response(f"An error occurred: {str(e)}")

    async def _handle_erp(
        self, text: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Handle /erp commands for Odoo 16 ERP.

        Subcommands:
            invoice <id> [db]  - Get invoice details
            pending [db]       - List pending approvals
            sales [period]     - Get sales metrics (today, mtd)
            help               - Show help
        """
        parts = text.split()
        subcommand = parts[0].lower() if parts else "help"

        if subcommand == "help" or not subcommand:
            return self._erp_help()

        if subcommand == "invoice":
            if len(parts) < 2:
                return self._error_response("Usage: /erp invoice <id> [db]")
            invoice_id = parts[1]
            db = parts[2] if len(parts) > 2 else "tln_db"
            return await self._erp_invoice(invoice_id, db, request)

        if subcommand == "pending":
            db = parts[1] if len(parts) > 1 else "tln_db"
            return await self._erp_pending(db, request)

        if subcommand == "sales":
            period = parts[1] if len(parts) > 1 else "today"
            db = parts[2] if len(parts) > 2 else "tln_db"
            return await self._erp_sales(period, db, request)

        return self._error_response(f"Unknown ERP subcommand: {subcommand}")

    async def _handle_hr(
        self, text: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Handle /hr commands for Odoo 13 HRIS.

        Subcommands:
            leave status     - Check leave balance
            leave pending    - List pending leave requests
            pending          - List all pending HR approvals
            help             - Show help
        """
        parts = text.split()
        subcommand = parts[0].lower() if parts else "help"

        if subcommand == "help" or not subcommand:
            return self._hr_help()

        if subcommand == "leave":
            action = parts[1] if len(parts) > 1 else "status"
            return await self._hr_leave(action, request)

        if subcommand == "pending":
            return await self._hr_pending(request)

        return self._error_response(f"Unknown HR subcommand: {subcommand}")

    async def _handle_frappe(
        self, text: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Handle /frappe commands for Frappe 15.

        Subcommands:
            crm leads [limit]     - List CRM leads
            crm customer <name>   - Get customer details
            order <id>            - Get sales order
            doc <doctype> <name>  - Get any document
            help                  - Show help
        """
        parts = text.split()
        subcommand = parts[0].lower() if parts else "help"

        if subcommand == "help" or not subcommand:
            return self._frappe_help()

        if subcommand == "crm":
            action = parts[1] if len(parts) > 1 else "leads"
            arg = parts[2] if len(parts) > 2 else None
            return await self._frappe_crm(action, arg, request)

        if subcommand == "order":
            if len(parts) < 2:
                return self._error_response("Usage: /frappe order <order_id>")
            order_id = parts[1]
            return await self._frappe_order(order_id, request)

        if subcommand == "doc":
            if len(parts) < 3:
                return self._error_response("Usage: /frappe doc <doctype> <name>")
            doctype = parts[1]
            name = parts[2]
            return await self._frappe_doc(doctype, name, request)

        return self._error_response(f"Unknown Frappe subcommand: {subcommand}")

    async def _handle_metabase(
        self, text: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Handle /metabase commands.

        Subcommands:
            dashboard <name|id>   - Get dashboard link
            question <id>         - Get saved question link
            search <query>        - Search dashboards
            help                  - Show help
        """
        parts = text.split()
        subcommand = parts[0].lower() if parts else "help"

        if subcommand == "help" or not subcommand:
            return self._metabase_help()

        if subcommand == "dashboard":
            if len(parts) < 2:
                return self._error_response("Usage: /metabase dashboard <name|id>")
            identifier = " ".join(parts[1:])
            return await self._metabase_dashboard(identifier, request)

        if subcommand == "question":
            if len(parts) < 2:
                return self._error_response("Usage: /metabase question <id>")
            question_id = parts[1]
            return await self._metabase_question(question_id, request)

        if subcommand == "search":
            query = " ".join(parts[1:]) if len(parts) > 1 else ""
            return await self._metabase_search(query, request)

        return self._error_response(f"Unknown Metabase subcommand: {subcommand}")

    async def _handle_access(
        self, text: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Handle /access commands for Authentik.

        Subcommands:
            request <app>    - Request access to an app
            status           - Check access status
            help             - Show help
        """
        parts = text.split()
        subcommand = parts[0].lower() if parts else "help"

        if subcommand == "help" or not subcommand:
            return self._access_help()

        if subcommand == "request":
            if len(parts) < 2:
                return self._error_response("Usage: /access request <app>")
            app = parts[1]
            return await self._access_request(app, request)

        if subcommand == "status":
            return await self._access_status(request)

        return self._error_response(f"Unknown access subcommand: {subcommand}")

    # =========================================================================
    # ERP Command Handlers
    # =========================================================================

    async def _erp_invoice(
        self, invoice_id: str, db: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Get invoice details from Odoo 16."""
        # TODO: Integrate with context_service.get_invoice_context()
        return SlashCommandResponse(
            response_type="ephemeral",
            text=f"Fetching invoice `{invoice_id}` from `{db}`...",
            attachments=[
                MattermostAttachment(
                    color="#3498db",
                    title=f"Invoice {invoice_id}",
                    text="Invoice details will be displayed here.",
                    fields=[
                        MattermostField(title="Database", value=db),
                        MattermostField(title="Status", value="Pending implementation"),
                    ],
                    footer="mm-core ERP",
                )
            ],
        )

    async def _erp_pending(
        self, db: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """List pending approvals from Odoo 16."""
        # TODO: Integrate with context_service.get_pending_approvals()
        return SlashCommandResponse(
            response_type="ephemeral",
            text=f"Pending approvals in `{db}`:",
            attachments=[
                MattermostAttachment(
                    color="#f39c12",
                    title="Pending Approvals",
                    text="No pending approvals found.",
                    fields=[
                        MattermostField(title="Database", value=db),
                    ],
                    footer="mm-core ERP",
                )
            ],
        )

    async def _erp_sales(
        self, period: str, db: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Get sales metrics from ClickHouse."""
        # TODO: Integrate with metrics_service
        return SlashCommandResponse(
            response_type="ephemeral",
            text=f"Sales metrics for `{period}` in `{db}`:",
            attachments=[
                MattermostAttachment(
                    color="#27ae60",
                    title=f"Sales - {period.upper()}",
                    fields=[
                        MattermostField(title="Period", value=period),
                        MattermostField(title="Database", value=db),
                        MattermostField(title="Revenue", value="Rp 0"),
                        MattermostField(title="Orders", value="0"),
                    ],
                    footer="mm-core Analytics",
                )
            ],
        )

    def _erp_help(self) -> SlashCommandResponse:
        """Show ERP command help."""
        return SlashCommandResponse(
            response_type="ephemeral",
            text="**ERP Commands** (Odoo 16)",
            attachments=[
                MattermostAttachment(
                    color="#3498db",
                    text="""
**Available commands:**
- `/erp invoice <id> [db]` - Get invoice details
- `/erp pending [db]` - List pending approvals
- `/erp sales [today|mtd] [db]` - Get sales metrics
- `/erp help` - Show this help

**Databases:** `tln_db`, `ieg_db`, `tmi_db`
""".strip(),
                )
            ],
        )

    # =========================================================================
    # HR Command Handlers
    # =========================================================================

    async def _hr_leave(
        self, action: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Handle leave-related commands."""
        if action == "status":
            return SlashCommandResponse(
                response_type="ephemeral",
                text="Your leave balance:",
                attachments=[
                    MattermostAttachment(
                        color="#9b59b6",
                        title="Leave Balance",
                        fields=[
                            MattermostField(title="Annual Leave", value="12 days"),
                            MattermostField(title="Sick Leave", value="5 days"),
                        ],
                        footer="mm-core HRIS",
                    )
                ],
            )
        elif action == "pending":
            return SlashCommandResponse(
                response_type="ephemeral",
                text="Pending leave requests:",
                attachments=[
                    MattermostAttachment(
                        color="#9b59b6",
                        title="Pending Leave Requests",
                        text="No pending leave requests.",
                        footer="mm-core HRIS",
                    )
                ],
            )
        return self._error_response(f"Unknown leave action: {action}")

    async def _hr_pending(self, request: SlashCommandRequest) -> SlashCommandResponse:
        """List pending HR approvals."""
        return SlashCommandResponse(
            response_type="ephemeral",
            text="Pending HR approvals:",
            attachments=[
                MattermostAttachment(
                    color="#9b59b6",
                    title="Pending HR Approvals",
                    text="No pending HR approvals.",
                    footer="mm-core HRIS",
                )
            ],
        )

    def _hr_help(self) -> SlashCommandResponse:
        """Show HR command help."""
        return SlashCommandResponse(
            response_type="ephemeral",
            text="**HR Commands** (Odoo 13 HRIS)",
            attachments=[
                MattermostAttachment(
                    color="#9b59b6",
                    text="""
**Available commands:**
- `/hr leave status` - Check your leave balance
- `/hr leave pending` - List pending leave requests
- `/hr pending` - List all pending HR approvals
- `/hr help` - Show this help
""".strip(),
                )
            ],
        )

    # =========================================================================
    # Frappe Command Handlers
    # =========================================================================

    async def _frappe_crm(
        self, action: str, arg: str | None, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Handle CRM commands."""
        if action == "leads":
            limit = int(arg) if arg and arg.isdigit() else 5
            # TODO: Integrate with frappe_service
            return SlashCommandResponse(
                response_type="ephemeral",
                text=f"Latest {limit} CRM leads:",
                attachments=[
                    MattermostAttachment(
                        color="#e74c3c",
                        title="CRM Leads",
                        text="No leads found.",
                        footer="mm-core Frappe",
                    )
                ],
            )
        elif action == "customer":
            if not arg:
                return self._error_response("Usage: /frappe crm customer <name>")
            # TODO: Integrate with frappe_service
            return SlashCommandResponse(
                response_type="ephemeral",
                text=f"Customer: {arg}",
                attachments=[
                    MattermostAttachment(
                        color="#e74c3c",
                        title=f"Customer: {arg}",
                        text="Customer details will be displayed here.",
                        footer="mm-core Frappe",
                    )
                ],
            )
        return self._error_response(f"Unknown CRM action: {action}")

    async def _frappe_order(
        self, order_id: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Get sales order from Frappe."""
        # TODO: Integrate with frappe_service
        return SlashCommandResponse(
            response_type="ephemeral",
            text=f"Sales Order: {order_id}",
            attachments=[
                MattermostAttachment(
                    color="#e74c3c",
                    title=f"Sales Order {order_id}",
                    text="Order details will be displayed here.",
                    footer="mm-core Frappe",
                )
            ],
        )

    async def _frappe_doc(
        self, doctype: str, name: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Get any Frappe document."""
        # TODO: Integrate with frappe_service
        return SlashCommandResponse(
            response_type="ephemeral",
            text=f"{doctype}: {name}",
            attachments=[
                MattermostAttachment(
                    color="#e74c3c",
                    title=f"{doctype}: {name}",
                    text="Document details will be displayed here.",
                    footer="mm-core Frappe",
                )
            ],
        )

    def _frappe_help(self) -> SlashCommandResponse:
        """Show Frappe command help."""
        return SlashCommandResponse(
            response_type="ephemeral",
            text="**Frappe Commands** (Frappe 15)",
            attachments=[
                MattermostAttachment(
                    color="#e74c3c",
                    text="""
**Available commands:**
- `/frappe crm leads [limit]` - List CRM leads
- `/frappe crm customer <name>` - Get customer details
- `/frappe order <id>` - Get sales order
- `/frappe doc <doctype> <name>` - Get any document
- `/frappe help` - Show this help
""".strip(),
                )
            ],
        )

    # =========================================================================
    # Metabase Command Handlers
    # =========================================================================

    async def _metabase_dashboard(
        self, identifier: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Get Metabase dashboard link."""
        # TODO: Integrate with metabase_service
        mb_domain = self.settings.mb_domain
        url = f"https://{mb_domain}/dashboard/{identifier}"

        return SlashCommandResponse(
            response_type="in_channel",
            text=f"**Dashboard:** [{identifier}]({url})",
            attachments=[
                MattermostAttachment(
                    color="#509EE3",
                    title=f"Dashboard: {identifier}",
                    title_link=url,
                    text="Click the link above to view the dashboard.",
                    footer="mm-core Metabase",
                )
            ],
        )

    async def _metabase_question(
        self, question_id: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Get Metabase saved question link."""
        mb_domain = self.settings.mb_domain
        url = f"https://{mb_domain}/question/{question_id}"

        return SlashCommandResponse(
            response_type="in_channel",
            text=f"**Question:** [{question_id}]({url})",
            attachments=[
                MattermostAttachment(
                    color="#509EE3",
                    title=f"Question: {question_id}",
                    title_link=url,
                    text="Click the link above to view the question.",
                    footer="mm-core Metabase",
                )
            ],
        )

    async def _metabase_search(
        self, query: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Search Metabase dashboards."""
        # TODO: Integrate with metabase_service
        return SlashCommandResponse(
            response_type="ephemeral",
            text=f"Searching dashboards for: `{query}`",
            attachments=[
                MattermostAttachment(
                    color="#509EE3",
                    title="Dashboard Search Results",
                    text="No dashboards found matching your query.",
                    footer="mm-core Metabase",
                )
            ],
        )

    def _metabase_help(self) -> SlashCommandResponse:
        """Show Metabase command help."""
        return SlashCommandResponse(
            response_type="ephemeral",
            text="**Metabase Commands**",
            attachments=[
                MattermostAttachment(
                    color="#509EE3",
                    text="""
**Available commands:**
- `/metabase dashboard <name|id>` - Get dashboard link
- `/metabase question <id>` - Get saved question link
- `/metabase search <query>` - Search dashboards
- `/metabase help` - Show this help
""".strip(),
                )
            ],
        )

    # =========================================================================
    # Access Command Handlers
    # =========================================================================

    async def _access_request(
        self, app: str, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Request access to an application."""
        # TODO: Integrate with Authentik API
        return SlashCommandResponse(
            response_type="ephemeral",
            text=f"Access request submitted for `{app}`",
            attachments=[
                MattermostAttachment(
                    color="#fd4b2d",
                    title="Access Request Submitted",
                    text=f"Your request for access to **{app}** has been submitted. "
                    "You will be notified when it's approved.",
                    footer="mm-core Authentik",
                )
            ],
        )

    async def _access_status(
        self, request: SlashCommandRequest
    ) -> SlashCommandResponse:
        """Check access status."""
        # TODO: Integrate with Authentik API
        return SlashCommandResponse(
            response_type="ephemeral",
            text="Your access status:",
            attachments=[
                MattermostAttachment(
                    color="#fd4b2d",
                    title="Access Status",
                    fields=[
                        MattermostField(title="ERP", value="Approved"),
                        MattermostField(title="HRIS", value="Approved"),
                        MattermostField(title="Metabase", value="Pending"),
                    ],
                    footer="mm-core Authentik",
                )
            ],
        )

    def _access_help(self) -> SlashCommandResponse:
        """Show access command help."""
        return SlashCommandResponse(
            response_type="ephemeral",
            text="**Access Commands** (Authentik)",
            attachments=[
                MattermostAttachment(
                    color="#fd4b2d",
                    text="""
**Available commands:**
- `/access request <app>` - Request access to an app
- `/access status` - Check your access status
- `/access help` - Show this help

**Available apps:** `erp`, `hris`, `metabase`, `frappe`
""".strip(),
                )
            ],
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _error_response(self, message: str) -> SlashCommandResponse:
        """Create an error response."""
        return SlashCommandResponse(
            response_type="ephemeral",
            text=f":x: **Error:** {message}",
            attachments=[
                MattermostAttachment(
                    color="#c0392b",
                    text=message,
                )
            ],
        )


def get_slash_command_service(settings: Settings | None = None) -> SlashCommandService:
    """Get slash command service instance."""
    return SlashCommandService(settings)
