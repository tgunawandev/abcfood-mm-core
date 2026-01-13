"""PostgreSQL client for audit logs and Odoo data reads."""

from contextlib import contextmanager
from typing import Any, Generator

import psycopg2
from psycopg2.extras import RealDictCursor

from app.core.config import get_settings
from app.core.exceptions import PostgresError
from app.core.logging import get_logger

logger = get_logger(__name__)


class PostgresClient:
    """PostgreSQL client for database operations."""

    def __init__(self, db_name: str | None = None) -> None:
        """Initialize PostgreSQL client.

        Args:
            db_name: Database name. If None, uses audit database from settings.
        """
        self.settings = get_settings()
        self.db_name = db_name or self.settings.pg_audit_db

    @contextmanager
    def get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """Get a database connection as context manager.

        Yields:
            PostgreSQL connection

        Raises:
            PostgresError: If connection fails
        """
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.settings.pg_host,
                port=self.settings.pg_port,
                user=self.settings.pg_user,
                password=self.settings.pg_password,
                dbname=self.db_name,
                connect_timeout=10,
            )
            yield conn
        except psycopg2.Error as e:
            logger.error("postgres_connection_error", db=self.db_name, error=str(e))
            raise PostgresError(f"Failed to connect to PostgreSQL: {e}") from e
        finally:
            if conn:
                conn.close()

    @contextmanager
    def get_cursor(
        self, commit: bool = False
    ) -> Generator[psycopg2.extensions.cursor, None, None]:
        """Get a database cursor as context manager.

        Args:
            commit: Whether to commit after operations

        Yields:
            PostgreSQL cursor with RealDictCursor factory
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cursor
                if commit:
                    conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def execute(
        self,
        query: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
        commit: bool = False,
    ) -> list[dict[str, Any]]:
        """Execute a query and return results.

        Args:
            query: SQL query
            params: Query parameters
            commit: Whether to commit

        Returns:
            List of result rows as dictionaries
        """
        with self.get_cursor(commit=commit) as cursor:
            cursor.execute(query, params)
            if cursor.description:
                return [dict(row) for row in cursor.fetchall()]
            return []

    def execute_one(
        self,
        query: str,
        params: tuple[Any, ...] | dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Execute a query and return single result.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Single result row or None
        """
        results = self.execute(query, params)
        return results[0] if results else None

    def insert(
        self,
        table: str,
        data: dict[str, Any],
        returning: str | None = "id",
    ) -> Any:
        """Insert a row into a table.

        Args:
            table: Table name
            data: Column-value mapping
            returning: Column to return (default: id)

        Returns:
            Value of returning column if specified
        """
        columns = list(data.keys())
        placeholders = [f"%({col})s" for col in columns]

        query = f"""
            INSERT INTO {table} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """

        if returning:
            query += f" RETURNING {returning}"

        with self.get_cursor(commit=True) as cursor:
            cursor.execute(query, data)
            if returning and cursor.description:
                result = cursor.fetchone()
                return result[returning] if result else None
            return None

    def test_connection(self) -> bool:
        """Test database connectivity.

        Returns:
            True if connection successful
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception as e:
            logger.warning("postgres_test_failed", db=self.db_name, error=str(e))
            return False


class AuditPostgresClient(PostgresClient):
    """Specialized PostgreSQL client for audit logs."""

    def __init__(self) -> None:
        """Initialize with audit database."""
        super().__init__()

    def ensure_audit_table(self) -> None:
        """Create audit log table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS mm_audit_logs (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            action_type VARCHAR(100) NOT NULL,
            actor VARCHAR(255) NOT NULL,
            actor_role VARCHAR(100),
            odoo_db VARCHAR(50) NOT NULL,
            object_type VARCHAR(100) NOT NULL,
            object_id VARCHAR(100) NOT NULL,
            object_data JSONB,
            result VARCHAR(50) NOT NULL,
            error_message TEXT,
            metadata JSONB,
            source VARCHAR(50) NOT NULL,
            request_id VARCHAR(100)
        );

        CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at
            ON mm_audit_logs(created_at);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_action_type
            ON mm_audit_logs(action_type);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_actor
            ON mm_audit_logs(actor);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_object
            ON mm_audit_logs(object_type, object_id);
        """

        with self.get_cursor(commit=True) as cursor:
            cursor.execute(create_table_sql)
        logger.info("audit_table_ensured")


class OdooPostgresClient(PostgresClient):
    """Specialized PostgreSQL client for reading Odoo data."""

    def __init__(self, db_name: str) -> None:
        """Initialize with specific Odoo database.

        Args:
            db_name: Odoo database name (tln_db, ieg_db, tmi_db)
        """
        settings = get_settings()
        if db_name not in settings.allowed_odoo_dbs:
            raise ValueError(f"Database {db_name} not in allowed list")
        super().__init__(db_name)

    def get_invoice(self, invoice_id: int) -> dict[str, Any] | None:
        """Get invoice details.

        Args:
            invoice_id: Invoice ID

        Returns:
            Invoice data or None
        """
        query = """
        SELECT
            am.id,
            am.name,
            am.state,
            am.move_type,
            am.amount_total,
            am.amount_residual,
            am.currency_id,
            am.date,
            am.invoice_date,
            am.invoice_date_due,
            rp.name as partner_name,
            rp.id as partner_id,
            rc.symbol as currency_symbol
        FROM account_move am
        LEFT JOIN res_partner rp ON am.partner_id = rp.id
        LEFT JOIN res_currency rc ON am.currency_id = rc.id
        WHERE am.id = %s
        """
        return self.execute_one(query, (invoice_id,))

    def get_pending_invoices(self, state: str = "draft") -> list[dict[str, Any]]:
        """Get pending invoices.

        Args:
            state: Invoice state to filter

        Returns:
            List of pending invoices
        """
        query = """
        SELECT
            am.id,
            am.name,
            am.state,
            am.amount_total,
            am.create_date,
            rp.name as partner_name
        FROM account_move am
        LEFT JOIN res_partner rp ON am.partner_id = rp.id
        WHERE am.state = %s
            AND am.move_type IN ('out_invoice', 'out_refund')
        ORDER BY am.create_date DESC
        LIMIT 100
        """
        return self.execute(query, (state,))

    def get_overdue_invoices(self, threshold_days: int = 0) -> list[dict[str, Any]]:
        """Get overdue invoices.

        Args:
            threshold_days: Minimum days overdue

        Returns:
            List of overdue invoices
        """
        query = """
        SELECT
            am.id,
            am.name,
            am.state,
            am.amount_total,
            am.amount_residual,
            am.invoice_date_due,
            CURRENT_DATE - am.invoice_date_due::date as days_overdue,
            rp.name as partner_name,
            rc.symbol as currency_symbol
        FROM account_move am
        LEFT JOIN res_partner rp ON am.partner_id = rp.id
        LEFT JOIN res_currency rc ON am.currency_id = rc.id
        WHERE am.state = 'posted'
            AND am.move_type IN ('out_invoice', 'out_refund')
            AND am.amount_residual > 0
            AND am.invoice_date_due < CURRENT_DATE - INTERVAL '%s days'
        ORDER BY days_overdue DESC
        LIMIT 100
        """
        return self.execute(query, (threshold_days,))


def get_audit_client() -> AuditPostgresClient:
    """Get audit PostgreSQL client."""
    return AuditPostgresClient()


def get_odoo_client(db_name: str) -> OdooPostgresClient:
    """Get Odoo PostgreSQL client for specific database."""
    return OdooPostgresClient(db_name)
