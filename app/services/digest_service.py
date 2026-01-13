"""Digest service for generating daily summaries (Live Business Pulse)."""

from typing import Any

from app.clients.clickhouse import get_clickhouse_client
from app.clients.postgres import get_odoo_client
from app.core.logging import get_logger
from app.models.enums import AlertType, DigestType, OdooDatabase
from app.models.schemas import DigestAlert, DigestResponse
from app.utils.time import format_date, local_now, utc_now

logger = get_logger(__name__)


class DigestService:
    """Service for generating digest summaries.

    Digests are structured data meant to be formatted by n8n
    and posted to Mattermost channels.
    """

    def __init__(self, db_name: str) -> None:
        """Initialize digest service.

        Args:
            db_name: Odoo database name
        """
        self.db_name = db_name
        self._clickhouse = get_clickhouse_client()
        self._postgres = get_odoo_client(db_name)

    def get_sales_daily(self) -> DigestResponse:
        """Generate daily sales digest.

        Returns:
            Sales digest for n8n to format
        """
        alerts: list[DigestAlert] = []

        try:
            # Get today's sales
            today_data = self._clickhouse.get_sales_today(self.db_name)
            total_revenue = float(today_data.get("total_revenue", 0))
            order_count = int(today_data.get("order_count", 0))
            avg_order_value = float(today_data.get("avg_order_value", 0))

            # Get comparison
            comparison = self._clickhouse.get_sales_comparison(
                self.db_name, total_revenue, "yesterday"
            )

            # Get top products
            top_products = self._clickhouse.get_top_products(
                self.db_name, limit=5, period="today"
            )

            # Generate alerts
            if order_count == 0:
                alerts.append(
                    DigestAlert(type=AlertType.WARNING, message="No orders today")
                )
            elif comparison and comparison.startswith("-") and len(comparison) > 3:
                # Significant drop
                alerts.append(
                    DigestAlert(
                        type=AlertType.WARNING,
                        message=f"Sales down {comparison} vs yesterday",
                    )
                )

            # Check for pending orders (from PostgreSQL)
            pending = self._get_pending_orders_count()
            if pending > 0:
                alerts.append(
                    DigestAlert(
                        type=AlertType.INFO,
                        message=f"{pending} orders pending confirmation",
                    )
                )

            metrics = {
                "total_revenue": total_revenue,
                "order_count": order_count,
                "avg_order_value": avg_order_value,
                "top_products": [
                    {
                        "product_code": p.get("product_code", ""),
                        "product_name": p.get("product_name", ""),
                        "quantity": p.get("quantity", 0),
                        "revenue": p.get("revenue", 0),
                    }
                    for p in top_products
                ],
                "comparison_yesterday": comparison,
            }

            return DigestResponse(
                digest_type=DigestType.SALES_DAILY,
                db=OdooDatabase(self.db_name),
                period=format_date(local_now()),
                generated_at=utc_now(),
                metrics=metrics,
                alerts=alerts,
            )

        except Exception as e:
            logger.error("sales_digest_error", db=self.db_name, error=str(e))
            return DigestResponse(
                digest_type=DigestType.SALES_DAILY,
                db=OdooDatabase(self.db_name),
                period=format_date(local_now()),
                generated_at=utc_now(),
                metrics={"error": str(e)},
                alerts=[
                    DigestAlert(
                        type=AlertType.CRITICAL,
                        message="Failed to generate sales digest",
                    )
                ],
            )

    def get_finance_daily(self) -> DigestResponse:
        """Generate daily finance digest.

        Returns:
            Finance digest for n8n to format
        """
        alerts: list[DigestAlert] = []

        try:
            # Get overdue invoices
            overdue_records = self._postgres.get_overdue_invoices(0)
            total_overdue = sum(
                float(r.get("amount_residual", 0)) for r in overdue_records
            )
            overdue_count = len(overdue_records)

            # Get severely overdue (>30 days)
            severe_overdue = [
                r for r in overdue_records if int(r.get("days_overdue", 0)) > 30
            ]

            # Generate alerts
            if overdue_count > 0:
                alerts.append(
                    DigestAlert(
                        type=AlertType.WARNING,
                        message=f"{overdue_count} invoices overdue (Rp {total_overdue:,.0f})",
                    )
                )

            if len(severe_overdue) > 0:
                severe_amount = sum(
                    float(r.get("amount_residual", 0)) for r in severe_overdue
                )
                alerts.append(
                    DigestAlert(
                        type=AlertType.CRITICAL,
                        message=f"{len(severe_overdue)} invoices >30 days overdue (Rp {severe_amount:,.0f})",
                    )
                )

            metrics = {
                "total_receivable": 0,  # Would need additional query
                "total_payable": 0,
                "overdue_receivable": total_overdue,
                "overdue_count": overdue_count,
                "severe_overdue_count": len(severe_overdue),
            }

            return DigestResponse(
                digest_type=DigestType.FINANCE_DAILY,
                db=OdooDatabase(self.db_name),
                period=format_date(local_now()),
                generated_at=utc_now(),
                metrics=metrics,
                alerts=alerts,
            )

        except Exception as e:
            logger.error("finance_digest_error", db=self.db_name, error=str(e))
            return DigestResponse(
                digest_type=DigestType.FINANCE_DAILY,
                db=OdooDatabase(self.db_name),
                period=format_date(local_now()),
                generated_at=utc_now(),
                metrics={"error": str(e)},
                alerts=[
                    DigestAlert(
                        type=AlertType.CRITICAL,
                        message="Failed to generate finance digest",
                    )
                ],
            )

    def get_ops_daily(self) -> DigestResponse:
        """Generate daily operations digest.

        Returns:
            Operations digest for n8n to format
        """
        alerts: list[DigestAlert] = []

        try:
            # Get pending orders count
            pending_orders = self._get_pending_orders_count()

            # Get pending deliveries count
            pending_deliveries = self._get_pending_deliveries_count()

            # Generate alerts
            if pending_orders > 10:
                alerts.append(
                    DigestAlert(
                        type=AlertType.WARNING,
                        message=f"{pending_orders} orders awaiting confirmation",
                    )
                )

            if pending_deliveries > 10:
                alerts.append(
                    DigestAlert(
                        type=AlertType.WARNING,
                        message=f"{pending_deliveries} deliveries pending",
                    )
                )

            metrics = {
                "pending_orders": pending_orders,
                "pending_deliveries": pending_deliveries,
                "low_stock_items": 0,  # Would need additional query
            }

            return DigestResponse(
                digest_type=DigestType.OPS_DAILY,
                db=OdooDatabase(self.db_name),
                period=format_date(local_now()),
                generated_at=utc_now(),
                metrics=metrics,
                alerts=alerts,
            )

        except Exception as e:
            logger.error("ops_digest_error", db=self.db_name, error=str(e))
            return DigestResponse(
                digest_type=DigestType.OPS_DAILY,
                db=OdooDatabase(self.db_name),
                period=format_date(local_now()),
                generated_at=utc_now(),
                metrics={"error": str(e)},
                alerts=[
                    DigestAlert(
                        type=AlertType.CRITICAL,
                        message="Failed to generate ops digest",
                    )
                ],
            )

    def _get_pending_orders_count(self) -> int:
        """Get count of pending orders."""
        try:
            result = self._postgres.execute_one(
                "SELECT count(*) as count FROM sale_order WHERE state = 'draft'"
            )
            return int(result["count"]) if result else 0
        except Exception:
            return 0

    def _get_pending_deliveries_count(self) -> int:
        """Get count of pending deliveries."""
        try:
            result = self._postgres.execute_one(
                "SELECT count(*) as count FROM stock_picking WHERE state IN ('confirmed', 'assigned')"
            )
            return int(result["count"]) if result else 0
        except Exception:
            return 0


def get_digest_service(db_name: str) -> DigestService:
    """Get digest service instance for specific database."""
    return DigestService(db_name)
