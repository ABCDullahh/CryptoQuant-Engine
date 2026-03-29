"""Phase 4 Integration Tests - Risk management end-to-end flow."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import numpy as np
import pytest

from app.config.constants import (
    Direction,
    MarketRegime,
    SignalGrade,
    StopLossType,
    CircuitBreakerState,
)
from app.core.models import (
    Candle,
    CompositeSignal,
    MarketContext,
    Position,
    PositionSize,
    RiskReward,
    TakeProfit,
)
from app.risk import (
    CircuitBreaker,
    PortfolioRiskManager,
    PositionSizer,
    RiskEvaluator,
    StopLossManager,
)


def _make_signal(
    direction: Direction = Direction.LONG,
    entry: float = 43200.0,
    stop_loss: float = 42900.0,
    quantity: float = 0.667,
) -> CompositeSignal:
    return CompositeSignal(
        symbol="BTC/USDT",
        direction=direction,
        grade=SignalGrade.B,
        strength=0.70,
        entry_price=entry,
        entry_zone=(entry - 100, entry + 100),
        stop_loss=stop_loss,
        sl_type=StopLossType.ATR_BASED,
        take_profits=[
            TakeProfit(level="TP1", price=43650.0, close_pct=50, rr_ratio=1.5),
            TakeProfit(level="TP2", price=44100.0, close_pct=30, rr_ratio=3.0),
            TakeProfit(level="TP3", price=44700.0, close_pct=20, rr_ratio=5.0),
        ],
        risk_reward=RiskReward(rr_tp1=1.5, rr_tp2=3.0, rr_tp3=5.0, weighted_rr=2.65),
        position_size=PositionSize(
            quantity=quantity, notional=quantity * entry,
            margin=quantity * entry / 3,
            risk_amount=200.0, risk_pct=0.02, leverage=3,
        ),
        strategy_scores={"momentum": 0.8, "smc": 0.7, "volume": 0.6},
        market_context=MarketContext(),
    )


def _make_candles(n: int = 30) -> list[Candle]:
    np.random.seed(42)
    candles = []
    price = 43000.0
    for i in range(n):
        price += np.random.randn() * 30
        candles.append(Candle(
            time=datetime(2024, 1, 1, i % 24, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=price - 10, high=price + 30, low=price - 30, close=price,
            volume=100.0,
        ))
    return candles


class TestPositionSizerToEvaluator:
    def test_fixed_fractional_feeds_evaluator(self):
        """PositionSizer output feeds into RiskEvaluator."""
        ps = PositionSizer.fixed_fractional(
            entry=43200.0, stop_loss=42900.0, balance=100000.0,
        )
        signal = _make_signal()
        signal = signal.model_copy(update={"position_size": ps})

        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        evaluator = RiskEvaluator(portfolio=portfolio)
        result = evaluator.evaluate(signal)
        assert result.approved is True
        assert result.signal.position_size.risk_pct == 0.02

    def test_volatility_based_feeds_evaluator(self):
        ps = PositionSizer.volatility_based(
            entry=43200.0, atr=200.0, balance=100000.0,
            regime=MarketRegime.TRENDING_UP,
        )
        signal = _make_signal()
        signal = signal.model_copy(update={"position_size": ps})

        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        evaluator = RiskEvaluator(portfolio=portfolio)
        result = evaluator.evaluate(signal)
        assert result.approved is True


class TestStopLossToSignal:
    def test_combined_sl_with_regime(self):
        """StopLossManager combined method produces valid SL for signal."""
        candles = _make_candles(30)
        sl, sl_type = StopLossManager.combined(
            entry=43200.0, direction=Direction.LONG,
            candles=candles, atr=200.0,
            regime=MarketRegime.RANGING,
        )
        assert sl < 43200.0  # Below entry for LONG
        assert sl_type == StopLossType.COMBINED

    def test_trailing_stop_after_tp1(self):
        """After TP1 hit, move SL to breakeven then use trailing."""
        entry = 43200.0
        current_sl = 42900.0

        # TP1 hit → move to breakeven
        new_sl = StopLossManager.should_move_to_breakeven(
            entry=entry, current_sl=current_sl,
            direction=Direction.LONG, tp1_hit=True,
        )
        assert new_sl == entry

        # Price moved up → trailing stop
        ts = StopLossManager.trailing_stop(
            current_price=44000.0, direction=Direction.LONG,
            highest_since_entry=44500.0, lowest_since_entry=43000.0,
            atr=200.0,
        )
        assert ts > entry  # Trailing above entry = profit locked in


class TestCircuitBreakerToEvaluator:
    def test_cb_blocks_signal(self):
        """Circuit breaker OPEN blocks all signals."""
        portfolio = PortfolioRiskManager(initial_balance=10000.0)
        cb = CircuitBreaker()
        cb.check_triggers(daily_loss_pct=0.06)
        evaluator = RiskEvaluator(portfolio=portfolio, circuit_breaker=cb)

        result = evaluator.evaluate(_make_signal())
        assert result.approved is False
        assert cb.state == CircuitBreakerState.OPEN

    def test_cb_reduce_shrinks_position(self):
        """Circuit breaker REDUCE_50 halves position size."""
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        cb = CircuitBreaker()
        cb.check_triggers(consecutive_losses=3)
        evaluator = RiskEvaluator(portfolio=portfolio, circuit_breaker=cb)

        signal = _make_signal(quantity=1.0)
        result = evaluator.evaluate(signal)
        assert result.approved is True
        assert result.signal.position_size.quantity == pytest.approx(0.5)


class TestPortfolioLimitsIntegration:
    def test_max_positions_enforced(self):
        """Can't exceed max positions."""
        portfolio = PortfolioRiskManager(initial_balance=100000.0, max_positions=1)
        portfolio.add_position(Position(
            signal_id=uuid4(), symbol="BTC/USDT", direction=Direction.LONG,
            entry_price=43200.0, quantity=0.5, remaining_qty=0.5,
            leverage=3, stop_loss=42900.0,
        ))
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = evaluator.evaluate(_make_signal())
        assert result.approved is False

    def test_drawdown_auto_rejects(self):
        """20% drawdown → auto-reject all signals."""
        portfolio = PortfolioRiskManager(initial_balance=10000.0)
        portfolio.record_trade_result(-2000.0)
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = evaluator.evaluate(_make_signal())
        assert result.approved is False


class TestFullRiskFlow:
    @patch("app.risk.evaluator.event_bus")
    async def test_end_to_end_approve_and_publish(self, mock_bus):
        """Complete flow: Signal → RiskEvaluator → approve → publish."""
        mock_bus.publish = AsyncMock()
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        evaluator = RiskEvaluator(portfolio=portfolio)

        signal = _make_signal()
        result = await evaluator.evaluate_and_publish(signal)

        assert result.approved is True
        mock_bus.publish.assert_called_once()
        channel = mock_bus.publish.call_args[0][0]
        assert channel == "signal.approved"

    @patch("app.risk.evaluator.event_bus")
    async def test_end_to_end_reject_and_alert(self, mock_bus):
        """Complete flow: Signal → RiskEvaluator → reject → alert."""
        mock_bus.publish = AsyncMock()
        portfolio = PortfolioRiskManager(initial_balance=10000.0)
        portfolio.record_trade_result(-2000.0)
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = await evaluator.evaluate_and_publish(_make_signal())

        assert result.approved is False
        mock_bus.publish.assert_called_once()
        channel = mock_bus.publish.call_args[0][0]
        assert channel == "risk.alert"


class TestPhase1ModelsInRisk:
    def test_portfolio_state_model(self):
        """Phase 1 PortfolioState model populated by risk manager."""
        portfolio = PortfolioRiskManager(initial_balance=10000.0)
        portfolio.record_trade_result(500.0)
        portfolio.record_trade_result(-200.0)

        state = portfolio.get_state()
        assert state.balance == 10300.0
        assert state.consecutive_losses == 1
        assert state.max_drawdown > 0

    def test_position_model_in_portfolio(self):
        """Phase 1 Position model works with portfolio manager."""
        portfolio = PortfolioRiskManager(initial_balance=10000.0)
        pos = Position(
            signal_id=uuid4(), symbol="BTC/USDT",
            direction=Direction.LONG,
            entry_price=43200.0, quantity=0.5, remaining_qty=0.5,
            leverage=3, stop_loss=42900.0,
        )
        portfolio.add_position(pos)
        assert portfolio.calculate_heat() > 0
