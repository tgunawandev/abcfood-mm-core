"""Metrics service for ChatOps query endpoints."""

from datetime import datetime
from typing import Any

from app.clients.clickhouse import get_clickhouse_client
from app.clients.postgres import get_odoo_client
from app.core.logging import get_logger
from app.models.enums import OdooDatabase
from app.models.schemas import (
    CustomerRisk,
    OverdueInvoice,
    OverdueInvoicesResponse,
    SalesSummary,
)
from app.utils.time import days_between, utc_now

logger = get_logger(__name__)


class MetricsService:
    """Service for metrics and ChatOps queries.

    Uses ClickHouse for analytics queries (read-only).
    Falls back to PostgreSQL for direct Odoo data if needed.
    """

    def __init__(self, db_name: str) -> None:
        """Initialize metrics service.

        Args:
            db_name: Odoo database name
        """
        self.db_name = db_name
        self._clickhouse = get_clickhouse_client()
        self._postgres = get_odoo_client(db_name)

    def get_sales_today(self) -> SalesSummary:
        """Get today's sales summary.

        Returns:
            Sales summary for today
        """
        try:
            data = self._clickhouse.get_sales_today(self.db_name)
            comparison = self._clickhouse.get_sales_comparison(
                self.db_name,
                data.get("total_revenue", 0),
                "yesterday",
            )

            return SalesSummary(
                db=OdooDatabase(self.db_name),
                period="today",
                total_revenue=float(data.get("total_revenue", 0)),
                order_count=int(data.get("order_count", 0)),
                avg_order_value=float(data.get("avg_order_value", 0)),
                currency="IDR",
                comparison_previous=comparison,
            )
        except Exception as e:
            logger.error("sales_today_error", db=self.db_name, error=str(e))
            # Return empty summary on error
            return SalesSummary(
                db=OdooDatabase(self.db_name),
                period="today",
                total_revenue=0,
                order_count=0,
                avg_order_value=0,
            )

    def get_sales_mtd(self) -> SalesSummary:
        """Get month-to-date sales summary.

        Returns:
            Sales summary for current month
        """
        try:
            data = self._clickhouse.get_sales_mtd(self.db_name)

            return SalesSummary(
                db=OdooDatabase(self.db_name),
                period="mtd",
                total_revenue=float(data.get("total_revenue", 0)),
                order_count=int(data.get("order_count", 0)),
                avg_order_value=float(data.get("avg_order_value", 0)),
                currency="IDR",
            )
        except Exception as e:
            logger.error("sales_mtd_error", db=self.db_name, error=str(e))
            return SalesSummary(
                db=OdooDatabase(self.db_name),
                period="mtd",
                total_revenue=0,
                order_count=0,
                avg_order_value=0,
            )

    def get_overdue_invoices(
        self,
        threshold_days: int = 0,
    ) -> OverdueInvoicesResponse:
        """Get overdue invoices.

        Args:
            threshold_days: Minimum days overdue to include

        Returns:
            List of overdue invoices
        """
        try:
            # Use PostgreSQL for real-time data
            records = self._postgres.get_overdue_invoices(threshold_days)

            invoices = []
            total_amount = 0.0

            for record in records:
                amount_residual = float(record.get("amount_residual", 0))
                total_amount += amount_residual

                # Parse due date
                due_date = record.get("invoice_date_due")
                if isinstance(due_date, str):
                    due_date = datetime.fromisoformat(due_date)

                invoices.append(
                    OverdueInvoice(
                        id=record["id"],
                        name=record.get("name", ""),
                        partner_name=record.get("partner_name", "Unknown"),
                        amount_total=float(record.get("amount_total", 0)),
                        amount_residual=amount_residual,
                        date_due=due_date or utc_now(),
                        days_overdue=int(record.get("days_overdue", 0)),
                        currency=record.get("currency_symbol", "IDR") or "IDR",
                    )
                )

            return OverdueInvoicesResponse(
                db=OdooDatabase(self.db_name),
                count=len(invoices),
                total_overdue_amount=total_amount,
                invoices=invoices,
            )

        except Exception as e:
            logger.error("overdue_invoices_error", db=self.db_name, error=str(e))
            return OverdueInvoicesResponse(
                db=OdooDatabase(self.db_name),
                count=0,
                total_overdue_amount=0,
                invoices=[],
            )

    def get_customer_risk(self, customer_id: int) -> CustomerRisk | None:
        """Get customer risk snapshot.

        Args:
            customer_id: Customer ID

        Returns:
            Customer risk data or None
        """
        try:
            data = self._clickhouse.get_customer_risk(self.db_name, customer_id)
            if not data:
                return None

            return CustomerRisk(
                db=OdooDatabase(self.db_name),
                customer_id=customer_id,
                customer_name=data.get("customer_name", "Unknown"),
                total_receivable=float(data.get("total_receivable", 0)),
                total_overdue=float(data.get("total_overdue", 0)),
                overdue_count=int(data.get("overdue_count", 0)),
                avg_days_to_pay=0.0,  # Would need additional query
                risk_score=data.get("risk_score", "unknown"),
            )

        except Exception as e:
            logger.error(
                "customer_risk_error",
                db=self.db_name,
                customer_id=customer_id,
                error=str(e),
            )
            return None


def get_metrics_service(db_name: str) -> MetricsService:
    """Get metrics service instance for specific database."""
    return MetricsService(db_name)
