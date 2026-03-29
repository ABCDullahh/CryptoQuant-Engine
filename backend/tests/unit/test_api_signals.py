"""Tests for signal API endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture
def seeded_client(api_client, seed_db):
    """Client with signal data seeded."""
    s1_id = str(uuid4())
    s2_id = str(uuid4())
    seed_db(
        "INSERT INTO signals (id, symbol, direction, signal_grade, signal_strength, "
        "entry_price, stop_loss, sl_type, tp1_price, tp1_pct, leverage, "
        "strategy_scores, status) VALUES "
        "(:id, 'BTC/USDT', 'LONG', 'A', 0.85, 43000.0, 42500.0, "
        "'ATR_BASED', 44000.0, 50, 3, '{\"momentum\": 0.8}', 'ACTIVE')",
        {"id": s1_id},
    )
    seed_db(
        "INSERT INTO signals (id, symbol, direction, signal_grade, signal_strength, "
        "entry_price, stop_loss, sl_type, tp1_price, tp1_pct, leverage, "
        "strategy_scores, status) VALUES "
        "(:id, 'ETH/USDT', 'SHORT', 'B', 0.65, 2200.0, 2300.0, "
        "'PERCENTAGE', 2100.0, 50, 2, '{\"smc\": 0.7}', 'EXECUTED')",
        {"id": s2_id},
    )
    return api_client, s1_id, s2_id


class TestListSignals:
    def test_list_all_signals_default(self, seeded_client):
        c, s1_id, _ = seeded_client
        resp = c.get("/api/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # Default returns all statuses

    def test_list_active_signals(self, seeded_client):
        c, s1_id, _ = seeded_client
        resp = c.get("/api/signals?status=ACTIVE")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["symbol"] == "BTC/USDT"

    def test_filter_by_status(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/signals?status=EXECUTED")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["symbol"] == "ETH/USDT"

    def test_filter_by_direction(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/signals?direction=LONG")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


class TestGetSignal:
    def test_get_existing(self, seeded_client):
        c, s1_id, _ = seeded_client
        resp = c.get(f"/api/signals/{s1_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == s1_id

    def test_get_not_found(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get(f"/api/signals/{uuid4()}")
        assert resp.status_code == 404


class TestSignalHistory:
    def test_history_returns_closed(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/signals/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "EXECUTED"

    def test_history_excludes_active(self, seeded_client):
        """History should NOT include ACTIVE signals."""
        c, _, _ = seeded_client
        resp = c.get("/api/signals/history")
        statuses = [s["status"] for s in resp.json()["items"]]
        assert "ACTIVE" not in statuses

    def test_history_filter_by_symbol(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/signals/history?symbol=ETH/USDT")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_history_pagination(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/signals/history?limit=1&offset=0")
        assert resp.status_code == 200
        assert resp.json()["limit"] == 1


class TestSignalFilters:
    def test_filter_by_grade(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/signals?grade=A")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["signal_grade"] == "A"

    def test_filter_by_grade_b(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/signals?grade=B")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_combined_filters(self, seeded_client):
        """Grade + direction + status combined."""
        c, _, _ = seeded_client
        resp = c.get("/api/signals?grade=A&direction=LONG&status=ACTIVE")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_combined_filters_no_match(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/signals?grade=A&direction=SHORT")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_status_all(self, seeded_client):
        """status=ALL should return all signals."""
        c, _, _ = seeded_client
        resp = c.get("/api/signals?status=ALL")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_pagination_limit(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/signals?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1
        assert resp.json()["total"] == 2

    def test_pagination_offset(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.get("/api/signals?offset=100")
        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestSignalDetail:
    def test_detail_has_all_fields(self, seeded_client):
        c, s1_id, _ = seeded_client
        resp = c.get(f"/api/signals/{s1_id}")
        data = resp.json()
        for field in ("id", "symbol", "direction", "signal_grade", "signal_strength",
                       "entry_price", "stop_loss", "sl_type", "tp1_price",
                       "leverage", "strategy_scores", "status"):
            assert field in data

    def test_detail_strategy_scores_dict(self, seeded_client):
        c, s1_id, _ = seeded_client
        resp = c.get(f"/api/signals/{s1_id}")
        scores = resp.json()["strategy_scores"]
        assert isinstance(scores, dict)
        assert "momentum" in scores


class TestExecuteSignalEdgeCases:
    def test_execute_already_executed(self, seeded_client):
        """Cannot execute a signal that is already EXECUTED."""
        c, _, s2_id = seeded_client  # s2 is EXECUTED
        resp = c.post(f"/api/signals/{s2_id}/execute")
        assert resp.status_code == 400

    def test_execute_not_found(self, seeded_client):
        c, _, _ = seeded_client
        resp = c.post(f"/api/signals/{uuid4()}/execute")
        assert resp.status_code == 404
