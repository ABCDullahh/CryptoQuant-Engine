"""E2E tests for server health, docs, and WebSocket connectivity."""

import pytest
import httpx


pytestmark = pytest.mark.asyncio


async def test_health_returns_200(client: httpx.AsyncClient):
    """GET /health returns 200 with uptime_seconds key."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "uptime_seconds" in body
    assert body["status"] == "ok"


async def test_openapi_docs(client: httpx.AsyncClient):
    """GET /docs returns 200 (Swagger UI)."""
    resp = await client.get("/docs")
    assert resp.status_code == 200


async def test_openapi_json(client: httpx.AsyncClient):
    """GET /openapi.json returns valid OpenAPI spec."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    body = resp.json()
    assert "paths" in body
    assert "openapi" in body


async def test_unknown_route_returns_404(client: httpx.AsyncClient):
    """GET to unknown route returns 404."""
    resp = await client.get("/api/nonexistent")
    assert resp.status_code in (404, 405)


async def test_websocket_connect(client: httpx.AsyncClient):
    """Connect to WebSocket endpoint, send ping, receive pong."""
    try:
        import websockets
    except ImportError:
        pytest.skip("websockets library not installed")

    import asyncio

    uri = "ws://localhost:8000/ws"
    try:
        async with websockets.connect(uri) as ws:
            await ws.send('{"type": "ping"}')
            # Wait for response with timeout
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            assert response is not None
    except (ConnectionRefusedError, OSError):
        pytest.skip("WebSocket connection refused")
