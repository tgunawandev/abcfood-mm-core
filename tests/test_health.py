"""Tests for health endpoints."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


def test_health_no_auth_required(client: TestClient) -> None:
    """Health check should not require authentication."""
    # No X-API-Key header
    response = client.get("/api/v1/health")
    assert response.status_code == 200
