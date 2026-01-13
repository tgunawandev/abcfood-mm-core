"""Audit log model for PostgreSQL."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import ApprovalResult, ObjectType


class AuditLogEntry(BaseModel):
    """Audit log entry to be written to PostgreSQL."""

    action_type: str = Field(description="Action type (e.g., invoice.approve)")
    actor: str = Field(description="User performing action")
    actor_role: str | None = Field(default=None, description="Role of the actor")
    odoo_db: str = Field(description="Odoo database name")
    object_type: ObjectType = Field(description="Type of object")
    object_id: str = Field(description="ID of the object")
    object_data: dict[str, Any] | None = Field(default=None, description="Snapshot of object state")
    result: ApprovalResult = Field(description="Result of the operation")
    error_message: str | None = Field(default=None, description="Error message if failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    source: str = Field(description="Source of the action")
    request_id: str | None = Field(default=None, description="Request ID for tracing")


class AuditLogRecord(AuditLogEntry):
    """Audit log record as stored in PostgreSQL (with id and timestamp)."""

    id: int = Field(description="Record ID")
    created_at: datetime = Field(description="When the record was created")
