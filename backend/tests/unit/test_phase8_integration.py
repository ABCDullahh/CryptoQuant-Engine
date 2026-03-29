"""Phase 8 Integration Tests — API layer end-to-end with all phases."""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture
def full_client(api_client, seed_db):
    """Client with data across all model types."""
    signal_id = str(uuid4())
    order_id = str(uuid4())
    pos_id = str(uuid4())
    bt_id = str(uuid4())

    # Signal (Phase 3 output → Phase 8 API)
    seed_db(
        "INSERT INTO signals (id, symbol, direction, signal_grade, signal_strength, "
        "entry_price, stop_loss, sl_type, tp1_price, tp1_pct, leverage, position_size_qty, "
        "strategy_scores, market_context, status) "
        "VALUES (:id, 'BTC/USDT', 'LONG', 'A', 0.85, 43000.0, 42500.0, "
        "'ATR_BASED', 44000.0, 50, 3, 0.5, "
        "'{\"momentum\": 0.8, \"smc\": 0.9}', '{\"regime\": \"TRENDING_UP\"}', 'ACTIVE')",
        {"id": signal_id},
    )
    # Order (Phase 6 output)
    seed_db(
        "INSERT INTO orders (id, signal_id, symbol, side, order_type, price, "
        "quantity, filled_qty, status, avg_fill_price, fees) "
        "VALUES (:oid, :sid, 'BTC/USDT', 'BUY', 'MARKET', 43000.0, "
        "0.5, 0.5, 'FILLED', 43010.0, 0.47)",
        {"oid": order_id, "sid": signal_id},
    )
    # Position (Phase 6 output)
    seed_db(
        "INSERT INTO positions (id, signal_id, symbol, direction, entry_price, "
        "current_price, quantity, remaining_qty, leverage, stop_loss, tp1_price, "
        "unrealized_pnl, realized_pnl, total_fees, status) "
        "VALUES (:pid, :sid, 'BTC/USDT', 'LONG', 43010.0, 43500.0, "
        "0.5, 0.5, 3, 42500.0, 44000.0, 245.0, 0, 0, 'OPEN')",
        {"pid": pos_id, "sid": signal_id},
    )
    # Backtest run (Phase 7 output)
    seed_db(
        "INSERT INTO backtest_runs (id, strategy_name, symbol, timeframe, "
        "start_date, end_date, initial_capital, final_capital, total_return, "
        "sharpe_ratio, max_drawdown, win_rate, total_trades) "
        "VALUES (:id, 'momentum', 'BTC/USDT', '1h', '2024-01-01', '2024-06-01', "
        "10000.0, 11500.0, 0.15, 1.5, 0.08, 0.62, 45)",
        {"id": bt_id},
    )
    return api_client, signal_id, order_id, pos_id, bt_id


class TestEndToEnd:
    def test_signal_to_order_flow(self, full_client):
        """Signal → Execute Order → Check position."""
        c, signal_id, _, _, _ = full_client

        # 1. Get signal
        resp = c.get(f"/api/signals/{signal_id}")
        assert resp.status_code == 200
        assert resp.json()["signal_grade"] == "A"

        # 2. Execute order
        resp = c.post("/api/orders/execute", json={
            "signal_id": signal_id, "mode": "ONE_CLICK"
        })
        assert resp.status_code == 201

        # 3. Check positions
        resp = c.get("/api/positions")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_full_api_surface(self, full_client):
        """Verify all major endpoints are accessible."""
        c, *_ = full_client
        endpoints = [
            ("GET", "/health"),
            ("GET", "/api/signals"),
            ("GET", "/api/orders"),
            ("GET", "/api/positions"),
            ("GET", "/api/bot/status"),
            ("GET", "/api/bot/performance"),
            ("GET", "/api/backtest/history"),
            ("GET", "/api/settings"),
        ]
        for method, path in endpoints:
            resp = c.request(method, path)
            assert resp.status_code == 200, f"{method} {path} failed: {resp.status_code}"


class TestPhaseConnections:
    def test_phase1_models_in_api(self, full_client):
        """Phase 1 Pydantic models properly serialized through API."""
        c, signal_id, *_ = full_client
        resp = c.get(f"/api/signals/{signal_id}")
        data = resp.json()
        assert "strategy_scores" in data
        assert "market_context" in data

    def test_phase6_execution_in_api(self, full_client):
        """Phase 6 order/position data accessible via API."""
        c, _, order_id, pos_id, _ = full_client

        resp = c.get(f"/api/orders/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "FILLED"

        resp = c.get(f"/api/positions/{pos_id}")
        assert resp.status_code == 200
        assert resp.json()["unrealized_pnl"] == 245.0

    def test_phase7_backtest_in_api(self, full_client):
        """Phase 7 backtest results accessible via API."""
        c, *_ = full_client
        resp = c.get("/api/backtest/history")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        assert items[0]["total_trades"] == 45

    def test_bot_lifecycle(self, full_client):
        """Bot management lifecycle through API."""
        c, *_ = full_client
        resp = c.post("/api/bot/start")
        assert resp.json()["status"] == "RUNNING"

        resp = c.get("/api/bot/status")
        assert resp.json()["status"] == "RUNNING"

        resp = c.post("/api/bot/stop")
        assert resp.json()["status"] == "STOPPED"

    def test_settings_round_trip(self, full_client):
        """Settings update and retrieve cycle."""
        c, *_ = full_client
        c.put("/api/settings/risk", json={"default_risk_pct": 0.025})
        resp = c.get("/api/settings")
        assert resp.json()["risk_params"]["default_risk_pct"] == 0.025


class TestImportsClean:
    def test_all_api_imports(self):
        """All API modules importable."""
        from app.api.auth import create_access_token, decode_access_token
        from app.api.dependencies import get_current_user, get_db, optional_auth
        from app.api.schemas import (
            BacktestRunRequest, ExecuteOrderRequest, PaginatedResponse,
        )
        from app.api.websocket import ConnectionManager, ws_manager
        from app.api.routes.signals import router as sig_router
        from app.api.routes.orders import router as ord_router
        from app.api.routes.positions import router as pos_router
        from app.api.routes.bot import router as bot_router
        from app.api.routes.backtest import router as bt_router
        from app.api.routes.settings import router as set_router
        from app.main import app, create_app

        assert app is not None
        assert ws_manager is not None
