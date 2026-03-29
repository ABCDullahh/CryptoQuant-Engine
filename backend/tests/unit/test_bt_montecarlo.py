"""Tests for Monte Carlo simulation."""

from __future__ import annotations

import numpy as np
import pytest

from app.backtesting.monte_carlo import MonteCarloResult, MonteCarloSimulator


@pytest.fixture
def simulator():
    return MonteCarloSimulator(n_simulations=500, seed=42)


class TestMonteCarloInit:
    def test_defaults(self):
        mc = MonteCarloSimulator()
        assert mc.n_simulations == 1000
        assert mc.ruin_threshold == 0.50

    def test_custom(self):
        mc = MonteCarloSimulator(n_simulations=200, ruin_threshold=0.30)
        assert mc.n_simulations == 200
        assert mc.ruin_threshold == 0.30


class TestSimulate:
    def test_empty_trades(self, simulator):
        result = simulator.simulate(np.array([]))
        assert result.n_simulations == 0
        assert result.n_trades == 0

    def test_single_trade(self, simulator):
        result = simulator.simulate(np.array([100.0]))
        assert result.n_simulations == 0

    def test_basic_simulation(self, simulator):
        pnls = np.array([100, -50, 200, -30, 150, -80, 120, -40, 90, -20])
        result = simulator.simulate(pnls, initial_capital=10000.0)
        assert result.n_simulations == 500
        assert result.n_trades == 10
        assert isinstance(result.mean_return, float)
        assert isinstance(result.median_return, float)

    def test_return_confidence_intervals(self, simulator):
        pnls = np.array([100, -50, 200, -30, 150, -80, 120, -40, 90, -20])
        result = simulator.simulate(pnls, initial_capital=10000.0)
        # CI order: 5th < 25th < median < 75th < 95th
        assert result.return_ci_5 <= result.return_ci_25
        assert result.return_ci_25 <= result.median_return
        assert result.median_return <= result.return_ci_75
        assert result.return_ci_75 <= result.return_ci_95

    def test_drawdown_metrics(self, simulator):
        pnls = np.array([100, -50, 200, -30, 150, -80, 120, -40, 90, -20])
        result = simulator.simulate(pnls, initial_capital=10000.0)
        assert result.mean_max_drawdown >= 0
        assert result.worst_drawdown_95 >= result.mean_max_drawdown
        assert result.worst_drawdown_99 >= result.worst_drawdown_95

    def test_prob_of_profit(self, simulator):
        # Net-positive trades → high probability of profit
        pnls = np.array([100, 200, 150, -50, -30, 120, 80, -20, 90, 60])
        result = simulator.simulate(pnls, initial_capital=10000.0)
        assert result.prob_of_profit > 0.5

    def test_prob_of_ruin_low_for_good_trades(self, simulator):
        # Small trades relative to capital → low ruin probability
        pnls = np.array([10, -5, 20, -3, 15, -8, 12, -4, 9, -2])
        result = simulator.simulate(pnls, initial_capital=10000.0)
        assert result.prob_of_ruin < 0.01  # Very unlikely to lose 50% with small trades


class TestDistributions:
    def test_return_distribution_shape(self, simulator):
        pnls = np.array([100, -50, 200, -30, 150])
        result = simulator.simulate(pnls, initial_capital=10000.0)
        assert len(result.return_distribution) == 500

    def test_drawdown_distribution_shape(self, simulator):
        pnls = np.array([100, -50, 200, -30, 150])
        result = simulator.simulate(pnls, initial_capital=10000.0)
        assert len(result.drawdown_distribution) == 500

    def test_all_drawdowns_non_negative(self, simulator):
        pnls = np.array([100, -50, 200, -30, 150, -80])
        result = simulator.simulate(pnls, initial_capital=10000.0)
        assert np.all(result.drawdown_distribution >= 0)


class TestSharpeDistribution:
    def test_sharpe_bounds(self, simulator):
        pnls = np.array([100, -50, 200, -30, 150, -80, 120])
        result = simulator.simulate(pnls, initial_capital=10000.0)
        assert result.sharpe_ci_5 <= result.mean_sharpe
        assert result.mean_sharpe <= result.sharpe_ci_95


class TestReproducibility:
    def test_same_seed_same_result(self):
        pnls = np.array([100, -50, 200, -30, 150])
        mc1 = MonteCarloSimulator(n_simulations=100, seed=123)
        mc2 = MonteCarloSimulator(n_simulations=100, seed=123)
        r1 = mc1.simulate(pnls)
        r2 = mc2.simulate(pnls)
        assert r1.mean_return == pytest.approx(r2.mean_return)

    def test_different_seed_different_drawdowns(self):
        pnls = np.array([100, -50, 200, -30, 150, -80, 120, -60, 90, -40])
        mc1 = MonteCarloSimulator(n_simulations=200, seed=123)
        mc2 = MonteCarloSimulator(n_simulations=200, seed=456)
        r1 = mc1.simulate(pnls)
        r2 = mc2.simulate(pnls)
        # Drawdowns depend on order, so distributions should differ
        assert not np.array_equal(r1.drawdown_distribution, r2.drawdown_distribution)
