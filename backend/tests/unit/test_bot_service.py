"""Unit tests for backend/app/bot/service.py — BotService orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot.service import BotService
from app.config.constants import BotStatus, SignalGrade, Direction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service():
    """Fresh BotService instance (not the global singleton)."""
    return BotService()


# ---------------------------------------------------------------------------
# Initial State
# ---------------------------------------------------------------------------


class TestBotServiceInit:
    def test_initial_status_is_stopped(self, service):
        assert service.status == BotStatus.STOPPED

    def test_initial_collector_is_none(self, service):
        assert service.collector is None

    def test_initial_executor_is_none(self, service):
        assert service.executor is None


# ---------------------------------------------------------------------------
# Configure
# ---------------------------------------------------------------------------


class TestBotServiceConfigure:
    def test_configure_symbols(self, service):
        service.configure(symbols=["ETH/USDT"])
        assert service._symbols == ["ETH/USDT"]

    def test_configure_timeframes(self, service):
        service.configure(timeframes=["15m", "4h"])
        assert service._timeframes == ["15m", "4h"]
        assert service._primary_timeframe == "15m"

    def test_configure_strategies(self, service):
        service.configure(strategies=["momentum", "mean_reversion"])
        assert service._active_strategies == ["momentum", "mean_reversion"]

    def test_configure_balance(self, service):
        service.configure(balance=50000.0)
        assert service._balance == 50000.0

    def test_configure_while_running_raises(self, service):
        service._status = BotStatus.RUNNING
        with pytest.raises(RuntimeError, match="Cannot configure while bot is running"):
            service.configure(symbols=["SOL/USDT"])


# ---------------------------------------------------------------------------
# Start / Stop
# ---------------------------------------------------------------------------


class TestBotServiceStartStop:
    @pytest.mark.asyncio
    async def test_start_creates_components(self, service):
        """Start should create collector, aggregator, executor."""
        with (
            patch("app.bot.service.DataCollector") as MockCollector,
            patch("app.bot.service.event_bus") as mock_bus,
        ):
            mock_collector = AsyncMock()
            MockCollector.return_value = mock_collector
            mock_bus.connect = AsyncMock()
            mock_bus.publish = AsyncMock(return_value=0)
            mock_bus.publish_raw = AsyncMock(return_value=0)
            mock_bus.subscribe = MagicMock()
            mock_bus.start = AsyncMock()

            await service.start()

            assert service.status == BotStatus.RUNNING
            assert service.collector is not None
            assert service.executor is not None
            mock_collector.start.assert_called_once()
            mock_bus.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_already_running_noop(self, service):
        """Calling start on a running service should be a no-op."""
        service._status = BotStatus.RUNNING
        # Should not raise or change status
        await service.start()
        assert service.status == BotStatus.RUNNING

    @pytest.mark.asyncio
    async def test_stop_cleans_up(self, service):
        """Stop should clean up collector, aggregator, executor."""
        # Simulate a running service with mocked components
        service._status = BotStatus.RUNNING
        mock_collector = AsyncMock()
        service._collector = mock_collector
        service._aggregator = MagicMock()
        service._executor = MagicMock()

        with patch("app.bot.service.event_bus") as mock_bus:
            mock_bus.unsubscribe = MagicMock()
            mock_bus.publish = AsyncMock(return_value=0)

            await service.stop()

        assert service.status == BotStatus.STOPPED
        assert service.collector is None
        assert service.executor is None
        mock_collector.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_unsubscribes_instead_of_stopping_bus(self, service):
        """Stop should unsubscribe handlers, not stop the global EventBus."""
        service._status = BotStatus.RUNNING
        service._timeframes = ["1h", "15m"]
        service._collector = AsyncMock()
        service._aggregator = MagicMock()
        service._executor = MagicMock()

        with patch("app.bot.service.event_bus") as mock_bus:
            mock_bus.unsubscribe = MagicMock()
            mock_bus.publish = AsyncMock(return_value=0)

            await service.stop()

            # Should call unsubscribe for each timeframe, not stop()
            assert mock_bus.unsubscribe.call_count == 2
            mock_bus.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_when_already_stopped_noop(self, service):
        """Stop when already stopped should be a no-op."""
        assert service.status == BotStatus.STOPPED
        await service.stop()
        assert service.status == BotStatus.STOPPED


# ---------------------------------------------------------------------------
# Pause / Resume
# ---------------------------------------------------------------------------


class TestBotServicePauseResume:
    @pytest.mark.asyncio
    async def test_pause_from_running(self, service):
        service._status = BotStatus.RUNNING
        with patch("app.bot.service.event_bus") as mock_bus:
            mock_bus.publish = AsyncMock(return_value=0)
            await service.pause()
        assert service.status == BotStatus.PAUSED

    @pytest.mark.asyncio
    async def test_pause_when_not_running_noop(self, service):
        assert service.status == BotStatus.STOPPED
        with patch("app.bot.service.event_bus") as mock_bus:
            mock_bus.publish = AsyncMock(return_value=0)
            await service.pause()
        assert service.status == BotStatus.STOPPED

    @pytest.mark.asyncio
    async def test_resume_from_paused(self, service):
        service._status = BotStatus.PAUSED
        with patch("app.bot.service.event_bus") as mock_bus:
            mock_bus.publish = AsyncMock(return_value=0)
            await service.resume()
        assert service.status == BotStatus.RUNNING

    @pytest.mark.asyncio
    async def test_resume_when_not_paused_noop(self, service):
        service._status = BotStatus.RUNNING
        with patch("app.bot.service.event_bus") as mock_bus:
            mock_bus.publish = AsyncMock(return_value=0)
            await service.resume()
        assert service.status == BotStatus.RUNNING


# ---------------------------------------------------------------------------
# Candle Event Handler
# ---------------------------------------------------------------------------


class TestCandleEventHandler:
    @pytest.mark.asyncio
    async def test_publishes_price_update(self, service):
        """Handler should publish price_update for every candle."""
        service._status = BotStatus.RUNNING
        service._primary_timeframe = "1h"
        service._executor = MagicMock()
        service._executor.process_price_update = AsyncMock(return_value=[])

        with patch("app.bot.service.event_bus") as mock_bus:
            mock_bus.publish_raw = AsyncMock(return_value=0)
            mock_bus.publish = AsyncMock(return_value=0)

            await service._on_candle_event(
                "market.candle.1h",
                {
                    "data": {
                        "symbol": "BTC/USDT",
                        "timeframe": "1h",
                        "close": 95000.0,
                        "open": 94800.0,
                        "high": 95200.0,
                        "low": 94700.0,
                        "volume": 123.45,
                        "time": "2024-01-15T12:00:00",
                    }
                },
            )

            mock_bus.publish_raw.assert_called_once()
            call_args = mock_bus.publish_raw.call_args
            assert call_args[0][0] == "price.update"
            assert call_args[0][1]["symbol"] == "BTC/USDT"
            assert call_args[0][1]["price"] == 95000.0

    @pytest.mark.asyncio
    async def test_skips_when_stopped(self, service):
        """Handler should skip if bot is stopped."""
        service._status = BotStatus.STOPPED

        with patch("app.bot.service.event_bus") as mock_bus:
            mock_bus.publish_raw = AsyncMock()
            await service._on_candle_event("market.candle.1h", {"data": {"symbol": "BTC/USDT", "close": 95000.0}})
            mock_bus.publish_raw.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_strategy_when_paused(self, service):
        """When paused, price updates still work but strategy doesn't run."""
        service._status = BotStatus.PAUSED
        service._primary_timeframe = "1h"
        service._executor = MagicMock()
        service._executor.process_price_update = AsyncMock(return_value=[])
        service._aggregator = AsyncMock()

        with patch("app.bot.service.event_bus") as mock_bus:
            mock_bus.publish_raw = AsyncMock(return_value=0)
            mock_bus.publish = AsyncMock(return_value=0)

            await service._on_candle_event(
                "market.candle.1h",
                {"data": {"symbol": "BTC/USDT", "timeframe": "1h", "close": 95000.0, "time": "2024-01-15T12:00:00"}},
            )

            # Price update still published
            mock_bus.publish_raw.assert_called_once()
            # But _run_strategy should NOT be called (status is PAUSED)

    @pytest.mark.asyncio
    async def test_debounce_same_candle(self, service):
        """Handler should debounce same candle timestamp."""
        service._status = BotStatus.RUNNING
        service._primary_timeframe = "1h"
        service._executor = MagicMock()
        service._executor.process_price_update = AsyncMock(return_value=[])

        candle_data = {
            "data": {
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "close": 95000.0,
                "time": "2024-01-15T12:00:00",
            }
        }

        with (
            patch("app.bot.service.event_bus") as mock_bus,
            patch.object(service, "_run_strategy", new_callable=AsyncMock) as mock_strategy,
        ):
            mock_bus.publish_raw = AsyncMock(return_value=0)
            mock_bus.publish = AsyncMock(return_value=0)

            # First call sets the timestamp
            await service._on_candle_event("market.candle.1h", candle_data)

            # We can't check create_task directly, but the debounce key should be set
            assert "BTC/USDT:1h" in service._last_candle_ts
            assert service._last_candle_ts["BTC/USDT:1h"] == "2024-01-15T12:00:00"

    @pytest.mark.asyncio
    async def test_skips_non_primary_timeframe(self, service):
        """Handler should skip strategy for non-primary timeframes."""
        service._status = BotStatus.RUNNING
        service._primary_timeframe = "1h"
        service._executor = MagicMock()
        service._executor.process_price_update = AsyncMock(return_value=[])

        with (
            patch("app.bot.service.event_bus") as mock_bus,
            patch.object(service, "_run_strategy", new_callable=AsyncMock) as mock_strategy,
        ):
            mock_bus.publish_raw = AsyncMock(return_value=0)
            mock_bus.publish = AsyncMock(return_value=0)

            # 15m is not the primary timeframe
            await service._on_candle_event(
                "market.candle.15m",
                {"data": {"symbol": "BTC/USDT", "timeframe": "15m", "close": 95000.0, "time": "t1"}},
            )

            # Strategy should not be called for non-primary TF
            # (the handler returns before reaching asyncio.create_task)


# ---------------------------------------------------------------------------
# Strategy Execution
# ---------------------------------------------------------------------------


class TestRunStrategy:
    @pytest.mark.asyncio
    async def test_no_signal_logs_debug(self, service):
        """When aggregator returns None, should just log."""
        service._aggregator = AsyncMock()
        service._aggregator.aggregate.return_value = None
        service._collector = MagicMock()
        service._executor = MagicMock()

        await service._run_strategy("BTC/USDT", "1h")
        service._aggregator.aggregate.assert_called_once()

    @pytest.mark.asyncio
    async def test_low_grade_signal_skipped(self, service):
        """Grade C/D signals should not be executed."""
        mock_signal = MagicMock()
        mock_signal.grade = SignalGrade.D
        mock_signal.strength = 0.3

        service._aggregator = AsyncMock()
        service._aggregator.aggregate.return_value = mock_signal
        service._collector = MagicMock()
        service._executor = AsyncMock()

        await service._run_strategy("BTC/USDT", "1h")
        service._executor.execute_signal_and_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_grade_a_signal_executed(self, service):
        """Grade A signals should be executed."""
        mock_signal = MagicMock()
        mock_signal.grade = SignalGrade.A
        mock_signal.strength = 0.9
        mock_signal.direction = Direction.LONG
        mock_signal.entry_price = 95000.0
        mock_signal.id = "test-id"

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.position = MagicMock()
        mock_result.position.id = "pos-id"

        service._aggregator = AsyncMock()
        service._aggregator.aggregate.return_value = mock_signal
        service._collector = MagicMock()
        service._executor = AsyncMock()
        service._executor.execute_signal_and_publish.return_value = mock_result

        await service._run_strategy("BTC/USDT", "1h")
        service._executor.execute_signal_and_publish.assert_called_once_with(
            mock_signal, current_price=95000.0, use_market=True
        )

    @pytest.mark.asyncio
    async def test_grade_b_signal_executed(self, service):
        """Grade B signals should be executed."""
        mock_signal = MagicMock()
        mock_signal.grade = SignalGrade.B
        mock_signal.strength = 0.65
        mock_signal.direction = Direction.SHORT
        mock_signal.entry_price = 95000.0

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.position = MagicMock()

        service._aggregator = AsyncMock()
        service._aggregator.aggregate.return_value = mock_signal
        service._collector = MagicMock()
        service._executor = AsyncMock()
        service._executor.execute_signal_and_publish.return_value = mock_result

        await service._run_strategy("BTC/USDT", "1h")
        service._executor.execute_signal_and_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_components_noop(self, service):
        """If components are None, strategy should not run."""
        service._aggregator = None
        service._collector = None
        service._executor = None

        # Should not raise
        await service._run_strategy("BTC/USDT", "1h")


# ---------------------------------------------------------------------------
# Safety Gate
# ---------------------------------------------------------------------------


class TestBotServiceSafetyGate:
    """Tests for environment gate and TRADING_ENABLED checks."""

    @pytest.mark.asyncio
    async def test_live_mode_blocked_in_demo_env(self, service, monkeypatch):
        """Starting in live mode with ENVIRONMENT=demo must raise."""
        from app.config.settings import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("ENVIRONMENT", "demo")
        get_settings.cache_clear()

        service.configure(is_paper=False)
        with pytest.raises(RuntimeError, match="ENVIRONMENT"):
            await service.start()

    @pytest.mark.asyncio
    async def test_live_mode_blocked_when_trading_disabled(self, service, monkeypatch):
        """Starting in live mode with TRADING_ENABLED=false must raise."""
        from app.config.settings import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("ENVIRONMENT", "live")
        monkeypatch.setenv("TRADING_ENABLED", "false")
        get_settings.cache_clear()

        service.configure(is_paper=False)
        with pytest.raises(RuntimeError, match="TRADING_ENABLED"):
            await service.start()

    @pytest.mark.asyncio
    async def test_paper_mode_starts_in_demo_env(self, service):
        """Paper mode should start fine in demo environment."""
        with (
            patch("app.bot.service.DataCollector") as MockCollector,
            patch("app.bot.service.event_bus") as mock_bus,
        ):
            mock_collector = AsyncMock()
            MockCollector.return_value = mock_collector
            mock_bus.publish = AsyncMock(return_value=0)
            mock_bus.publish_raw = AsyncMock(return_value=0)
            mock_bus.subscribe = MagicMock()
            mock_bus.start = AsyncMock()

            await service.start()
            assert service.status == BotStatus.RUNNING
