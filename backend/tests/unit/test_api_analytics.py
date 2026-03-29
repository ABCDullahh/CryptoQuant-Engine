"""Tests for analytics API endpoints — live performance from closed positions."""

from __future__ import annotations

from uuid import uuid4

import pytest


def _insert_closed_position(seed_db, *, pnl, fees=0.0, opened="2026-03-10 10:00:00", closed="2026-03-10 14:00:00", symbol="BTC/USDT"):
    """Helper to insert a closed position with given P&L and dates."""
    pos_id = str(uuid4())
    seed_db(
        "INSERT INTO positions (id, signal_id, symbol, direction, entry_price, "
        "current_price, quantity, remaining_qty, leverage, stop_loss, "
        "unrealized_pnl, realized_pnl, total_fees, status, "
        "opened_at, closed_at) "
        "VALUES (:id, :sid, :symbol, 'LONG', 43000.0, 43500.0, "
        "0.5, 0, 3, 42500.0, 0, :pnl, :fees, 'CLOSED', "
        ":opened, :closed)",
        {
            "id": pos_id,
            "sid": str(uuid4()),
            "symbol": symbol,
            "pnl": pnl,
            "fees": fees,
            "opened": opened,
            "closed": closed,
        },
    )
    return pos_id


class TestLivePerformanceEmpty:
    def test_no_closed_positions(self, api_client):
        """Should return has_data=false when no closed trades exist."""
        resp = api_client.get("/api/analytics/live-performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_data"] is False
        assert "message" in data
        assert data["days"] == 30

    def test_no_closed_positions_custom_days(self, api_client):
        """Should respect custom days parameter."""
        resp = api_client.get("/api/analytics/live-performance?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_data"] is False
        assert data["days"] == 7


class TestLivePerformanceWithTrades:
    def test_basic_metrics(self, api_client, seed_db):
        """Insert 5 closed positions and verify all metrics are returned."""
        # 3 wins, 2 losses
        _insert_closed_position(seed_db, pnl=100.0, fees=2.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=200.0, fees=3.0, closed="2026-03-16 10:00:00")
        _insert_closed_position(seed_db, pnl=-50.0, fees=1.5, closed="2026-03-17 10:00:00")
        _insert_closed_position(seed_db, pnl=150.0, fees=2.5, closed="2026-03-18 10:00:00")
        _insert_closed_position(seed_db, pnl=-80.0, fees=1.0, closed="2026-03-19 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        assert resp.status_code == 200
        data = resp.json()

        assert data["has_data"] is True
        assert data["total_trades"] == 5
        assert data["total_pnl"] == pytest.approx(320.0)
        assert data["total_fees"] == pytest.approx(10.0)

        # All metric fields present
        for field in (
            "wins", "losses", "win_rate", "avg_win", "avg_loss",
            "profit_factor", "expectancy", "sharpe_ratio", "sortino_ratio",
            "max_drawdown_pct", "avg_holding_hours", "best_trade", "worst_trade",
            "equity_curve", "monthly_returns", "trade_pnls",
        ):
            assert field in data, f"Missing field: {field}"

    def test_response_types(self, api_client, seed_db):
        """Verify response types are correct."""
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=-50.0, closed="2026-03-16 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        assert isinstance(data["equity_curve"], list)
        assert isinstance(data["monthly_returns"], list)
        assert isinstance(data["trade_pnls"], list)
        assert isinstance(data["total_trades"], int)
        assert isinstance(data["win_rate"], float)


class TestLivePerformanceWinRate:
    def test_all_wins(self, api_client, seed_db):
        """All winning trades should give 100% win rate."""
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=200.0, closed="2026-03-16 10:00:00")
        _insert_closed_position(seed_db, pnl=50.0, closed="2026-03-17 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        assert data["wins"] == 3
        assert data["losses"] == 0
        assert data["win_rate"] == pytest.approx(1.0)
        # profit_factor should be None (inf) when no losses
        assert data["profit_factor"] is None

    def test_all_losses(self, api_client, seed_db):
        """All losing trades should give 0% win rate."""
        _insert_closed_position(seed_db, pnl=-100.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=-200.0, closed="2026-03-16 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        assert data["wins"] == 0
        assert data["losses"] == 2
        assert data["win_rate"] == pytest.approx(0.0)
        assert data["profit_factor"] == pytest.approx(0.0)

    def test_mixed_win_loss(self, api_client, seed_db):
        """3 wins, 2 losses = 60% win rate."""
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=200.0, closed="2026-03-16 10:00:00")
        _insert_closed_position(seed_db, pnl=-50.0, closed="2026-03-17 10:00:00")
        _insert_closed_position(seed_db, pnl=150.0, closed="2026-03-18 10:00:00")
        _insert_closed_position(seed_db, pnl=-80.0, closed="2026-03-19 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        assert data["wins"] == 3
        assert data["losses"] == 2
        assert data["win_rate"] == pytest.approx(0.6)
        assert data["avg_win"] == pytest.approx(150.0)  # (100+200+150)/3
        assert data["avg_loss"] == pytest.approx(65.0)   # (50+80)/2


class TestLivePerformanceEquityCurve:
    def test_running_balance(self, api_client, seed_db):
        """Equity curve should track running balance correctly."""
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=-30.0, closed="2026-03-16 10:00:00")
        _insert_closed_position(seed_db, pnl=50.0, closed="2026-03-17 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        curve = data["equity_curve"]
        assert len(curve) == 3

        # Starting balance is 10000.0
        assert curve[0]["balance"] == pytest.approx(10100.0)
        assert curve[0]["trade_pnl"] == pytest.approx(100.0)

        assert curve[1]["balance"] == pytest.approx(10070.0)
        assert curve[1]["trade_pnl"] == pytest.approx(-30.0)

        assert curve[2]["balance"] == pytest.approx(10120.0)
        assert curve[2]["trade_pnl"] == pytest.approx(50.0)

    def test_equity_curve_has_dates(self, api_client, seed_db):
        """Each equity curve point should have a date."""
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-03-15 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        curve = resp.json()["equity_curve"]

        assert len(curve) == 1
        assert curve[0]["date"] is not None


class TestLivePerformanceMonthlyReturns:
    def test_monthly_aggregation(self, api_client, seed_db):
        """Trades in different months should be grouped correctly."""
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-02-15 10:00:00")
        _insert_closed_position(seed_db, pnl=200.0, closed="2026-02-20 10:00:00")
        _insert_closed_position(seed_db, pnl=-50.0, closed="2026-03-15 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        monthly = data["monthly_returns"]
        assert len(monthly) == 2

        feb = next(m for m in monthly if m["month"] == "2026-02")
        mar = next(m for m in monthly if m["month"] == "2026-03")

        assert feb["pnl"] == pytest.approx(300.0)
        assert mar["pnl"] == pytest.approx(-50.0)

    def test_monthly_returns_sorted(self, api_client, seed_db):
        """Monthly returns should be sorted chronologically."""
        _insert_closed_position(seed_db, pnl=50.0, closed="2026-03-10 10:00:00")
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-01-10 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        monthly = resp.json()["monthly_returns"]

        months = [m["month"] for m in monthly]
        assert months == sorted(months)


class TestLivePerformanceDaysFilter:
    def test_filter_recent_only(self, api_client, seed_db):
        """Old trades should be excluded by the days filter."""
        # This position is closed recently — should be included
        _insert_closed_position(seed_db, pnl=100.0, opened="2026-03-25 10:00:00", closed="2026-03-26 10:00:00")
        # This position is from 60 days ago — should be excluded by days=7
        _insert_closed_position(seed_db, pnl=200.0, opened="2026-01-01 10:00:00", closed="2026-01-02 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=7")
        data = resp.json()

        # Only the recent trade should appear
        assert data["has_data"] is True
        assert data["total_trades"] == 1
        assert data["total_pnl"] == pytest.approx(100.0)

    def test_days_365_includes_all(self, api_client, seed_db):
        """A large days value should include all positions."""
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-03-25 10:00:00")
        _insert_closed_position(seed_db, pnl=200.0, closed="2025-06-15 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        assert data["has_data"] is True
        assert data["total_trades"] == 2


class TestLivePerformanceMetrics:
    def test_profit_factor(self, api_client, seed_db):
        """Profit factor = gross_wins / gross_losses."""
        _insert_closed_position(seed_db, pnl=300.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=-100.0, closed="2026-03-16 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        # 300 / 100 = 3.0
        assert data["profit_factor"] == pytest.approx(3.0)

    def test_expectancy(self, api_client, seed_db):
        """Expectancy = mean P&L per trade."""
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=-50.0, closed="2026-03-16 10:00:00")
        _insert_closed_position(seed_db, pnl=200.0, closed="2026-03-17 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        # (100 - 50 + 200) / 3 = 83.33
        assert data["expectancy"] == pytest.approx(83.33, abs=0.01)

    def test_best_worst_trade(self, api_client, seed_db):
        """Best and worst trade values."""
        _insert_closed_position(seed_db, pnl=500.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=-200.0, closed="2026-03-16 10:00:00")
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-03-17 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        assert data["best_trade"] == pytest.approx(500.0)
        assert data["worst_trade"] == pytest.approx(-200.0)

    def test_max_drawdown(self, api_client, seed_db):
        """Drawdown should capture peak-to-trough decline."""
        # Initial balance 10000, then +100, -300, +50 => equity: 10100, 9800, 9850
        # Peak=10100, trough=9800, drawdown = 300/10100 ~ 2.97%
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=-300.0, closed="2026-03-16 10:00:00")
        _insert_closed_position(seed_db, pnl=50.0, closed="2026-03-17 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        # max_dd = (10100 - 9800) / 10100 = 0.02970...
        assert data["max_drawdown_pct"] == pytest.approx(0.0297, abs=0.001)

    def test_holding_hours(self, api_client, seed_db):
        """Average holding hours calculated from opened_at to closed_at."""
        # 4 hours holding time
        _insert_closed_position(
            seed_db, pnl=100.0,
            opened="2026-03-15 10:00:00", closed="2026-03-15 14:00:00"
        )
        # 8 hours holding time
        _insert_closed_position(
            seed_db, pnl=-50.0,
            opened="2026-03-16 10:00:00", closed="2026-03-16 18:00:00"
        )

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        # avg = (4 + 8) / 2 = 6.0
        assert data["avg_holding_hours"] == pytest.approx(6.0)

    def test_total_fees(self, api_client, seed_db):
        """Total fees should be summed across all closed positions."""
        _insert_closed_position(seed_db, pnl=100.0, fees=5.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=-50.0, fees=3.0, closed="2026-03-16 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        assert data["total_fees"] == pytest.approx(8.0)

    def test_sharpe_ratio_nonzero(self, api_client, seed_db):
        """Sharpe ratio should be non-zero with varying returns."""
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=-50.0, closed="2026-03-16 10:00:00")
        _insert_closed_position(seed_db, pnl=200.0, closed="2026-03-17 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        assert data["sharpe_ratio"] != 0.0
        # Positive total PnL should give positive sharpe
        assert data["sharpe_ratio"] > 0

    def test_sortino_ratio_nonzero(self, api_client, seed_db):
        """Sortino ratio should be non-zero with some losing trades."""
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-03-15 10:00:00")
        _insert_closed_position(seed_db, pnl=-50.0, closed="2026-03-16 10:00:00")
        _insert_closed_position(seed_db, pnl=200.0, closed="2026-03-17 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        assert data["sortino_ratio"] != 0.0
        assert data["sortino_ratio"] > 0


class TestLivePerformanceEdgeCases:
    def test_single_trade(self, api_client, seed_db):
        """Single trade should still produce valid output."""
        _insert_closed_position(seed_db, pnl=100.0, closed="2026-03-15 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        assert data["has_data"] is True
        assert data["total_trades"] == 1
        assert data["wins"] == 1
        assert data["losses"] == 0
        assert data["equity_curve"][0]["balance"] == pytest.approx(10100.0)
        # Sharpe needs >= 2 trades
        assert data["sharpe_ratio"] == pytest.approx(0.0)

    def test_open_positions_excluded(self, api_client, seed_db):
        """OPEN positions should not be included in analytics."""
        # Insert an OPEN position
        seed_db(
            "INSERT INTO positions (id, signal_id, symbol, direction, entry_price, "
            "current_price, quantity, remaining_qty, leverage, stop_loss, "
            "unrealized_pnl, realized_pnl, total_fees, status) "
            "VALUES (:id, :sid, 'BTC/USDT', 'LONG', 43000.0, 43500.0, "
            "0.5, 0.5, 3, 42500.0, 250, 0, 0, 'OPEN')",
            {"id": str(uuid4()), "sid": str(uuid4())},
        )

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()
        assert data["has_data"] is False

    def test_zero_pnl_trade(self, api_client, seed_db):
        """A trade with 0 P&L should count as a loss."""
        _insert_closed_position(seed_db, pnl=0.0, closed="2026-03-15 10:00:00")

        resp = api_client.get("/api/analytics/live-performance?days=365")
        data = resp.json()

        assert data["total_trades"] == 1
        assert data["wins"] == 0
        assert data["losses"] == 1
