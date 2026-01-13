"""Audit logging service for writing audit logs to PostgreSQL."""

import json
from typing import Any

from app.clients.postgres import get_audit_client
from app.core.logging import get_logger
from app.models.audit import AuditLogEntry
from app.models.enums import ApprovalResult, ObjectType

logger = get_logger(__name__)


class AuditService:
    """Service for writing audit logs to PostgreSQL."""

    def __init__(self) -> None:
        """Initialize audit service."""
        self._client = get_audit_client()

    def ensure_table(self) -> None:
        """Ensure audit table exists."""
        self._client.ensure_audit_table()

    def log(self, entry: AuditLogEntry) -> int | None:
        """Write an audit log entry.

        Args:
            entry: Audit log entry to write

        Returns:
            Record ID if successful
        """
        try:
            data = {
                "action_type": entry.action_type,
                "actor": entry.actor,
                "actor_role": entry.actor_role,
                "odoo_db": entry.odoo_db,
                "object_type": entry.object_type.value,
                "object_id": entry.object_id,
                "object_data": json.dumps(entry.object_data) if entry.object_data else None,
                "result": entry.result.value,
                "error_message": entry.error_message,
                "metadata": json.dumps(entry.metadata) if entry.metadata else None,
                "source": entry.source,
                "request_id": entry.request_id,
            }

            record_id = self._client.insert("mm_audit_logs", data, returning="id")

            logger.info(
                "audit_logged",
                action_type=entry.action_type,
                actor=entry.actor,
                object_type=entry.object_type.value,
                object_id=entry.object_id,
                result=entry.result.value,
            )

            return record_id

        except Exception as e:
            logger.error(
                "audit_log_failed",
                action_type=entry.action_type,
                error=str(e),
            )
            return None

    def log_approval(
        self,
        action: str,
        actor: str,
        db_name: str,
        object_type: ObjectType,
        object_id: str,
        result: ApprovalResult,
        actor_role: str | None = None,
        object_data: dict[str, Any] | None = None,
        error_message: str | None = None,
        source: str = "api",
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int | None:
        """Convenience method to log approval actions.

        Args:
            action: Action type (approve, reject)
            actor: User performing action
            db_name: Odoo database name
            object_type: Type of object
            object_id: Object ID
            result: Result of operation
            actor_role: Role of the actor
            object_data: Snapshot of object state
            error_message: Error message if failed
            source: Source of action
            request_id: Request ID for tracing
            metadata: Additional context

        Returns:
            Record ID if successful
        """
        entry = AuditLogEntry(
            action_type=f"{object_type.value}.{action}",
            actor=actor,
            actor_role=actor_role,
            odoo_db=db_name,
            object_type=object_type,
            object_id=object_id,
            object_data=object_data,
            result=result,
            error_message=error_message,
            source=source,
            request_id=request_id,
            metadata=metadata or {},
        )
        return self.log(entry)

    def get_recent_logs(
        self,
        limit: int = 100,
        action_type: str | None = None,
        actor: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent audit logs.

        Args:
            limit: Maximum records to return
            action_type: Filter by action type
            actor: Filter by actor

        Returns:
            List of audit log records
        """
        conditions = []
        params: dict[str, Any] = {"limit": limit}

        if action_type:
            conditions.append("action_type = %(action_type)s")
            params["action_type"] = action_type

        if actor:
            conditions.append("actor = %(actor)s")
            params["actor"] = actor

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
        SELECT *
        FROM mm_audit_logs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT %(limit)s
        """

        return self._client.execute(query, params)


def get_audit_service() -> AuditService:
    """Get audit service instance."""
    return AuditService()
