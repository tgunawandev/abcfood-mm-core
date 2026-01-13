"""Metabase URL generation and API client."""

import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import Settings, get_settings
from app.core.exceptions import MetabaseError
from app.core.logging import get_logger

logger = get_logger(__name__)


class MetabaseClient:
    """Metabase client for URL generation and API access.

    Supports:
    - Public dashboard/question URLs
    - Signed embedded URLs (JWT-based)
    - API access for dashboard search/listing
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize Metabase client.

        Args:
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()
        self.domain = self.settings.mb_domain
        self.base_url = f"https://{self.domain}"
        self._session_token: str | None = self.settings.mb_session_token
        self._client: httpx.AsyncClient | None = None

        logger.debug("metabase_client_initialized", domain=self.domain)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self._session_token:
                headers["X-Metabase-Session"] = self._session_token
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # URL Generation (No API required)
    # =========================================================================

    def get_dashboard_url(
        self,
        dashboard_id: int | str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Generate public dashboard URL.

        Args:
            dashboard_id: Dashboard ID or slug
            params: Optional filter parameters

        Returns:
            Dashboard URL
        """
        url = f"{self.base_url}/dashboard/{dashboard_id}"
        if params:
            url += "?" + urlencode(params)
        return url

    def get_question_url(
        self,
        question_id: int | str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Generate public question URL.

        Args:
            question_id: Question ID
            params: Optional filter parameters

        Returns:
            Question URL
        """
        url = f"{self.base_url}/question/{question_id}"
        if params:
            url += "?" + urlencode(params)
        return url

    def get_public_dashboard_url(
        self,
        uuid: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Generate public sharing URL for dashboard.

        Args:
            uuid: Public sharing UUID
            params: Optional filter parameters

        Returns:
            Public dashboard URL
        """
        url = f"{self.base_url}/public/dashboard/{uuid}"
        if params:
            url += "?" + urlencode(params)
        return url

    def get_public_question_url(
        self,
        uuid: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Generate public sharing URL for question.

        Args:
            uuid: Public sharing UUID
            params: Optional filter parameters

        Returns:
            Public question URL
        """
        url = f"{self.base_url}/public/question/{uuid}"
        if params:
            url += "?" + urlencode(params)
        return url

    # =========================================================================
    # Signed Embedding URLs
    # =========================================================================

    def get_embedded_dashboard_url(
        self,
        dashboard_id: int,
        params: dict[str, Any] | None = None,
        expires_in: int = 600,
    ) -> str:
        """Generate signed embedded dashboard URL.

        Requires METABASE_EMBEDDING_SECRET to be configured.

        Args:
            dashboard_id: Dashboard ID
            params: Filter parameters to lock
            expires_in: Token expiry in seconds (default 10 minutes)

        Returns:
            Signed embedded URL

        Raises:
            MetabaseError: If embedding secret not configured
        """
        if not self.settings.mb_embedding_secret:
            raise MetabaseError("Metabase embedding secret not configured")

        payload = {
            "resource": {"dashboard": dashboard_id},
            "params": params or {},
            "exp": int(time.time()) + expires_in,
        }

        token = jwt.encode(
            payload,
            self.settings.mb_embedding_secret,
            algorithm="HS256",
        )

        return f"{self.base_url}/embed/dashboard/{token}"

    def get_embedded_question_url(
        self,
        question_id: int,
        params: dict[str, Any] | None = None,
        expires_in: int = 600,
    ) -> str:
        """Generate signed embedded question URL.

        Requires METABASE_EMBEDDING_SECRET to be configured.

        Args:
            question_id: Question ID
            params: Filter parameters to lock
            expires_in: Token expiry in seconds (default 10 minutes)

        Returns:
            Signed embedded URL

        Raises:
            MetabaseError: If embedding secret not configured
        """
        if not self.settings.mb_embedding_secret:
            raise MetabaseError("Metabase embedding secret not configured")

        payload = {
            "resource": {"question": question_id},
            "params": params or {},
            "exp": int(time.time()) + expires_in,
        }

        token = jwt.encode(
            payload,
            self.settings.mb_embedding_secret,
            algorithm="HS256",
        )

        return f"{self.base_url}/embed/question/{token}"

    # =========================================================================
    # API Operations (Requires session token)
    # =========================================================================

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        """Make API request to Metabase.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request body

        Returns:
            Response data

        Raises:
            MetabaseError: If request fails or session not configured
        """
        if not self._session_token:
            raise MetabaseError("Metabase session token not configured")

        client = await self._get_client()

        try:
            response = await client.request(
                method=method,
                url=endpoint,
                params=params,
                json=data,
            )

            if response.status_code == 401:
                raise MetabaseError("Metabase session expired or invalid")

            if response.status_code >= 400:
                raise MetabaseError(
                    f"Metabase API error: {response.text}",
                    {"status_code": response.status_code},
                )

            return response.json()

        except httpx.HTTPError as e:
            logger.error("metabase_request_failed", endpoint=endpoint, error=str(e))
            raise MetabaseError(f"HTTP error: {e}") from e

    async def get_dashboard(self, dashboard_id: int) -> dict[str, Any]:
        """Get dashboard details.

        Args:
            dashboard_id: Dashboard ID

        Returns:
            Dashboard data
        """
        return await self._api_request("GET", f"/api/dashboard/{dashboard_id}")

    async def get_question(self, question_id: int) -> dict[str, Any]:
        """Get question/card details.

        Args:
            question_id: Question ID

        Returns:
            Question data
        """
        return await self._api_request("GET", f"/api/card/{question_id}")

    async def list_dashboards(
        self,
        collection_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """List dashboards.

        Args:
            collection_id: Optional collection to filter

        Returns:
            List of dashboards
        """
        params = {}
        if collection_id:
            params["collection_id"] = collection_id

        result = await self._api_request("GET", "/api/dashboard", params=params)
        return result if isinstance(result, list) else []

    async def search_dashboards(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search dashboards by name.

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of matching dashboards
        """
        params = {
            "q": query,
            "models": "dashboard",
            "limit": limit,
        }
        result = await self._api_request("GET", "/api/search", params=params)
        return result.get("data", []) if isinstance(result, dict) else []

    async def search_questions(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search questions/cards by name.

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of matching questions
        """
        params = {
            "q": query,
            "models": "card",
            "limit": limit,
        }
        result = await self._api_request("GET", "/api/search", params=params)
        return result.get("data", []) if isinstance(result, dict) else []

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def test_connection(self) -> bool:
        """Test connection to Metabase API.

        Returns:
            True if connection successful
        """
        if not self._session_token:
            logger.warning("metabase_no_session_token")
            return False

        try:
            await self._api_request("GET", "/api/user/current")
            logger.info("metabase_connection_ok", domain=self.domain)
            return True
        except MetabaseError as e:
            logger.error("metabase_connection_failed", domain=self.domain, error=str(e))
            return False


# Dashboard name to ID mapping (configure based on your Metabase setup)
DASHBOARD_MAPPING: dict[str, int] = {
    "sales": 1,
    "finance": 2,
    "operations": 3,
    "inventory": 4,
    "customers": 5,
}


def get_dashboard_id(identifier: str) -> int | None:
    """Get dashboard ID from name or numeric ID.

    Args:
        identifier: Dashboard name or ID

    Returns:
        Dashboard ID or None if not found
    """
    # If numeric, return as-is
    if identifier.isdigit():
        return int(identifier)

    # Look up by name
    return DASHBOARD_MAPPING.get(identifier.lower())


def get_metabase_client(settings: Settings | None = None) -> MetabaseClient:
    """Get Metabase client instance."""
    return MetabaseClient(settings=settings)
