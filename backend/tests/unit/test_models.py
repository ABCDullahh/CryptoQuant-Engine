"""Unit tests for Pydantic models in backend/app/core/models.py"""

import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from pydantic import ValidationError
from app.config.constants import (
    Direction,
    SignalGrade,
    StopLossType,
    MarketRegime,
    SignalStatus,
    BotStatus,
    PositionStatus,
    OrderStatus,
)
from app.core.models import (
    Candle,
    OrderBook,
    FundingRate,
    IndicatorValues,
    MarketData,
    RawSignal,
    TakeProfit,
    RiskReward,
    PositionSize,
    MarketContext,
    CompositeSignal,
    OrderIntent,
    OrderResult,
    Position,
    PortfolioState,
    BacktestConfig,
    BacktestResult,
    BotState,
    EventMessage,
)


def test_candle_creation():
    """Test creating a valid Candle with all fields."""
    timestamp = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    candle = Candle(
        time=timestamp,
        symbol="BTC/USDT",
        timeframe="1h",
        open=50000.0,
        high=51000.0,
        low=49000.0,
        close=50500.0,
        volume=100.5,
        quote_volume=5025000.0,
        trades_count=1500,
    )

    assert candle.time == timestamp
    assert candle.symbol == "BTC/USDT"
    assert candle.timeframe == "1h"
    assert candle.open == 50000.0
    assert candle.high == 51000.0
    assert candle.low == 49000.0
    assert candle.close == 50500.0
    assert candle.volume == 100.5
    assert candle.quote_volume == 5025000.0
    assert candle.trades_count == 1500


def test_candle_optional_fields():
    """Test that quote_volume and trades_count default to None."""
    candle = Candle(
        time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="BTC/USDT",
        timeframe="1h",
        open=50000.0,
        high=51000.0,
        low=49000.0,
        close=50500.0,
        volume=100.5,
    )

    assert candle.quote_volume is None
    assert candle.trades_count is None


def test_raw_signal_strength_bounds():
    """Test that RawSignal strength must be between -1 and 1."""
    # Valid strengths
    for strength in [-1.0, -0.5, 0.0, 0.5, 1.0]:
        signal = RawSignal(
            strategy_name="test",
            symbol="BTC/USDT",
            direction=Direction.LONG,
            strength=strength,
            entry_price=50000.0,
            timeframe="1h",
        )
        assert signal.strength == strength

    # Invalid: below -1
    with pytest.raises(ValidationError):
        RawSignal(
            strategy_name="test",
            symbol="BTC/USDT",
            direction=Direction.LONG,
            strength=-1.1,
            entry_price=50000.0,
            timeframe="1h",
        )

    # Invalid: above 1
    with pytest.raises(ValidationError):
        RawSignal(
            strategy_name="test",
            symbol="BTC/USDT",
            direction=Direction.LONG,
            strength=1.1,
            entry_price=50000.0,
            timeframe="1h",
        )


def _make_composite_signal(**overrides):
    """Helper to create CompositeSignal with defaults."""
    defaults = dict(
        symbol="BTC/USDT",
        direction=Direction.LONG,
        grade=SignalGrade.A,
        strength=0.8,
        entry_price=50000.0,
        entry_zone=(49500.0, 50500.0),
        stop_loss=48000.0,
        sl_type=StopLossType.ATR_BASED,
        take_profits=[TakeProfit(level="TP1", price=52000.0, close_pct=50, rr_ratio=2.0)],
        risk_reward=RiskReward(rr_tp1=2.0, weighted_rr=2.0),
        position_size=PositionSize(
            quantity=1.0, notional=50000.0, margin=5000.0,
            risk_amount=1000.0, risk_pct=0.02, leverage=10,
        ),
        strategy_scores={"test_strategy": 0.8},
        market_context=MarketContext(),
    )
    defaults.update(overrides)
    return CompositeSignal(**defaults)


def test_composite_signal_defaults():
    """Test CompositeSignal auto-generated id, created_at, and status default."""
    signal = _make_composite_signal()

    assert isinstance(signal.id, UUID)
    assert isinstance(signal.created_at, datetime)
    assert signal.status == SignalStatus.ACTIVE
    assert signal.ml_confidence is None


def test_composite_signal_strength_bounds():
    """Test CompositeSignal strength ge=0, le=1."""
    for strength in [0.0, 0.5, 1.0]:
        signal = _make_composite_signal(strength=strength)
        assert signal.strength == strength

    with pytest.raises(ValidationError):
        _make_composite_signal(strength=-0.1)

    with pytest.raises(ValidationError):
        _make_composite_signal(strength=1.1)


def test_market_context_defaults():
    """Test MarketContext default values."""
    context = MarketContext()

    assert context.regime == MarketRegime.RANGING
    assert context.trend_1h == "NEUTRAL"
    assert context.trend_4h == "NEUTRAL"
    assert context.trend_1d == "NEUTRAL"
    assert context.volatility == "MEDIUM"
    assert context.volume_profile == "AVERAGE"
    assert context.fear_greed_index is None


def test_portfolio_state_defaults():
    """Test PortfolioState default values are all zero."""
    state = PortfolioState()

    assert state.balance == 0.0
    assert state.equity == 0.0
    assert state.unrealized_pnl == 0.0
    assert state.margin_used == 0.0
    assert state.margin_available == 0.0
    assert state.portfolio_heat == 0.0
    assert state.open_positions == 0
    assert state.daily_pnl == 0.0
    assert state.weekly_pnl == 0.0
    assert state.max_drawdown == 0.0
    assert state.consecutive_losses == 0


def test_backtest_config_defaults():
    """Test BacktestConfig default values."""
    config = BacktestConfig(
        strategy_name="momentum",
        symbol="BTC/USDT",
        timeframe="1h",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 12, 31, tzinfo=timezone.utc),
    )

    assert config.initial_capital == 10000.0
    assert config.risk_per_trade == 0.02
    assert config.max_positions == 5
    assert config.slippage_bps == 5.0
    assert config.maker_fee == 0.0002
    assert config.taker_fee == 0.0004
    assert config.parameters == {}


def test_event_message_auto_timestamp():
    """Test EventMessage gets timestamp automatically."""
    message = EventMessage(event_type="test_event", data={"key": "value"})

    assert isinstance(message.timestamp, datetime)
    assert message.event_type == "test_event"
    assert message.data == {"key": "value"}
    assert message.correlation_id is None


def test_candle_serialization():
    """Test Candle model_dump() works correctly."""
    timestamp = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    candle = Candle(
        time=timestamp,
        symbol="BTC/USDT",
        timeframe="1h",
        open=50000.0,
        high=51000.0,
        low=49000.0,
        close=50500.0,
        volume=100.5,
        quote_volume=5025000.0,
        trades_count=1500,
    )

    data = candle.model_dump()
    assert isinstance(data, dict)
    assert data["symbol"] == "BTC/USDT"
    assert data["open"] == 50000.0
    assert data["close"] == 50500.0
    assert data["volume"] == 100.5
    assert data["quote_volume"] == 5025000.0
    assert data["trades_count"] == 1500


def test_position_defaults():
    """Test Position default values."""
    pos = Position(
        signal_id=uuid4(),
        symbol="BTC/USDT",
        direction=Direction.LONG,
        entry_price=50000.0,
        quantity=1.0,
        remaining_qty=1.0,
        stop_loss=48000.0,
    )

    assert pos.status == PositionStatus.OPEN
    assert pos.unrealized_pnl == 0.0
    assert pos.realized_pnl == 0.0
    assert pos.total_fees == 0.0
    assert pos.current_price == 0.0
    assert pos.leverage == 1
    assert pos.closed_at is None
    assert pos.close_reason is None
    assert isinstance(pos.id, UUID)
    assert isinstance(pos.opened_at, datetime)


def test_bot_state_defaults():
    """Test BotState default values."""
    state = BotState()

    assert state.status == BotStatus.STOPPED
    assert state.is_paper_mode is True
    assert state.active_strategies == []
    assert state.started_at is None
    assert state.stopped_at is None
    assert state.total_pnl == 0.0


def test_order_result_defaults():
    """Test OrderResult default values."""
    result = OrderResult(success=True, message="Order placed")

    assert result.success is True
    assert result.order_id is None
    assert result.exchange_order_id is None
    assert result.filled_price is None
    assert result.filled_quantity is None
    assert result.fees == 0.0
    assert result.status == OrderStatus.PENDING


def test_indicator_values_all_optional():
    """Test IndicatorValues - all indicators default to None."""
    ind = IndicatorValues(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    assert ind.ema_9 is None
    assert ind.ema_21 is None
    assert ind.rsi_14 is None
    assert ind.atr_14 is None
    assert ind.vwap is None
    assert ind.macd is None
    assert ind.bb_upper is None
