"""Tests for backtest API endpoints."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest


@pytest.fixture
def seeded_client(api_client, seed_db):
    """Client with backtest run data seeded."""
    run_id = str(uuid4())
    seed_db(
        "INSERT INTO backtest_runs (id, strategy_name, symbol, timeframe, "
        "start_date, end_date, initial_capital, total_return, sharpe_ratio, "
        "max_drawdown, win_rate, total_trades) "
        "VALUES (:id, 'momentum', 'BTC/USDT', '1h', '2024-01-01', '2024-06-01', "
        "10000.0, 0.15, 1.5, 0.08, 0.62, 45)",
        {"id": run_id},
    )
    return api_client, run_id


@pytest.fixture
def seeded_client_full(api_client, seed_db):
    """Client with full backtest data including equity curve and trades."""
    run_id = str(uuid4())
    equity_curve = json.dumps([
        {"index": 0, "equity": 10000.0},
        {"index": 1, "equity": 10050.0},
        {"index": 2, "equity": 10150.0},
    ])
    trades = json.dumps([
        {
            "id": "t1",
            "direction": "LONG",
            "entry_price": 43000.0,
            "exit_price": 43100.0,
            "quantity": 0.5,
            "pnl": 50.0,
            "fees": 2.0,
            "close_reason": "TP1",
            "holding_periods": 5,
        },
        {
            "id": "t2",
            "direction": "SHORT",
            "entry_price": 43200.0,
            "exit_price": 43100.0,
            "quantity": 1.0,
            "pnl": 100.0,
            "fees": 3.0,
            "close_reason": "TP1",
            "holding_periods": 3,
        },
    ])
    seed_db(
        "INSERT INTO backtest_runs (id, strategy_name, symbol, timeframe, "
        "start_date, end_date, initial_capital, final_capital, total_return, "
        "sharpe_ratio, sortino_ratio, max_drawdown, win_rate, profit_factor, "
        "total_trades, equity_curve, trades, status) "
        "VALUES (:id, 'momentum', 'BTC/USDT', '1h', '2024-01-01', '2024-06-01', "
        "10000.0, 10150.0, 0.015, 1.5, 2.0, 0.02, 1.0, 3.0, "
        "2, :equity_curve, :trades, 'COMPLETED')",
        {"id": run_id, "equity_curve": equity_curve, "trades": trades},
    )
    return api_client, run_id


class TestRunBacktest:
    def test_submit_backtest(self, api_client):
        resp = api_client.post("/api/backtest/run", json={
            "strategy_name": "momentum",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-06-01T00:00:00Z",
        })
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "QUEUED"
        assert "job_id" in data


class TestBacktestHistory:
    def test_list_history(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/backtest/history")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_filter_by_strategy(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/backtest/history?strategy=momentum")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestGetBacktest:
    def test_get_existing(self, seeded_client):
        c, run_id = seeded_client
        resp = c.get(f"/api/backtest/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy_name"] == "momentum"
        assert data["total_trades"] == 45

    def test_get_not_found(self, seeded_client):
        c, _ = seeded_client
        resp = c.get(f"/api/backtest/{uuid4()}")
        assert resp.status_code == 404


class TestOptimize:
    def test_submit_optimization(self, api_client):
        resp = api_client.post("/api/backtest/optimize", json={
            "strategy_name": "momentum",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-06-01T00:00:00Z",
            "param_ranges": {"rsi_period": {"min": 10, "max": 20}},
        })
        assert resp.status_code == 202


class TestWalkForward:
    def test_submit_walkforward(self, api_client):
        resp = api_client.post("/api/backtest/walkforward", json={
            "strategy_name": "momentum",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-06-01T00:00:00Z",
        })
        assert resp.status_code == 202

    def test_walkforward_returns_job_id(self, api_client):
        resp = api_client.post("/api/backtest/walkforward", json={
            "strategy_name": "mean_reversion",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-06-01T00:00:00Z",
        })
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "QUEUED"


class TestBacktestResultDetail:
    def test_result_has_all_fields(self, seeded_client):
        c, run_id = seeded_client
        resp = c.get(f"/api/backtest/{run_id}")
        data = resp.json()
        for field in ("id", "strategy_name", "symbol", "timeframe",
                       "start_date", "end_date", "initial_capital",
                       "total_return", "sharpe_ratio", "max_drawdown",
                       "win_rate", "total_trades"):
            assert field in data

    def test_result_metrics_correct(self, seeded_client):
        c, run_id = seeded_client
        data = c.get(f"/api/backtest/{run_id}").json()
        assert data["total_return"] == pytest.approx(0.15)
        assert data["sharpe_ratio"] == pytest.approx(1.5)
        assert data["max_drawdown"] == pytest.approx(0.08)
        assert data["win_rate"] == pytest.approx(0.62)
        assert data["total_trades"] == 45


class TestBacktestHistoryFilters:
    def test_filter_nonexistent_strategy(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/backtest/history?strategy=nonexistent")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_pagination(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/backtest/history?limit=1&offset=0")
        assert resp.status_code == 200
        assert resp.json()["limit"] == 1

    def test_offset_beyond_total(self, seeded_client):
        c, _ = seeded_client
        resp = c.get("/api/backtest/history?offset=100")
        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestOptimizeResult:
    def test_optimize_returns_job_id(self, api_client):
        resp = api_client.post("/api/backtest/optimize", json={
            "strategy_name": "momentum",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-06-01T00:00:00Z",
            "param_ranges": {"rsi_period": {"min": 10, "max": 20}},
        })
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "QUEUED"
        assert data["progress"] == 0


class TestRunBacktestDefaults:
    def test_submit_with_defaults(self, api_client):
        """Backtest with minimal params should use defaults."""
        resp = api_client.post("/api/backtest/run", json={
            "strategy_name": "volume_analysis",
            "start_date": "2024-03-01T00:00:00Z",
            "end_date": "2024-06-01T00:00:00Z",
        })
        assert resp.status_code == 202
        assert resp.json()["status"] == "QUEUED"

    def test_submit_with_full_config(self, api_client):
        resp = api_client.post("/api/backtest/run", json={
            "strategy_name": "smc",
            "symbol": "ETH/USDT",
            "timeframe": "4h",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-06-01T00:00:00Z",
            "initial_capital": 50000.0,
            "parameters": {"lookback": 20},
        })
        assert resp.status_code == 202


class TestBacktestResponseEquityCurve:
    def test_backtest_response_includes_equity_curve(self, seeded_client_full):
        c, run_id = seeded_client_full
        resp = c.get(f"/api/backtest/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "equity_curve" in data
        assert isinstance(data["equity_curve"], list)
        assert len(data["equity_curve"]) == 3
        assert data["equity_curve"][0]["equity"] == 10000.0
        assert data["equity_curve"][-1]["equity"] == 10150.0

    def test_backtest_response_equity_curve_empty_when_none(self, seeded_client):
        c, run_id = seeded_client
        resp = c.get(f"/api/backtest/{run_id}")
        data = resp.json()
        assert data["equity_curve"] == [] or data["equity_curve"] is None


class TestBacktestResponseMetrics:
    def test_backtest_response_includes_metrics(self, seeded_client_full):
        c, run_id = seeded_client_full
        resp = c.get(f"/api/backtest/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        metrics = data["metrics"]
        assert isinstance(metrics, dict)
        assert metrics["total_return"] == pytest.approx(0.015)
        assert metrics["sharpe_ratio"] == pytest.approx(1.5)
        assert metrics["sortino_ratio"] == pytest.approx(2.0)
        assert metrics["max_drawdown"] == pytest.approx(0.02)
        assert metrics["win_rate"] == pytest.approx(1.0)
        assert metrics["profit_factor"] == pytest.approx(3.0)
        assert metrics["total_trades"] == 2
        assert metrics["final_capital"] == pytest.approx(10150.0)

    def test_backtest_response_includes_trade_list(self, seeded_client_full):
        c, run_id = seeded_client_full
        resp = c.get(f"/api/backtest/{run_id}")
        data = resp.json()
        assert "trade_list" in data
        assert isinstance(data["trade_list"], list)
        assert len(data["trade_list"]) == 2
        assert data["trade_list"][0]["id"] == "t1"
        assert data["trade_list"][0]["pnl"] == 50.0
        assert data["trade_list"][1]["direction"] == "SHORT"

    def test_backtest_response_includes_verification(self, seeded_client_full):
        c, run_id = seeded_client_full
        resp = c.get(f"/api/backtest/{run_id}")
        data = resp.json()
        assert "verification" in data
        v = data["verification"]
        assert "valid" in v
        assert "trade_pnl_sum" in v
        assert "equity_delta" in v
        assert "difference" in v
        # trade_pnl_sum = 50 + 100 = 150, equity_delta = 10150 - 10000 = 150
        assert v["trade_pnl_sum"] == 150.0
        assert v["equity_delta"] == 150.0
        assert v["valid"] is True

    def test_backtest_response_includes_monthly_returns(self, seeded_client_full):
        c, run_id = seeded_client_full
        resp = c.get(f"/api/backtest/{run_id}")
        data = resp.json()
        assert "monthly_returns" in data
        assert isinstance(data["monthly_returns"], dict)

    def test_backtest_response_backward_compat_trades(self, seeded_client_full):
        """Ensure 'trades' key still exists for backward compatibility."""
        c, run_id = seeded_client_full
        resp = c.get(f"/api/backtest/{run_id}")
        data = resp.json()
        assert "trades" in data
        assert isinstance(data["trades"], list)


class TestBacktestVerificationEndpoint:
    def test_backtest_verification_valid(self, seeded_client_full):
        """Verify cross-check passes for correct data (PnL sum matches equity delta)."""
        c, run_id = seeded_client_full
        resp = c.get(f"/api/backtest/verify/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["backtest_id"] == run_id
        assert data["overall"] == "PASS"
        assert len(data["checks"]) == 3
        # PnL cross-validation should pass
        pnl_check = data["checks"][0]
        assert pnl_check["name"] == "pnl_cross_validation"
        assert pnl_check["passed"] is True
        # No negative quantities
        qty_check = data["checks"][1]
        assert qty_check["name"] == "no_negative_quantities"
        assert qty_check["passed"] is True
        # SL placement (no SL in trades, so should pass vacuously)
        sl_check = data["checks"][2]
        assert sl_check["name"] == "sl_placement_valid"
        assert sl_check["passed"] is True

    def test_backtest_verification_invalid_pnl(self, api_client, seed_db):
        """Verify detection of mismatched P&L data."""
        run_id = str(uuid4())
        # equity delta = 10200 - 10000 = 200, but trade pnl sum = 50
        equity_curve = json.dumps([
            {"index": 0, "equity": 10000.0},
            {"index": 1, "equity": 10200.0},
        ])
        trades = json.dumps([
            {"id": "t1", "direction": "LONG", "entry_price": 100, "exit_price": 105,
             "quantity": 1.0, "pnl": 50.0, "fees": 1.0, "close_reason": "TP1",
             "holding_periods": 2},
        ])
        seed_db(
            "INSERT INTO backtest_runs (id, strategy_name, symbol, timeframe, "
            "start_date, end_date, initial_capital, total_trades, "
            "equity_curve, trades, status) "
            "VALUES (:id, 'momentum', 'BTC/USDT', '1h', '2024-01-01', '2024-06-01', "
            "10000.0, 1, :equity_curve, :trades, 'COMPLETED')",
            {"id": run_id, "equity_curve": equity_curve, "trades": trades},
        )
        resp = api_client.get(f"/api/backtest/verify/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall"] == "FAIL"
        pnl_check = data["checks"][0]
        assert pnl_check["name"] == "pnl_cross_validation"
        assert pnl_check["passed"] is False
        assert pnl_check["detail"]["difference"] == 150.0

    def test_backtest_verification_negative_quantity(self, api_client, seed_db):
        """Verify detection of negative quantity trades."""
        run_id = str(uuid4())
        equity_curve = json.dumps([
            {"index": 0, "equity": 10000.0},
            {"index": 1, "equity": 10050.0},
        ])
        trades = json.dumps([
            {"id": "bad1", "direction": "LONG", "entry_price": 100,
             "exit_price": 105, "quantity": -0.5, "pnl": 50.0,
             "fees": 1.0, "close_reason": "TP1", "holding_periods": 2},
        ])
        seed_db(
            "INSERT INTO backtest_runs (id, strategy_name, symbol, timeframe, "
            "start_date, end_date, initial_capital, total_trades, "
            "equity_curve, trades, status) "
            "VALUES (:id, 'momentum', 'BTC/USDT', '1h', '2024-01-01', '2024-06-01', "
            "10000.0, 1, :equity_curve, :trades, 'COMPLETED')",
            {"id": run_id, "equity_curve": equity_curve, "trades": trades},
        )
        resp = api_client.get(f"/api/backtest/verify/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        qty_check = data["checks"][1]
        assert qty_check["name"] == "no_negative_quantities"
        assert qty_check["passed"] is False
        assert "bad1" in qty_check["detail"]["negative_qty_trades"]

    def test_backtest_verification_sl_violation(self, api_client, seed_db):
        """Verify detection of SL above entry for LONG trade."""
        run_id = str(uuid4())
        equity_curve = json.dumps([
            {"index": 0, "equity": 10000.0},
            {"index": 1, "equity": 10050.0},
        ])
        trades = json.dumps([
            {"id": "sl_bad", "direction": "LONG", "entry_price": 100.0,
             "exit_price": 105.0, "quantity": 1.0, "pnl": 50.0,
             "stop_loss": 110.0,  # SL above entry for LONG -- violation
             "fees": 1.0, "close_reason": "TP1", "holding_periods": 2},
        ])
        seed_db(
            "INSERT INTO backtest_runs (id, strategy_name, symbol, timeframe, "
            "start_date, end_date, initial_capital, total_trades, "
            "equity_curve, trades, status) "
            "VALUES (:id, 'momentum', 'BTC/USDT', '1h', '2024-01-01', '2024-06-01', "
            "10000.0, 1, :equity_curve, :trades, 'COMPLETED')",
            {"id": run_id, "equity_curve": equity_curve, "trades": trades},
        )
        resp = api_client.get(f"/api/backtest/verify/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        sl_check = data["checks"][2]
        assert sl_check["name"] == "sl_placement_valid"
        assert sl_check["passed"] is False
        assert len(sl_check["detail"]["violations"]) == 1
        assert sl_check["detail"]["violations"][0]["trade_id"] == "sl_bad"

    def test_backtest_verification_not_found(self, api_client):
        resp = api_client.get(f"/api/backtest/verify/{uuid4()}")
        assert resp.status_code == 404
