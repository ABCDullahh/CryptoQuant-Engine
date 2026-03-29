"""Backtesting engine — event-driven simulation against historical candles.

Runs strategies against historical data using the same indicator pipeline,
strategy evaluation, and risk management as live trading.
No look-ahead bias: each candle is processed sequentially.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import numpy as np

from app.backtesting.metrics import PerformanceMetrics, compute_all_metrics
from app.backtesting.simulator import TradeSimulator
from app.config.constants import (
    DEFAULT_SLIPPAGE_BPS,
    Direction,
    StopLossType,
    TAKER_FEE,
    TP1_CLOSE_PCT,
    TP1_RR_RATIO,
    TP2_CLOSE_PCT,
    TP2_RR_RATIO,
    TP3_CLOSE_PCT,
    TP3_RR_RATIO,
)
from app.core.models import (
    BacktestConfig,
    BacktestResult,
    Candle,
    IndicatorValues,
    MarketContext,
    RawSignal,
)
from app.indicators.base import IndicatorPipeline
from app.signals.regime import MarketRegimeDetector
from app.strategies.base import BaseStrategy


class BacktestEngine:
    """Event-driven backtesting engine.

    Processes historical candles sequentially, running strategies and simulating
    trades with realistic slippage and fees. Produces BacktestResult with
    comprehensive performance metrics.
    """

    def __init__(
        self,
        strategies: list[BaseStrategy],
        config: BacktestConfig,
        regime_detector: MarketRegimeDetector | None = None,
    ):
        self.strategies = strategies
        self.config = config
        self.regime_detector = regime_detector or MarketRegimeDetector()
        self._pipeline = IndicatorPipeline()

        self._simulator = TradeSimulator(
            initial_balance=config.initial_capital,
            slippage_bps=config.slippage_bps,
            fee_rate=config.taker_fee,
        )

    def run(self, candles: list[Candle]) -> BacktestResult:
        """Run backtest on historical candles.

        Args:
            candles: List of Candle objects sorted by time ascending.
                     Must have enough history for indicator warm-up.

        Returns:
            BacktestResult with metrics, equity curve, and trade list.
        """
        self._simulator.reset()

        if len(candles) < 2:
            return self._empty_result()

        # Determine minimum lookback needed
        min_candles = max(s.min_candles for s in self.strategies) if self.strategies else 50
        min_candles = max(min_candles, 55)  # At least 55 for EMA55

        dates: list[str] = []

        for i in range(min_candles, len(candles)):
            window = candles[:i + 1]
            current = candles[i]
            dates.append(str(current.time)[:10])

            # 1. Compute indicators on the window
            try:
                indicators = self._pipeline.compute(window)
            except (ValueError, IndexError):
                continue

            # 2. Detect regime
            context = self.regime_detector.detect(window, indicators)

            # 3. Evaluate all strategies
            signals = self._evaluate_strategies(window, indicators, context)

            # 4. Process signals → open positions
            if signals:
                self._process_signals(signals, current, i, indicators, context)

            # 5. Update existing positions with current candle
            self._simulator.process_candle(
                current.symbol,
                current.high,
                current.low,
                current.close,
                time_idx=i,
            )

        # Force-close any remaining open positions at last price
        self._close_remaining(candles)

        return self._build_result(dates)

    def _evaluate_strategies(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
        context: MarketContext,
    ) -> list[RawSignal]:
        """Run all strategies and collect non-None signals."""
        signals = []
        for strategy in self.strategies:
            try:
                if len(candles) >= strategy.min_candles:
                    signal = strategy.evaluate(candles, indicators, context)
                    if signal is not None:
                        signals.append(signal)
            except Exception:
                continue
        return signals

    def _process_signals(
        self,
        signals: list[RawSignal],
        current_candle: Candle,
        time_idx: int,
        indicators: IndicatorValues | None = None,
        context: MarketContext | None = None,
    ) -> None:
        """Process raw signals — filter for agreement and open positions."""
        # Count direction agreement
        directions = [s.direction for s in signals]
        long_count = directions.count(Direction.LONG)
        short_count = directions.count(Direction.SHORT)

        # Need at least 2 strategies agreeing (relaxed for backtest)
        min_agree = min(2, len(self.strategies))

        direction = None
        if long_count >= min_agree:
            direction = Direction.LONG
        elif short_count >= min_agree:
            direction = Direction.SHORT

        if direction is None:
            return

        # Already have max positions?
        if len(self._simulator.positions) >= self.config.max_positions:
            return

        # Calculate entry, SL, TPs
        entry_price = current_candle.close
        risk_amount = self._simulator.balance * self.config.risk_per_trade

        # Use ATR-based SL (same logic as live trading) when indicators available
        atr = getattr(indicators, "atr_14", None) if indicators else None
        if atr and atr > 0:
            from app.signals.aggregator import SignalAggregator
            regime = context.regime if context else None
            sl, _ = SignalAggregator._calculate_stop_loss(
                [current_candle], direction, atr, regime=regime,
            )
            sl_distance = abs(entry_price - sl)
        else:
            # Fallback: percentage-based SL using risk_per_trade config
            sl_distance = entry_price * self.config.risk_per_trade

        if direction == Direction.LONG:
            stop_loss = entry_price - sl_distance
            tp1 = entry_price + sl_distance * TP1_RR_RATIO
            tp2 = entry_price + sl_distance * TP2_RR_RATIO
            tp3 = entry_price + sl_distance * TP3_RR_RATIO
        else:
            stop_loss = entry_price + sl_distance
            tp1 = entry_price - sl_distance * TP1_RR_RATIO
            tp2 = entry_price - sl_distance * TP2_RR_RATIO
            tp3 = entry_price - sl_distance * TP3_RR_RATIO

        # Position size based on risk
        if sl_distance > 0:
            quantity = risk_amount / sl_distance
        else:
            return

        take_profits = [
            (tp1, TP1_CLOSE_PCT),
            (tp2, TP2_CLOSE_PCT),
            (tp3, TP3_CLOSE_PCT),
        ]

        self._simulator.open_position(
            symbol=current_candle.symbol,
            direction=direction,
            price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profits=take_profits,
            time_idx=time_idx,
        )

    def _close_remaining(self, candles: list[Candle]) -> None:
        """Force-close all remaining open positions at last candle's close."""
        if not candles:
            return
        last = candles[-1]
        remaining = list(self._simulator.positions.values())
        for pos in remaining:
            self._simulator._close_position(
                pos, last.close, len(candles) - 1, "END_OF_BACKTEST",
            )

    def _build_result(self, dates: list[str]) -> BacktestResult:
        """Build BacktestResult from simulator state."""
        equity = self._simulator.get_equity_curve()
        pnls = self._simulator.get_trade_pnls()
        durations = self._simulator.get_trade_durations()

        metrics = compute_all_metrics(
            equity_curve=equity,
            trade_pnls=pnls,
            trade_durations=durations,
            dates=dates if dates else None,
            initial_capital=self.config.initial_capital,
        )

        # Build trade list dicts
        trade_list = []
        for t in self._simulator.closed_trades:
            trade_list.append({
                "id": t.id,
                "direction": str(t.direction),
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "quantity": t.quantity,
                "pnl": t.net_pnl,
                "fees": t.fees,
                "close_reason": t.close_reason,
                "holding_periods": t.holding_periods,
            })

        # Build equity curve dicts
        eq_dicts = []
        for i, val in enumerate(equity):
            eq_dicts.append({"index": i, "equity": val})

        return BacktestResult(
            config=self.config,
            total_return=metrics.total_return,
            annual_return=metrics.annual_return,
            sharpe_ratio=metrics.sharpe_ratio,
            sortino_ratio=metrics.sortino_ratio,
            max_drawdown=metrics.max_drawdown,
            win_rate=metrics.win_rate,
            profit_factor=metrics.profit_factor,
            total_trades=metrics.total_trades,
            avg_holding_period=f"{metrics.avg_holding_periods:.1f} candles",
            expectancy=metrics.expectancy,
            avg_win=metrics.avg_win,
            avg_loss=metrics.avg_loss,
            calmar_ratio=metrics.calmar_ratio,
            equity_curve=eq_dicts,
            trades=trade_list,
            monthly_returns=metrics.monthly_returns,
        )

    def _empty_result(self) -> BacktestResult:
        """Return empty result for edge cases."""
        return BacktestResult(config=self.config)
