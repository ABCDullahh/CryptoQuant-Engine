"""Tests for order API endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture
def seeded_client(api_client, seed_db):
    """Client with signal and order data seeded."""
    signal_id = str(uuid4())
    order_id = str(uuid4())
    seed_db(
        "INSERT INTO signals (id, symbol, direction, signal_grade, signal_strength, "
        "entry_price, stop_loss, sl_type, tp1_price, tp1_pct, leverage, "
        "position_size_qty, strategy_scores, status) VALUES "
        "(:id, 'BTC/USDT', 'LONG', 'A', 0.85, 43000.0, 42500.0, "
        "'ATR_BASED', 44000.0, 50, 3, 0.5, '{\"momentum\": 0.8}', 'ACTIVE')",
        {"id": signal_id},
    )
    seed_db(
        "INSERT INTO orders (id, signal_id, symbol, side, order_type, price, "
        "quantity, filled_qty, fees, status) VALUES "
        "(:oid, :sid, 'BTC/USDT', 'BUY', 'MARKET', 43000.0, 0.5, 0, 0, 'SUBMITTED')",
        {"oid": order_id, "sid": signal_id},
    )
    return api_client, signal_id, order_id


class TestExecuteOrder:
    def test_execute_creates_order(self, seeded_client):
        """Should create an order when bot executor is available."""
        c, signal_id, _ = seeded_client
        resp = c.post("/api/orders/execute", json={
            "signal_id": signal_id, "mode": "ONE_CLICK"
        })
        assert resp.status_code == 201

    def test_execute_signal_not_found(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.post("/api/orders/execute", json={
            "signal_id": str(uuid4()), "mode": "ONE_CLICK"
        })
        assert resp.status_code == 404


class TestCancelOrder:
    def test_cancel_submitted(self, seeded_client):
        c, _, order_id = seeded_client
        resp = c.post(f"/api/orders/{order_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLED"

    def test_cancel_not_found(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.post(f"/api/orders/{uuid4()}/cancel")
        assert resp.status_code == 404


class TestListOrders:
    def test_list_all(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/orders")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestGetOrder:
    def test_get_existing(self, seeded_client):
        c, _, order_id = seeded_client
        resp = c.get(f"/api/orders/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == order_id

    def test_get_not_found(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get(f"/api/orders/{uuid4()}")
        assert resp.status_code == 404

    def test_order_detail_has_all_fields(self, seeded_client):
        c, _, order_id = seeded_client
        resp = c.get(f"/api/orders/{order_id}")
        data = resp.json()
        for field in ("id", "signal_id", "symbol", "side", "order_type",
                       "price", "quantity", "filled_qty", "status", "fees"):
            assert field in data


class TestCancelOrderEdgeCases:
    def test_cancel_already_filled(self, seeded_client, seed_db):
        """Cannot cancel a FILLED order."""
        c, _, _ = seeded_client
        filled_id = str(uuid4())
        seed_db(
            "INSERT INTO orders (id, symbol, side, order_type, price, quantity, "
            "filled_qty, fees, status) VALUES (:id, 'BTC/USDT', 'BUY', 'MARKET', "
            "43000.0, 0.5, 0.5, 0, 'FILLED')",
            {"id": filled_id},
        )
        resp = c.post(f"/api/orders/{filled_id}/cancel")
        assert resp.status_code == 409

    def test_cancel_already_cancelled(self, seeded_client, seed_db):
        """Cannot cancel an already CANCELLED order."""
        c, _, _ = seeded_client
        cancelled_id = str(uuid4())
        seed_db(
            "INSERT INTO orders (id, symbol, side, order_type, price, quantity, "
            "filled_qty, fees, status) VALUES (:id, 'BTC/USDT', 'BUY', 'MARKET', "
            "43000.0, 0.5, 0, 0, 'CANCELLED')",
            {"id": cancelled_id},
        )
        resp = c.post(f"/api/orders/{cancelled_id}/cancel")
        assert resp.status_code == 409


class TestListOrdersFilters:
    def test_filter_by_symbol(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/orders?symbol=BTC/USDT")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_filter_nonexistent_symbol(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/orders?symbol=DOGE/USDT")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_filter_by_status(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/orders?status=SUBMITTED")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_pagination(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/orders?limit=1&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 1
        assert data["offset"] == 0

    def test_offset_beyond_total(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/orders?offset=1000")
        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestExecuteOrderEdgeCases:
    def test_execute_inactive_signal(self, seeded_client, seed_db):
        """Cannot execute order for non-ACTIVE signal."""
        c, _, _ = seeded_client
        executed_sig = str(uuid4())
        seed_db(
            "INSERT INTO signals (id, symbol, direction, signal_grade, signal_strength, "
            "entry_price, stop_loss, sl_type, tp1_price, tp1_pct, leverage, "
            "strategy_scores, status) VALUES "
            "(:id, 'BTC/USDT', 'LONG', 'A', 0.85, 43000.0, 42500.0, "
            "'ATR_BASED', 44000.0, 50, 3, '{\"momentum\": 0.8}', 'EXECUTED')",
            {"id": executed_sig},
        )
        resp = c.post("/api/orders/execute", json={
            "signal_id": executed_sig, "mode": "ONE_CLICK"
        })
        assert resp.status_code == 409
