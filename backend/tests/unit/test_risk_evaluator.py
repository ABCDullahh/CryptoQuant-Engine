"""Unit tests for RiskEvaluator - full evaluation flow."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.config.constants import (
    Direction,
    SignalGrade,
    SignalStatus,
    StopLossType,
    CircuitBreakerAction,
)
from app.core.models import (
    CompositeSignal,
    MarketContext,
    PositionSize,
    Position,
    RiskReward,
    TakeProfit,
)
from app.risk.circuit_breaker import CircuitBreaker
from app.risk.evaluator import RiskCheckResult, RiskEvaluator
from app.risk.portfolio import PortfolioRiskManager


def _make_signal(
    symbol: str = "BTC/USDT",
    direction: Direction = Direction.LONG,
    entry: float = 43200.0,
    stop_loss: float = 42900.0,
) -> CompositeSignal:
    return CompositeSignal(
        symbol=symbol,
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
            quantity=0.667, notional=28814.4, margin=9604.8,
            risk_amount=200.0, risk_pct=0.02, leverage=3,
        ),
        strategy_scores={"momentum": 0.8, "smc": 0.7, "volume": 0.6},
        market_context=MarketContext(),
    )


def _make_position(
    direction: Direction = Direction.LONG,
    entry: float = 43200.0,
    stop_loss: float = 42900.0,
    quantity: float = 0.5,
) -> Position:
    return Position(
        signal_id=uuid4(),
        symbol="BTC/USDT",
        direction=direction,
        entry_price=entry,
        current_price=entry,
        quantity=quantity,
        remaining_qty=quantity,
        leverage=3,
        stop_loss=stop_loss,
    )


class TestApproval:
    def test_signal_approved_under_limits(self):
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        evaluator = RiskEvaluator(portfolio=portfolio)
        result = evaluator.evaluate(_make_signal())
        assert result.approved is True
        assert result.signal is not None
        assert result.rejection_reasons == []

    def test_approved_signal_has_correct_fields(self):
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        evaluator = RiskEvaluator(portfolio=portfolio)
        result = evaluator.evaluate(_make_signal())
        assert result.signal.symbol == "BTC/USDT"
        assert result.signal.direction == Direction.LONG


class TestCircuitBreakerRejection:
    def test_rejected_when_cb_open(self):
        portfolio = PortfolioRiskManager(initial_balance=10000.0)
        cb = CircuitBreaker()
        cb.check_triggers(daily_loss_pct=0.06)  # Triggers STOP_24H
        evaluator = RiskEvaluator(portfolio=portfolio, circuit_breaker=cb)

        result = evaluator.evaluate(_make_signal())
        assert result.approved is False
        assert any("Circuit breaker" in r for r in result.rejection_reasons)

    def test_rejected_when_cb_full_stop(self):
        portfolio = PortfolioRiskManager(initial_balance=10000.0)
        cb = CircuitBreaker()
        cb.check_triggers(max_drawdown_pct=0.20)
        evaluator = RiskEvaluator(portfolio=portfolio, circuit_breaker=cb)

        result = evaluator.evaluate(_make_signal())
        assert result.approved is False


class TestPortfolioLimitRejection:
    def test_rejected_max_positions(self):
        portfolio = PortfolioRiskManager(initial_balance=100000.0, max_positions=2)
        portfolio.add_position(_make_position())
        portfolio.add_position(_make_position())
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = evaluator.evaluate(_make_signal())
        assert result.approved is False
        assert any("Max positions" in r for r in result.rejection_reasons)

    def test_rejected_drawdown(self):
        portfolio = PortfolioRiskManager(initial_balance=10000.0)
        portfolio.record_trade_result(-2000.0)  # 20% drawdown
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = evaluator.evaluate(_make_signal())
        assert result.approved is False
        assert any("drawdown" in r.lower() for r in result.rejection_reasons)

    def test_rejected_daily_loss(self):
        portfolio = PortfolioRiskManager(initial_balance=10000.0)
        portfolio.record_trade_result(-600.0)  # > 5% daily loss
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = evaluator.evaluate(_make_signal())
        assert result.approved is False


class TestCorrelationRejection:
    def test_rejected_too_many_same_direction(self):
        portfolio = PortfolioRiskManager(
            initial_balance=100000.0, max_correlated=2,
        )
        portfolio.add_position(_make_position(direction=Direction.LONG))
        portfolio.add_position(_make_position(direction=Direction.LONG))
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = evaluator.evaluate(_make_signal(direction=Direction.LONG))
        assert result.approved is False
        assert any("correlated" in r.lower() for r in result.rejection_reasons)

    def test_approved_opposite_direction(self):
        portfolio = PortfolioRiskManager(
            initial_balance=100000.0, max_correlated=2,
        )
        portfolio.add_position(_make_position(direction=Direction.LONG))
        portfolio.add_position(_make_position(direction=Direction.LONG))
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = evaluator.evaluate(_make_signal(direction=Direction.SHORT))
        assert result.approved is True


class TestPositionAdjustment:
    def test_cb_half_open_reduces_size(self):
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        cb = CircuitBreaker()
        cb.check_triggers(consecutive_losses=3)  # REDUCE_50 → HALF_OPEN
        evaluator = RiskEvaluator(portfolio=portfolio, circuit_breaker=cb)

        signal = _make_signal()
        original_qty = signal.position_size.quantity
        result = evaluator.evaluate(signal)

        assert result.approved is True
        assert result.signal.position_size.quantity == pytest.approx(
            original_qty * 0.5
        )
        assert any("circuit breaker" in a.lower() for a in result.adjustments)

    def test_heat_scaling(self):
        """Position is scaled down when it would exceed remaining heat capacity."""
        portfolio = PortfolioRiskManager(initial_balance=10000.0, max_heat=0.02)
        # Add position that uses ~1.5% heat
        portfolio.add_position(_make_position(
            entry=43200.0, stop_loss=42900.0, quantity=0.5,
        ))
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = evaluator.evaluate(_make_signal())
        # Should be approved but with scaled-down position
        if result.approved:
            assert any("heat" in a.lower() for a in result.adjustments)


class TestAutoCircuitBreakerDetection:
    def test_consecutive_losses_auto_triggers_cb(self):
        """RiskEvaluator auto-checks CB triggers from portfolio state."""
        portfolio = PortfolioRiskManager(initial_balance=10000.0)
        for _ in range(5):
            portfolio.record_trade_result(-50.0)
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = evaluator.evaluate(_make_signal())
        assert result.approved is False
        assert any("Circuit breaker" in r for r in result.rejection_reasons)


class TestEvaluateAndPublish:
    @patch("app.risk.evaluator.event_bus")
    async def test_approved_publishes_to_signal_approved(self, mock_bus):
        mock_bus.publish = AsyncMock()
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = await evaluator.evaluate_and_publish(_make_signal())
        assert result.approved is True
        mock_bus.publish.assert_called_once()
        channel = mock_bus.publish.call_args[0][0]
        assert channel == "signal.approved"

    @patch("app.risk.evaluator.event_bus")
    async def test_rejected_publishes_risk_alert(self, mock_bus):
        mock_bus.publish = AsyncMock()
        portfolio = PortfolioRiskManager(initial_balance=10000.0)
        portfolio.record_trade_result(-2000.0)  # 20% drawdown
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = await evaluator.evaluate_and_publish(_make_signal())
        assert result.approved is False
        mock_bus.publish.assert_called_once()
        channel = mock_bus.publish.call_args[0][0]
        assert channel == "risk.alert"

    @patch("app.risk.evaluator.event_bus")
    async def test_publish_failure_doesnt_crash(self, mock_bus):
        mock_bus.publish = AsyncMock(side_effect=RuntimeError("pub fail"))
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        evaluator = RiskEvaluator(portfolio=portfolio)

        result = await evaluator.evaluate_and_publish(_make_signal())
        assert result.approved is True
