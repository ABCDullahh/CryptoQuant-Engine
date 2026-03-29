"""Monte Carlo simulation for backtesting robustness analysis.

Randomizes trade sequences to estimate:
- Confidence intervals for returns and drawdowns
- Worst-case drawdown at 95% confidence
- Probability of ruin (losing X% of capital)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.backtesting.metrics import calc_max_drawdown, calc_sharpe_ratio


@dataclass
class MonteCarloResult:
    """Results of Monte Carlo simulation."""

    n_simulations: int = 0
    n_trades: int = 0

    # Return distribution
    mean_return: float = 0.0
    median_return: float = 0.0
    return_ci_5: float = 0.0   # 5th percentile
    return_ci_25: float = 0.0  # 25th percentile
    return_ci_75: float = 0.0
    return_ci_95: float = 0.0  # 95th percentile

    # Drawdown distribution
    mean_max_drawdown: float = 0.0
    median_max_drawdown: float = 0.0
    worst_drawdown_95: float = 0.0  # 95th percentile worst DD
    worst_drawdown_99: float = 0.0  # 99th percentile worst DD

    # Sharpe distribution
    mean_sharpe: float = 0.0
    sharpe_ci_5: float = 0.0
    sharpe_ci_95: float = 0.0

    # Risk metrics
    prob_of_profit: float = 0.0     # P(return > 0)
    prob_of_ruin: float = 0.0       # P(drawdown > ruin_threshold)
    ruin_threshold: float = 0.50    # Default: 50% loss = ruin

    # Raw distribution arrays (for histograms)
    return_distribution: np.ndarray = field(default_factory=lambda: np.array([]))
    drawdown_distribution: np.ndarray = field(default_factory=lambda: np.array([]))


class MonteCarloSimulator:
    """Monte Carlo trade-sequence randomizer.

    Takes the list of trade P&Ls from a backtest and reshuffles them
    many times to estimate the distribution of outcomes.
    """

    def __init__(
        self,
        n_simulations: int = 1000,
        ruin_threshold: float = 0.50,
        seed: int | None = None,
    ):
        self.n_simulations = n_simulations
        self.ruin_threshold = ruin_threshold
        self._rng = np.random.default_rng(seed)

    def simulate(
        self,
        trade_pnls: np.ndarray,
        initial_capital: float = 10000.0,
    ) -> MonteCarloResult:
        """Run Monte Carlo simulation by shuffling trade order.

        Args:
            trade_pnls: Array of P&L values for each trade.
            initial_capital: Starting capital.

        Returns:
            MonteCarloResult with distribution statistics.
        """
        trade_pnls = np.asarray(trade_pnls, dtype=np.float64)
        n_trades = len(trade_pnls)

        if n_trades < 2:
            return MonteCarloResult(
                n_simulations=0,
                n_trades=n_trades,
                ruin_threshold=self.ruin_threshold,
            )

        returns = np.zeros(self.n_simulations)
        max_drawdowns = np.zeros(self.n_simulations)
        sharpes = np.zeros(self.n_simulations)

        for i in range(self.n_simulations):
            # Shuffle trade order
            shuffled = self._rng.permutation(trade_pnls)

            # Build equity curve from shuffled trades
            equity = np.empty(n_trades + 1)
            equity[0] = initial_capital
            for j, pnl in enumerate(shuffled):
                equity[j + 1] = equity[j] + pnl

            # Calculate metrics for this simulation
            total_ret = (equity[-1] - initial_capital) / initial_capital
            returns[i] = total_ret
            max_drawdowns[i] = calc_max_drawdown(equity)

            # Period returns for Sharpe
            period_returns = np.diff(equity) / equity[:-1]
            period_returns = np.nan_to_num(period_returns, nan=0.0)
            sharpes[i] = calc_sharpe_ratio(period_returns, periods_per_year=365)

        prob_profit = float(np.mean(returns > 0))
        prob_ruin = float(np.mean(max_drawdowns > self.ruin_threshold))

        return MonteCarloResult(
            n_simulations=self.n_simulations,
            n_trades=n_trades,
            mean_return=float(np.mean(returns)),
            median_return=float(np.median(returns)),
            return_ci_5=float(np.percentile(returns, 5)),
            return_ci_25=float(np.percentile(returns, 25)),
            return_ci_75=float(np.percentile(returns, 75)),
            return_ci_95=float(np.percentile(returns, 95)),
            mean_max_drawdown=float(np.mean(max_drawdowns)),
            median_max_drawdown=float(np.median(max_drawdowns)),
            worst_drawdown_95=float(np.percentile(max_drawdowns, 95)),
            worst_drawdown_99=float(np.percentile(max_drawdowns, 99)),
            mean_sharpe=float(np.mean(sharpes)),
            sharpe_ci_5=float(np.percentile(sharpes, 5)),
            sharpe_ci_95=float(np.percentile(sharpes, 95)),
            prob_of_profit=prob_profit,
            prob_of_ruin=prob_ruin,
            ruin_threshold=self.ruin_threshold,
            return_distribution=returns,
            drawdown_distribution=max_drawdowns,
        )
