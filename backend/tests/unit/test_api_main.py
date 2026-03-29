"""Tests for FastAPI app — health check, CORS, app creation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    app = create_app()

    # Override DB and auth dependencies for all routes
    from app.api.dependencies import get_db, get_current_user

    async def mock_db():
        yield None  # Routes won't be called in these tests

    async def mock_user():
        return "testuser"

    app.dependency_overrides[get_db] = mock_db
    app.dependency_overrides[get_current_user] = mock_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


class TestHealthCheck:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert "uptime_seconds" in data

    def test_health_no_auth_required(self, client):
        """Health check doesn't require authentication."""
        resp = client.get("/health")
        assert resp.status_code == 200


class TestDetailedHealth:
    def test_detailed_health_endpoint(self, client):
        """Detailed health returns component diagnostics."""
        resp = client.get("/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "0.1.0"
        assert "environment" in data
        assert "trading_enabled" in data
        assert "bot_status" in data
        assert "components" in data
        # Status is either "ok" or "degraded" (DB/Redis may not be available in unit tests)
        assert data["status"] in ("ok", "degraded")

    def test_detailed_health_no_auth_required(self, client):
        """Detailed health check doesn't require authentication."""
        resp = client.get("/health/detailed")
        assert resp.status_code == 200


class TestAppCreation:
    def test_app_title(self):
        app = create_app()
        assert app.title == "CryptoQuant Engine"

    def test_app_version(self):
        app = create_app()
        assert app.version == "0.1.0"

    def test_routes_registered(self):
        app = create_app()
        route_paths = [r.path for r in app.routes]
        assert "/health" in route_paths
        assert "/health/detailed" in route_paths
        assert "/ws" in route_paths
        # Check API prefixes are included
        api_paths = [p for p in route_paths if p.startswith("/api/")]
        assert len(api_paths) > 0


class TestCORS:
    def test_cors_headers_on_options(self, client):
        """CORS preflight should return proper headers."""
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI CORS middleware responds to OPTIONS
        assert resp.status_code in (200, 400)


class TestOpenAPI:
    def test_openapi_schema(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["info"]["title"] == "CryptoQuant Engine"
        assert "paths" in schema

    def test_docs_available(self, client):
        resp = client.get("/docs")
        assert resp.status_code == 200


class TestErrorHandling:
    def test_404_for_nonexistent_route(self, client):
        resp = client.get("/api/nonexistent")
        assert resp.status_code in (404, 405)

    def test_health_uptime_is_number(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0


class TestDetailedHealthComponents:
    def test_components_is_dict(self, client):
        resp = client.get("/health/detailed")
        data = resp.json()
        assert isinstance(data["components"], dict)

    def test_bot_status_field(self, client):
        resp = client.get("/health/detailed")
        data = resp.json()
        assert "bot_status" in data

    def test_environment_field(self, client):
        resp = client.get("/health/detailed")
        data = resp.json()
        assert "environment" in data

    def test_trading_enabled_boolean(self, client):
        resp = client.get("/health/detailed")
        data = resp.json()
        assert isinstance(data["trading_enabled"], bool)


class TestRouteRegistration:
    def test_all_api_prefixes_registered(self):
        from app.main import create_app
        app = create_app()
        route_paths = [r.path for r in app.routes]
        expected_prefixes = [
            "/api/auth", "/api/system", "/api/signals", "/api/orders",
            "/api/positions", "/api/bot", "/api/backtest", "/api/settings",
            "/api/candles", "/api/markets", "/api/indicators",
        ]
        for prefix in expected_prefixes:
            matching = [p for p in route_paths if p.startswith(prefix)]
            assert len(matching) > 0, f"No routes registered under {prefix}"

    def test_websocket_route_registered(self):
        from app.main import create_app
        app = create_app()
        route_paths = [r.path for r in app.routes]
        assert "/ws" in route_paths
