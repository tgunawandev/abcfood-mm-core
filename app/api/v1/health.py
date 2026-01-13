"""Health check endpoints."""

from fastapi import APIRouter, Depends

from app import __version__
from app.api.deps import SettingsDep
from app.core.config import Settings
from app.core.logging import get_logger
from app.models.schemas import HealthResponse, ReadinessResponse
from app.utils.time import utc_now

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint.

    Returns application status, version, and current timestamp.
    Does not require authentication.
    """
    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=utc_now(),
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(settings: SettingsDep) -> ReadinessResponse:
    """Readiness check with database connectivity verification.

    Checks connectivity to:
    - PostgreSQL (audit logs)
    - ClickHouse (analytics)

    Does not require authentication.
    """
    checks: dict[str, bool] = {}

    # Check PostgreSQL connectivity
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=settings.pg_host,
            port=settings.pg_port,
            user=settings.pg_user,
            password=settings.pg_password,
            dbname=settings.pg_audit_db,
            connect_timeout=5,
        )
        conn.close()
        checks["postgresql"] = True
    except Exception as e:
        logger.warning("postgresql_check_failed", error=str(e))
        checks["postgresql"] = False

    # Check ClickHouse connectivity
    try:
        import clickhouse_connect

        client = clickhouse_connect.get_client(
            host=settings.ch_host,
            port=settings.ch_port,
            username=settings.ch_user,
            password=settings.ch_password,
        )
        client.ping()
        client.close()
        checks["clickhouse"] = True
    except Exception as e:
        logger.warning("clickhouse_check_failed", error=str(e))
        checks["clickhouse"] = False

    # Overall status
    all_healthy = all(checks.values())
    status = "ready" if all_healthy else "degraded"

    return ReadinessResponse(
        status=status,
        checks=checks,
    )
