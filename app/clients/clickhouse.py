"""ClickHouse client for analytics queries."""

from datetime import datetime
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.client import Client

from app.core.config import get_settings
from app.core.exceptions import ClickHouseError
from app.core.logging import get_logger

logger = get_logger(__name__)


class ClickHouseClient:
    """ClickHouse client for analytics queries.

    This client is READ-ONLY and should only be used for analytics.
    Audit logs are stored in PostgreSQL, not ClickHouse.
    """

    def __init__(self) -> None:
        """Initialize ClickHouse client."""
        self.settings = get_settings()
        self._client: Client | None = None

    def _get_client(self) -> Client:
        """Get or create ClickHouse client.

        Returns:
            ClickHouse client instance

        Raises:
            ClickHouseError: If connection fails
        """
        if self._client is None:
            try:
                self._client = clickhouse_connect.get_client(
                    host=self.settings.ch_host,
                    port=self.settings.ch_port,
                    username=self.settings.ch_user,
                    password=self.settings.ch_password,
                )
            except Exception as e:
                logger.error("clickhouse_connection_error", error=str(e))
                raise ClickHouseError(f"Failed to connect to ClickHouse: {e}") from e
        return self._client

    def close(self) -> None:
        """Close the client connection."""
        if self._client:
            self._client.close()
            self._client = None

    def query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a query and return results as list of dicts.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of result rows as dictionaries

        Raises:
            ClickHouseError: If query fails
        """
        try:
            client = self._get_client()
            result = client.query(query, parameters=params)
            columns = result.column_names
            return [dict(zip(columns, row)) for row in result.result_rows]
        except Exception as e:
            logger.error("clickhouse_query_error", query=query[:100], error=str(e))
            raise ClickHouseError(f"ClickHouse query failed: {e}") from e

    def query_one(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Execute a query and return single result.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Single result row or None
        """
        results = self.query(query, params)
        return results[0] if results else None

    def test_connection(self) -> bool:
        """Test ClickHouse connectivity.

        Returns:
            True if connection successful
        """
        try:
            client = self._get_client()
            client.ping()
            return True
        except Exception as e:
            logger.warning("clickhouse_test_failed", error=str(e))
            return False

    # =========================================================================
    # Sales Analytics Queries
    # =========================================================================

    def get_sales_today(self, db_name: str) -> dict[str, Any]:
        """Get today's sales summary.

        Args:
            db_name: Source database name

        Returns:
            Sales summary data
        """
        query = """
        SELECT
            count(*) as order_count,
            coalesce(sum(amount_total), 0) as total_revenue,
            coalesce(avg(amount_total), 0) as avg_order_value
        FROM {db}.sale_order
        WHERE toDate(date_order) = today()
            AND state IN ('sale', 'done')
        """.format(db=db_name)

        result = self.query_one(query)
        return result or {"order_count": 0, "total_revenue": 0, "avg_order_value": 0}

    def get_sales_mtd(self, db_name: str) -> dict[str, Any]:
        """Get month-to-date sales summary.

        Args:
            db_name: Source database name

        Returns:
            Sales summary data
        """
        query = """
        SELECT
            count(*) as order_count,
            coalesce(sum(amount_total), 0) as total_revenue,
            coalesce(avg(amount_total), 0) as avg_order_value
        FROM {db}.sale_order
        WHERE toStartOfMonth(date_order) = toStartOfMonth(today())
            AND state IN ('sale', 'done')
        """.format(db=db_name)

        result = self.query_one(query)
        return result or {"order_count": 0, "total_revenue": 0, "avg_order_value": 0}

    def get_sales_comparison(
        self, db_name: str, current: float, period: str = "yesterday"
    ) -> str:
        """Calculate sales comparison with previous period.

        Args:
            db_name: Source database name
            current: Current period total
            period: Comparison period

        Returns:
            Comparison string (e.g., "+12%")
        """
        if period == "yesterday":
            query = """
            SELECT coalesce(sum(amount_total), 0) as total
            FROM {db}.sale_order
            WHERE toDate(date_order) = today() - 1
                AND state IN ('sale', 'done')
            """.format(db=db_name)
        else:
            return "N/A"

        result = self.query_one(query)
        previous = result["total"] if result else 0

        if previous == 0:
            return "N/A" if current == 0 else "+∞"

        change = ((current - previous) / previous) * 100
        sign = "+" if change >= 0 else ""
        return f"{sign}{change:.0f}%"

    def get_top_products(
        self, db_name: str, limit: int = 5, period: str = "today"
    ) -> list[dict[str, Any]]:
        """Get top selling products.

        Args:
            db_name: Source database name
            limit: Number of products to return
            period: Time period (today, mtd)

        Returns:
            List of top products with quantities and revenue
        """
        date_filter = "toDate(so.date_order) = today()" if period == "today" else \
            "toStartOfMonth(so.date_order) = toStartOfMonth(today())"

        query = """
        SELECT
            sol.product_id,
            pp.default_code as product_code,
            pt.name as product_name,
            sum(sol.product_uom_qty) as quantity,
            sum(sol.price_subtotal) as revenue
        FROM {db}.sale_order_line sol
        JOIN {db}.sale_order so ON sol.order_id = so.id
        LEFT JOIN {db}.product_product pp ON sol.product_id = pp.id
        LEFT JOIN {db}.product_template pt ON pp.product_tmpl_id = pt.id
        WHERE {date_filter}
            AND so.state IN ('sale', 'done')
        GROUP BY sol.product_id, pp.default_code, pt.name
        ORDER BY revenue DESC
        LIMIT {limit}
        """.format(db=db_name, date_filter=date_filter, limit=limit)

        return self.query(query)

    # =========================================================================
    # Customer Analytics Queries
    # =========================================================================

    def get_customer_risk(self, db_name: str, customer_id: int) -> dict[str, Any] | None:
        """Get customer risk snapshot.

        Args:
            db_name: Source database name
            customer_id: Customer ID

        Returns:
            Customer risk data
        """
        query = """
        SELECT
            rp.id as customer_id,
            rp.name as customer_name,
            coalesce(sum(CASE WHEN am.amount_residual > 0 THEN am.amount_residual ELSE 0 END), 0) as total_receivable,
            coalesce(sum(CASE
                WHEN am.amount_residual > 0 AND am.invoice_date_due < today()
                THEN am.amount_residual ELSE 0 END), 0) as total_overdue,
            count(CASE WHEN am.amount_residual > 0 AND am.invoice_date_due < today() THEN 1 END) as overdue_count
        FROM {db}.res_partner rp
        LEFT JOIN {db}.account_move am ON am.partner_id = rp.id
            AND am.state = 'posted'
            AND am.move_type IN ('out_invoice', 'out_refund')
        WHERE rp.id = {{customer_id:Int32}}
        GROUP BY rp.id, rp.name
        """.format(db=db_name)

        result = self.query_one(query, {"customer_id": customer_id})

        if result:
            # Calculate risk score
            total_overdue = result.get("total_overdue", 0)
            overdue_count = result.get("overdue_count", 0)

            if total_overdue > 100000000 or overdue_count > 5:  # 100M IDR
                risk_score = "high"
            elif total_overdue > 50000000 or overdue_count > 2:  # 50M IDR
                risk_score = "medium"
            else:
                risk_score = "low"

            result["risk_score"] = risk_score

        return result


def get_clickhouse_client() -> ClickHouseClient:
    """Get ClickHouse client instance."""
    return ClickHouseClient()
