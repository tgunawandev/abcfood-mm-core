"""Pydantic schemas for request/response models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import (
    AlertType,
    ApprovalAction,
    ApprovalResult,
    DigestType,
    ObjectType,
    OdooDatabase,
    Priority,
)


# =============================================================================
# Health Check
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(description="Health status")
    version: str = Field(description="Application version")
    timestamp: datetime = Field(description="Current timestamp")


class ReadinessResponse(BaseModel):
    """Readiness check response with DB connectivity status."""

    status: str = Field(description="Overall readiness status")
    checks: dict[str, bool] = Field(description="Individual check results")


# =============================================================================
# Approval Schemas
# =============================================================================


class ApprovalRequest(BaseModel):
    """Request body for approval actions."""

    action: ApprovalAction = Field(description="Action to perform")
    actor: str = Field(description="User performing the action (email)")
    actor_role: str | None = Field(default=None, description="Role of the actor")
    reason: str | None = Field(default=None, description="Reason for rejection")
    source: str = Field(default="api", description="Source of the action")
    request_id: str | None = Field(default=None, description="Request ID for tracing")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")


class ApprovalResponse(BaseModel):
    """Response for approval actions."""

    success: bool = Field(description="Whether the action succeeded")
    object_type: ObjectType = Field(description="Type of object")
    object_id: str = Field(description="ID of the object")
    action: ApprovalAction = Field(description="Action performed")
    new_state: str = Field(description="New state after action")
    actor: str = Field(description="User who performed the action")
    timestamp: datetime = Field(description="When the action was performed")
    summary: str = Field(description="Human-readable summary")
    result: ApprovalResult = Field(description="Result of the operation")
    error_message: str | None = Field(default=None, description="Error message if failed")


# =============================================================================
# Metrics Schemas
# =============================================================================


class SalesSummary(BaseModel):
    """Sales summary metrics."""

    db: OdooDatabase = Field(description="Source database")
    period: str = Field(description="Period covered (today, mtd, etc.)")
    total_revenue: float = Field(description="Total revenue")
    order_count: int = Field(description="Number of orders")
    avg_order_value: float = Field(description="Average order value")
    currency: str = Field(default="IDR", description="Currency")
    comparison_previous: str | None = Field(default=None, description="Comparison with previous period")


class OverdueInvoice(BaseModel):
    """Single overdue invoice."""

    id: int = Field(description="Invoice ID")
    name: str = Field(description="Invoice number")
    partner_name: str = Field(description="Customer name")
    amount_total: float = Field(description="Total amount")
    amount_residual: float = Field(description="Amount due")
    date_due: datetime = Field(description="Due date")
    days_overdue: int = Field(description="Days overdue")
    currency: str = Field(default="IDR", description="Currency")


class OverdueInvoicesResponse(BaseModel):
    """Response for overdue invoices query."""

    db: OdooDatabase = Field(description="Source database")
    count: int = Field(description="Number of overdue invoices")
    total_overdue_amount: float = Field(description="Total overdue amount")
    invoices: list[OverdueInvoice] = Field(description="List of overdue invoices")


class CustomerRisk(BaseModel):
    """Customer risk snapshot."""

    db: OdooDatabase = Field(description="Source database")
    customer_id: int = Field(description="Customer ID")
    customer_name: str = Field(description="Customer name")
    total_receivable: float = Field(description="Total receivable amount")
    total_overdue: float = Field(description="Total overdue amount")
    overdue_count: int = Field(description="Number of overdue invoices")
    avg_days_to_pay: float = Field(description="Average days to pay")
    risk_score: str = Field(description="Risk level (low, medium, high)")
    last_payment_date: datetime | None = Field(default=None, description="Last payment date")


# =============================================================================
# Digest Schemas
# =============================================================================


class DigestAlert(BaseModel):
    """Alert item in a digest."""

    type: AlertType = Field(description="Alert type")
    message: str = Field(description="Alert message")


class DigestMetrics(BaseModel):
    """Metrics section of a digest."""

    pass  # Will be extended by specific digest types


class SalesDigestMetrics(DigestMetrics):
    """Sales-specific digest metrics."""

    total_revenue: float = Field(description="Total revenue")
    order_count: int = Field(description="Number of orders")
    avg_order_value: float = Field(description="Average order value")
    top_products: list[dict[str, Any]] = Field(default_factory=list, description="Top selling products")
    comparison_yesterday: str | None = Field(default=None, description="Comparison with yesterday")


class FinanceDigestMetrics(DigestMetrics):
    """Finance-specific digest metrics."""

    total_receivable: float = Field(description="Total receivable")
    total_payable: float = Field(description="Total payable")
    overdue_receivable: float = Field(description="Overdue receivable")
    overdue_payable: float = Field(description="Overdue payable")
    cash_position: float | None = Field(default=None, description="Cash position if available")


class OpsDigestMetrics(DigestMetrics):
    """Operations-specific digest metrics."""

    pending_orders: int = Field(description="Pending orders")
    pending_deliveries: int = Field(description="Pending deliveries")
    low_stock_items: int = Field(description="Low stock items count")
    fulfillment_rate: float | None = Field(default=None, description="Fulfillment rate")


class DigestResponse(BaseModel):
    """Response for digest queries."""

    digest_type: DigestType = Field(description="Type of digest")
    db: OdooDatabase = Field(description="Source database")
    period: str = Field(description="Period covered")
    generated_at: datetime = Field(description="When the digest was generated")
    metrics: dict[str, Any] = Field(description="Digest metrics")
    alerts: list[DigestAlert] = Field(default_factory=list, description="Alerts")


# =============================================================================
# Context Schemas
# =============================================================================


class ObjectContext(BaseModel):
    """Context for an object with available actions."""

    object_type: ObjectType = Field(description="Type of object")
    object_id: str = Field(description="Object ID")
    display_name: str = Field(description="Display name")
    state: str = Field(description="Current state")
    amount: float | None = Field(default=None, description="Amount if applicable")
    partner: str | None = Field(default=None, description="Partner/customer name")
    due_date: datetime | None = Field(default=None, description="Due date if applicable")
    days_overdue: int = Field(default=0, description="Days overdue")
    available_actions: list[str] = Field(description="Available actions")
    requires_role: str | None = Field(default=None, description="Role required for actions")
    additional_info: dict[str, Any] = Field(default_factory=dict, description="Additional context")


# =============================================================================
# Pending Items Schemas
# =============================================================================


class PendingItem(BaseModel):
    """Single pending item awaiting action."""

    object_type: ObjectType = Field(description="Type of object")
    object_id: str = Field(description="Object ID")
    display_name: str = Field(description="Display name")
    amount: float | None = Field(default=None, description="Amount if applicable")
    waiting_since: datetime = Field(description="When the item started waiting")
    days_pending: int = Field(description="Days pending")
    priority: Priority = Field(description="Priority level")
    assignee: str | None = Field(default=None, description="Assigned user")


class PendingItemsResponse(BaseModel):
    """Response for pending items query."""

    db: OdooDatabase = Field(description="Source database")
    count: int = Field(description="Number of pending items")
    items: list[PendingItem] = Field(description="List of pending items")


# =============================================================================
# Error Response
# =============================================================================


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(description="Error code")
    message: str = Field(description="Error message")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional details")


# =============================================================================
# Mattermost Slash Command Schemas
# =============================================================================


class SlashCommandRequest(BaseModel):
    """Mattermost slash command payload (form-urlencoded)."""

    channel_id: str = Field(description="Channel ID where command was invoked")
    channel_name: str = Field(default="", description="Channel name")
    command: str = Field(description="Command name (e.g., /erp)")
    response_url: str = Field(default="", description="URL for delayed responses")
    team_domain: str = Field(default="", description="Team domain")
    team_id: str = Field(default="", description="Team ID")
    text: str = Field(default="", description="Text after the command")
    token: str = Field(description="Slash command verification token")
    trigger_id: str = Field(default="", description="Trigger ID for interactive dialogs")
    user_id: str = Field(description="Mattermost user ID")
    user_name: str = Field(default="", description="Mattermost username")


class MattermostField(BaseModel):
    """Field in a Mattermost attachment."""

    title: str = Field(description="Field title")
    value: str = Field(description="Field value")
    short: bool = Field(default=True, description="Display as short field")


class MattermostAction(BaseModel):
    """Action button in a Mattermost attachment."""

    id: str = Field(description="Action ID")
    name: str = Field(description="Button text")
    type: str = Field(default="button", description="Action type")
    integration: dict[str, Any] = Field(default_factory=dict, description="Integration config")


class MattermostAttachment(BaseModel):
    """Mattermost message attachment."""

    fallback: str | None = Field(default=None, description="Fallback text")
    color: str | None = Field(default=None, description="Sidebar color (hex)")
    pretext: str | None = Field(default=None, description="Text before attachment")
    author_name: str | None = Field(default=None, description="Author name")
    author_icon: str | None = Field(default=None, description="Author icon URL")
    title: str | None = Field(default=None, description="Attachment title")
    title_link: str | None = Field(default=None, description="Title hyperlink")
    text: str | None = Field(default=None, description="Main attachment text")
    fields: list[MattermostField] = Field(default_factory=list, description="Fields")
    actions: list[MattermostAction] = Field(default_factory=list, description="Action buttons")
    image_url: str | None = Field(default=None, description="Image URL")
    thumb_url: str | None = Field(default=None, description="Thumbnail URL")
    footer: str | None = Field(default=None, description="Footer text")
    footer_icon: str | None = Field(default=None, description="Footer icon URL")


class SlashCommandResponse(BaseModel):
    """Mattermost slash command response."""

    response_type: str = Field(
        default="ephemeral",
        description="Response visibility: 'in_channel' or 'ephemeral'",
    )
    text: str | None = Field(default=None, description="Response text")
    attachments: list[MattermostAttachment] = Field(
        default_factory=list,
        description="Message attachments",
    )
    username: str | None = Field(default=None, description="Override bot username")
    icon_url: str | None = Field(default=None, description="Override bot icon")
