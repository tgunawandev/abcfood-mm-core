"""Pytest configuration and fixtures."""

import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient

# Set test environment variables before importing app
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("PG_HOST", "localhost")
os.environ.setdefault("PG_PASSWORD", "test")
os.environ.setdefault("ODOO_USER", "test")
os.environ.setdefault("ODOO_PASSWORD", "test")
os.environ.setdefault("CH_PASSWORD", "test")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DEBUG", "true")

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def api_key() -> str:
    """Get test API key."""
    return "test-api-key"


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    """Get authentication headers."""
    return {"X-API-Key": api_key}
