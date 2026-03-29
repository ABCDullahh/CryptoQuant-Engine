"""Tests for backtest report generator."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pytest

from app.backtesting.monte_carlo import MonteCarloResult
from app.backtesting.report import BacktestReport
from app.backtesting.walk_forward import WalkForwardResult, WFWindow
from app.core.models import BacktestConfig, BacktestResult


@pytest.fixture
def config():
    return BacktestConfig(
        strategy_name="momentum", symbol="BTC/USDT", timeframe="1h",
        start_date=datetime(2024, 1, 1, tzinfo=UTC),
        end_date=datetime(2024, 2, 1, tzinfo=UTC),
        initial_capital=10000.0,
    )


@pytest.fixture
def bt_result(config):
    return BacktestResult(
        config=config,
        total_return=0.15,
        annual_return=0.80,
        sharpe_ratio=1.8,
        sortino_ratio=2.5,
        max_drawdown=0.08,
        win_rate=0.55,
        profit_factor=1.65,
        total_trades=42,
        expectancy=35.0,
        avg_holding_period="12.5 candles",
        equity_curve=[
            {"index": 0, "equity": 10000},
            {"index": 1, "equity": 10200},
            {"index": 2, "equity": 10500},
            {"index": 3, "equity": 10300},
            {"index": 4, "equity": 11500},
        ],
        trades=[
            {"id": "t1", "direction": "LONG", "entry_price": 40000,
             "exit_price": 41000, "pnl": 100, "fees": 5, "close_reason": "TP1_HIT"},
            {"id": "t2", "direction": "SHORT", "entry_price": 41000,
             "exit_price": 41500, "pnl": -50, "fees": 5, "close_reason": "SL_HIT"},
        ],
        monthly_returns={"2024-01": 0.10, "2024-02": 0.05},
    )


@pytest.fixture
def mc_result():
    return MonteCarloResult(
        n_simulations=1000, n_trades=42,
        mean_return=0.14, median_return=0.13,
        return_ci_5=0.02, return_ci_95=0.28,
        mean_max_drawdown=0.06, worst_drawdown_95=0.12, worst_drawdown_99=0.18,
        mean_sharpe=1.7, sharpe_ci_5=0.8, sharpe_ci_95=2.6,
        prob_of_profit=0.92, prob_of_ruin=0.01,
    )


@pytest.fixture
def wf_result():
    return WalkForwardResult(
        windows=[
            WFWindow(window_id=0, in_sample_start=0, in_sample_end=100,
                     oos_start=100, oos_end=150, in_sample_sharpe=2.0,
                     oos_sharpe=1.5, oos_return=0.05, efficiency_ratio=0.75),
            WFWindow(window_id=1, in_sample_start=50, in_sample_end=150,
                     oos_start=150, oos_end=200, in_sample_sharpe=1.8,
                     oos_sharpe=1.2, oos_return=0.03, efficiency_ratio=0.67),
        ],
        avg_oos_return=0.04,
        avg_oos_sharpe=1.35,
        avg_efficiency_ratio=0.71,
        consistency_score=1.0,
        total_candles=200,
        n_windows=2,
    )


class TestReportGenerate:
    def test_basic_report(self, bt_result):
        report = BacktestReport(bt_result)
        data = report.generate()
        assert "config" in data
        assert "summary" in data
        assert "equity_curve" in data
        assert "drawdown" in data
        assert "trades" in data
        assert "monthly_returns" in data
        assert "generated_at" in data

    def test_config_section(self, bt_result):
        report = BacktestReport(bt_result)
        data = report.generate()
        cfg = data["config"]
        assert cfg["strategy"] == "momentum"
        assert cfg["symbol"] == "BTC/USDT"
        assert cfg["initial_capital"] == 10000.0

    def test_summary_section(self, bt_result):
        report = BacktestReport(bt_result)
        data = report.generate()
        s = data["summary"]
        assert s["total_return_pct"] == 15.0
        assert s["sharpe_ratio"] == 1.8
        assert s["total_trades"] == 42
        assert s["win_rate_pct"] == 55.0

    def test_equity_curve_section(self, bt_result):
        report = BacktestReport(bt_result)
        data = report.generate()
        eq = data["equity_curve"]
        assert len(eq) == 5
        assert eq[0]["equity"] == 10000

    def test_drawdown_section(self, bt_result):
        report = BacktestReport(bt_result)
        data = report.generate()
        dd = data["drawdown"]
        assert dd["max_drawdown_pct"] == 8.0
        assert len(dd["drawdown_series"]) > 0

    def test_trades_section(self, bt_result):
        report = BacktestReport(bt_result)
        data = report.generate()
        t = data["trades"]
        assert t["count"] == 2
        assert t["winners"] == 1
        assert t["losers"] == 1

    def test_monthly_returns(self, bt_result):
        report = BacktestReport(bt_result)
        data = report.generate()
        m = data["monthly_returns"]
        assert len(m["months"]) == 2


class TestMonteCarlo:
    def test_mc_included(self, bt_result, mc_result):
        report = BacktestReport(bt_result, monte_carlo=mc_result)
        data = report.generate()
        assert "monte_carlo" in data
        mc = data["monte_carlo"]
        assert mc["n_simulations"] == 1000
        assert mc["prob_of_profit_pct"] == 92.0

    def test_mc_not_included(self, bt_result):
        report = BacktestReport(bt_result)
        data = report.generate()
        assert "monte_carlo" not in data


class TestWalkForward:
    def test_wf_included(self, bt_result, wf_result):
        report = BacktestReport(bt_result, walk_forward=wf_result)
        data = report.generate()
        assert "walk_forward" in data
        wf = data["walk_forward"]
        assert wf["n_windows"] == 2
        assert wf["consistency_score_pct"] == 100.0

    def test_wf_not_included(self, bt_result):
        report = BacktestReport(bt_result)
        data = report.generate()
        assert "walk_forward" not in data


class TestJSON:
    def test_to_json(self, bt_result):
        report = BacktestReport(bt_result)
        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert "summary" in parsed

    def test_save(self, bt_result, tmp_path):
        report = BacktestReport(bt_result)
        path = tmp_path / "report.json"
        result_path = report.save(path)
        assert result_path.exists()
        content = json.loads(result_path.read_text())
        assert "config" in content


class TestEdgeCases:
    def test_empty_equity_curve(self, config):
        bt = BacktestResult(config=config, equity_curve=[])
        report = BacktestReport(bt)
        data = report.generate()
        assert data["drawdown"]["max_drawdown_pct"] == 0

    def test_no_trades(self, config):
        bt = BacktestResult(config=config, trades=[])
        report = BacktestReport(bt)
        data = report.generate()
        assert data["trades"]["count"] == 0

    def test_full_report_with_all(self, bt_result, mc_result, wf_result):
        report = BacktestReport(bt_result, mc_result, wf_result)
        data = report.generate()
        assert "monte_carlo" in data
        assert "walk_forward" in data
        assert data["summary"]["total_trades"] == 42
