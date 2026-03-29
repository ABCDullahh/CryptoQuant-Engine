"""Pydantic models for CryptoQuant Engine core data types."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.config.constants import (
    BotStatus,
    Direction,
    MarketRegime,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionStatus,
    SignalGrade,
    SignalStatus,
    StopLossType,
)


# --- Market Data Models ---


class Candle(BaseModel):
    """OHLCV candlestick data."""

    time: datetime
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float | None = None
    trades_count: int | None = None


class OrderBook(BaseModel):
    """Order book snapshot."""

    symbol: str
    timestamp: datetime
    bids: list[tuple[float, float]]  # (price, quantity)
    asks: list[tuple[float, float]]


class FundingRate(BaseModel):
    """Perpetual futures funding rate."""

    symbol: str
    timestamp: datetime
    rate: float
    next_funding_time: datetime | None = None


# --- Indicator Data ---


class IndicatorValues(BaseModel):
    """Computed indicator values attached to a candle."""

    symbol: str
    timeframe: str
    timestamp: datetime

    # Trend
    ema_9: float | None = None
    ema_21: float | None = None
    ema_55: float | None = None
    ema_200: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    adx: float | None = None

    # Momentum
    rsi_14: float | None = None
    stoch_k: float | None = None
    stoch_d: float | None = None

    # Volatility
    atr_14: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    bb_width: float | None = None

    # Volume
    vwap: float | None = None
    obv: float | None = None
    volume_sma_20: float | None = None
    mfi: float | None = None


class MarketData(BaseModel):
    """Combined market data passed to strategies."""

    candle: Candle
    indicators: IndicatorValues | None = None
    orderbook: OrderBook | None = None
    funding_rate: FundingRate | None = None


# --- Signal Models ---


class RawSignal(BaseModel):
    """Individual strategy signal output."""

    strategy_name: str
    symbol: str
    direction: Direction
    strength: float = Field(ge=-1.0, le=1.0)
    entry_price: float
    timeframe: str
    conditions: list[str] = []
    metadata: dict = {}


class TakeProfit(BaseModel):
    """Take profit level."""

    level: str  # "TP1", "TP2", "TP3"
    price: float
    close_pct: int  # Percentage of position to close
    rr_ratio: float


class RiskReward(BaseModel):
    """Risk-reward ratios."""

    rr_tp1: float
    rr_tp2: float | None = None
    rr_tp3: float | None = None
    weighted_rr: float


class PositionSize(BaseModel):
    """Position sizing result."""

    quantity: float
    notional: float
    margin: float
    risk_amount: float
    risk_pct: float
    leverage: int


class MarketContext(BaseModel):
    """Current market context."""

    regime: MarketRegime = MarketRegime.RANGING
    trend_1h: str = "NEUTRAL"
    trend_4h: str = "NEUTRAL"
    trend_1d: str = "NEUTRAL"
    volatility: str = "MEDIUM"
    volume_profile: str = "AVERAGE"
    fear_greed_index: int | None = None


class CompositeSignal(BaseModel):
    """Aggregated signal from multiple strategies."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    symbol: str
    direction: Direction
    grade: SignalGrade
    strength: float = Field(ge=0.0, le=1.0)
    entry_price: float
    entry_zone: tuple[float, float]
    stop_loss: float
    sl_type: StopLossType
    take_profits: list[TakeProfit]
    risk_reward: RiskReward
    position_size: PositionSize
    strategy_scores: dict[str, float]
    market_context: MarketContext
    ml_confidence: float | None = None
    status: SignalStatus = SignalStatus.ACTIVE


# --- Order Models ---


class OrderIntent(BaseModel):
    """Order intent to be executed."""

    id: UUID = Field(default_factory=uuid4)
    signal_id: UUID
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float | None = None
    quantity: float
    stop_loss: float
    take_profits: list[TakeProfit]
    leverage: int = 1
    is_paper: bool = False


class OrderResult(BaseModel):
    """Result of order execution."""

    success: bool
    order_id: str | None = None
    exchange_order_id: str | None = None
    message: str
    filled_price: float | None = None
    filled_quantity: float | None = None
    fees: float = 0.0
    status: OrderStatus = OrderStatus.PENDING


# --- Position Models ---


class Position(BaseModel):
    """Active trading position."""

    id: UUID = Field(default_factory=uuid4)
    signal_id: UUID
    symbol: str
    direction: Direction
    entry_price: float
    current_price: float = 0.0
    quantity: float
    remaining_qty: float
    leverage: int = 1
    stop_loss: float
    take_profits: list[TakeProfit] = []
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_fees: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    opened_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    closed_at: datetime | None = None
    close_reason: str | None = None


# --- Portfolio Models ---


class PortfolioState(BaseModel):
    """Current portfolio state."""

    balance: float = 0.0
    equity: float = 0.0
    unrealized_pnl: float = 0.0
    margin_used: float = 0.0
    margin_available: float = 0.0
    portfolio_heat: float = 0.0  # Total % at risk
    open_positions: int = 0
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    max_drawdown: float = 0.0
    consecutive_losses: int = 0


# --- Backtest Models ---


class BacktestConfig(BaseModel):
    """Backtest configuration."""

    strategy_name: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    risk_per_trade: float = 0.02
    max_positions: int = 5
    slippage_bps: float = 5.0
    maker_fee: float = 0.0002
    taker_fee: float = 0.0004
    parameters: dict = {}


class BacktestResult(BaseModel):
    """Backtest execution result."""

    id: UUID = Field(default_factory=uuid4)
    config: BacktestConfig
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_holding_period: str = ""
    expectancy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    calmar_ratio: float = 0.0
    equity_curve: list[dict] = []
    trades: list[dict] = []
    monthly_returns: dict = {}


# --- Bot Models ---


class BotState(BaseModel):
    """Auto-bot state."""

    status: BotStatus = BotStatus.STOPPED
    is_paper_mode: bool = True
    active_strategies: list[str] = []
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    total_pnl: float = 0.0


# --- Event Models ---


class EventMessage(BaseModel):
    """Base event message for Redis Pub/Sub."""

    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    correlation_id: str | None = None
    data: dict = {}
