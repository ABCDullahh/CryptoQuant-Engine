"""API request/response schemas for CryptoQuant Engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# --- Pagination ---


class PaginationParams(BaseModel):
    """Common pagination parameters."""

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    items: list[Any]
    total: int
    limit: int
    offset: int


# --- Auth ---


class TokenRequest(BaseModel):
    """Login request."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


# --- Signal Schemas ---


class SignalListParams(BaseModel):
    """Signal list query filters."""

    symbol: str | None = None
    grade: str | None = None
    direction: str | None = None
    status: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# --- Order Schemas ---


class ExecuteOrderRequest(BaseModel):
    """Execute an order from a signal."""

    signal_id: str
    mode: str = "ONE_CLICK"  # ONE_CLICK or ADVANCED
    entry_price: float | None = None
    stop_loss: float | None = None
    position_size: float | None = None
    leverage: int | None = None
    order_type: str = "MARKET"


class ManualOrderRequest(BaseModel):
    """Place a manual order directly on exchange."""

    symbol: str
    direction: str  # "LONG" or "SHORT"
    order_type: str = "MARKET"  # "MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT"
    quantity: float = Field(gt=0)
    price: float | None = None
    stop_price: float | None = None
    leverage: int = Field(ge=1, le=125, default=1)
    stop_loss: float | None = None
    take_profit: float | None = None
    reduce_only: bool = False
    time_in_force: str = "GTC"


class CancelOrderRequest(BaseModel):
    """Cancel an order."""

    reason: str = "user_cancelled"


# --- Wallet Schemas ---


class TransferRequest(BaseModel):
    """Internal wallet transfer request."""

    from_wallet: str
    to_wallet: str
    currency: str = "USDT"
    amount: float = Field(gt=0)


# --- Position Schemas ---


class UpdateStopLossRequest(BaseModel):
    """Update position stop loss."""

    new_sl: float = Field(gt=0)


class UpdateTakeProfitRequest(BaseModel):
    """Update position take profit levels."""

    take_profits: list[dict[str, Any]]


class ClosePositionRequest(BaseModel):
    """Close a position."""

    close_pct: float = Field(default=100.0, ge=0, le=100)


# --- Bot Schemas ---


class BotStartRequest(BaseModel):
    """Start bot with configuration."""

    symbols: list[str] = Field(default=["BTC/USDT"])
    timeframes: list[str] = Field(default=["1h"])
    strategies: list[str] = Field(default=[])  # empty = all
    initial_balance: float = Field(default=10000.0, gt=0)
    is_paper: bool = True


class BotStrategyUpdate(BaseModel):
    """Enable/disable strategies."""

    strategies: dict[str, bool]


class BotPaperModeUpdate(BaseModel):
    """Toggle paper mode."""

    paper_mode: bool


# --- Backtest Schemas ---


class BacktestRunRequest(BaseModel):
    """Run a backtest."""

    strategy_name: str
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    slippage_bps: float = 5.0
    taker_fee: float = 0.0004
    parameters: dict = {}
    risk_per_trade: float = 0.02
    max_positions: int = 5


class BacktestJobResponse(BaseModel):
    """Backtest job status."""

    job_id: str
    status: str  # QUEUED, RUNNING, COMPLETED, FAILED
    progress: int = 0


class OptimizeRequest(BaseModel):
    """Parameter optimization request."""

    strategy_name: str
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    param_ranges: dict[str, dict]
    optimization_metric: str = "sharpe_ratio"
    max_trials: int = 50


class WalkForwardRequest(BaseModel):
    """Walk-forward analysis request."""

    strategy_name: str
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    in_sample_size: int = 500
    oos_size: int = 168


# --- Settings Schemas ---


class ExchangeSettingsUpdate(BaseModel):
    """Update exchange API keys."""

    api_key: str
    api_secret: str
    testnet: bool = True


class RiskSettingsUpdate(BaseModel):
    """Update risk parameters."""

    default_risk_pct: float | None = None
    max_leverage: int | None = None
    default_leverage: int | None = None
    max_positions: int | None = None
    max_portfolio_heat: float | None = None
    max_daily_loss: float | None = None
    max_drawdown: float | None = None


class DCASettingsUpdate(BaseModel):
    """Update DCA (Dollar Cost Averaging) configuration."""

    enabled: bool | None = None
    max_dca_orders: int | None = None  # 1-5 additional orders
    trigger_drop_pct: list[float] | None = None  # e.g., [2.0, 4.0, 6.0] — % drop from entry for each DCA level
    qty_multiplier: list[float] | None = None  # e.g., [1.0, 1.5, 2.0] — multiplier for each DCA order vs initial
    max_total_risk_pct: float | None = None  # max total portfolio % at risk across all DCA orders
    sl_recalc_mode: str | None = None  # "fixed" (keep original SL) or "follow" (move SL based on new avg entry)
    tp_recalc_mode: str | None = None  # "fixed" (keep TPs) or "recalculate" (recalc from new avg entry)


class NotificationSettingsUpdate(BaseModel):
    """Update notification preferences."""

    telegram_enabled: bool | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    discord_enabled: bool | None = None
    discord_webhook_url: str | None = None


# --- Error Response ---


class ErrorDetail(BaseModel):
    """Error detail."""

    code: str
    message: str
    details: dict = {}


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail


# --- Health ---


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "0.1.0"
    uptime_seconds: float = 0


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    status: str  # "ok" or "error"
    latency_ms: float | None = None
    message: str = ""


class DetailedHealthResponse(BaseModel):
    """Detailed health check with component diagnostics."""

    status: str = "ok"
    version: str = "0.1.0"
    uptime_seconds: float = 0
    environment: str = "demo"
    trading_enabled: bool = False
    bot_status: str = "STOPPED"
    components: dict[str, ComponentHealth] = {}


# ---------------------------------------------------------------------------
# System Status (real-time dashboard)
# ---------------------------------------------------------------------------


class ComponentStatusDetail(BaseModel):
    """Health status of a single system component with extended info."""

    name: str
    status: str  # "ok", "degraded", "error"
    latency_ms: float | None = None
    message: str = ""
    details: dict = {}


class DataFreshness(BaseModel):
    """Data freshness metrics."""

    latest_candle_time: str | None = None
    latest_signal_time: str | None = None
    candle_count: int = 0
    signal_count: int = 0
    candle_age_seconds: float | None = None
    signal_age_seconds: float | None = None


class SystemInfo(BaseModel):
    """System-level metadata."""

    uptime_seconds: float = 0
    python_version: str = ""
    environment: str = "demo"
    trading_enabled: bool = False
    version: str = "0.1.0"
    started_at: str | None = None


class SystemStatusResponse(BaseModel):
    """Comprehensive system status response."""

    overall_status: str  # "ready", "degraded", "offline"
    timestamp: str
    components: list[ComponentStatusDetail]
    data_freshness: DataFreshness
    system_info: SystemInfo


class PingResponse(BaseModel):
    """Simple ping response for client-side RTT measurement."""

    timestamp: float
    server_time: str
