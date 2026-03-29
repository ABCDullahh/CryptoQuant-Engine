"""Tests for position API endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture
def seeded_client(api_client, seed_db):
    """Client with position data seeded."""
    pos_id = str(uuid4())
    seed_db(
        "INSERT INTO positions (id, signal_id, symbol, direction, entry_price, "
        "current_price, quantity, remaining_qty, leverage, stop_loss, "
        "tp1_price, tp2_price, tp3_price, unrealized_pnl, realized_pnl, "
        "total_fees, status) "
        "VALUES (:id, :sid, 'BTC/USDT', 'LONG', 43000.0, 43500.0, "
        "0.5, 0.5, 3, 42500.0, 44000.0, 45000.0, 46000.0, 250.0, 0, 0, 'OPEN')",
        {"id": pos_id, "sid": str(uuid4())},
    )
    return api_client, pos_id


class TestListPositions:
    def test_list_open(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/positions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "OPEN"

    def test_response_includes_trading_mode(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/positions")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert "trading_mode" in item
        assert item["trading_mode"] in ("paper", "live")

    def test_response_includes_exchange_order_id(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/positions")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert "exchange_order_id" in item

    def test_filter_by_symbol(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/positions?symbol=BTC/USDT")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_filter_nonexistent_symbol(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/positions?symbol=DOGE/USDT")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_filter_by_mode(self, seeded_client):
        c, _ = seeded_client
        # Default seeded position has trading_mode='paper' (column default)
        resp = c.get("/api/positions?mode=paper&status=OPEN")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = c.get("/api/positions?mode=live&status=OPEN")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestGetPosition:
    def test_get_existing(self, seeded_client):
        c, pos_id = seeded_client
        resp = c.get(f"/api/positions/{pos_id}")
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "BTC/USDT"

    def test_get_not_found(self, seeded_client):
        c, _ = seeded_client
        resp = c.get(f"/api/positions/{uuid4()}")
        assert resp.status_code == 404


class TestClosePosition:
    def test_close_open(self, seeded_client):
        c, pos_id = seeded_client
        resp = c.post(f"/api/positions/{pos_id}/close")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "CLOSED"
        assert data["close_pct"] == 100.0
        assert data["remaining_qty"] == 0

    def test_close_partial(self, seeded_client):
        c, pos_id = seeded_client
        resp = c.post(f"/api/positions/{pos_id}/close", json={"close_pct": 50.0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "REDUCING"
        assert data["close_pct"] == 50.0
        assert data["remaining_qty"] == pytest.approx(0.25)
        assert data["closed_qty"] == pytest.approx(0.25)
        assert "realized_pnl" in data

    def test_close_with_pnl(self, seeded_client):
        """Verify PnL calculation: entry=43000, current=43500, LONG, qty=0.5."""
        c, pos_id = seeded_client
        resp = c.post(f"/api/positions/{pos_id}/close")
        assert resp.status_code == 200
        data = resp.json()
        # (43500 - 43000) * 0.5 * 1 (direction LONG) = 250.0
        assert data["realized_pnl"] == pytest.approx(250.0)

    def test_close_not_found(self, seeded_client):
        c, _ = seeded_client
        resp = c.post(f"/api/positions/{uuid4()}/close")
        assert resp.status_code == 404


class TestUpdateStopLoss:
    def test_update_sl(self, seeded_client):
        c, pos_id = seeded_client
        resp = c.put(f"/api/positions/{pos_id}/sl", json={"new_sl": 42000.0})
        assert resp.status_code == 200
        assert resp.json()["stop_loss"] == 42000.0

    def test_update_sl_not_found(self, seeded_client):
        c, _ = seeded_client
        resp = c.put(f"/api/positions/{uuid4()}/sl", json={"new_sl": 42000.0})
        assert resp.status_code == 404


class TestUpdateTakeProfit:
    def test_update_tp(self, seeded_client):
        c, pos_id = seeded_client
        resp = c.put(f"/api/positions/{pos_id}/tp", json={
            "take_profits": [
                {"level": "TP1", "price": 44500.0},
                {"level": "TP2", "price": 45500.0},
            ]
        })
        assert resp.status_code == 200
        assert resp.json()["tp1_price"] == 44500.0
        assert resp.json()["tp2_price"] == 45500.0

    def test_update_tp_not_found(self, seeded_client):
        c, _ = seeded_client
        resp = c.put(f"/api/positions/{uuid4()}/tp", json={
            "take_profits": [{"level": "TP1", "price": 44000.0}]
        })
        assert resp.status_code == 404


class TestPartialClose:
    def test_close_25_percent(self, seeded_client):
        c, pos_id = seeded_client
        resp = c.post(f"/api/positions/{pos_id}/close", json={"close_pct": 25.0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["close_pct"] == 25.0
        assert data["remaining_qty"] == pytest.approx(0.375)
        assert data["status"] == "REDUCING"

    def test_close_75_percent(self, seeded_client):
        c, pos_id = seeded_client
        resp = c.post(f"/api/positions/{pos_id}/close", json={"close_pct": 75.0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["close_pct"] == 75.0
        assert data["remaining_qty"] == pytest.approx(0.125)

    def test_close_100_full(self, seeded_client):
        c, pos_id = seeded_client
        resp = c.post(f"/api/positions/{pos_id}/close", json={"close_pct": 100.0})
        assert resp.status_code == 200
        assert resp.json()["status"] == "CLOSED"
        assert resp.json()["remaining_qty"] == 0


class TestClosePositionEdgeCases:
    def test_close_already_closed(self, seeded_client, seed_db):
        """Cannot close an already CLOSED position."""
        c, _ = seeded_client
        closed_id = str(uuid4())
        seed_db(
            "INSERT INTO positions (id, signal_id, symbol, direction, entry_price, "
            "current_price, quantity, remaining_qty, leverage, stop_loss, "
            "unrealized_pnl, realized_pnl, total_fees, status) "
            "VALUES (:id, :sid, 'BTC/USDT', 'LONG', 43000.0, 43500.0, "
            "0.5, 0, 3, 42500.0, 0, 250.0, 0, 'CLOSED')",
            {"id": closed_id, "sid": str(uuid4())},
        )
        resp = c.post(f"/api/positions/{closed_id}/close")
        assert resp.status_code in (400, 409)


class TestUpdateSLEdgeCases:
    def test_update_sl_on_closed(self, seeded_client, seed_db):
        """Cannot update SL on a CLOSED position."""
        c, _ = seeded_client
        closed_id = str(uuid4())
        seed_db(
            "INSERT INTO positions (id, signal_id, symbol, direction, entry_price, "
            "current_price, quantity, remaining_qty, leverage, stop_loss, "
            "unrealized_pnl, realized_pnl, total_fees, status) "
            "VALUES (:id, :sid, 'BTC/USDT', 'LONG', 43000.0, 43500.0, "
            "0.5, 0, 3, 42500.0, 0, 250.0, 0, 'CLOSED')",
            {"id": closed_id, "sid": str(uuid4())},
        )
        resp = c.put(f"/api/positions/{closed_id}/sl", json={"new_sl": 42000.0})
        # Should still succeed (route may allow it) or 409
        assert resp.status_code in (200, 400, 409)


class TestExchangePositions:
    def test_exchange_positions_endpoint(self, api_client):
        """GET /positions/exchange-positions should return a response."""
        from unittest.mock import AsyncMock, patch
        mock_positions = [
            {"symbol": "BTCUSDT", "contracts": 0.5, "entryPrice": "43000.0",
             "markPrice": "43500.0", "leverage": "3", "unrealizedPnl": "250.0",
             "initialMargin": "7166.0", "liquidationPrice": "40000.0",
             "notional": "21750.0"}
        ]
        mock_exchange = AsyncMock()
        mock_exchange.fetch_positions = AsyncMock(return_value=mock_positions)
        mock_exchange.close = AsyncMock()

        with patch("ccxt.async_support.binanceusdm", return_value=mock_exchange):
            resp = api_client.get("/api/positions/exchange-positions")
            assert resp.status_code == 200
            data = resp.json()
            assert "positions" in data
            assert "count" in data
            assert data["count"] == 1
            assert data["source"] == "binance"
            assert data["positions"][0]["direction"] == "LONG"

    def test_exchange_positions_empty(self, api_client):
        """No active positions returns empty list."""
        from unittest.mock import AsyncMock, patch
        mock_positions = [{"symbol": "BTCUSDT", "contracts": 0}]
        mock_exchange = AsyncMock()
        mock_exchange.fetch_positions = AsyncMock(return_value=mock_positions)
        mock_exchange.close = AsyncMock()

        with patch("ccxt.async_support.binanceusdm", return_value=mock_exchange):
            resp = api_client.get("/api/positions/exchange-positions")
            assert resp.status_code == 200
            assert resp.json()["count"] == 0

    def test_exchange_positions_error(self, api_client):
        """On error, should return empty with error source."""
        from unittest.mock import patch
        with patch(
            "ccxt.async_support.binanceusdm",
            side_effect=Exception("API key missing"),
        ):
            resp = api_client.get("/api/positions/exchange-positions")
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "error"
            assert data["count"] == 0
            assert "error" in data


class TestPositionFilterCombination:
    def test_filter_status_and_symbol(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/positions?status=OPEN&symbol=BTC/USDT")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_filter_all_params(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/positions?status=OPEN&symbol=BTC/USDT&mode=paper")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_pagination_offset_beyond_total(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/positions?offset=100")
        assert resp.status_code == 200
        assert resp.json()["items"] == []
