"""Models package - exports all schemas and enums."""

from app.models.audit import AuditLogEntry, AuditLogRecord
from app.models.enums import (
    ActionSource,
    AlertType,
    ApprovalAction,
    ApprovalResult,
    DigestType,
    ObjectState,
    ObjectType,
    OdooDatabase,
    Priority,
)
from app.models.schemas import (
    ApprovalRequest,
    ApprovalResponse,
    CustomerRisk,
    DigestAlert,
    DigestResponse,
    ErrorResponse,
    FinanceDigestMetrics,
    HealthResponse,
    ObjectContext,
    OpsDigestMetrics,
    OverdueInvoice,
    OverdueInvoicesResponse,
    PendingItem,
    PendingItemsResponse,
    ReadinessResponse,
    SalesDigestMetrics,
    SalesSummary,
)

__all__ = [
    # Enums
    "ActionSource",
    "AlertType",
    "ApprovalAction",
    "ApprovalResult",
    "DigestType",
    "ObjectState",
    "ObjectType",
    "OdooDatabase",
    "Priority",
    # Audit
    "AuditLogEntry",
    "AuditLogRecord",
    # Schemas
    "ApprovalRequest",
    "ApprovalResponse",
    "CustomerRisk",
    "DigestAlert",
    "DigestResponse",
    "ErrorResponse",
    "FinanceDigestMetrics",
    "HealthResponse",
    "ObjectContext",
    "OpsDigestMetrics",
    "OverdueInvoice",
    "OverdueInvoicesResponse",
    "PendingItem",
    "PendingItemsResponse",
    "ReadinessResponse",
    "SalesDigestMetrics",
    "SalesSummary",
]
