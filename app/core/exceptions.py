"""Custom exception hierarchy for the application."""

from typing import Any


class MMCoreError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(MMCoreError):
    """Raised when authentication fails."""

    pass


class AuthorizationError(MMCoreError):
    """Raised when user lacks permission for an action."""

    pass


class ValidationError(MMCoreError):
    """Raised when input validation fails."""

    pass


class NotFoundError(MMCoreError):
    """Raised when a requested resource is not found."""

    pass


class ConflictError(MMCoreError):
    """Raised when there's a conflict (e.g., duplicate approval)."""

    pass


class ExternalServiceError(MMCoreError):
    """Base exception for external service errors."""

    pass


class OdooError(ExternalServiceError):
    """Raised when Odoo operations fail."""

    pass


class ClickHouseError(ExternalServiceError):
    """Raised when ClickHouse operations fail."""

    pass


class PostgresError(ExternalServiceError):
    """Raised when PostgreSQL operations fail."""

    pass


class ApprovalError(MMCoreError):
    """Base exception for approval-related errors."""

    pass


class ApprovalLimitExceededError(ApprovalError):
    """Raised when approval limit is exceeded."""

    pass


class AlreadyApprovedError(ApprovalError):
    """Raised when item is already approved (idempotency check)."""

    pass


class InvalidStateError(ApprovalError):
    """Raised when object is in invalid state for the requested action."""

    pass


class JWTValidationError(AuthenticationError):
    """Raised when JWT token validation fails."""

    pass


class FrappeError(ExternalServiceError):
    """Raised when Frappe operations fail."""

    pass


class MetabaseError(ExternalServiceError):
    """Raised when Metabase operations fail."""

    pass


class SlashCommandError(MMCoreError):
    """Raised for slash command errors."""

    pass
