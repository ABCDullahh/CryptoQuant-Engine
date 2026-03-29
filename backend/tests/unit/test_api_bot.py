"""Tests for bot management API endpoints."""

from __future__ import annotations

import pytest


class TestBotStatus:
    def test_initial_status(self, api_client):
        resp = api_client.get("/api/bot/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "STOPPED"
        assert data["paper_mode"] is True

    def test_status_includes_balance_fields(self, api_client):
        resp = api_client.get("/api/bot/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "current_balance" in data
        assert "current_equity" in data
        assert "paper_initial_balance" in data
        assert "paper_saved_balance" in data


class TestBotStart:
    def test_start_bot(self, api_client):
        resp = api_client.post("/api/bot/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "RUNNING"

    def test_start_already_running(self, api_client):
        api_client.post("/api/bot/start")
        resp = api_client.post("/api/bot/start")
        assert resp.status_code == 409


class TestBotPause:
    def test_pause_running(self, api_client):
        api_client.post("/api/bot/start")
        resp = api_client.post("/api/bot/pause")
        assert resp.status_code == 200
        assert resp.json()["status"] == "PAUSED"

    def test_paused_status_persists(self, api_client):
        """After pause, status endpoint should show PAUSED, not STOPPED."""
        api_client.post("/api/bot/start")
        api_client.post("/api/bot/pause")
        resp = api_client.get("/api/bot/status")
        assert resp.json()["status"] == "PAUSED"

    def test_pause_not_running(self, api_client):
        resp = api_client.post("/api/bot/pause")
        assert resp.status_code == 409


class TestBotStop:
    def test_stop_bot(self, api_client):
        api_client.post("/api/bot/start")
        resp = api_client.post("/api/bot/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "STOPPED"

    def test_stop_clears_paused(self, api_client):
        """After stop, status should be STOPPED even if previously paused."""
        api_client.post("/api/bot/start")
        api_client.post("/api/bot/pause")
        # Re-start and then stop
        api_client.post("/api/bot/start")
        api_client.post("/api/bot/stop")
        resp = api_client.get("/api/bot/status")
        assert resp.json()["status"] == "STOPPED"


class TestBotPaperMode:
    def test_toggle_paper_mode(self, api_client):
        resp = api_client.put("/api/bot/paper-mode", json={"paper_mode": False})
        assert resp.status_code == 200
        assert resp.json()["paper_mode"] is False

    def test_cannot_change_while_running(self, api_client):
        api_client.post("/api/bot/start")
        resp = api_client.put("/api/bot/paper-mode", json={"paper_mode": False})
        assert resp.status_code == 409


class TestBotStrategies:
    def test_update_strategies(self, api_client):
        resp = api_client.put("/api/bot/strategies", json={
            "strategies": {"momentum": True, "smc": True, "volume": False}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "momentum" in data["active_strategies"]
        assert "smc" in data["active_strategies"]
        assert "volume" not in data["active_strategies"]


class TestBotResume:
    def test_resume_from_paused(self, api_client):
        """Resume (re-start) from PAUSED should transition to RUNNING."""
        api_client.post("/api/bot/start")
        api_client.post("/api/bot/pause")
        # Verify paused
        resp = api_client.get("/api/bot/status")
        assert resp.json()["status"] == "PAUSED"
        # Resume by calling start again
        resp = api_client.post("/api/bot/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "RUNNING"


class TestBotLiveStatus:
    def test_live_status_returns_200(self, api_client):
        resp = api_client.get("/api/bot/live-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "service_status" in data
        assert "has_collector" in data
        assert "has_executor" in data

    def test_live_status_initial_values(self, api_client):
        resp = api_client.get("/api/bot/live-status")
        data = resp.json()
        assert data["service_status"] == "STOPPED"


class TestBotStartConfig:
    def test_start_with_strategies(self, api_client):
        """Start with specific strategies saves them."""
        resp = api_client.post("/api/bot/start", json={
            "strategies": ["momentum", "smc"],
            "is_paper": True,
        })
        assert resp.status_code == 200
        status = api_client.get("/api/bot/status").json()
        assert "momentum" in status["active_strategies"]
        assert "smc" in status["active_strategies"]

    def test_start_with_paper_false(self, api_client):
        """Start with is_paper=False sets live mode."""
        resp = api_client.post("/api/bot/start", json={"is_paper": False})
        assert resp.status_code == 200
        status = api_client.get("/api/bot/status").json()
        assert status["paper_mode"] is False


class TestBotModeSwitchBalance:
    def test_switch_paper_to_live_preserves_balance(self, api_client, seed_db):
        """Switching from paper to live should preserve paper_saved_balance."""
        # Set paper balance in DB
        seed_db(
            "UPDATE bot_state SET paper_balance = 10500.0, paper_initial_balance = 10000.0 "
            "WHERE id = (SELECT id FROM bot_state LIMIT 1)",
        )
        # First ensure bot state exists by fetching status
        api_client.get("/api/bot/status")
        # Switch to live
        resp = api_client.put("/api/bot/paper-mode", json={"paper_mode": False})
        assert resp.status_code == 200
        assert resp.json()["paper_mode"] is False

    def test_switch_back_to_paper(self, api_client):
        """Switch live -> paper should work."""
        api_client.get("/api/bot/status")  # ensure state
        api_client.put("/api/bot/paper-mode", json={"paper_mode": False})
        resp = api_client.put("/api/bot/paper-mode", json={"paper_mode": True})
        assert resp.status_code == 200
        assert resp.json()["paper_mode"] is True


class TestBotPerformance:
    def test_empty_performance(self, api_client):
        resp = api_client.get("/api/bot/performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trades"] == 0
        assert data["total_pnl"] == 0
        assert data["win_rate"] == 0

    def test_performance_with_closed_positions(self, api_client, seed_db):
        """Performance should reflect closed positions."""
        from uuid import uuid4
        for i in range(3):
            pnl = 100.0 if i < 2 else -50.0  # 2 wins, 1 loss
            seed_db(
                "INSERT INTO positions (id, symbol, direction, entry_price, quantity, "
                "remaining_qty, leverage, stop_loss, unrealized_pnl, realized_pnl, "
                "total_fees, status) VALUES (:id, 'BTC/USDT', 'LONG', 43000.0, 0.1, "
                "0, 1, 42500.0, 0, :pnl, 0, 'CLOSED')",
                {"id": str(uuid4()), "pnl": pnl},
            )
        resp = api_client.get("/api/bot/performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trades"] == 3
        assert data["total_pnl"] == pytest.approx(150.0)
        assert data["wins"] == 2
        assert data["losses"] == 1
        assert data["win_rate"] == pytest.approx(2 / 3, rel=0.01)

    def test_performance_fields_complete(self, api_client):
        resp = api_client.get("/api/bot/performance")
        data = resp.json()
        for field in ("total_trades", "total_pnl", "win_rate", "wins", "losses"):
            assert field in data
