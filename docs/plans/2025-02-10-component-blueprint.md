# CryptoQuant Engine - Component Blueprint

**Date:** 2025-02-10
**Purpose:** Dependency maps, data flows, state machines, interface contracts, concurrency model, error handling

---

## Table of Contents

1. [Component Dependency Map](#1-component-dependency-map)
2. [Build Order (Critical Path)](#2-build-order)
3. [Data Flow Diagrams](#3-data-flow-diagrams)
4. [State Machines](#4-state-machines)
5. [Interface Contracts](#5-interface-contracts)
6. [Concurrency Model](#6-concurrency-model)
7. [Error Handling Matrix](#7-error-handling-matrix)
8. [Implementation Phases Checklist](#8-implementation-phases-checklist)

---

## 1. Component Dependency Map

```
                    ┌─────────────┐
                    │   Config    │  (no dependencies)
                    │   Models    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼────┐ ┌────▼──────┐
        │ Database  │ │ Redis  │ │  Logger   │
        │ (TimescaleDB)│ │ Client │ │ (structlog)│
        └─────┬─────┘ └───┬────┘ └───────────┘
              │            │
              └──────┬─────┘
                     │
              ┌──────▼──────┐
              │  Event Bus  │  (Redis Pub/Sub wrapper)
              └──────┬──────┘
                     │
         ┌───────────┼────────────────────┐
         │           │                    │
   ┌─────▼─────┐ ┌──▼───────┐ ┌─────────▼────────┐
   │   Data    │ │Indicators│ │  Sentiment       │
   │ Collector │ │ Library  │ │  Collector        │
   └─────┬─────┘ └──┬───────┘ └─────────┬────────┘
         │           │                    │
         └───────────┼────────────────────┘
                     │
              ┌──────▼──────┐
              │  Strategy   │  (depends on: Data, Indicators, Sentiment)
              │  Engine     │
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │   Signal    │  (depends on: Strategy Engine)
              │ Aggregator  │
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │    Risk     │  (depends on: Signal Aggregator, Portfolio State)
              │  Manager    │
              └──────┬──────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
   ┌─────▼─────┐ ┌──▼────────┐ ┌▼─────────────┐
   │ Execution │ │  ML/AI    │ │ Backtesting   │
   │  Engine   │ │  Engine   │ │ Engine        │
   └─────┬─────┘ └───────────┘ └───────────────┘
         │
   ┌─────▼──────┐
   │ Position   │
   │ Tracker    │
   └─────┬──────┘
         │
   ┌─────▼──────┐     ┌──────────────┐
   │Notifications│     │  FastAPI      │
   │ (TG/Discord)│     │  Backend     │
   └─────────────┘     └──────┬───────┘
                              │
                       ┌──────▼───────┐
                       │  Next.js 16  │
                       │  Frontend    │
                       └──────────────┘
```

### Dependency Rules
1. **No circular dependencies** - data flows downward only
2. **Event bus decouples components** - publishers don't know subscribers
3. **Each component has a single owner** - no shared mutable state
4. **Config/Models are the only shared layer** - everything else communicates via events

---

## 2. Build Order (Critical Path)

```
Phase │ Week │ Component                    │ Depends On           │ Critical?
──────┼──────┼──────────────────────────────┼──────────────────────┼──────────
1     │ 1-2  │ Config + Models              │ (none)               │ YES
1     │ 1-2  │ Database + Redis + Logger    │ Config               │ YES
1     │ 1-2  │ Event Bus                    │ Redis                │ YES
2     │ 3-4  │ Data Collector               │ Event Bus, DB        │ YES
2     │ 3-4  │ Historical Data Loader       │ DB                   │ YES
3     │ 5-6  │ Indicator Library            │ (standalone)         │ YES
3     │ 5-7  │ Strategy Engine              │ Data, Indicators     │ YES
3     │ 7    │ Signal Aggregator            │ Strategy Engine      │ YES
4     │ 8-9  │ Risk Manager                 │ Signal Aggregator    │ YES
5     │ 10   │ Execution Engine             │ Risk Manager         │ YES
5     │ 10   │ Position Tracker             │ Execution Engine     │ YES
6     │ 11-12│ Backtesting Engine           │ Strategies, Risk     │ NO (parallel)
7     │ 13-16│ FastAPI Backend              │ All backend          │ YES
7     │ 13-16│ Next.js Frontend             │ FastAPI              │ YES
8     │ 17-18│ ML/AI Layer                  │ Features, Training   │ NO (parallel)
9     │ 19-20│ Notifications                │ Events               │ NO (parallel)
10    │ 21-22│ Docker + Deploy              │ All                  │ YES
```

**Critical path**: Config → DB/Redis → Event Bus → Data Collector → Indicators → Strategies → Aggregator → Risk → Execution → FastAPI → Frontend → Deploy

**Parallelizable**: Backtesting, ML/AI, Notifications (can be built alongside main path)

---

## 3. Data Flow Diagrams

### 3.1 Signal Generation Flow

```
Binance WebSocket
       │
       ▼
DataCollector.stream_ohlcv()
       │
       ├── Store in TimescaleDB (candles table)
       ├── Cache in Redis (candle:{symbol}:{tf})
       └── Publish to "market.candle.{tf}" channel
                    │
                    ▼
            IndicatorEngine.on_candle()
                    │
                    ├── Calculate: RSI, MACD, EMA, ATR, BB, VWAP, OBV
                    ├── Cache in Redis (indicator:{symbol}:{tf}:{name})
                    └── Attach to MarketData object
                              │
                              ▼
                    StrategyEngine.evaluate_all()
                              │
                    ┌─────────┼─────────┬──────────┐
                    │         │         │          │
                    ▼         ▼         ▼          ▼
              Momentum   MeanRev    SMC       Volume
              Strategy   Strategy   Strategy   Strategy
                    │         │         │          │
                    └─────────┼─────────┴──────────┘
                              │
                              ▼ (list of RawSignals)
                    SignalAggregator.aggregate()
                              │
                              ├── Calculate weighted composite score
                              ├── Check minimum agreement (3/7)
                              ├── Check volume confirmation
                              ├── Grade signal (A/B/C/D)
                              └── Publish to "signal.composite" channel
                                        │
                                        ▼
                              RiskManager.evaluate()
                                        │
                                        ├── Check portfolio heat
                                        ├── Check position limits
                                        ├── Check circuit breakers
                                        ├── Calculate position size
                                        ├── Calculate SL/TP levels
                                        └── If approved → "signal.approved"
                                                  │
                                                  ▼
                                        Dashboard (display to user)
                                                  │
                                        ┌─────────┴─────────┐
                                        │                   │
                                        ▼                   ▼
                               [One-Click Execute]   [Auto-Bot Execute]
                                        │                   │
                                        └─────────┬─────────┘
                                                  │
                                                  ▼
                                        ExecutionEngine.execute()
                                                  │
                                                  └── Place order on Binance
```

### 3.2 Position Lifecycle Flow

```
Order Filled (from Binance)
       │
       ▼
PositionTracker.open_position()
       │
       ├── Create position record (DB + Redis)
       ├── Place SL order on exchange
       ├── Place TP1/TP2/TP3 limit orders
       ├── Publish "position.update" event
       └── Start monitoring loop
                │
                ▼
    ┌───── Monitor Loop (1s interval) ─────┐
    │                                       │
    │  Get current price                   │
    │  Update unrealized P&L               │
    │  Check SL hit?  ──YES──► Close 100%  │
    │  Check TP1 hit? ──YES──► Close 50%   │
    │    └── Move SL to breakeven          │
    │  Check TP2 hit? ──YES──► Close 30%   │
    │    └── Activate trailing stop        │
    │  Check TP3 hit? ──YES──► Close 20%   │
    │  Check liquidation risk?             │
    │  Re-sync with exchange (every 5min)  │
    │                                       │
    └───────────────────────────────────────┘
                │
                ▼ (when position fully closed)
    PositionTracker.close_position()
       │
       ├── Record final P&L
       ├── Update signals table (outcome)
       ├── Publish "position.closed" event
       ├── Update portfolio state
       └── Notify user (Telegram/Discord)
```

### 3.3 Backtest Flow

```
User submits backtest request (Frontend)
       │
       ▼
POST /api/backtest/run
       │
       ▼
BacktestEngine.run(config)  [async background task]
       │
       ├── 1. Load historical candles from TimescaleDB
       ├── 2. Calculate all indicators
       ├── 3. For each candle (chronological):
       │       ├── Feed to strategy
       │       ├── If signal → RiskManager.evaluate()
       │       ├── If approved → Simulator.fill(signal)
       │       │   └── Apply slippage model + fees
       │       ├── Update positions (check SL/TP)
       │       └── Record equity point
       ├── 4. Calculate performance metrics
       ├── 5. Store results in backtest_runs table
       └── 6. Return BacktestResult
                │
                ▼
       Frontend displays:
       - Equity curve chart
       - Drawdown chart
       - Trade list table
       - Metrics dashboard (Sharpe, MDD, WR, PF)
```

---

## 4. State Machines

### 4.1 Signal State Machine

```
  ┌──────────┐
  │ GENERATED│ ←── SignalAggregator creates composite signal
  └────┬─────┘
       │ RiskManager evaluates
       │
  ┌────▼─────┐         ┌──────────┐
  │ APPROVED │         │ REJECTED │ ←── Risk limits exceeded
  └────┬─────┘         └──────────┘
       │ User/Bot decides to execute
       │
  ┌────▼─────────┐     ┌──────────┐
  │ EXECUTING    │     │ EXPIRED  │ ←── Signal timeout (e.g., 15min)
  └────┬─────────┘     └──────────┘
       │ Order filled
       │
  ┌────▼─────────┐
  │ IN_POSITION  │ ←── Position opened, monitoring active
  └────┬─────────┘
       │ Position closed (SL/TP/manual)
       │
  ┌────▼─────────┐
  │  COMPLETED   │ ←── Final P&L recorded
  └──────────────┘
       │
       ├── outcome: WIN (P&L > 0)
       ├── outcome: LOSS (P&L < 0)
       └── outcome: BREAKEVEN
```

### 4.2 Auto-Bot State Machine

```
  ┌──────────┐
  │ STOPPED  │ ←── Initial state / user clicked Stop
  └────┬─────┘
       │ User clicks Start
       │
  ┌────▼──────────────────────────┐
  │ STARTING                       │
  │ - Load strategies              │
  │ - Connect to exchange          │
  │ - Verify API keys              │
  │ - Start data streams           │
  └────┬──────────────────────────┘
       │ All connections ready
       │
  ┌────▼──────────────────────────┐
  │ RUNNING                        │
  │ - Processing signals           │     ┌────────────────┐
  │ - Auto-executing trades        │◄────┤ User clicks    │
  │ - Monitoring positions         │     │ Resume         │
  └────┬─────────────┬────────────┘     └────────────────┘
       │             │                          ▲
       │ User clicks │ Circuit breaker          │
       │ Pause       │ triggered                │
       │             │                          │
  ┌────▼─────────────▼────────────┐             │
  │ PAUSED                         │─────────────┘
  │ - No new trades                │
  │ - Existing positions monitored │
  │ - Data streams still active    │
  └────┬──────────────────────────┘
       │ User clicks Stop
       │
  ┌────▼──────────────────────────┐
  │ STOPPING                       │
  │ - Cancel pending orders        │
  │ - Optionally close positions   │
  │ - Disconnect streams           │
  └────┬──────────────────────────┘
       │
       ▼
  ┌──────────┐
  │ STOPPED  │
  └──────────┘

  Paper Mode Toggle: Can be changed in any state.
  When paper=true, ExecutionEngine uses PaperTrader instead of real exchange.
```

### 4.3 Order State Machine

```
  ┌──────────┐
  │ PENDING  │ ←── Order created, not yet submitted
  └────┬─────┘
       │ Submit to exchange
       │
  ┌────▼─────────┐
  │ SUBMITTED    │ ←── Sent to exchange, awaiting fill
  └────┬─────────┘
       │
  ┌────┼──────────────────────────────────┐
  │    │                                   │
  │    ▼                                   ▼
  │ ┌──────────────┐              ┌────────────┐
  │ │PARTIALLY_FILLED│              │ CANCELLED  │ ←── User cancelled / timeout
  │ └────┬─────────┘              └────────────┘
  │      │                                 ▲
  │      ▼                                 │
  │ ┌──────────┐                           │
  │ │ FILLED   │ ←── All quantity filled   │
  │ └──────────┘                           │
  │      │ Time-in-force expired ──────────┘
  └──────┘
```

### 4.4 Circuit Breaker State Machine

```
  ┌──────────┐
  │ CLOSED   │ ←── Normal operation, trading allowed
  └────┬─────┘
       │ Trigger condition met (e.g., 5 consecutive losses)
       │
  ┌────▼─────┐
  │ OPEN     │ ←── Trading halted
  │          │     - No new positions
  │          │     - Existing positions monitored
  │          │     - Alert sent to user
  └────┬─────┘
       │ Cooldown period elapsed (e.g., 4 hours)
       │
  ┌────▼─────────┐
  │ HALF_OPEN    │ ←── Testing with reduced size (50%)
  └────┬─────────┘
       │
  ┌────┼─────────────────────────┐
  │    │                          │
  │    ▼ (trade succeeds)        ▼ (trade fails)
  │ ┌──────────┐          ┌──────────┐
  │ │ CLOSED   │          │ OPEN     │ (reset cooldown)
  │ └──────────┘          └──────────┘
  └──────────────────────────────────┘
```

---

## 5. Interface Contracts

### 5.1 Core Data Models (Pydantic)

```python
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from enum import Enum

class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class SignalGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"

class Candle(BaseModel):
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

class RawSignal(BaseModel):
    strategy_name: str
    symbol: str
    direction: Direction
    strength: float          # [-1.0, +1.0]
    entry_price: float
    timeframe: str
    conditions: list[str]
    metadata: dict = {}

class CompositeSignal(BaseModel):
    id: UUID
    created_at: datetime
    symbol: str
    direction: Direction
    grade: SignalGrade
    strength: float          # [0.0, 1.0]
    entry_price: float
    entry_zone: tuple[float, float]
    stop_loss: float
    sl_type: str
    take_profits: list[TakeProfit]
    risk_reward: RiskReward
    position_size: PositionSize
    strategy_scores: dict[str, float]
    market_context: MarketContext
    ml_confidence: float | None = None

class TakeProfit(BaseModel):
    level: str               # "TP1", "TP2", "TP3"
    price: float
    close_pct: int           # 50, 30, 20
    rr_ratio: float

class RiskReward(BaseModel):
    rr_tp1: float
    rr_tp2: float | None
    rr_tp3: float | None
    weighted_rr: float

class PositionSize(BaseModel):
    quantity: float
    notional: float
    margin: float
    risk_amount: float
    risk_pct: float
    leverage: int

class MarketContext(BaseModel):
    regime: str              # TRENDING_UP, RANGING, etc.
    trend_1h: str
    trend_4h: str
    trend_1d: str
    volatility: str          # LOW, MEDIUM, HIGH
    volume_profile: str      # BELOW, AVERAGE, ABOVE
    fear_greed_index: int | None = None

class OrderIntent(BaseModel):
    signal_id: UUID
    symbol: str
    side: str                # "BUY" or "SELL"
    order_type: str          # "MARKET", "LIMIT"
    price: float | None      # For limit orders
    quantity: float
    stop_loss: float
    take_profits: list[TakeProfit]
    leverage: int
    is_paper: bool = False

class Position(BaseModel):
    id: UUID
    signal_id: UUID
    symbol: str
    direction: Direction
    entry_price: float
    current_price: float
    quantity: float
    remaining_qty: float
    leverage: int
    stop_loss: float
    take_profits: list[TakeProfit]
    unrealized_pnl: float
    realized_pnl: float
    total_fees: float
    status: str              # OPEN, CLOSED
    opened_at: datetime
    closed_at: datetime | None = None

class BacktestConfig(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    risk_per_trade: float = 0.02
    max_positions: int = 5
    slippage_bps: float = 5.0
    maker_fee: float = 0.0002
    taker_fee: float = 0.0004
    parameters: dict = {}

class BacktestResult(BaseModel):
    id: UUID
    config: BacktestConfig
    total_return: float
    annual_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_holding_period: str
    expectancy: float
    equity_curve: list[dict]
    trades: list[dict]
    monthly_returns: dict
```

### 5.2 Service Interfaces

```python
# Each service exposes a clean async interface

class IDataCollector(ABC):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def get_candles(self, symbol: str, tf: str, limit: int) -> list[Candle]: ...
    async def get_orderbook(self, symbol: str) -> OrderBook: ...

class IStrategyEngine(ABC):
    async def evaluate(self, market_data: MarketData) -> list[RawSignal]: ...
    def get_active_strategies(self) -> list[str]: ...
    def enable_strategy(self, name: str) -> None: ...
    def disable_strategy(self, name: str) -> None: ...

class ISignalAggregator(ABC):
    async def aggregate(self, signals: list[RawSignal]) -> CompositeSignal | None: ...

class IRiskManager(ABC):
    async def evaluate(self, signal: CompositeSignal) -> ApprovedSignal | None: ...
    def get_portfolio_state(self) -> PortfolioState: ...
    def check_circuit_breaker(self) -> bool: ...

class IExecutionEngine(ABC):
    async def execute(self, intent: OrderIntent) -> OrderResult: ...
    async def cancel_order(self, order_id: str) -> bool: ...
    async def close_position(self, position_id: UUID) -> OrderResult: ...

class IPositionTracker(ABC):
    async def get_positions(self) -> list[Position]: ...
    async def update_sl(self, position_id: UUID, new_sl: float) -> None: ...
    async def update_tp(self, position_id: UUID, tps: list[TakeProfit]) -> None: ...

class IBacktestEngine(ABC):
    async def run(self, config: BacktestConfig) -> BacktestResult: ...
    async def optimize(self, config: OptimizeConfig) -> list[BacktestResult]: ...
    async def walk_forward(self, config: WalkForwardConfig) -> WFResult: ...

class INotificationService(ABC):
    async def send_signal_alert(self, signal: CompositeSignal) -> None: ...
    async def send_position_update(self, position: Position) -> None: ...
    async def send_risk_alert(self, alert: RiskAlert) -> None: ...
```

---

## 6. Concurrency Model

### 6.1 Async Architecture (asyncio)

```
Main Event Loop (asyncio)
├── DataCollector tasks (long-running)
│   ├── Task: stream_ohlcv (per symbol × timeframe)
│   ├── Task: stream_trades (per symbol)
│   ├── Task: stream_orderbook (per symbol)
│   ├── Task: collect_funding (periodic, every 8h)
│   └── Task: collect_sentiment (periodic, every 5min)
│
├── StrategyEngine tasks (event-driven)
│   ├── Subscriber: listen to "market.candle.*" events
│   └── For each candle: evaluate all strategies → publish raw signals
│
├── SignalAggregator task (event-driven)
│   ├── Subscriber: listen to "signal.raw.*" events
│   └── Aggregate + grade → publish composite signal
│
├── RiskManager task (event-driven)
│   ├── Subscriber: listen to "signal.composite" events
│   └── Evaluate + size + SL/TP → publish approved signal
│
├── ExecutionEngine tasks (event-driven + long-running)
│   ├── Subscriber: listen to "signal.approved" events (Auto-Bot mode)
│   └── Task: position monitoring loop (per position)
│
├── FastAPI server (uvicorn, separate process or same)
│   ├── REST endpoint handlers
│   └── WebSocket connections (fan-out from Redis to clients)
│
└── Background tasks
    ├── ML model retraining (weekly cron)
    ├── Data gap detection (hourly)
    └── Health check (every 30s)
```

### 6.2 Thread Safety Rules

1. **No shared mutable state** between async tasks - use Redis for state
2. **Database access** via async connection pool (asyncpg) - thread-safe
3. **Redis operations** are atomic - safe for concurrent reads/writes
4. **Portfolio state** stored in Redis with atomic updates (MULTI/EXEC)
5. **ML inference** via ONNX Runtime (thread-safe, lock-free)
6. **Heavy computation** (backtest, ML training) offloaded to background workers

### 6.3 Rate Limiting

```python
class RateLimiter:
    """Token bucket rate limiter for exchange API calls."""

    async def acquire(self, exchange: str, endpoint: str):
        """Wait until a request token is available."""
        key = f"ratelimit:{exchange}:{endpoint}"
        # Use Redis INCR with TTL for sliding window
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 60)  # 1 minute window
        if count > self.limits[exchange][endpoint]:
            wait_time = await self.redis.ttl(key)
            await asyncio.sleep(wait_time)
```

---

## 7. Error Handling Matrix

### 7.1 Exchange API Errors

| Error | Code | Handling | Retry? | User Impact |
|-------|------|----------|--------|-------------|
| Rate limit | 429 | Exponential backoff | Yes (after wait) | Temporary delay |
| Invalid API key | 401 | Alert admin, stop trading | No | Critical - manual fix |
| Insufficient balance | 400 | Reject order, notify user | No | Order rejected |
| Invalid price | 400 | Reject order, log | No | Order rejected |
| Server error | 500/503 | Retry 3x with backoff | Yes | Temporary delay |
| Timeout | - | Retry once, then check status | Yes | Status uncertain |
| WebSocket disconnect | - | Auto-reconnect (exp backoff) | Yes | Data gap possible |

### 7.2 Database Errors

| Error | Handling | Recovery |
|-------|----------|----------|
| Connection lost | Retry 3x, fallback to Redis buffer | Auto-reconnect |
| Pool exhausted | Queue request, log warning | Increase pool |
| Query timeout (30s) | Cancel, log slow query | Optimize query |
| Constraint violation | Log, reject operation | Fix data |
| Deadlock | Retry transaction 3x | Automatic |

### 7.3 Strategy Errors

| Error | Handling | Recovery |
|-------|----------|----------|
| Division by zero | Catch, skip candle | Continue next candle |
| Missing indicator data | Extend warmup, skip | Wait for more data |
| Invalid signal value | Log, disable strategy | Manual fix |
| ML model error | Fallback to non-ML signals | Continue degraded |
| Strategy timeout (5s) | Kill task, restart | Auto-restart |
| 5+ consecutive errors | Auto-disable strategy, alert | Manual review |

### 7.4 Critical System Failures

| Failure | Detection | Immediate Action | Recovery |
|---------|-----------|------------------|----------|
| Redis down | Connection refused | Switch to memory buffer | Restart Redis, replay |
| TimescaleDB down | Connection timeout | Write to file buffer | Reconnect, batch insert |
| Multiple strategy failure | 3+ error simultaneously | Circuit breaker → OPEN | Manual investigation |
| Exchange API down | All requests fail 5min+ | Pause trading, alert | Wait for exchange |
| Deployment crash | Startup failure | Auto-rollback to previous | Fix code, redeploy |

### 7.5 Error Handling Pattern

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class BaseService:
    """Base class with standard error handling patterns."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _retry_operation(self, operation, *args, **kwargs):
        try:
            return await operation(*args, **kwargs)
        except RateLimitError:
            logger.warning("Rate limit hit, backing off...")
            raise  # tenacity will retry
        except AuthenticationError:
            logger.critical("Auth failed - stopping!")
            await self.emergency_shutdown()
            raise  # Don't retry auth errors
        except Exception as e:
            logger.error(f"Operation failed: {e}")
            raise
```

---

## 8. Implementation Phases Checklist

### Phase 1: Foundation (Weeks 1-2)

**Deliverables:**
```
backend/app/config/settings.py       # Pydantic Settings
backend/app/config/constants.py      # Enums
backend/app/core/models.py           # All Pydantic models
backend/app/core/exceptions.py       # Custom exceptions
backend/app/core/events.py           # Redis event bus
backend/app/db/database.py           # Async DB engine
backend/app/db/models.py             # SQLAlchemy models
backend/app/db/redis_client.py       # Redis wrapper
backend/app/utils/logger.py          # structlog config
docker-compose.yml                   # TimescaleDB + Redis
pyproject.toml                       # Dependencies
.env.example                         # Env template
```

**Tests:**
- [ ] Config loads from .env correctly
- [ ] All Pydantic models validate/serialize
- [ ] TimescaleDB connection + insert + query
- [ ] Redis pub/sub message delivery
- [ ] Logger outputs structured JSON

---

### Phase 2: Data Collection (Weeks 3-4)

**Deliverables:**
```
backend/app/data/collector.py
backend/app/data/providers/binance.py
backend/app/data/feed/websocket_manager.py
backend/app/data/feed/rest_client.py
backend/app/data/feed/historical_loader.py
backend/app/data/normalization/normalizer.py
```

**Tests:**
- [ ] WebSocket connects to Binance, receives BTC/USDT trades
- [ ] OHLCV candles stream for multiple timeframes
- [ ] Historical data loads from data.binance.vision
- [ ] Data normalizes correctly (timestamps UTC, decimal precision)
- [ ] Candles stored in TimescaleDB
- [ ] Redis receives market.candle events
- [ ] Auto-reconnect works after simulated disconnect

---

### Phase 3: Indicators & Strategies (Weeks 5-7)

**Deliverables:**
```
backend/app/indicators/trend.py          # EMA, MACD, ADX
backend/app/indicators/momentum.py       # RSI, Stochastic
backend/app/indicators/volatility.py     # ATR, Bollinger
backend/app/indicators/volume.py         # VWAP, OBV, CVD
backend/app/strategies/technical/momentum_rsi_ema.py
backend/app/strategies/technical/mean_reversion_bb.py
backend/app/strategies/smart_money/market_structure.py
backend/app/strategies/smart_money/order_blocks.py
backend/app/strategies/smart_money/fair_value_gaps.py
backend/app/strategies/composite/signal_aggregator.py
backend/app/strategies/composite/regime_detector.py
```

**Tests:**
- [ ] RSI(14) matches pandas-ta output exactly
- [ ] EMA(20) matches pandas-ta output exactly
- [ ] Momentum strategy generates signals on historical data
- [ ] SMC detects BOS/CHoCH on known chart patterns
- [ ] Signal aggregator combines and grades correctly
- [ ] Market regime detection classifies known periods

---

### Phase 4: Risk Management (Weeks 8-9)

**Deliverables:**
```
backend/app/risk/position_sizer.py
backend/app/risk/stop_loss.py
backend/app/risk/take_profit.py
backend/app/risk/rr_optimizer.py
backend/app/risk/portfolio_risk.py
backend/app/risk/circuit_breaker.py
backend/app/risk/exposure_manager.py
```

**Tests:**
- [ ] Position size = $200 risk for 2% on $10K account
- [ ] ATR-based SL calculates correctly for trending/ranging
- [ ] Multi-level TP achieves target RR ratios
- [ ] Portfolio heat rejects signal when at 6%
- [ ] Circuit breaker trips after 5 consecutive losses
- [ ] Exposure manager tracks correlated positions

---

### Phase 5: Execution Engine (Week 10)

**Deliverables:**
```
backend/app/execution/executor.py
backend/app/execution/order_manager.py
backend/app/execution/position_tracker.py
backend/app/execution/paper_trader.py
```

**Tests:**
- [ ] Paper trade: market order fills at current price + slippage
- [ ] Paper trade: SL triggers correctly
- [ ] Paper trade: TP partial closes work
- [ ] Binance testnet: limit order placed and filled
- [ ] Position state updates in real-time
- [ ] Trailing stop moves correctly

---

### Phase 6: Backtesting (Weeks 11-12)

**Deliverables:**
```
backend/app/backtesting/engine.py
backend/app/backtesting/simulator.py
backend/app/backtesting/metrics.py
backend/app/backtesting/walk_forward.py
backend/app/backtesting/monte_carlo.py
backend/app/backtesting/optimizer.py
backend/app/backtesting/report.py
```

**Tests:**
- [ ] Backtest runs without errors on 6 months BTC data
- [ ] Metrics match manual calculations
- [ ] Walk-forward produces consistent OOS results
- [ ] Monte Carlo generates distribution at 95% CI
- [ ] Optimizer finds better params than defaults

---

### Phase 7: API + Frontend (Weeks 13-16)

**Deliverables:**
```
backend/app/api/ (all routes)
frontend/app/ (all pages)
frontend/components/ (all components)
```

**Tests:**
- [ ] All REST endpoints return correct data
- [ ] WebSocket delivers real-time updates
- [ ] Signal Terminal displays signals with chart
- [ ] Execute modal places order (paper mode)
- [ ] Auto-Bot controls work (start/pause/stop)
- [ ] Backtest Lab runs and displays results
- [ ] Settings page saves exchange keys (encrypted)

---

### Phase 8: ML/AI (Weeks 17-18)

**Deliverables:**
```
backend/app/ml/features/engineering.py
backend/app/ml/models/signal_classifier.py
backend/app/ml/models/direction_predictor.py
backend/app/ml/training/trainer.py
backend/app/ml/serving/predictor.py
```

**Tests:**
- [ ] Feature engineering produces 50+ features
- [ ] XGBoost classifier trained and exported to ONNX
- [ ] GRU model trained on 6-month window
- [ ] ONNX inference < 10ms per prediction
- [ ] ML-enhanced signals show improvement in backtest

---

### Phase 9: Notifications (Week 19)

**Deliverables:**
```
backend/app/notifications/telegram.py
backend/app/notifications/discord.py
```

**Tests:**
- [ ] Telegram bot sends formatted signal alert
- [ ] Discord webhook sends embed
- [ ] Alert on position SL/TP hit
- [ ] Alert on circuit breaker trigger

---

### Phase 10: Deploy (Weeks 20-22)

**Tasks:**
- [ ] Docker images built for ARM (Oracle Cloud)
- [ ] docker-compose.yml production config
- [ ] SSL/HTTPS via Let's Encrypt
- [ ] Grafana Cloud monitoring setup
- [ ] 2-week paper trading validation
- [ ] Go live with minimum capital

---

*Component Blueprint v1.0 - Created 2025-02-10*
*Ready for Phase 1 implementation*
