"""BotService - orchestrates the real-time trading pipeline.

Connects DataCollector → SignalAggregator → Executor into a live loop.
When started, subscribes to candle events from DataCollector and runs
strategies on each closed candle to generate and execute signals.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog

from app.config.constants import (
    BotStatus,
    EventChannel,
    SignalGrade,
    Timeframe,
)
from app.core.events import event_bus
from app.core.models import EventMessage
from app.data.collector import DataCollector
from app.data.providers.binance import BinanceProvider
from app.execution.executor import Executor
from app.execution.live_trader import LiveTrader
from app.execution.paper_trader import PaperTrader
from app.risk import CircuitBreaker, PortfolioRiskManager
from app.signals.aggregator import SignalAggregator
from app.strategies import STRATEGY_REGISTRY

logger = structlog.get_logger(__name__)


class BotService:
    """Singleton orchestrator for the live trading pipeline.

    Lifecycle:
        configure() → start() → [running] → pause()/resume() → stop()

    On each candle event:
        1. Publish price_update for frontend
        2. Run Executor.process_price_update() for SL/TP
        3. On primary timeframe closed candle (debounced):
           SignalAggregator.aggregate() → Executor.execute_signal_and_publish()
    """

    def __init__(self) -> None:
        self._status: BotStatus = BotStatus.STOPPED
        self._collector: DataCollector | None = None
        self._aggregator: SignalAggregator | None = None
        self._executor: Executor | None = None
        self._provider: BinanceProvider | None = None

        # Configuration
        self._symbols: list[str] = ["BTC/USDT"]
        self._timeframes: list[str] = [Timeframe.H1]
        self._primary_timeframe: str = Timeframe.H1
        self._active_strategies: list[str] = list(STRATEGY_REGISTRY.keys())
        self._balance: float = 10000.0
        self._is_paper: bool = True
        self._min_grade: SignalGrade = SignalGrade.C

        # Debounce: track last processed candle timestamp per symbol
        self._last_candle_ts: dict[str, float] = {}

    @property
    def status(self) -> BotStatus:
        return self._status

    @property
    def collector(self) -> DataCollector | None:
        return self._collector

    @property
    def executor(self) -> Executor | None:
        return self._executor

    def configure(
        self,
        symbols: list[str] | None = None,
        timeframes: list[str] | None = None,
        strategies: list[str] | None = None,
        balance: float | None = None,
        is_paper: bool | None = None,
    ) -> None:
        """Configure bot parameters. Must be called before start() or while stopped."""
        if self._status not in (BotStatus.STOPPED,):
            raise RuntimeError("Cannot configure while bot is running")

        if symbols is not None:
            self._symbols = symbols
        if timeframes is not None:
            self._timeframes = timeframes
            self._primary_timeframe = timeframes[0] if timeframes else Timeframe.H1
        if strategies is not None:
            self._active_strategies = strategies
        if balance is not None:
            self._balance = balance
        if is_paper is not None:
            self._is_paper = is_paper

    async def start(self) -> None:
        """Start the real-time trading pipeline."""
        if self._status == BotStatus.RUNNING:
            logger.warning("bot.already_running")
            return

        # Safety gate: block non-paper mode unless environment is explicitly "live"
        from app.config.settings import get_settings
        settings = get_settings()
        if not self._is_paper and settings.environment != "live":
            raise RuntimeError(
                f"Cannot start live trading: ENVIRONMENT={settings.environment!r} (must be 'live'). "
                "Use paper mode or set ENVIRONMENT=live explicitly."
            )
        if not self._is_paper and not settings.trading_enabled:
            raise RuntimeError(
                "Cannot start live trading: TRADING_ENABLED=false. "
                "Set TRADING_ENABLED=true in .env to enable."
            )

        self._status = BotStatus.STARTING
        logger.info(
            "bot.starting",
            symbols=self._symbols,
            timeframes=self._timeframes,
            strategies=self._active_strategies,
        )

        try:
            # Publish status change
            await self._publish_status()

            # Build components
            self._collector = DataCollector(
                symbols=self._symbols,
                timeframes=self._timeframes,
            )

            strategy_instances = []
            for name in self._active_strategies:
                cls = STRATEGY_REGISTRY.get(name)
                if cls:
                    strategy_instances.append(cls())

            self._aggregator = SignalAggregator(strategies=strategy_instances)

            # Create LiveTrader for live mode + fetch real balance
            live_trader = None
            balance = self._balance
            if not self._is_paper:
                self._provider = BinanceProvider()
                await self._provider.connect()
                live_trader = LiveTrader(self._provider)
                # Use real exchange balance instead of configured default
                try:
                    bal_data = await self._provider.fetch_balance()
                    usdt_bal = bal_data.get("USDT", {})
                    real_balance = float(usdt_bal.get("free", 0) or 0)
                    if real_balance > 0:
                        balance = real_balance
                        self._balance = balance  # Update for aggregator position sizing
                        logger.info("bot.balance_from_exchange", balance=balance)
                except Exception:
                    logger.warning("bot.balance_fetch_failed_using_default", balance=balance)
                logger.info("bot.live_trader_ready")

            # For paper mode: try to resume from DB balance
            if self._is_paper:
                saved_balance = await self._load_paper_balance()
                if saved_balance is not None and saved_balance > 0:
                    balance = saved_balance
                    self._balance = balance
                    logger.info("bot.paper_balance_resumed", balance=balance)
                else:
                    # First run or no saved balance — save initial
                    await self._save_paper_balance(balance, initial=True)

            portfolio = PortfolioRiskManager(initial_balance=balance)
            circuit_breaker = CircuitBreaker()
            paper_trader = PaperTrader(initial_balance=balance)

            self._executor = Executor(
                portfolio=portfolio,
                circuit_breaker=circuit_breaker,
                paper_trader=paper_trader,
                live_trader=live_trader,
                is_paper=self._is_paper,
            )

            # Subscribe to candle events for each timeframe
            for tf in self._timeframes:
                channel = EventChannel.MARKET_CANDLE.format(timeframe=tf)
                event_bus.subscribe(channel, self._on_candle_event)

            # Start data collection (connects to exchange, starts WS streams)
            await self._collector.start()

            # Pre-load historical candles so strategies have data from the start
            try:
                loaded = await self._collector.load_historical(days_back=14)
                logger.info("bot.history_loaded", loaded=loaded)
            except Exception:
                logger.warning("bot.history_load_failed")

            # Start the event bus listener
            await event_bus.start()

            self._status = BotStatus.RUNNING
            self._last_candle_ts.clear()
            await self._publish_status()
            logger.info("bot.started")

        except Exception as exc:
            self._status = BotStatus.STOPPED
            logger.error("bot.start_failed", error=str(exc))
            raise

    async def stop(self) -> None:
        """Stop the trading pipeline completely."""
        if self._status == BotStatus.STOPPED:
            return

        self._status = BotStatus.STOPPING
        logger.info("bot.stopping")
        await self._publish_status()

        # Save paper balance before shutdown
        if self._is_paper and self._executor:
            try:
                paper_bal = self._executor.paper_balance
                if paper_bal is not None:
                    await self._save_paper_balance(paper_bal)
                    logger.info("bot.paper_balance_saved", balance=paper_bal)
            except Exception:
                logger.warning("bot.paper_balance_save_failed")

        # Stop data collector
        if self._collector:
            try:
                await self._collector.stop()
            except Exception:
                logger.warning("bot.collector_stop_error")

        # Unsubscribe our handlers from event bus (don't stop the global bus)
        for tf in self._timeframes:
            channel = EventChannel.MARKET_CANDLE.format(timeframe=tf)
            event_bus.unsubscribe(channel, self._on_candle_event)

        # Disconnect live provider if active
        if self._provider:
            try:
                await self._provider.close()
            except Exception:
                logger.warning("bot.provider_close_error")
            self._provider = None

        self._collector = None
        self._aggregator = None
        self._executor = None
        self._last_candle_ts.clear()
        self._status = BotStatus.STOPPED
        await self._publish_status()
        logger.info("bot.stopped")

    async def pause(self) -> None:
        """Pause signal generation. Price monitoring for SL/TP continues."""
        if self._status != BotStatus.RUNNING:
            logger.warning("bot.not_running_cannot_pause")
            return

        self._status = BotStatus.PAUSED
        await self._publish_status()
        logger.info("bot.paused")

    async def resume(self) -> None:
        """Resume signal generation from paused state."""
        if self._status != BotStatus.PAUSED:
            logger.warning("bot.not_paused_cannot_resume")
            return

        self._status = BotStatus.RUNNING
        await self._publish_status()
        logger.info("bot.resumed")

    async def _on_candle_event(self, channel: str, data: dict) -> None:
        """Handle a candle event from the DataCollector via EventBus.

        Args:
            channel: Redis channel name (e.g. "market.candle.1h")
            data: EventMessage data dict containing candle fields
        """
        if self._status not in (BotStatus.RUNNING, BotStatus.PAUSED):
            return

        # Extract candle info from the event data
        candle_data = data.get("data", data)
        symbol = candle_data.get("symbol", "")
        timeframe = candle_data.get("timeframe", "")
        close_price = candle_data.get("close", 0.0)
        candle_time = candle_data.get("time", "")

        logger.debug("bot.candle_received", symbol=symbol, timeframe=timeframe, close=close_price)

        if not symbol or not close_price:
            return

        # 1. Publish price_update for frontend (every candle tick)
        try:
            await event_bus.publish_raw(
                "price.update",
                {
                    "symbol": symbol,
                    "price": close_price,
                    "timeframe": timeframe,
                    "time": candle_time,
                    "open": candle_data.get("open", close_price),
                    "high": candle_data.get("high", close_price),
                    "low": candle_data.get("low", close_price),
                    "close": close_price,
                    "volume": candle_data.get("volume", 0),
                },
            )
        except Exception as exc:
            logger.debug("bot.candle_publish_failed", error=str(exc))

        # 2. Process price for SL/TP management
        if self._executor:
            try:
                events = await self._executor.process_price_update(symbol, close_price)
                # Publish position close events
                for evt in events:
                    if evt.event_type == "close":
                        await event_bus.publish(
                            EventChannel.POSITION_CLOSED,
                            EventMessage(
                                event_type="position.closed",
                                data={
                                    "position_id": evt.position_id,
                                    "close_price": evt.close_price,
                                    "reason": evt.reason,
                                },
                            ),
                        )
            except Exception:
                logger.warning("bot.price_update_error", symbol=symbol)

        # 3. Run strategy only on primary timeframe + only when RUNNING (not PAUSED)
        if self._status != BotStatus.RUNNING:
            return
        if timeframe != self._primary_timeframe:
            return

        # Debounce: skip if we already processed this exact candle timestamp
        ts_key = f"{symbol}:{timeframe}"
        candle_ts = str(candle_time)
        if self._last_candle_ts.get(ts_key) == candle_ts:
            return
        self._last_candle_ts[ts_key] = candle_ts

        # Run strategy in a background task (non-blocking)
        asyncio.create_task(self._run_strategy(symbol, timeframe))

    async def _run_strategy(self, symbol: str, timeframe: str) -> None:
        """Run the signal aggregator and execute any qualifying signals."""
        if not self._aggregator or not self._collector or not self._executor:
            return

        try:
            signal = await self._aggregator.aggregate(
                self._collector,
                symbol,
                timeframe,
                self._balance,
            )

            if signal is None:
                return

            # Filter out low-quality signals (only D grade is rejected)
            if signal.grade == SignalGrade.D:
                return

            # Persist signal to DB for the signals page
            await self._persist_signal(signal)

            # Close conflicting position (same symbol, opposite direction)
            await self._close_conflicting_position(symbol, signal.direction, signal.entry_price)

            logger.info(
                "bot.executing_signal",
                symbol=symbol,
                direction=signal.direction,
                grade=signal.grade,
                strength=round(signal.strength, 3),
            )

            result = await self._executor.execute_signal_and_publish(
                signal,
                current_price=signal.entry_price,
                use_market=True,
            )

            if result.success:
                logger.info(
                    "bot.signal_executed",
                    symbol=symbol,
                    position_id=str(result.position.id) if result.position else None,
                )
                await self._update_signal_status(str(signal.id), "EXECUTED")
            else:
                logger.warning(
                    "bot.signal_execution_failed",
                    symbol=symbol,
                    reason=result.message,
                )
                await self._update_signal_status(str(signal.id), "REJECTED")

        except Exception as exc:
            logger.error("bot.strategy_error", symbol=symbol, timeframe=timeframe, error=str(exc))

    async def _close_conflicting_position(
        self, symbol: str, new_direction, current_price: float,
    ) -> None:
        """Close any existing position on this symbol with opposite direction.

        Safely handles cases where executor internals aren't fully initialized.
        """
        if not self._executor:
            return
        try:
            tracker = self._executor.position_tracker
            positions = list(tracker.get_positions_by_symbol(symbol))
            for pos in positions:
                if str(pos.direction) != str(new_direction):
                    pnl = await self._executor.close_position(
                        str(pos.id), close_price=current_price, reason="DIRECTION_FLIP",
                    )
                    logger.info(
                        "bot.conflict_closed",
                        symbol=symbol,
                        old_direction=pos.direction,
                        new_direction=new_direction,
                        pnl=round(pnl, 2),
                    )
        except Exception as exc:
            logger.debug("bot.conflict_check_skipped", error=str(exc), symbol=symbol)

    async def _persist_signal(self, signal) -> None:
        """Persist a CompositeSignal to the signals table."""
        try:
            from app.db.database import async_session_factory
            from app.db.models import SignalModel

            async with async_session_factory() as session:
                row = SignalModel(
                    id=str(signal.id),
                    symbol=signal.symbol,
                    direction=signal.direction,
                    signal_grade=signal.grade,
                    signal_strength=signal.strength,
                    entry_price=signal.entry_price,
                    entry_zone_low=signal.entry_zone[0] if signal.entry_zone else None,
                    entry_zone_high=signal.entry_zone[1] if signal.entry_zone else None,
                    stop_loss=signal.stop_loss,
                    sl_type=signal.sl_type,
                    tp1_price=signal.take_profits[0].price if signal.take_profits else signal.entry_price,
                    tp1_pct=signal.take_profits[0].close_pct if signal.take_profits else 50,
                    tp2_price=signal.take_profits[1].price if len(signal.take_profits) > 1 else None,
                    tp2_pct=signal.take_profits[1].close_pct if len(signal.take_profits) > 1 else None,
                    tp3_price=signal.take_profits[2].price if len(signal.take_profits) > 2 else None,
                    tp3_pct=signal.take_profits[2].close_pct if len(signal.take_profits) > 2 else None,
                    rr_tp1=signal.risk_reward.rr_tp1 if signal.risk_reward else None,
                    rr_tp2=signal.risk_reward.rr_tp2 if signal.risk_reward else None,
                    rr_tp3=signal.risk_reward.rr_tp3 if signal.risk_reward else None,
                    weighted_rr=signal.risk_reward.weighted_rr if signal.risk_reward else None,
                    position_size_qty=signal.position_size.quantity if signal.position_size else None,
                    leverage=signal.position_size.leverage if signal.position_size else 1,
                    risk_amount=signal.position_size.risk_amount if signal.position_size else None,
                    strategy_scores=signal.strategy_scores or {},
                    market_context=signal.market_context.model_dump() if signal.market_context else None,
                    status="ACTIVE",
                )
                session.add(row)
                await session.commit()
        except Exception as exc:
            logger.error("bot.signal_persist_error", error=str(exc))

    async def _update_signal_status(self, signal_id: str, status: str) -> None:
        """Update signal status in the DB."""
        try:
            from sqlalchemy import update
            from app.db.database import async_session_factory
            from app.db.models import SignalModel

            async with async_session_factory() as session:
                await session.execute(
                    update(SignalModel).where(SignalModel.id == signal_id).values(status=status)
                )
                await session.commit()
        except Exception as exc:
            logger.debug("bot.signal_status_update_failed", error=str(exc))

    async def _load_paper_balance(self) -> float | None:
        """Load paper trading balance from BotStateModel."""
        try:
            from sqlalchemy import select
            from app.db.database import async_session_factory
            from app.db.models import BotStateModel

            async with async_session_factory() as session:
                result = await session.execute(select(BotStateModel).limit(1))
                state = result.scalar_one_or_none()
                if state and state.paper_balance is not None:
                    return float(state.paper_balance)
        except Exception as exc:
            logger.debug("bot.load_paper_balance_failed", error=str(exc))
        return None

    async def _save_paper_balance(
        self, balance: float, initial: bool = False,
    ) -> None:
        """Persist paper trading balance to BotStateModel."""
        try:
            from sqlalchemy import select
            from app.db.database import async_session_factory
            from app.db.models import BotStateModel

            async with async_session_factory() as session:
                result = await session.execute(select(BotStateModel).limit(1))
                state = result.scalar_one_or_none()
                if state:
                    state.paper_balance = balance
                    if initial:
                        state.paper_initial_balance = balance
                    await session.commit()
        except Exception as exc:
            logger.debug("bot.save_paper_balance_failed", error=str(exc))

    def get_current_balance(self) -> float | None:
        """Get current trading balance (paper or live)."""
        if self._executor is None:
            return None
        if self._is_paper:
            return self._executor.paper_balance
        return self._balance  # Live balance set at start

    async def _publish_status(self) -> None:
        """Publish bot status change to EventBus."""
        try:
            await event_bus.publish(
                EventChannel.BOT_STATUS,
                EventMessage(
                    event_type="bot.status",
                    data={
                        "status": self._status,
                        "symbols": self._symbols,
                        "timeframes": self._timeframes,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    },
                ),
            )
        except Exception as exc:
            logger.debug("bot.status_publish_failed", error=str(exc))


# Global singleton
bot_service = BotService()
