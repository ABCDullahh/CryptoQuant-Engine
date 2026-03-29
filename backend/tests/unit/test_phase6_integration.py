"""Phase 6 Integration Tests - Execution engine end-to-end flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.config.constants import (
    CloseReason,
    Direction,
    MarketRegime,
    OrderStatus,
    PositionStatus,
    SignalGrade,
    StopLossType,
)
from app.core.models import (
    CompositeSignal,
    MarketContext,
    PositionSize,
    RiskReward,
    TakeProfit,
)
from app.execution import (
    ExecutionResult,
    Executor,
    OrderManager,
    PaperTrader,
    PositionTracker,
)
from app.risk import CircuitBreaker, PortfolioRiskManager, RiskEvaluator


def _make_signal(
    direction=Direction.LONG,
    grade=SignalGrade.B,
    entry=43200.0,
    quantity=0.5,
) -> CompositeSignal:
    return CompositeSignal(
        symbol="BTC/USDT",
        direction=direction,
        grade=grade,
        strength=0.70,
        entry_price=entry,
        entry_zone=(entry - 100, entry + 100),
        stop_loss=entry - 300,
        sl_type=StopLossType.ATR_BASED,
        take_profits=[
            TakeProfit(level="TP1", price=entry + 450, close_pct=50, rr_ratio=1.5),
            TakeProfit(level="TP2", price=entry + 900, close_pct=30, rr_ratio=3.0),
            TakeProfit(level="TP3", price=entry + 1500, close_pct=20, rr_ratio=5.0),
        ],
        risk_reward=RiskReward(rr_tp1=1.5, rr_tp2=3.0, rr_tp3=5.0, weighted_rr=2.65),
        position_size=PositionSize(
            quantity=quantity, notional=quantity * entry,
            margin=quantity * entry / 3,
            risk_amount=200.0, risk_pct=0.02, leverage=3,
        ),
        strategy_scores={"momentum": 0.8},
        market_context=MarketContext(),
    )


class TestRiskToExecution:
    async def test_risk_approved_signal_executes(self):
        """Signal approved by RiskEvaluator -> executed by Executor."""
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        evaluator = RiskEvaluator(portfolio=portfolio)

        signal = _make_signal()
        risk_result = evaluator.evaluate(signal)
        assert risk_result.approved is True

        executor = Executor(portfolio=portfolio)
        exec_result = await executor.execute_signal(risk_result.signal, current_price=43200.0)
        assert exec_result.success is True
        assert exec_result.position is not None

    async def test_risk_rejected_not_executed(self):
        """Signal rejected by RiskEvaluator -> not sent to Executor."""
        portfolio = PortfolioRiskManager(initial_balance=10000.0)
        portfolio.record_trade_result(-2000.0)  # 20% drawdown
        evaluator = RiskEvaluator(portfolio=portfolio)

        risk_result = evaluator.evaluate(_make_signal())
        assert risk_result.approved is False
        # Don't execute rejected signals


class TestFullLifecycle:
    @patch("app.execution.executor.Executor._persist_position_close", new_callable=AsyncMock)
    async def test_signal_to_tp1_to_sl(self, mock_persist):
        """Full lifecycle: execute -> TP1 hit -> SL at breakeven -> SL hit."""
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=0, fee_rate=0)
        executor = Executor(portfolio=portfolio, paper_trader=pt)

        # Execute signal (no slippage for predictable test)
        signal = _make_signal(entry=43200.0)
        result = await executor.execute_signal(signal, current_price=43200.0)
        assert result.success

        # Price rises to TP1 (43650)
        events = await executor.process_price_update("BTC/USDT", 43700.0)
        tp1_events = [e for e in events if e.reason == CloseReason.TP1_HIT]
        assert len(tp1_events) == 1

        # SL should now be at breakeven (entry price)
        pos = list(executor.position_tracker.positions.values())[0]
        assert pos.stop_loss == pytest.approx(pos.entry_price, abs=1.0)

        # Price drops back to breakeven SL
        events = await executor.process_price_update("BTC/USDT", pos.entry_price - 50)
        sl_events = [e for e in events if e.reason == CloseReason.SL_HIT]
        assert len(sl_events) == 1
        assert executor.position_tracker.position_count == 0

    @patch("app.execution.executor.Executor._persist_position_close", new_callable=AsyncMock)
    async def test_signal_to_tp2_trailing_stop(self, mock_persist):
        """Execute -> TP1 -> TP2 -> trailing stop triggers."""
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio)

        signal = _make_signal(entry=43200.0)
        await executor.execute_signal(signal, current_price=43200.0)

        # TP1 hit
        await executor.process_price_update("BTC/USDT", 43700.0)
        # TP2 hit (activates trailing)
        await executor.process_price_update("BTC/USDT", 44200.0)
        assert executor.position_tracker.is_trailing_active(
            list(executor.position_tracker.positions.keys())[0]
        )

        # Price goes higher then drops
        await executor.process_price_update("BTC/USDT", 45000.0)
        events = await executor.process_price_update("BTC/USDT", 44700.0)
        trailing_events = [e for e in events if e.reason == CloseReason.TRAILING_STOP]
        assert len(trailing_events) == 1

    async def test_multiple_positions_independent(self):
        """Multiple positions tracked independently."""
        portfolio = PortfolioRiskManager(initial_balance=100000.0, max_positions=3)
        executor = Executor(portfolio=portfolio)

        sig1 = _make_signal(entry=43200.0, quantity=0.3)
        sig2 = _make_signal(entry=43200.0, quantity=0.3)
        await executor.execute_signal(sig1, current_price=43200.0)
        await executor.execute_signal(sig2, current_price=43200.0)
        assert executor.position_tracker.position_count == 2


class TestCircuitBreakerIntegration:
    async def test_cb_blocks_then_recovers(self):
        """Circuit breaker blocks, then allows after reset."""
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        cb = CircuitBreaker()
        executor = Executor(portfolio=portfolio, circuit_breaker=cb)

        # Trigger circuit breaker
        cb.check_triggers(daily_loss_pct=0.06)
        result = await executor.execute_signal(_make_signal(), current_price=43200.0)
        assert result.success is False

        # Reset circuit breaker
        cb.reset()
        result = await executor.execute_signal(_make_signal(), current_price=43200.0)
        assert result.success is True


class TestPaperTraderIntegration:
    async def test_paper_balance_updates(self):
        """Paper trader balance reflects fees and P&L."""
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=0, fee_rate=0.0004)
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio, paper_trader=pt)

        signal = _make_signal(quantity=0.5)
        await executor.execute_signal(signal, current_price=43200.0)

        # Fees deducted
        assert pt.balance < 100000.0


class TestImportsClean:
    def test_execution_package_imports(self):
        """All execution classes importable from app.execution."""
        from app.execution import (
            ExecutionResult,
            Executor,
            OrderManager,
            OrderValidationError,
            PaperTrader,
            PositionEvent,
            PositionTracker,
        )
        assert ExecutionResult is not None

    def test_close_reason_enum(self):
        """CloseReason enum available and complete."""
        from app.config.constants import CloseReason
        assert CloseReason.SL_HIT == "SL_HIT"
        assert CloseReason.TP1_HIT == "TP1_HIT"
        assert CloseReason.TRAILING_STOP == "TRAILING_STOP"
        assert CloseReason.MANUAL_CLOSE == "MANUAL_CLOSE"
