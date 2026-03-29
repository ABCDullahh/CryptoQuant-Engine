"""Tests for backtesting performance metrics calculator."""

from __future__ import annotations

import numpy as np
import pytest

from app.backtesting.metrics import (
    PerformanceMetrics,
    calc_annual_return,
    calc_calmar_ratio,
    calc_common_sense_ratio,
    calc_drawdown_series,
    calc_expectancy,
    calc_max_drawdown,
    calc_max_drawdown_duration,
    calc_monthly_returns,
    calc_profit_factor,
    calc_recovery_factor,
    calc_returns_from_equity,
    calc_sharpe_ratio,
    calc_sortino_ratio,
    calc_tail_ratio,
    calc_total_return,
    calc_ulcer_index,
    calc_win_rate,
    compute_all_metrics,
)


class TestTotalReturn:
    def test_positive_return(self):
        eq = np.array([10000, 10500, 11000, 12000])
        assert calc_total_return(eq) == pytest.approx(0.20)

    def test_negative_return(self):
        eq = np.array([10000, 9500, 9000, 8000])
        assert calc_total_return(eq) == pytest.approx(-0.20)

    def test_zero_start(self):
        eq = np.array([0, 100])
        assert calc_total_return(eq) == 0.0

    def test_single_value(self):
        assert calc_total_return(np.array([10000])) == 0.0

    def test_empty(self):
        assert calc_total_return(np.array([])) == 0.0


class TestAnnualReturn:
    def test_one_year_exact(self):
        assert calc_annual_return(0.20, 365, 365) == pytest.approx(0.20)

    def test_half_year(self):
        result = calc_annual_return(0.10, 182, 365)
        assert result > 0.10  # Annualized should be higher

    def test_zero_periods(self):
        assert calc_annual_return(0.10, 0) == 0.0

    def test_total_loss(self):
        assert calc_annual_return(-1.0, 365) == -1.0


class TestDrawdown:
    def test_drawdown_series(self):
        eq = np.array([100, 110, 105, 120, 90])
        dd = calc_drawdown_series(eq)
        assert dd[0] == 0.0
        assert dd[1] == 0.0  # New high
        assert dd[2] == pytest.approx(-5 / 110)
        assert dd[3] == 0.0  # New high
        assert dd[4] == pytest.approx(-30 / 120)

    def test_max_drawdown(self):
        eq = np.array([100, 110, 105, 120, 90, 100])
        assert calc_max_drawdown(eq) == pytest.approx(30 / 120)

    def test_no_drawdown(self):
        eq = np.array([100, 110, 120, 130])
        assert calc_max_drawdown(eq) == 0.0

    def test_max_drawdown_duration(self):
        eq = np.array([100, 110, 105, 100, 95, 120])  # DD from period 2-4 (3 periods)
        dur = calc_max_drawdown_duration(eq)
        assert dur == 3


class TestSharpeRatio:
    def test_positive_sharpe(self):
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.01, 365)
        sharpe = calc_sharpe_ratio(returns, periods_per_year=365)
        assert sharpe > 0

    def test_zero_std(self):
        returns = np.ones(100) * 0.01
        assert calc_sharpe_ratio(returns) == 0.0

    def test_too_few_returns(self):
        assert calc_sharpe_ratio(np.array([0.01])) == 0.0


class TestSortinoRatio:
    def test_positive_sortino(self):
        np.random.seed(42)
        returns = np.random.normal(0.002, 0.01, 365)
        sortino = calc_sortino_ratio(returns, periods_per_year=365)
        assert sortino > 0

    def test_no_downside(self):
        returns = np.abs(np.random.normal(0.01, 0.005, 100))
        assert calc_sortino_ratio(returns) == 0.0  # No downside deviation possible

    def test_sortino_higher_than_sharpe(self):
        """Sortino should typically be >= Sharpe for asymmetric returns."""
        np.random.seed(42)
        returns = np.random.normal(0.002, 0.01, 365)
        sharpe = calc_sharpe_ratio(returns, periods_per_year=365)
        sortino = calc_sortino_ratio(returns, periods_per_year=365)
        assert sortino >= sharpe * 0.8  # Allow some tolerance


class TestCalmarRatio:
    def test_basic(self):
        assert calc_calmar_ratio(0.30, 0.10) == pytest.approx(3.0)

    def test_zero_drawdown(self):
        assert calc_calmar_ratio(0.30, 0.0) == 0.0


class TestTradeMetrics:
    def test_win_rate(self):
        pnls = np.array([100, -50, 200, -30, 150])
        assert calc_win_rate(pnls) == pytest.approx(0.60)

    def test_win_rate_all_wins(self):
        pnls = np.array([100, 200, 300])
        assert calc_win_rate(pnls) == pytest.approx(1.0)

    def test_win_rate_empty(self):
        assert calc_win_rate(np.array([])) == 0.0

    def test_profit_factor(self):
        pnls = np.array([100, -50, 200, -30, 150])
        pf = calc_profit_factor(pnls)
        assert pf == pytest.approx(450 / 80)

    def test_profit_factor_no_losses(self):
        pnls = np.array([100, 200])
        assert calc_profit_factor(pnls) == float("inf")

    def test_profit_factor_empty(self):
        assert calc_profit_factor(np.array([])) == 0.0

    def test_expectancy(self):
        pnls = np.array([100, -50, 200])
        assert calc_expectancy(pnls) == pytest.approx(250 / 3)


class TestRecoveryAndUlcer:
    def test_recovery_factor(self):
        assert calc_recovery_factor(5000.0, 2000.0) == pytest.approx(2.5)

    def test_recovery_zero_dd(self):
        assert calc_recovery_factor(5000.0, 0.0) == 0.0

    def test_ulcer_index_no_drawdown(self):
        eq = np.array([100, 110, 120, 130])
        assert calc_ulcer_index(eq) == 0.0

    def test_ulcer_index_with_drawdown(self):
        eq = np.array([100, 110, 100, 90, 100, 110])
        ui = calc_ulcer_index(eq)
        assert ui > 0


class TestTailAndCSR:
    def test_tail_ratio(self):
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.01, 200)
        tail = calc_tail_ratio(returns)
        assert tail > 0

    def test_tail_ratio_insufficient_data(self):
        assert calc_tail_ratio(np.array([0.01] * 10)) == 0.0

    def test_common_sense_ratio(self):
        assert calc_common_sense_ratio(2.0, 1.5) == pytest.approx(3.0)


class TestReturnsFromEquity:
    def test_basic(self):
        eq = np.array([100, 110, 105])
        ret = calc_returns_from_equity(eq)
        assert len(ret) == 2
        assert ret[0] == pytest.approx(0.10)
        assert ret[1] == pytest.approx(-5 / 110)

    def test_empty(self):
        assert len(calc_returns_from_equity(np.array([100]))) == 0


class TestMonthlyReturns:
    def test_two_months(self):
        dates = ["2024-01-01", "2024-01-15", "2024-02-01", "2024-02-15"]
        eq = np.array([10000, 10500, 10200, 10800])
        monthly = calc_monthly_returns(eq, dates)
        assert "2024-01" in monthly
        assert "2024-02" in monthly

    def test_empty(self):
        assert calc_monthly_returns(np.array([]), []) == {}


class TestComputeAll:
    def test_full_computation(self):
        eq = np.array([10000, 10200, 10500, 10300, 10800, 11000, 10700, 11200])
        pnls = np.array([200, 300, -200, 500, 200, -300, 500])
        durations = np.array([5, 3, 2, 8, 4, 1, 6])

        metrics = compute_all_metrics(eq, pnls, durations, initial_capital=10000)
        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_return == pytest.approx(0.12)
        assert metrics.total_trades == 7
        assert metrics.winning_trades == 5
        assert metrics.losing_trades == 2
        assert metrics.win_rate == pytest.approx(5 / 7)
        assert metrics.avg_holding_periods == pytest.approx(29 / 7)
        assert metrics.final_equity == 11200.0
        assert metrics.max_drawdown > 0

    def test_no_trades(self):
        eq = np.array([10000, 10000, 10000])
        pnls = np.array([])
        metrics = compute_all_metrics(eq, pnls)
        assert metrics.total_trades == 0
        assert metrics.total_return == 0.0
