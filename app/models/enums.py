"""Enumerations used across the application."""

from enum import Enum


class ApprovalAction(str, Enum):
    """Actions that can be performed on approvable items."""

    APPROVE = "approve"
    REJECT = "reject"


class ApprovalResult(str, Enum):
    """Results of approval operations."""

    SUCCESS = "success"
    FAILED = "failed"
    DENIED = "denied"


class ObjectType(str, Enum):
    """Types of objects that can be approved or queried."""

    INVOICE = "invoice"
    EXPENSE = "expense"
    LEAVE = "leave"


class ObjectState(str, Enum):
    """Common states for Odoo objects."""

    DRAFT = "draft"
    OPEN = "open"
    POSTED = "posted"
    PAID = "paid"
    CANCEL = "cancel"
    APPROVED = "approved"
    REJECTED = "rejected"


class OdooDatabase(str, Enum):
    """Allowed Odoo databases."""

    TLN_DB = "tln_db"
    IEG_DB = "ieg_db"
    TMI_DB = "tmi_db"


class ActionSource(str, Enum):
    """Source of actions for audit logging."""

    N8N = "n8n"
    MATTERMOST = "mattermost"
    API = "api"


class DigestType(str, Enum):
    """Types of digests."""

    SALES_DAILY = "sales_daily"
    FINANCE_DAILY = "finance_daily"
    OPS_DAILY = "ops_daily"


class AlertType(str, Enum):
    """Types of alerts in digests."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Priority(str, Enum):
    """Priority levels for pending items."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
