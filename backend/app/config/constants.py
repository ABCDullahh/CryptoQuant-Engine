"""Constants and enumerations for CryptoQuant Engine."""

from enum import StrEnum


class Exchange(StrEnum):
    """Supported exchanges."""
    BINANCE = "binance"
    BYBIT = "bybit"


class Direction(StrEnum):
    """Trading direction."""
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class SignalGrade(StrEnum):
    """Signal quality grade."""
    A = "A"  # Strong signal (score >= 0.80)
    B = "B"  # Good signal (score >= 0.60)
    C = "C"  # Weak signal (score >= 0.40)
    D = "D"  # No trade (score < 0.40)


class OrderSide(StrEnum):
    """Order side."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    """Order type."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(StrEnum):
    """Order lifecycle status."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PositionStatus(StrEnum):
    """Position lifecycle status."""
    OPEN = "OPEN"
    MONITORING = "MONITORING"
    REDUCING = "REDUCING"
    CLOSED = "CLOSED"


class SignalStatus(StrEnum):
    """Signal lifecycle status."""
    ACTIVE = "ACTIVE"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class MarketRegime(StrEnum):
    """Market regime classification."""
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    CHOPPY = "CHOPPY"


class Timeframe(StrEnum):
    """Supported candlestick timeframes."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class BotStatus(StrEnum):
    """Auto-bot status."""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"


class StopLossType(StrEnum):
    """Stop loss calculation method."""
    ATR_BASED = "ATR_BASED"
    STRUCTURE_BASED = "STRUCTURE_BASED"
    PERCENTAGE = "PERCENTAGE"
    ORDER_BLOCK = "ORDER_BLOCK"
    COMBINED = "COMBINED"


class CircuitBreakerState(StrEnum):
    """Circuit breaker state machine."""
    CLOSED = "CLOSED"        # Normal operation
    OPEN = "OPEN"            # Trading halted
    HALF_OPEN = "HALF_OPEN"  # Testing with reduced size


class CircuitBreakerAction(StrEnum):
    """Circuit breaker action type."""
    REDUCE_50 = "REDUCE_50"    # Reduce position sizes by 50%
    PAUSE_4H = "PAUSE_4H"     # Pause for 4 hours
    STOP_24H = "STOP_24H"     # Stop for 24 hours
    FULL_STOP = "FULL_STOP"   # Full stop, manual review


class CloseReason(StrEnum):
    """Reason a position was closed."""
    SL_HIT = "SL_HIT"
    TP1_HIT = "TP1_HIT"
    TP2_HIT = "TP2_HIT"
    TP3_HIT = "TP3_HIT"
    TRAILING_STOP = "TRAILING_STOP"
    MANUAL_CLOSE = "MANUAL_CLOSE"
    LIQUIDATION = "LIQUIDATION"
    EXPIRED = "EXPIRED"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"


# Redis Pub/Sub channel patterns
class EventChannel:
    """Redis Pub/Sub channel names."""
    MARKET_CANDLE = "market.candle.{timeframe}"
    MARKET_TRADE = "market.trade"
    MARKET_ORDERBOOK = "market.orderbook"
    MARKET_FUNDING = "market.funding"
    SIGNAL_RAW = "signal.raw.{strategy}"
    SIGNAL_COMPOSITE = "signal.composite"
    SIGNAL_APPROVED = "signal.approved"
    ORDER_PLACED = "order.placed"
    ORDER_FILLED = "order.filled"
    POSITION_UPDATE = "position.update"
    POSITION_CLOSED = "position.closed"
    RISK_ALERT = "risk.alert"
    RISK_CIRCUIT_BREAKER = "risk.circuit_breaker"
    BOT_STATUS = "bot.status"
    SYSTEM_HEALTH = "system.health"


# Default trading parameters
DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
DEFAULT_TIMEFRAMES = [Timeframe.M15, Timeframe.H1, Timeframe.H4, Timeframe.D1]

# Signal aggregation
MIN_STRATEGY_AGREEMENT = 1  # At least 1 strategy must fire for signal generation
MIN_VOLUME_RATIO = 1.0  # Volume must be >= 20-period average
SIGNAL_EXPIRY_SECONDS = 900  # 15 minutes

# Risk defaults
MAX_RISK_PER_TRADE = 0.02  # 2%
MAX_RISK_PER_TRADE_ABSOLUTE = 0.03  # 3% absolute max
MAX_PORTFOLIO_HEAT = 0.20  # 20% — allows multiple concurrent positions
MAX_DAILY_LOSS = 0.05  # 5%
MAX_WEEKLY_LOSS = 0.10  # 10%
MAX_DRAWDOWN = 0.15  # 15%
CONSECUTIVE_LOSS_PAUSE = 5
CONSECUTIVE_LOSS_REDUCE = 3
MAX_OPEN_POSITIONS = 5
MAX_CORRELATED_POSITIONS = 3
MAX_SL_PERCENT = 0.03  # 3% max SL distance from entry
MIN_SL_PERCENT = 0.005  # 0.5% min SL distance from entry (prevent noise stops)
DEFAULT_LEVERAGE = 3
MAX_LEVERAGE = 10
CIRCUIT_BREAKER_COOLDOWN_HOURS = 4

# ATR multipliers per market regime
ATR_MULTIPLIER_TRENDING = 2.0
ATR_MULTIPLIER_RANGING = 1.5
ATR_MULTIPLIER_VOLATILE = 2.5
ATR_MULTIPLIER_LOW_VOL = 1.5
ATR_MULTIPLIER_DEFAULT = 1.5

# --- Order Block Zone Strategy Constants ---
OB_ZONE_LOOKBACK = 5
OB_ZONE_VOLUME_THRESHOLD = 1.5
OB_ZONE_BODY_RATIO = 0.60
OB_ZONE_ATR_MULT = 2.0
OB_ZONE_SL_ATR_MULT = 0.3
OB_ZONE_SL_MIN_PCT = 0.0015
OB_ZONE_MIN_SCORE = 0.50
OB_ZONE_MIN_RR = 1.0
OB_ZONE_MAX_TOUCH = 3
OB_ZONE_MAX_AGE_CANDLES = 500
OB_ZONE_MAX_DISTANCE_ATR = 3.0
OB_ZONE_RSI_DIV_LOOKBACK = 10
OB_ZONE_WEIGHT = 0.20

# Kelly criterion
KELLY_FRACTION = 0.25  # Use 25% of full Kelly

# Trailing stop
TRAILING_STOP_ATR_MULTIPLIER = 1.0

# Take profit defaults
TP1_RR_RATIO = 1.5
TP1_CLOSE_PCT = 50
TP2_RR_RATIO = 3.0
TP2_CLOSE_PCT = 30
TP3_RR_RATIO = 5.0
TP3_CLOSE_PCT = 20

# Execution engine defaults
DEFAULT_SLIPPAGE_BPS = 5.0       # 0.05% default slippage
MAKER_FEE = 0.0002               # 0.02% maker fee
TAKER_FEE = 0.0004               # 0.04% taker fee
ORDER_TIMEOUT_SECONDS = 30       # Order timeout before cancel
MAX_RETRIES = 3                  # Max retries on exchange error
RETRY_DELAY_SECONDS = 2.0        # Base retry delay (exponential backoff)
PRICE_STALENESS_SECONDS = 10     # Alert if price older than this
POSITION_SYNC_INTERVAL = 300     # Re-sync positions with exchange every 5 min
TRAILING_STOP_CALLBACK_PCT = 0.005  # 0.5% trailing callback

# Entry zone tolerance for order execution
ENTRY_ZONE_PCT = 0.002  # ±0.2% — configurable via this constant

# Available strategies (single source of truth for FE/BE)
AVAILABLE_STRATEGIES = [
    {"id": "momentum", "label": "Momentum"},
    {"id": "mean_reversion", "label": "Mean Reversion"},
    {"id": "smart_money", "label": "Smart Money"},
    {"id": "volume_analysis", "label": "Volume Analysis"},
    {"id": "funding_arb", "label": "Funding Arbitrage"},
    {"id": "ob_zones", "label": "Order Block Zones"},
]

APP_VERSION = "0.1.0"

# Regime position size multiplier (adapt, don't block)
REGIME_POSITION_MULTIPLIER = {
    "TRENDING_UP": 1.0,
    "TRENDING_DOWN": 1.0,
    "RANGING": 0.85,
    "HIGH_VOLATILITY": 0.50,
    "LOW_VOLATILITY": 0.90,
    "CHOPPY": 0.60,
}

# Grade risk multiplier (higher grade = more risk allowed)
GRADE_RISK_MULTIPLIER = {
    "A": 1.0,
    "B": 0.75,
    "C": 0.50,
    "D": 0.0,
}

# Multi-timeframe higher timeframe mapping
HIGHER_TF_MAP = {
    "1m": "15m",
    "5m": "1h",
    "15m": "4h",
    "1h": "4h",
    "4h": "1d",
    "1d": "1d",
}

# Multi-timeframe alignment boost/penalty
MTF_ALIGNMENT_BOOST = 0.15
MTF_MISALIGNMENT_PENALTY = 0.20

# Signal execution policy presets
SIGNAL_POLICY_PRESETS = {
    "conservative": {
        "momentum": {"A": "alert", "B": "alert", "C": "alert", "D": "skip"},
        "mean_reversion": {"A": "alert", "B": "alert", "C": "alert", "D": "skip"},
        "smart_money": {"A": "alert", "B": "alert", "C": "alert", "D": "skip"},
        "volume_analysis": {"A": "alert", "B": "alert", "C": "alert", "D": "skip"},
        "funding_arb": {"A": "alert", "B": "alert", "C": "skip", "D": "skip"},
        "ob_zones": {"A": "alert", "B": "alert", "C": "alert", "D": "skip"},
    },
    "balanced": {
        "momentum": {"A": "auto", "B": "alert", "C": "skip", "D": "skip"},
        "mean_reversion": {"A": "alert", "B": "alert", "C": "skip", "D": "skip"},
        "smart_money": {"A": "auto", "B": "alert", "C": "alert", "D": "skip"},
        "volume_analysis": {"A": "auto", "B": "alert", "C": "skip", "D": "skip"},
        "funding_arb": {"A": "alert", "B": "alert", "C": "skip", "D": "skip"},
        "ob_zones": {"A": "auto", "B": "alert", "C": "skip", "D": "skip"},
    },
    "aggressive": {
        "momentum": {"A": "auto", "B": "auto", "C": "alert", "D": "skip"},
        "mean_reversion": {"A": "alert", "B": "alert", "C": "skip", "D": "skip"},
        "smart_money": {"A": "auto", "B": "alert", "C": "alert", "D": "skip"},
        "volume_analysis": {"A": "auto", "B": "auto", "C": "alert", "D": "skip"},
        "funding_arb": {"A": "alert", "B": "alert", "C": "skip", "D": "skip"},
        "ob_zones": {"A": "auto", "B": "auto", "C": "alert", "D": "skip"},
    },
}
