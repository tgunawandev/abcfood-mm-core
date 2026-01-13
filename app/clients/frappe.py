"""Frappe 15 REST API client."""

import json
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import FrappeError
from app.core.logging import get_logger

logger = get_logger(__name__)


class FrappeClient:
    """Frappe 15 REST API client.

    Uses token-based authentication with API key and secret.
    All operations use async httpx for non-blocking I/O.
    """

    def __init__(self, site: str | None = None, settings: Settings | None = None) -> None:
        """Initialize Frappe client.

        Args:
            site: Frappe site domain (e.g., erp.abcfood.app)
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()
        self.site = site or self.settings.frappe_site
        self.base_url = f"https://{self.site}"
        self._client: httpx.AsyncClient | None = None

        logger.debug("frappe_client_initialized", site=self.site)

    @property
    def _auth_header(self) -> dict[str, str]:
        """Get authorization header for Frappe API."""
        if not self.settings.frappe_api_key or not self.settings.frappe_api_secret:
            raise FrappeError("Frappe API credentials not configured")
        token = f"{self.settings.frappe_api_key}:{self.settings.frappe_api_secret}"
        return {"Authorization": f"token {token}"}

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    **self._auth_header,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request to Frappe.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data

        Returns:
            Response data as dict

        Raises:
            FrappeError: If request fails
        """
        client = await self._get_client()

        try:
            response = await client.request(
                method=method,
                url=endpoint,
                params=params,
                json=data,
            )

            if response.status_code == 404:
                raise FrappeError(
                    f"Resource not found: {endpoint}",
                    {"status_code": 404, "endpoint": endpoint},
                )

            if response.status_code == 403:
                raise FrappeError(
                    "Permission denied",
                    {"status_code": 403, "endpoint": endpoint},
                )

            if response.status_code >= 400:
                error_detail = response.text
                try:
                    error_json = response.json()
                    if "exc" in error_json:
                        error_detail = error_json.get("exc", error_detail)
                    elif "message" in error_json:
                        error_detail = error_json.get("message", error_detail)
                except json.JSONDecodeError:
                    pass

                raise FrappeError(
                    f"Frappe API error: {error_detail}",
                    {"status_code": response.status_code, "endpoint": endpoint},
                )

            return response.json()

        except httpx.HTTPError as e:
            logger.error("frappe_request_failed", endpoint=endpoint, error=str(e))
            raise FrappeError(f"HTTP error: {e}") from e

    # =========================================================================
    # Generic CRUD Operations
    # =========================================================================

    async def get_doc(
        self,
        doctype: str,
        name: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get a single document.

        Args:
            doctype: Document type (e.g., "Sales Order", "Customer")
            name: Document name/ID
            fields: Optional list of fields to return

        Returns:
            Document data

        Raises:
            FrappeError: If document not found or request fails
        """
        endpoint = f"/api/resource/{doctype}/{name}"
        params = {}
        if fields:
            params["fields"] = json.dumps(fields)

        logger.debug("frappe_get_doc", doctype=doctype, name=name)
        result = await self._request("GET", endpoint, params=params)
        return result.get("data", result)

    async def get_list(
        self,
        doctype: str,
        filters: dict[str, Any] | list[list[str]] | None = None,
        fields: list[str] | None = None,
        order_by: str | None = None,
        limit_start: int = 0,
        limit_page_length: int = 20,
    ) -> list[dict[str, Any]]:
        """Get a list of documents.

        Args:
            doctype: Document type
            filters: Filter conditions (dict or list of lists)
            fields: Fields to return
            order_by: Sort order (e.g., "creation desc")
            limit_start: Offset for pagination
            limit_page_length: Number of records to return

        Returns:
            List of documents
        """
        endpoint = f"/api/resource/{doctype}"
        params: dict[str, Any] = {
            "limit_start": limit_start,
            "limit_page_length": limit_page_length,
        }

        if filters:
            params["filters"] = json.dumps(filters)
        if fields:
            params["fields"] = json.dumps(fields)
        if order_by:
            params["order_by"] = order_by

        logger.debug("frappe_get_list", doctype=doctype, filters=filters)
        result = await self._request("GET", endpoint, params=params)
        return result.get("data", [])

    async def create_doc(
        self,
        doctype: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new document.

        Args:
            doctype: Document type
            data: Document data

        Returns:
            Created document
        """
        endpoint = f"/api/resource/{doctype}"
        logger.info("frappe_create_doc", doctype=doctype)
        result = await self._request("POST", endpoint, data=data)
        return result.get("data", result)

    async def update_doc(
        self,
        doctype: str,
        name: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing document.

        Args:
            doctype: Document type
            name: Document name
            data: Fields to update

        Returns:
            Updated document
        """
        endpoint = f"/api/resource/{doctype}/{name}"
        logger.info("frappe_update_doc", doctype=doctype, name=name)
        result = await self._request("PUT", endpoint, data=data)
        return result.get("data", result)

    async def delete_doc(
        self,
        doctype: str,
        name: str,
    ) -> dict[str, Any]:
        """Delete a document.

        Args:
            doctype: Document type
            name: Document name

        Returns:
            Deletion response
        """
        endpoint = f"/api/resource/{doctype}/{name}"
        logger.info("frappe_delete_doc", doctype=doctype, name=name)
        return await self._request("DELETE", endpoint)

    async def call_method(
        self,
        method: str,
        args: dict[str, Any] | None = None,
    ) -> Any:
        """Call a Frappe whitelisted method.

        Args:
            method: Full method path (e.g., "frappe.client.get_count")
            args: Method arguments

        Returns:
            Method result
        """
        endpoint = f"/api/method/{method}"
        logger.debug("frappe_call_method", method=method)
        result = await self._request("POST", endpoint, data=args)
        return result.get("message", result)

    # =========================================================================
    # CRM Operations
    # =========================================================================

    async def get_crm_leads(
        self,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get CRM leads.

        Args:
            status: Filter by status (Open, Replied, etc.)
            limit: Number of records

        Returns:
            List of leads
        """
        filters: dict[str, Any] = {}
        if status:
            filters["status"] = status

        return await self.get_list(
            doctype="Lead",
            filters=filters if filters else None,
            fields=["name", "lead_name", "company_name", "status", "source", "creation"],
            order_by="creation desc",
            limit_page_length=limit,
        )

    async def get_customer(self, customer_name: str) -> dict[str, Any]:
        """Get customer details.

        Args:
            customer_name: Customer name/ID

        Returns:
            Customer data
        """
        return await self.get_doc(
            doctype="Customer",
            name=customer_name,
            fields=[
                "name",
                "customer_name",
                "customer_group",
                "territory",
                "customer_type",
                "default_currency",
            ],
        )

    async def search_customers(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search customers by name.

        Args:
            query: Search query
            limit: Number of results

        Returns:
            List of matching customers
        """
        filters = [["customer_name", "like", f"%{query}%"]]
        return await self.get_list(
            doctype="Customer",
            filters=filters,
            fields=["name", "customer_name", "customer_group", "territory"],
            limit_page_length=limit,
        )

    # =========================================================================
    # Sales Operations
    # =========================================================================

    async def get_sales_order(self, order_name: str) -> dict[str, Any]:
        """Get sales order with line items.

        Args:
            order_name: Sales order name (e.g., SAL-ORD-00001)

        Returns:
            Sales order with items
        """
        return await self.get_doc(
            doctype="Sales Order",
            name=order_name,
        )

    async def get_sales_orders(
        self,
        status: str | None = None,
        customer: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get list of sales orders.

        Args:
            status: Filter by status (Draft, To Deliver and Bill, etc.)
            customer: Filter by customer
            limit: Number of records

        Returns:
            List of sales orders
        """
        filters: dict[str, Any] = {"docstatus": ["!=", 2]}  # Exclude cancelled
        if status:
            filters["status"] = status
        if customer:
            filters["customer"] = customer

        return await self.get_list(
            doctype="Sales Order",
            filters=filters if filters else None,
            fields=[
                "name",
                "customer",
                "transaction_date",
                "grand_total",
                "status",
                "delivery_status",
            ],
            order_by="transaction_date desc",
            limit_page_length=limit,
        )

    async def get_sales_invoice(self, invoice_name: str) -> dict[str, Any]:
        """Get sales invoice.

        Args:
            invoice_name: Invoice name

        Returns:
            Sales invoice data
        """
        return await self.get_doc(
            doctype="Sales Invoice",
            name=invoice_name,
        )

    async def get_sales_invoices(
        self,
        status: str | None = None,
        customer: str | None = None,
        is_return: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get list of sales invoices.

        Args:
            status: Filter by status
            customer: Filter by customer
            is_return: Filter by return invoices
            limit: Number of records

        Returns:
            List of sales invoices
        """
        filters: dict[str, Any] = {
            "docstatus": 1,  # Only submitted
            "is_return": 1 if is_return else 0,
        }
        if status:
            filters["status"] = status
        if customer:
            filters["customer"] = customer

        return await self.get_list(
            doctype="Sales Invoice",
            filters=filters,
            fields=[
                "name",
                "customer",
                "posting_date",
                "grand_total",
                "outstanding_amount",
                "status",
            ],
            order_by="posting_date desc",
            limit_page_length=limit,
        )

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def get_count(
        self,
        doctype: str,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Get count of documents.

        Args:
            doctype: Document type
            filters: Filter conditions

        Returns:
            Count of matching documents
        """
        result = await self.call_method(
            "frappe.client.get_count",
            {"doctype": doctype, "filters": filters},
        )
        return int(result) if result else 0

    async def test_connection(self) -> bool:
        """Test connection to Frappe.

        Returns:
            True if connection successful
        """
        try:
            await self.call_method("frappe.ping")
            logger.info("frappe_connection_ok", site=self.site)
            return True
        except FrappeError as e:
            logger.error("frappe_connection_failed", site=self.site, error=str(e))
            return False


def get_frappe_client(settings: Settings | None = None) -> FrappeClient:
    """Get Frappe client instance."""
    return FrappeClient(settings=settings)
