"""Unit tests for Executor - main execution orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.config.constants import (
    CircuitBreakerState,
    CloseReason,
    Direction,
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
from app.execution.executor import ExecutionResult, Executor
from app.execution.paper_trader import PaperTrader
from app.risk import CircuitBreaker, PortfolioRiskManager


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


class TestExecuteSignal:
    async def test_basic_execution(self):
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio, is_paper=True)
        signal = _make_signal()
        result = await executor.execute_signal(signal, current_price=43200.0)
        assert result.success is True
        assert result.position is not None
        assert result.order_result.status == OrderStatus.FILLED

    async def test_position_registered_in_tracker(self):
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio)
        signal = _make_signal()
        await executor.execute_signal(signal, current_price=43200.0)
        assert executor.position_tracker.position_count == 1

    async def test_position_added_to_portfolio(self):
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio)
        signal = _make_signal()
        await executor.execute_signal(signal, current_price=43200.0)
        state = portfolio.get_state()
        assert state.open_positions == 1

    async def test_neutral_direction_fails(self):
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio)
        signal = _make_signal(direction=Direction.NEUTRAL)
        result = await executor.execute_signal(signal, current_price=43200.0)
        assert result.success is False

    async def test_insufficient_balance_fails(self):
        portfolio = PortfolioRiskManager(initial_balance=100.0)
        pt = PaperTrader(initial_balance=100.0)
        executor = Executor(portfolio=portfolio, paper_trader=pt)
        signal = _make_signal(quantity=1.0)
        result = await executor.execute_signal(signal, current_price=43200.0)
        assert result.success is False


class TestPreExecutionChecks:
    async def test_circuit_breaker_blocks(self):
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        cb = CircuitBreaker()
        cb.check_triggers(daily_loss_pct=0.06)
        executor = Executor(portfolio=portfolio, circuit_breaker=cb)
        result = await executor.execute_signal(_make_signal(), current_price=43200.0)
        assert result.success is False
        assert "Circuit breaker" in result.message

    async def test_max_positions_blocks(self):
        portfolio = PortfolioRiskManager(initial_balance=100000.0, max_positions=1)
        executor = Executor(portfolio=portfolio)
        # Open first position
        await executor.execute_signal(_make_signal(), current_price=43200.0)
        # Second should be blocked by portfolio
        result = await executor.execute_signal(_make_signal(), current_price=43200.0)
        assert result.success is False


class TestPriceUpdates:
    @patch("app.execution.executor.Executor._persist_position_close", new_callable=AsyncMock)
    async def test_sl_hit_closes_position(self, mock_persist):
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio)
        signal = _make_signal(entry=43200.0)
        result = await executor.execute_signal(signal, current_price=43200.0)
        assert result.success
        # Price drops below SL (42900)
        events = await executor.process_price_update("BTC/USDT", 42800.0)
        assert len(events) == 1
        assert events[0].reason == CloseReason.SL_HIT
        # Position should be removed from tracker
        assert executor.position_tracker.position_count == 0

    @patch("app.execution.executor.Executor._persist_position_close", new_callable=AsyncMock)
    async def test_tp1_partial_close(self, mock_persist):
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio)
        signal = _make_signal(entry=43200.0)
        await executor.execute_signal(signal, current_price=43200.0)
        # Price hits TP1 (43650)
        events = await executor.process_price_update("BTC/USDT", 43700.0)
        tp1_events = [e for e in events if e.reason == CloseReason.TP1_HIT]
        assert len(tp1_events) == 1
        # Position still open (partially closed)
        assert executor.position_tracker.position_count == 1


class TestManualClose:
    @patch("app.execution.executor.Executor._persist_position_close", new_callable=AsyncMock)
    async def test_manual_close(self, mock_persist):
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio)
        signal = _make_signal()
        result = await executor.execute_signal(signal, current_price=43200.0)
        pos_id = str(result.position.id)
        pnl = await executor.close_position(pos_id, close_price=43500.0)
        assert executor.position_tracker.position_count == 0


class TestAsyncPublish:
    @patch("app.execution.executor.Executor._persist_fill", new_callable=AsyncMock)
    @patch("app.execution.executor.event_bus")
    async def test_execute_and_publish_success(self, mock_bus, mock_persist):
        mock_bus.publish = AsyncMock()
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio)
        signal = _make_signal()
        result = await executor.execute_signal_and_publish(signal, current_price=43200.0)
        assert result.success
        mock_bus.publish.assert_called_once()
        channel = mock_bus.publish.call_args[0][0]
        assert channel == "order.filled"

    @patch("app.execution.executor.event_bus")
    async def test_execute_and_publish_failure(self, mock_bus):
        mock_bus.publish = AsyncMock()
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        cb = CircuitBreaker()
        cb.check_triggers(daily_loss_pct=0.06)
        executor = Executor(portfolio=portfolio, circuit_breaker=cb)
        result = await executor.execute_signal_and_publish(_make_signal(), current_price=43200.0)
        assert not result.success
        mock_bus.publish.assert_called_once()
        channel = mock_bus.publish.call_args[0][0]
        assert channel == "risk.alert"


class TestSafetyGate:
    """Tests for TRADING_ENABLED master kill switch."""

    async def test_trading_disabled_blocks_live_execution(self, monkeypatch):
        """When TRADING_ENABLED=false and is_paper=False, execute_signal must fail."""
        from app.config.settings import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("TRADING_ENABLED", "false")
        get_settings.cache_clear()

        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio, is_paper=False)
        result = await executor.execute_signal(_make_signal(), current_price=43200.0)
        assert result.success is False
        assert "TRADING_ENABLED" in result.message

    async def test_trading_disabled_allows_paper_execution(self, monkeypatch):
        """Paper trading bypasses TRADING_ENABLED kill switch."""
        from app.config.settings import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("TRADING_ENABLED", "false")
        get_settings.cache_clear()

        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio, is_paper=True)
        result = await executor.execute_signal(_make_signal(), current_price=43200.0)
        assert result.success is True

    async def test_trading_enabled_allows_execution(self, monkeypatch):
        """When TRADING_ENABLED=true, execute_signal works normally."""
        from app.config.settings import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("TRADING_ENABLED", "true")
        get_settings.cache_clear()

        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio)
        result = await executor.execute_signal(_make_signal(), current_price=43200.0)
        assert result.success is True


class TestLiveModeExecution:
    """Tests for live (non-paper) mode execution path."""

    async def test_live_mode_without_live_trader_fails(self):
        """When is_paper=False but no live_trader, execution should fail."""
        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(portfolio=portfolio, is_paper=False, live_trader=None)
        signal = _make_signal()
        result = await executor.execute_signal(signal, current_price=43200.0)
        assert result.success is False
        assert "Live trader not configured" in result.message

    async def test_live_mode_with_live_trader_succeeds(self):
        """When is_paper=False and live_trader is provided, should use it."""
        from app.core.models import OrderResult as OR
        mock_live_trader = AsyncMock()
        mock_live_trader.execute_order.return_value = OR(
            success=True,
            order_id="test-order",
            exchange_order_id="BINANCE-123",
            message="Live order filled",
            filled_price=43200.0,
            filled_quantity=0.5,
            fees=10.0,
            status=OrderStatus.FILLED,
        )

        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(
            portfolio=portfolio,
            is_paper=False,
            live_trader=mock_live_trader,
        )
        signal = _make_signal()
        result = await executor.execute_signal(signal, current_price=43200.0)
        assert result.success is True
        mock_live_trader.execute_order.assert_called_once()

    @patch("app.execution.executor.Executor._persist_position_close", new_callable=AsyncMock)
    async def test_live_mode_close_position(self, mock_persist):
        """Close position in live mode should call live_trader."""
        from app.core.models import OrderResult as OR
        mock_live_trader = AsyncMock()
        mock_live_trader.execute_order.return_value = OR(
            success=True, order_id="test", exchange_order_id="B-1",
            message="Filled", filled_price=43200.0, filled_quantity=0.5,
            fees=10.0, status=OrderStatus.FILLED,
        )
        mock_live_trader.close_position.return_value = OR(
            success=True, order_id="test-pos", exchange_order_id="B-2",
            message="Closed", filled_price=43500.0, filled_quantity=0.5,
            fees=10.0, status=OrderStatus.FILLED,
        )

        portfolio = PortfolioRiskManager(initial_balance=100000.0)
        executor = Executor(
            portfolio=portfolio, is_paper=False, live_trader=mock_live_trader,
        )
        signal = _make_signal()
        result = await executor.execute_signal(signal, current_price=43200.0)
        assert result.success

        pos_id = str(result.position.id)
        pnl = await executor.close_position(pos_id, close_price=43500.0)
        mock_live_trader.close_position.assert_called_once()
        assert executor.position_tracker.position_count == 0


class TestCalcPnl:
    def test_long_profit(self):
        from app.core.models import Position
        from uuid import uuid4
        pos = Position(
            symbol="BTC/USDT", direction=Direction.LONG, signal_id=uuid4(),
            entry_price=40000.0, quantity=1.0, remaining_qty=1.0,
            leverage=5, stop_loss=39000.0, take_profits=[],
        )
        pnl = Executor._calc_pnl(pos, 41000.0)
        assert pnl == (41000.0 - 40000.0) * 1.0 * 5

    def test_short_profit(self):
        from app.core.models import Position
        from uuid import uuid4
        pos = Position(
            symbol="BTC/USDT", direction=Direction.SHORT, signal_id=uuid4(),
            entry_price=40000.0, quantity=1.0, remaining_qty=1.0,
            leverage=5, stop_loss=41000.0, take_profits=[],
        )
        pnl = Executor._calc_pnl(pos, 39000.0)
        assert pnl == (40000.0 - 39000.0) * 1.0 * 5

    def test_partial_qty(self):
        from app.core.models import Position
        from uuid import uuid4
        pos = Position(
            symbol="BTC/USDT", direction=Direction.LONG, signal_id=uuid4(),
            entry_price=40000.0, quantity=1.0, remaining_qty=0.5,
            leverage=3, stop_loss=39000.0, take_profits=[],
        )
        pnl = Executor._calc_pnl(pos, 41000.0, qty=0.3)
        assert pnl == (41000.0 - 40000.0) * 0.3 * 3


class TestExecutionResult:
    def test_repr(self):
        r = ExecutionResult(success=True, message="ok")
        assert "success=True" in repr(r)
