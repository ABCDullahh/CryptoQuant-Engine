"""
Unit tests for app.config.constants module.

Tests enum types, default values, and configuration constants.
"""
import pytest
from app.config.constants import (
    Exchange,
    Direction,
    SignalGrade,
    OrderSide,
    OrderType,
    OrderStatus,
    PositionStatus,
    SignalStatus,
    MarketRegime,
    Timeframe,
    BotStatus,
    StopLossType,
    EventChannel,
    DEFAULT_SYMBOLS,
    DEFAULT_TIMEFRAMES,
    MIN_STRATEGY_AGREEMENT,
    MIN_VOLUME_RATIO,
    SIGNAL_EXPIRY_SECONDS,
    MAX_RISK_PER_TRADE,
    MAX_PORTFOLIO_HEAT,
    MAX_DAILY_LOSS,
    MAX_WEEKLY_LOSS,
    MAX_DRAWDOWN,
    CONSECUTIVE_LOSS_PAUSE,
    CONSECUTIVE_LOSS_REDUCE,
    TP1_RR_RATIO,
    TP1_CLOSE_PCT,
    TP2_RR_RATIO,
    TP2_CLOSE_PCT,
    TP3_RR_RATIO,
    TP3_CLOSE_PCT,
)


class TestEnumTypes:
    """Test that all enums are proper string instances."""

    def test_exchange_is_string_enum(self):
        assert isinstance(Exchange.BINANCE, str)
        assert isinstance(Exchange.BYBIT, str)

    def test_direction_is_string_enum(self):
        assert isinstance(Direction.LONG, str)
        assert isinstance(Direction.SHORT, str)
        assert isinstance(Direction.NEUTRAL, str)

    def test_signal_grade_is_string_enum(self):
        assert isinstance(SignalGrade.A, str)
        assert isinstance(SignalGrade.B, str)

    def test_order_side_is_string_enum(self):
        assert isinstance(OrderSide.BUY, str)
        assert isinstance(OrderSide.SELL, str)

    def test_order_type_is_string_enum(self):
        assert isinstance(OrderType.MARKET, str)
        assert isinstance(OrderType.LIMIT, str)

    def test_order_status_is_string_enum(self):
        assert isinstance(OrderStatus.PENDING, str)
        assert isinstance(OrderStatus.FILLED, str)

    def test_position_status_is_string_enum(self):
        assert isinstance(PositionStatus.OPEN, str)
        assert isinstance(PositionStatus.CLOSED, str)

    def test_signal_status_is_string_enum(self):
        assert isinstance(SignalStatus.ACTIVE, str)
        assert isinstance(SignalStatus.EXECUTED, str)

    def test_market_regime_is_string_enum(self):
        assert isinstance(MarketRegime.TRENDING_UP, str)
        assert isinstance(MarketRegime.RANGING, str)

    def test_timeframe_is_string_enum(self):
        assert isinstance(Timeframe.M1, str)
        assert isinstance(Timeframe.H1, str)

    def test_bot_status_is_string_enum(self):
        assert isinstance(BotStatus.RUNNING, str)
        assert isinstance(BotStatus.STOPPED, str)

    def test_stop_loss_type_is_string_enum(self):
        assert isinstance(StopLossType.ATR_BASED, str)
        assert isinstance(StopLossType.STRUCTURE_BASED, str)


class TestEnumValues:
    """Test that enum values match expected strings."""

    def test_exchange_values(self):
        assert Exchange.BINANCE == "binance"
        assert Exchange.BYBIT == "bybit"

    def test_direction_values(self):
        assert Direction.LONG == "LONG"
        assert Direction.SHORT == "SHORT"
        assert Direction.NEUTRAL == "NEUTRAL"

    def test_signal_grade_values(self):
        assert SignalGrade.A == "A"
        assert SignalGrade.B == "B"
        assert SignalGrade.C == "C"
        assert SignalGrade.D == "D"

    def test_order_side_values(self):
        assert OrderSide.BUY == "BUY"
        assert OrderSide.SELL == "SELL"

    def test_order_type_values(self):
        assert OrderType.MARKET == "MARKET"
        assert OrderType.LIMIT == "LIMIT"
        assert OrderType.STOP_MARKET == "STOP_MARKET"
        assert OrderType.STOP_LIMIT == "STOP_LIMIT"

    def test_timeframe_values(self):
        assert Timeframe.M1 == "1m"
        assert Timeframe.M5 == "5m"
        assert Timeframe.M15 == "15m"
        assert Timeframe.H1 == "1h"
        assert Timeframe.H4 == "4h"
        assert Timeframe.D1 == "1d"

    def test_market_regime_values(self):
        assert MarketRegime.TRENDING_UP == "TRENDING_UP"
        assert MarketRegime.TRENDING_DOWN == "TRENDING_DOWN"
        assert MarketRegime.RANGING == "RANGING"
        assert MarketRegime.HIGH_VOLATILITY == "HIGH_VOLATILITY"

    def test_stop_loss_type_values(self):
        assert StopLossType.ATR_BASED == "ATR_BASED"
        assert StopLossType.STRUCTURE_BASED == "STRUCTURE_BASED"
        assert StopLossType.PERCENTAGE == "PERCENTAGE"
        assert StopLossType.ORDER_BLOCK == "ORDER_BLOCK"


class TestEnumMembership:
    """Test enum membership and iteration."""

    def test_direction_has_three_members(self):
        assert len(Direction) == 3
        assert Direction.LONG in Direction
        assert Direction.SHORT in Direction
        assert Direction.NEUTRAL in Direction

    def test_signal_grade_has_four_members(self):
        assert len(SignalGrade) == 4
        assert SignalGrade.A in SignalGrade
        assert SignalGrade.D in SignalGrade

    def test_timeframe_has_six_members(self):
        assert len(Timeframe) == 6
        assert Timeframe.M1 in Timeframe
        assert Timeframe.D1 in Timeframe

    def test_can_iterate_over_enum(self):
        directions = [d for d in Direction]
        assert len(directions) == 3
        assert Direction.LONG in directions


class TestEnumStringComparison:
    """Test that StrEnum can be compared with plain strings."""

    def test_direction_string_comparison(self):
        assert Direction.LONG == "LONG"
        assert "LONG" == Direction.LONG
        assert Direction.SHORT != "LONG"

    def test_timeframe_string_comparison(self):
        assert Timeframe.H1 == "1h"
        assert "1h" == Timeframe.H1
        assert Timeframe.M15 == "15m"

    def test_signal_grade_string_comparison(self):
        assert SignalGrade.A == "A"
        assert "B" == SignalGrade.B

    def test_exchange_string_comparison(self):
        assert Exchange.BINANCE == "binance"
        assert "bybit" == Exchange.BYBIT


class TestEventChannel:
    """Test EventChannel format strings."""

    def test_market_candle_format(self):
        channel = EventChannel.MARKET_CANDLE.format(timeframe="1h")
        assert channel == "market.candle.1h"

        channel = EventChannel.MARKET_CANDLE.format(timeframe="15m")
        assert channel == "market.candle.15m"

    def test_event_channel_is_plain_class(self):
        # EventChannel should be a regular class with string attributes
        assert hasattr(EventChannel, "MARKET_CANDLE")
        assert isinstance(EventChannel.MARKET_CANDLE, str)


class TestDefaultConstants:
    """Test default configuration constants."""

    def test_default_symbols_count(self):
        assert len(DEFAULT_SYMBOLS) == 5

    def test_default_symbols_contains_btc(self):
        assert "BTC/USDT" in DEFAULT_SYMBOLS

    def test_default_symbols_values(self):
        expected = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
        assert DEFAULT_SYMBOLS == expected

    def test_default_timeframes_count(self):
        assert len(DEFAULT_TIMEFRAMES) == 4

    def test_default_timeframes_are_timeframe_instances(self):
        for tf in DEFAULT_TIMEFRAMES:
            assert isinstance(tf, Timeframe)

    def test_default_timeframes_values(self):
        assert Timeframe.M15 in DEFAULT_TIMEFRAMES
        assert Timeframe.H1 in DEFAULT_TIMEFRAMES
        assert Timeframe.H4 in DEFAULT_TIMEFRAMES
        assert Timeframe.D1 in DEFAULT_TIMEFRAMES

    def test_min_strategy_agreement(self):
        assert MIN_STRATEGY_AGREEMENT == 1
        assert isinstance(MIN_STRATEGY_AGREEMENT, int)

    def test_min_volume_ratio(self):
        assert MIN_VOLUME_RATIO == 1.0
        assert isinstance(MIN_VOLUME_RATIO, float)

    def test_signal_expiry_seconds(self):
        assert SIGNAL_EXPIRY_SECONDS == 900
        assert isinstance(SIGNAL_EXPIRY_SECONDS, int)


class TestRiskConstants:
    """Test risk management constants are within valid ranges."""

    def test_max_risk_per_trade_range(self):
        assert 0 < MAX_RISK_PER_TRADE < 1
        assert MAX_RISK_PER_TRADE == 0.02

    def test_max_portfolio_heat_range(self):
        assert 0 < MAX_PORTFOLIO_HEAT < 1
        assert MAX_PORTFOLIO_HEAT == 0.20

    def test_max_daily_loss_range(self):
        assert 0 < MAX_DAILY_LOSS < 1
        assert MAX_DAILY_LOSS == 0.05

    def test_max_weekly_loss_range(self):
        assert 0 < MAX_WEEKLY_LOSS < 1
        assert MAX_WEEKLY_LOSS == 0.10

    def test_max_drawdown_range(self):
        assert 0 < MAX_DRAWDOWN < 1
        assert MAX_DRAWDOWN == 0.15

    def test_consecutive_loss_values(self):
        assert CONSECUTIVE_LOSS_PAUSE == 5
        assert CONSECUTIVE_LOSS_REDUCE == 3
        assert isinstance(CONSECUTIVE_LOSS_PAUSE, int)
        assert isinstance(CONSECUTIVE_LOSS_REDUCE, int)


class TestTakeProfitConstants:
    """Test take profit configuration constants."""

    def test_tp1_values(self):
        assert TP1_RR_RATIO == 1.5
        assert TP1_CLOSE_PCT == 50

    def test_tp2_values(self):
        assert TP2_RR_RATIO == 3.0
        assert TP2_CLOSE_PCT == 30

    def test_tp3_values(self):
        assert TP3_RR_RATIO == 5.0
        assert TP3_CLOSE_PCT == 20

    def test_tp_levels_sum_to_100_percent(self):
        total_pct = TP1_CLOSE_PCT + TP2_CLOSE_PCT + TP3_CLOSE_PCT
        assert total_pct == 100

    def test_tp_risk_reward_ascending(self):
        assert TP1_RR_RATIO < TP2_RR_RATIO < TP3_RR_RATIO
