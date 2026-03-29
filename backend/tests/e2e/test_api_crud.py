"""E2E tests for CRUD API endpoints."""

import pytest
import httpx


pytestmark = pytest.mark.asyncio


# --- Signals ---


async def test_signals_list(client: httpx.AsyncClient):
    """GET /api/signals returns 200 with paginated response."""
    resp = await client.get("/api/signals")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    assert "total" in body


async def test_signals_history(client: httpx.AsyncClient):
    """GET /api/signals/history returns 200 with paginated response."""
    resp = await client.get("/api/signals/history")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)


# --- Orders ---


async def test_orders_list(client: httpx.AsyncClient):
    """GET /api/orders returns 200 with paginated response."""
    resp = await client.get("/api/orders")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)


# --- Positions ---


async def test_positions_list(client: httpx.AsyncClient):
    """GET /api/positions returns 200 with paginated response."""
    resp = await client.get("/api/positions")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)


# --- Bot ---


async def test_bot_status(client: httpx.AsyncClient):
    """GET /api/bot/status returns 200 with expected fields."""
    resp = await client.get("/api/bot/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "paper_mode" in body
    assert "active_strategies" in body


async def test_bot_stop(client: httpx.AsyncClient):
    """POST /api/bot/stop returns 200."""
    resp = await client.post("/api/bot/stop")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "STOPPED"


async def test_bot_start(client: httpx.AsyncClient):
    """POST /api/bot/start returns 200."""
    # Ensure bot is stopped first
    await client.post("/api/bot/stop")
    resp = await client.post("/api/bot/start")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "RUNNING"
    # Clean up: stop the bot
    await client.post("/api/bot/stop")


async def test_bot_start_then_stop(client: httpx.AsyncClient):
    """Start and stop the bot in sequence."""
    await client.post("/api/bot/stop")
    start_resp = await client.post("/api/bot/start")
    assert start_resp.status_code == 200

    stop_resp = await client.post("/api/bot/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "STOPPED"


# --- Settings ---


async def test_settings_get(client: httpx.AsyncClient):
    """GET /api/settings returns 200 with risk_params."""
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert "risk_params" in body


async def test_settings_update_risk(client: httpx.AsyncClient):
    """PUT /api/settings/risk updates risk parameters."""
    payload = {"default_risk_pct": 0.03, "max_positions": 8}
    resp = await client.put("/api/settings/risk", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert "risk_params" in body
    assert body["risk_params"]["default_risk_pct"] == 0.03
    assert body["risk_params"]["max_positions"] == 8

    # Restore defaults
    restore = {"default_risk_pct": 0.02, "max_positions": 5}
    await client.put("/api/settings/risk", json=restore)


# --- Backtest ---


async def test_backtest_history(client: httpx.AsyncClient):
    """GET /api/backtest/history returns 200 with paginated response."""
    resp = await client.get("/api/backtest/history")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)
