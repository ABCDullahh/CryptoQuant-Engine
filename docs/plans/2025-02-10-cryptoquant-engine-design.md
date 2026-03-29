# CryptoQuant Engine - Comprehensive Architecture Design

**Date:** 2025-02-10
**Status:** Final Design - Ready for Implementation
**Platform:** Single Web Application (Next.js 16 + FastAPI)

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Data Layer Design](#2-data-layer-design)
3. [Strategy Engine](#3-strategy-engine)
4. [Risk Management Engine](#4-risk-management-engine)
5. [ML/AI Enhancement Layer](#5-mlai-enhancement-layer)
6. [Execution Engine](#6-execution-engine)
7. [Backtesting Engine](#7-backtesting-engine)
8. [Frontend Architecture - 3 Sections](#8-frontend-architecture)
9. [Backend API Design](#9-backend-api-design)
10. [Notification System](#10-notification-system)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Implementation Phases](#12-implementation-phases)
13. [Complete File Structure](#13-complete-file-structure)
14. [Configuration Reference](#14-configuration-reference)

---

## 1. System Architecture Overview

### 1.1 Architecture Pattern: Modular Monolith, Event-Driven

```
┌─────────────────────────────────────────────────────────────────┐
│                    CryptoQuant Engine                            │
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐ │
│  │ Frontend  │◄──►│  FastAPI      │◄──►│  Trading Engine       │ │
│  │ Next.js16 │    │  Backend      │    │  (Python async)       │ │
│  │           │    │              │    │                        │ │
│  │ 3 Sections│    │ REST + WS    │    │ ┌──────────────────┐ │ │
│  │ -Signal   │    │ endpoints    │    │ │ Data Collector    │ │ │
│  │ -AutoBot  │    │              │    │ │ Strategy Engine   │ │ │
│  │ -Backtest │    │              │    │ │ Risk Manager      │ │ │
│  └──────────┘    └──────┬───────┘    │ │ ML Engine         │ │ │
│                         │            │ │ Execution Engine  │ │ │
│                         │            │ │ Backtest Engine   │ │ │
│                         │            │ └──────────────────┘ │ │
│                         │            └───────────┬───────────┘ │
│                         │                        │              │
│              ┌──────────▼────────────────────────▼──────────┐  │
│              │              Redis Event Bus                   │  │
│              │  Pub/Sub channels: market.*, signal.*,         │  │
│              │  order.*, position.*, risk.*, system.*         │  │
│              └──────────┬────────────────────────┬───────────┘  │
│                         │                        │              │
│              ┌──────────▼──────┐  ┌──────────────▼───────────┐ │
│              │  TimescaleDB    │  │     Redis Cache           │ │
│              │  (persistent)   │  │  (real-time state)        │ │
│              └─────────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
      ┌──────────┐ ┌──────────┐ ┌──────────┐
      │ Binance  │ │ Telegram │ │ Discord  │
      │ Exchange │ │ Bot API  │ │ Webhook  │
      └──────────┘ └──────────┘ └──────────┘
```

### 1.2 Technology Stack (Latest Versions via Context7)

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Frontend | Next.js | 16.x | App Router, Server Components, Middleware auth |
| Charts | TradingView Lightweight Charts | 5.x | Candlestick, real-time updates, indicators |
| Backend API | FastAPI | 0.128+ | REST + WebSocket, dependency injection, BackgroundTasks |
| Exchange | CCXT | 4.x | Async Binance USDM, watchOHLCV, WebSocket |
| Database | TimescaleDB | PostgreSQL 16 | Hypertables for OHLCV, continuous aggregates |
| Cache/Events | Redis/Valkey | 7.x | Pub/Sub event bus, real-time cache |
| ML Primary | XGBoost/LightGBM | latest | Signal classification, feature importance |
| ML Deep | PyTorch | 2.x | GRU/LSTM for sequence prediction |
| ML Tuning | Optuna | latest | Bayesian hyperparameter optimization |
| ML Inference | ONNX Runtime | latest | Fast production inference |
| Indicators | pandas-ta | latest | 150+ indicators, pure Python |
| Container | Docker Compose | latest | Multi-service orchestration |
| Deploy | Oracle Cloud | Always Free | 4 ARM cores, 24GB RAM |

### 1.3 Event Bus Architecture (Redis Pub/Sub)

All internal communication flows through Redis Pub/Sub channels:

```
Channel Pattern          │ Publisher              │ Subscribers
─────────────────────────┼────────────────────────┼──────────────────────
market.candle.{tf}       │ DataCollector          │ StrategyEngine, Indicators
market.trade             │ DataCollector          │ VolumeAnalysis, OrderFlow
market.orderbook         │ DataCollector          │ ExecutionEngine
market.funding           │ DataCollector          │ FundingArbStrategy
signal.raw.{strategy}    │ Individual Strategies  │ SignalAggregator
signal.composite         │ SignalAggregator       │ RiskManager, Dashboard
signal.approved          │ RiskManager            │ ExecutionEngine, Dashboard
order.placed             │ ExecutionEngine        │ PositionTracker, Dashboard
order.filled             │ ExecutionEngine        │ PositionTracker, RiskManager
position.update          │ PositionTracker        │ Dashboard, RiskManager
position.closed          │ PositionTracker        │ Analytics, Dashboard
risk.alert               │ RiskManager            │ Dashboard, Notifications
risk.circuit_breaker     │ CircuitBreaker         │ All engines (halt)
system.health            │ HealthMonitor          │ Dashboard, Notifications
bot.status               │ AutoBotManager         │ Dashboard
```

### 1.4 User Flow: Three Sections

```
┌─────────────────────────────────────────────────────────────────────┐
│                        WEB APPLICATION                               │
│                                                                      │
│  ┌─────────────────┐ ┌──────────────────┐ ┌─────────────────────┐  │
│  │ SIGNAL TERMINAL  │ │ AUTO-BOT MANAGER │ │  BACKTEST LAB       │  │
│  │                  │ │                  │ │                      │  │
│  │ Live chart with  │ │ Start/Pause/Stop │ │ Select strategy     │  │
│  │ TradingView      │ │ autonomous bot   │ │ Select date range   │  │
│  │                  │ │                  │ │ Run backtest         │  │
│  │ Signal cards     │ │ Paper trading    │ │                      │  │
│  │ with grade A/B/C │ │ toggle           │ │ Equity curve        │  │
│  │                  │ │                  │ │ Drawdown chart       │  │
│  │ One-click execute│ │ Strategy enable/ │ │ Trade list           │  │
│  │ (sends to        │ │ disable toggles  │ │ Performance metrics │  │
│  │  Binance)        │ │                  │ │                      │  │
│  │                  │ │ Live P&L tracker │ │ Walk-forward results │  │
│  │ Advanced execute │ │ Position monitor │ │ Monte Carlo sim      │  │
│  │ (customize entry,│ │ Trade history    │ │ Parameter optimizer  │  │
│  │  TP, SL, size,   │ │ Daily/weekly     │ │                      │  │
│  │  leverage)       │ │ performance      │ │ Compare strategies   │  │
│  └─────────────────┘ └──────────────────┘ └─────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ SETTINGS: Exchange API keys | Risk params | Notifications      │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Layer Design

### 2.1 Data Collection Architecture

```python
# WebSocket Manager with CCXT 4.x async
class DataCollector:
    """
    Manages all data streams from Binance using CCXT 4.x async.
    Publishes normalized data to Redis event bus.
    """

    async def start(self):
        # Parallel streams
        await asyncio.gather(
            self._stream_ohlcv(),      # Multi-timeframe candles
            self._stream_trades(),      # Real-time trades
            self._stream_orderbook(),   # L2 order book
            self._stream_funding(),     # Funding rates (every 8h)
            self._stream_liquidations(),# Liquidation events
            self._collect_sentiment(),  # Periodic sentiment fetch
        )

    async def _stream_ohlcv(self):
        """CCXT 4.x watchOHLCV for multi-timeframe streaming"""
        exchange = ccxt.pro.binanceusdm()
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        symbols = await self._get_monitored_symbols()

        for symbol in symbols:
            for tf in timeframes:
                asyncio.create_task(
                    self._watch_ohlcv(exchange, symbol, tf)
                )

    async def _watch_ohlcv(self, exchange, symbol, timeframe):
        while True:
            try:
                ohlcv = await exchange.watchOHLCV(symbol, timeframe)
                candle = self._normalize_candle(ohlcv[-1], symbol, timeframe)
                await self.redis.publish(
                    f"market.candle.{timeframe}",
                    candle.model_dump_json()
                )
                await self.db.insert_candle(candle)
            except Exception as e:
                logger.error(f"OHLCV stream error {symbol}/{timeframe}: {e}")
                await asyncio.sleep(5)
```

### 2.2 Data Sources (All Free, $0/month)

| Data Type | Source | Method | Rate Limit |
|-----------|--------|--------|------------|
| Real-time OHLCV | Binance WebSocket via CCXT | watchOHLCV | Unlimited (WS) |
| Historical OHLCV | data.binance.vision | Bulk CSV download | No limit |
| Order Book | Binance WebSocket | watchOrderBook | Unlimited (WS) |
| Funding Rates | Binance Futures REST | GET /fapi/v1/fundingRate | 500 req/min |
| Open Interest | Binance Futures REST | GET /fapi/v1/openInterest | 500 req/min |
| Liquidations | Binance WebSocket | forceOrder stream | Unlimited (WS) |
| Sentiment | Alternative.me Fear & Greed | REST | 1 req/day |
| News | CryptoPanic API + RSS feeds | REST + feedparser | 30 req/min |
| On-chain (DeFi) | DeFiLlama API | REST | 300 req/5min |
| Options Data | Deribit API | REST/WS | Free tier |
| Social Sentiment | Reddit via PRAW | REST | 60 req/min |
| Market Overview | CoinGecko Demo API | REST | 30 req/min |

### 2.3 Database Schema (TimescaleDB)

```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- OHLCV Candles (hypertable)
CREATE TABLE candles (
    time        TIMESTAMPTZ NOT NULL,
    exchange    TEXT NOT NULL DEFAULT 'binance',
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    open        NUMERIC(20,8) NOT NULL,
    high        NUMERIC(20,8) NOT NULL,
    low         NUMERIC(20,8) NOT NULL,
    close       NUMERIC(20,8) NOT NULL,
    volume      NUMERIC(20,8) NOT NULL,
    quote_volume NUMERIC(20,8),
    trades_count INTEGER,
    PRIMARY KEY (time, symbol, timeframe)
);
SELECT create_hypertable('candles', 'time');
CREATE INDEX idx_candles_symbol_tf ON candles (symbol, timeframe, time DESC);

-- Trading Signals
CREATE TABLE signals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    signal_grade    TEXT NOT NULL CHECK (signal_grade IN ('A', 'B', 'C', 'D')),
    signal_strength NUMERIC(5,4) NOT NULL,
    entry_price     NUMERIC(20,8) NOT NULL,
    entry_zone_low  NUMERIC(20,8),
    entry_zone_high NUMERIC(20,8),
    stop_loss       NUMERIC(20,8) NOT NULL,
    sl_type         TEXT NOT NULL,
    tp1_price       NUMERIC(20,8) NOT NULL,
    tp1_pct         INTEGER DEFAULT 50,
    tp2_price       NUMERIC(20,8),
    tp2_pct         INTEGER DEFAULT 30,
    tp3_price       NUMERIC(20,8),
    tp3_pct         INTEGER DEFAULT 20,
    rr_tp1          NUMERIC(5,2),
    rr_tp2          NUMERIC(5,2),
    rr_tp3          NUMERIC(5,2),
    weighted_rr     NUMERIC(5,2),
    position_size   NUMERIC(20,8),
    leverage        INTEGER DEFAULT 1,
    risk_amount     NUMERIC(20,8),
    strategy_scores JSONB NOT NULL,
    market_context  JSONB,
    ml_confidence   NUMERIC(5,4),
    status          TEXT DEFAULT 'ACTIVE',
    outcome         TEXT,
    actual_pnl      NUMERIC(20,8)
);
SELECT create_hypertable('signals', 'created_at');

-- Executed Orders
CREATE TABLE orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id       UUID REFERENCES signals(id),
    exchange_order_id TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,
    order_type      TEXT NOT NULL,
    price           NUMERIC(20,8),
    quantity        NUMERIC(20,8) NOT NULL,
    filled_qty      NUMERIC(20,8) DEFAULT 0,
    avg_fill_price  NUMERIC(20,8),
    status          TEXT NOT NULL DEFAULT 'PENDING',
    fees            NUMERIC(20,8) DEFAULT 0,
    metadata        JSONB
);

-- Active Positions
CREATE TABLE positions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id       UUID REFERENCES signals(id),
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,
    entry_price     NUMERIC(20,8) NOT NULL,
    current_price   NUMERIC(20,8),
    quantity        NUMERIC(20,8) NOT NULL,
    remaining_qty   NUMERIC(20,8) NOT NULL,
    leverage        INTEGER DEFAULT 1,
    stop_loss       NUMERIC(20,8) NOT NULL,
    tp1_price       NUMERIC(20,8),
    tp2_price       NUMERIC(20,8),
    tp3_price       NUMERIC(20,8),
    unrealized_pnl  NUMERIC(20,8) DEFAULT 0,
    realized_pnl    NUMERIC(20,8) DEFAULT 0,
    total_fees      NUMERIC(20,8) DEFAULT 0,
    status          TEXT DEFAULT 'OPEN',
    close_reason    TEXT,
    metadata        JSONB
);

-- Backtest Results
CREATE TABLE backtest_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    strategy_name   TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    start_date      TIMESTAMPTZ NOT NULL,
    end_date        TIMESTAMPTZ NOT NULL,
    initial_capital NUMERIC(20,8) NOT NULL,
    final_capital   NUMERIC(20,8),
    total_return    NUMERIC(10,4),
    sharpe_ratio    NUMERIC(8,4),
    sortino_ratio   NUMERIC(8,4),
    max_drawdown    NUMERIC(8,4),
    win_rate        NUMERIC(5,4),
    profit_factor   NUMERIC(8,4),
    total_trades    INTEGER,
    parameters      JSONB,
    equity_curve    JSONB,
    trades          JSONB
);

-- User Settings (encrypted exchange keys)
CREATE TABLE user_settings (
    id              SERIAL PRIMARY KEY,
    exchange_keys   BYTEA,  -- AES-256 encrypted
    risk_params     JSONB NOT NULL DEFAULT '{}',
    strategy_config JSONB NOT NULL DEFAULT '{}',
    notification_config JSONB NOT NULL DEFAULT '{}',
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Bot State
CREATE TABLE bot_state (
    id              SERIAL PRIMARY KEY,
    is_running      BOOLEAN DEFAULT FALSE,
    is_paper_mode   BOOLEAN DEFAULT TRUE,
    active_strategies JSONB DEFAULT '[]',
    started_at      TIMESTAMPTZ,
    stopped_at      TIMESTAMPTZ,
    total_pnl       NUMERIC(20,8) DEFAULT 0,
    metadata        JSONB DEFAULT '{}'
);
```

### 2.4 Redis Cache Structure

```
# Real-time price cache
price:{symbol}               → {"bid": 97250, "ask": 97251, "last": 97250.5, "ts": 1707...}

# Latest candle per timeframe
candle:{symbol}:{tf}         → Candle JSON

# Order book snapshot (top 20 levels)
orderbook:{symbol}           → {"bids": [...], "asks": [...], "ts": ...}

# Active signals
signal:active:{id}           → Signal JSON

# Active positions
position:active:{id}         → Position JSON

# Portfolio state
portfolio:state              → {"balance": 10000, "equity": 10250, "heat": 0.04, ...}

# Bot state
bot:state                    → {"running": true, "paper": false, "strategies": [...]}

# Rate limiting
ratelimit:{exchange}:{endpoint} → Counter with TTL

# Indicator cache
indicator:{symbol}:{tf}:{name} → Indicator values JSON
```

---

## 3. Strategy Engine

### 3.1 Strategy Base Class

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from enum import Enum

class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"

class RawSignal(BaseModel):
    strategy_name: str
    symbol: str
    direction: SignalDirection
    strength: float  # [-1.0, +1.0]
    entry_price: float
    timeframe: str
    conditions: list[str]
    metadata: dict = {}

class BaseStrategy(ABC):
    """All strategies implement this interface."""

    @abstractmethod
    async def calculate(self, market_data: MarketData) -> RawSignal | None:
        """Calculate signal from market data. Return None if no signal."""
        pass

    @abstractmethod
    def required_indicators(self) -> list[str]:
        """List of indicator names this strategy needs."""
        pass

    @abstractmethod
    def required_timeframes(self) -> list[str]:
        """Timeframes this strategy operates on."""
        pass

    @abstractmethod
    def warmup_periods(self) -> int:
        """Number of candles needed before strategy can generate signals."""
        pass
```

### 3.2 Implemented Strategies

| Strategy | Type | Primary TF | Weight | Key Indicators |
|----------|------|-----------|--------|----------------|
| Momentum RSI/EMA | Technical | 1H/4H | 0.15 | RSI(14), EMA(8/21/55/200), MACD |
| Mean Reversion BB | Technical | 15m/1H | 0.10 | Bollinger(20,2), RSI, Z-Score |
| Smart Money (SMC) | Structure | 1H/4H | 0.25 | BOS/CHoCH, Order Blocks, FVG |
| Volume Analysis | Technical | 15m/1H | 0.15 | VWAP, OBV, CVD, Volume Profile |
| Funding Arb | Quantitative | 8H | 0.05 | Funding rates, OI delta |
| ML Enhancement | AI | 1H | 0.20 | XGBoost signal classifier output |
| Sentiment | Alternative | 1D | 0.10 | Fear & Greed, Social sentiment |

### 3.3 Signal Aggregation

```python
class SignalAggregator:
    """Combines raw signals from all strategies into composite signal."""

    GRADE_THRESHOLDS = {
        'A': 0.80,  # Strong signal
        'B': 0.60,  # Good signal
        'C': 0.40,  # Weak signal
        'D': 0.0,   # No trade
    }

    MIN_STRATEGY_AGREEMENT = 3  # At least 3/7 must agree on direction
    MIN_VOLUME_RATIO = 1.0      # Volume must be >= 20-period avg

    async def aggregate(self, raw_signals: list[RawSignal]) -> CompositeSignal | None:
        # 1. Filter valid signals (same direction)
        # 2. Calculate weighted composite score
        # 3. Check minimum agreement threshold
        # 4. Check volume confirmation
        # 5. Check higher timeframe alignment
        # 6. Grade the signal (A/B/C/D)
        # 7. If grade >= C, publish to signal.composite channel
        pass
```

### 3.4 Market Regime Detection

```
Regime          │ ADX   │ BB Width │ ATR %ile │ Strategy Adjustment
────────────────┼───────┼──────────┼──────────┼────────────────────────
TRENDING_UP     │ > 25  │ Normal   │ > 50th   │ Momentum +weight, wider TP
TRENDING_DOWN   │ > 25  │ Normal   │ > 50th   │ Short bias, wider TP
RANGING         │ < 20  │ Normal   │ < 50th   │ Mean reversion +weight
HIGH_VOLATILITY │ Any   │ Wide     │ > 80th   │ Reduce size 50%, wider SL
LOW_VOLATILITY  │ < 15  │ Squeeze  │ < 20th   │ Breakout strategies, tight SL
CHOPPY          │ 20-25 │ Variable │ Variable │ Reduce trading frequency
```

---

## 4. Risk Management Engine

### 4.1 Position Sizing

```python
class PositionSizer:
    """Calculates position size based on risk parameters."""

    def fixed_fractional(
        self,
        balance: float,
        risk_pct: float,        # Default: 0.02 (2%)
        entry_price: float,
        stop_loss: float,
        leverage: int = 1,
    ) -> PositionSize:
        risk_amount = balance * risk_pct
        sl_distance = abs(entry_price - stop_loss)
        sl_pct = sl_distance / entry_price

        position_size = risk_amount / sl_distance
        notional_value = position_size * entry_price
        margin_required = notional_value / leverage

        return PositionSize(
            quantity=position_size,
            notional=notional_value,
            margin=margin_required,
            risk_amount=risk_amount,
            leverage=leverage,
        )
```

### 4.2 Dynamic SL/TP Calculation

```
Stop Loss Methods:
─────────────────
1. ATR-Based (Primary):     SL = entry ∓ ATR(14) × multiplier
   - Trending: mult = 2.0   - Ranging: mult = 1.0   - Volatile: mult = 2.5

2. Structure-Based (SMC):   SL = below swing low / above swing high + buffer

3. Combined:                SL = max_protective(ATR_SL, Structure_SL)

Take Profit (Multi-Level):
──────────────────────────
TP1 = entry + SL_distance × 1.5  → Close 50% position → Move SL to breakeven
TP2 = entry + SL_distance × 3.0  → Close 30% position → Activate trailing stop
TP3 = entry + SL_distance × 5.0  → Close 20% position (or trail)
```

### 4.3 Portfolio Risk Rules

| Rule | Threshold | Action |
|------|-----------|--------|
| Max open positions | 5 | Reject new signals |
| Max portfolio heat | 6% total at risk | Reject new signals |
| Max single trade risk | 2% | Reduce position size |
| Max daily loss | 5% | Stop trading 24h |
| Max weekly loss | 10% | Stop trading 7 days |
| Max drawdown | 15% | Full stop, manual review |
| 3 consecutive losses | - | Reduce size 50% |
| 5 consecutive losses | - | Stop trading 4h |
| Max leverage | 10x (hard cap) | Reject/reduce |
| Default leverage | 1x-3x | Configurable |

### 4.4 Circuit Breaker

```python
class CircuitBreaker:
    """Emergency stop mechanisms."""

    triggers = [
        ("consecutive_losses", 5, "PAUSE_4H"),
        ("daily_loss_pct", 0.03, "REDUCE_50"),
        ("daily_loss_pct", 0.05, "STOP_24H"),
        ("max_drawdown_pct", 0.15, "FULL_STOP"),
        ("exchange_error_count", 10, "CANCEL_ALL"),
        ("abnormal_spread", 2.0, "PAUSE_NEW_ENTRIES"),
    ]

    async def check(self, state: PortfolioState) -> list[CircuitAction]:
        """Check all triggers and return actions if any are tripped."""
        pass
```

---

## 5. ML/AI Enhancement Layer

### 5.1 Feature Engineering (50+ features)

```
Category              │ Features                                    │ Count
──────────────────────┼─────────────────────────────────────────────┼──────
Price                 │ Returns (1m-1d), log returns, realized vol  │ 8
Technical Indicators  │ RSI, MACD hist, BB %B, ATR, ADX, Stoch    │ 10
Volume                │ Vol ratio, buy/sell ratio, OBV slope, VWAP │ 6
Order Book            │ Spread, imbalance, depth levels             │ 5
Cross-Asset           │ BTC dom, correlation, funding rate          │ 5
On-Chain              │ Exchange flow, active addr, whale txns      │ 5
Sentiment             │ Fear/Greed, social score, news score        │ 4
Temporal              │ Hour (sin/cos), day (sin/cos), session      │ 5
Microstructure        │ Trade arrival rate, Kyle's lambda           │ 3
```

### 5.2 ML Model Stack

```
Model 1: XGBoost Signal Classifier (Primary)
  Task:     Classify signal quality (good/bad entry)
  Input:    50+ features + current strategy signal scores
  Output:   Probability of profitable trade [0, 1]
  Retrain:  Weekly, walk-forward with purged k-fold

Model 2: GRU Sequence Model (Direction Prediction)
  Task:     Predict price direction next 1H
  Input:    Sequence of last 100 candles × features
  Output:   Up/Down probability + expected magnitude
  Retrain:  Bi-weekly, 6-month rolling windows

Model 3: Market Regime Classifier
  Task:     Classify current regime
  Input:    Volatility, trend, volume features
  Output:   Regime label (trending/ranging/volatile/choppy)
  Use:      Adjust strategy weights dynamically

Model 4: Anomaly Detector (Isolation Forest)
  Task:     Detect unusual market conditions
  Input:    Multi-dimensional market features
  Output:   Anomaly score [0, 1]
  Use:      Trigger caution mode when score > 0.8
```

### 5.3 ML Training Pipeline

```
1. Data Prep → 2. Walk-Forward Split → 3. Feature Selection (SHAP top 30-50)
→ 4. Hyperopt (Optuna, maximize Sharpe) → 5. Evaluate (OOS performance)
→ 6. Export ONNX → 7. Deploy to model registry → 8. Monitor for drift
```

---

## 6. Execution Engine

### 6.1 Order Flow

```
Signal Approved (from RiskManager)
    │
    ▼
┌──────────────────────────────────────┐
│ Pre-Execution Checks                  │
│ - Balance sufficient?                 │
│ - Position limit OK?                  │
│ - Portfolio heat OK?                  │
│ - Spread < threshold?                │
│ - Circuit breaker clear?             │
└──────────────┬───────────────────────┘
               │ PASS
               ▼
┌──────────────────────────────────────┐
│ Order Placement (via CCXT 4.x)       │
│                                       │
│ Signal Terminal (manual):             │
│   One-Click → Market order            │
│   Advanced → Limit order + custom     │
│                                       │
│ Auto-Bot:                             │
│   Grade A → Market order              │
│   Grade B/C → Limit order             │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Post-Fill: Place SL + TP orders       │
│ - SL: Stop-limit order               │
│ - TP1/TP2/TP3: Limit sell orders     │
│ - Start position monitoring          │
└──────────────────────────────────────┘
```

### 6.2 Position Tracking

```python
class PositionTracker:
    """Monitors active positions for SL/TP hits."""

    async def monitor(self, position: Position):
        while position.status == "OPEN":
            price = await self.get_current_price(position.symbol)

            # Check stale data
            if price.age_seconds > 10:
                await self.alert_stale_data(position)

            # Update unrealized P&L
            position.unrealized_pnl = self._calc_pnl(position, price)

            # Check SL hit
            if self._is_sl_hit(position, price):
                await self.close_position(position, reason="SL_HIT")

            # Check TP levels
            for tp in position.take_profits:
                if not tp.filled and self._is_tp_hit(tp, price):
                    await self.partial_close(position, tp)
                    if tp.level == "TP1":
                        position.stop_loss = position.entry_price  # Move to BE

            # Check liquidation risk (futures)
            if position.leverage > 1:
                liq_distance = self._liquidation_distance(position, price)
                if liq_distance < 0.05:
                    await self.alert_liquidation_risk(position)

            # Re-sync with exchange every 5 min
            if self._should_resync(position):
                await self.resync_with_exchange(position)

            await asyncio.sleep(1)
```

---

## 7. Backtesting Engine

### 7.1 Engine Design

```python
class BacktestEngine:
    """Event-driven backtesting engine with realistic simulation."""

    async def run(self, config: BacktestConfig) -> BacktestResult:
        # 1. Load historical data from TimescaleDB
        data = await self.load_data(config.symbol, config.timeframe,
                                     config.start_date, config.end_date)

        # 2. Calculate indicators
        indicators = self.calculate_indicators(data, config.strategy)

        # 3. Simulate candle-by-candle
        for candle in data.itertuples():
            # Generate signal
            signal = await config.strategy.calculate(candle, indicators)

            if signal:
                # Apply risk management
                approved = self.risk_manager.check(signal, self.portfolio)
                if approved:
                    # Simulate execution (with slippage + fees)
                    trade = self.simulate_fill(signal, candle,
                                               slippage_model=config.slippage)
                    self.portfolio.open_position(trade)

            # Update positions (check SL/TP)
            self.portfolio.update_positions(candle)

            # Record equity
            self.equity_curve.append(self.portfolio.equity)

        # 4. Calculate metrics
        return self.calculate_metrics()
```

### 7.2 Performance Metrics

| Metric | Target | Formula |
|--------|--------|---------|
| Sharpe Ratio | > 1.5 | (mean_return - rf) / std_return |
| Sortino Ratio | > 2.0 | (mean_return - rf) / downside_dev |
| Max Drawdown | < 15% | (peak - trough) / peak |
| Win Rate | > 45% | wins / total_trades |
| Profit Factor | > 1.5 | gross_profit / gross_loss |
| Calmar Ratio | > 1.0 | annual_return / max_drawdown |
| Expectancy | > 0 | (WR × avg_win) - (LR × avg_loss) |
| Recovery Factor | > 3.0 | total_return / max_drawdown |

### 7.3 Walk-Forward Analysis

```
Training Window: 6 months (in-sample)
Testing Window:  2 months (out-of-sample)
Step Size:       2 months (roll forward)

│← Train (6mo) →│← Test (2mo) →│
                 │← Train (6mo) →│← Test (2mo) →│
                                  │← Train (6mo) →│← Test (2mo) →│

Validation: OOS performance must be within 70% of IS performance.
Monte Carlo: 1000 randomized trade sequences → 95% confidence drawdown estimate.
```

---

## 8. Frontend Architecture

### 8.1 Next.js 16 App Router Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout with sidebar navigation
│   ├── page.tsx                # Redirect to /signals
│   ├── signals/
│   │   └── page.tsx            # Signal Terminal (Section 1)
│   ├── autobot/
│   │   └── page.tsx            # Auto-Bot Manager (Section 2)
│   ├── backtest/
│   │   └── page.tsx            # Backtest Lab (Section 3)
│   ├── settings/
│   │   └── page.tsx            # Settings & Exchange Keys
│   └── api/                    # Next.js API routes (proxy to FastAPI)
├── components/
│   ├── charts/
│   │   ├── TradingChart.tsx    # TradingView Lightweight Charts 5.x wrapper
│   │   ├── EquityCurve.tsx     # Backtest equity curve
│   │   └── DrawdownChart.tsx   # Drawdown visualization
│   ├── signals/
│   │   ├── SignalCard.tsx      # Signal card with grade badge
│   │   ├── SignalList.tsx      # Scrollable signal list
│   │   ├── ExecuteModal.tsx    # One-click + Advanced execute modal
│   │   └── SignalFilters.tsx   # Filter by pair/grade/strategy
│   ├── positions/
│   │   ├── PositionTable.tsx   # Active positions with live P&L
│   │   ├── PositionCard.tsx    # Individual position detail
│   │   └── PortfolioSummary.tsx
│   ├── autobot/
│   │   ├── BotControls.tsx     # Start/Pause/Stop + Paper toggle
│   │   ├── StrategyToggles.tsx # Enable/disable strategies
│   │   ├── BotPerformance.tsx  # Live P&L chart
│   │   └── TradeHistory.tsx    # Bot trade log
│   ├── backtest/
│   │   ├── BacktestForm.tsx    # Strategy, dates, params
│   │   ├── BacktestResults.tsx # Metrics dashboard
│   │   ├── TradeList.tsx       # Individual trades table
│   │   └── ParameterOptimizer.tsx # Optimization UI
│   ├── layout/
│   │   ├── Sidebar.tsx         # Navigation sidebar
│   │   ├── Header.tsx          # Top bar with portfolio summary
│   │   └── NotificationBell.tsx
│   └── shared/
│       ├── LoadingSpinner.tsx
│       ├── ErrorBoundary.tsx
│       └── WebSocketProvider.tsx # Real-time data context
├── hooks/
│   ├── useWebSocket.ts         # WebSocket connection hook
│   ├── useSignals.ts           # Signal data + SSE
│   ├── usePositions.ts         # Position data + real-time
│   ├── useBotStatus.ts         # Auto-bot state
│   └── useBacktest.ts          # Backtest operations
├── lib/
│   ├── api.ts                  # API client (fetch wrapper)
│   ├── ws.ts                   # WebSocket client
│   └── utils.ts                # Formatters, helpers
└── package.json
```

### 8.2 Signal Terminal Page (Section 1)

```
┌──────────────────────────────────────────────────────────────────┐
│ [Sidebar] │              SIGNAL TERMINAL                          │
│           │                                                       │
│ Signals   │ ┌─────────────────────────────────────────────────┐  │
│ Auto-Bot  │ │          TradingView Chart (Lightweight 5.x)     │  │
│ Backtest  │ │  Candlestick + EMA + Bollinger + Signal Markers │  │
│ Settings  │ │  Multi-timeframe selector: 1m 5m 15m 1H 4H 1D  │  │
│           │ └─────────────────────────────────────────────────┘  │
│           │                                                       │
│           │ ┌──────────┬──────────┬──────────┬──────────┐        │
│           │ │ Signal 1 │ Signal 2 │ Signal 3 │ Signal 4 │        │
│           │ │ BTC LONG │ ETH SHORT│ SOL LONG │ DOGE LONG│        │
│           │ │ Grade: A │ Grade: B │ Grade: B │ Grade: C │        │
│           │ │ RR: 2.68 │ RR: 2.10 │ RR: 1.85 │ RR: 1.55│        │
│           │ │          │          │          │          │         │
│           │ │ [Execute]│ [Execute]│ [Execute]│ [Execute]│         │
│           │ └──────────┴──────────┴──────────┴──────────┘        │
│           │                                                       │
│           │ ┌───────────────────────────────────────────────────┐ │
│           │ │ ACTIVE POSITIONS                          [P&L]  │ │
│           │ │ BTC/USDT LONG  Entry: 97250  P&L: +$125 (+1.2%) │ │
│           │ │ ETH/USDT SHORT Entry: 2650   P&L: -$30  (-0.3%) │ │
│           │ └───────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 8.3 Execute Modal (One-Click + Advanced)

```
┌────────────────────────────────────────┐
│         EXECUTE SIGNAL                  │
│                                         │
│  BTC/USDT LONG  |  Grade A (0.85)      │
│                                         │
│  ┌─────────────┐ ┌──────────────────┐  │
│  │ ONE-CLICK   │ │ ADVANCED         │  │
│  │ Execute     │ │ Customize        │  │
│  └─────────────┘ └──────────────────┘  │
│                                         │
│  [Advanced Mode expanded:]              │
│  Entry Price:  [97,250.00 ] (editable)  │
│  Stop Loss:    [96,400.00 ] (editable)  │
│  TP1:          [98,500.00 ] (50%)       │
│  TP2:          [99,800.00 ] (30%)       │
│  TP3:          [101,500.00] (20%)       │
│  Position Size: [0.235 BTC] (editable)  │
│  Leverage:     [3x        ] (slider)    │
│  Risk Amount:  $200 (2.0%)              │
│  RR Ratio:     2.68x                    │
│                                         │
│  [ Cancel ]          [ Place Order ]    │
└────────────────────────────────────────┘
```

### 8.4 TradingView Chart Integration (Lightweight Charts 5.x)

```typescript
// Using Lightweight Charts 5.x API (from Context7)
import { createChart, CandlestickSeries } from 'lightweight-charts';

function TradingChart({ symbol, timeframe, signals }) {
  const chartRef = useRef(null);

  useEffect(() => {
    const chart = createChart(chartRef.current, {
      width: 800, height: 400,
      layout: { background: { color: '#1a1a2e' }, textColor: '#e0e0e0' },
      grid: { vertLines: { color: '#2a2a4a' }, horzLines: { color: '#2a2a4a' } },
      crosshair: { mode: 0 },
      timeScale: { timeVisible: true },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a', downColor: '#ef5350',
      wickUpColor: '#26a69a', wickDownColor: '#ef5350',
    });

    // Set initial data
    candleSeries.setData(historicalCandles);

    // Real-time updates via WebSocket
    ws.onmessage = (msg) => {
      const candle = JSON.parse(msg.data);
      candleSeries.update(candle);
    };

    // Signal markers
    const markers = signals.map(s => ({
      time: s.timestamp,
      position: s.direction === 'LONG' ? 'belowBar' : 'aboveBar',
      color: s.grade === 'A' ? '#26a69a' : '#ffb74d',
      shape: s.direction === 'LONG' ? 'arrowUp' : 'arrowDown',
      text: `${s.grade} ${s.direction}`,
    }));
    candleSeries.setMarkers(markers);

    return () => chart.remove();
  }, [symbol, timeframe]);

  return <div ref={chartRef} />;
}
```

---

## 9. Backend API Design

### 9.1 FastAPI Application Structure

```python
# main.py - FastAPI app with WebSocket support
from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CryptoQuant Engine API", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# REST Endpoints
app.include_router(signals_router, prefix="/api/signals", tags=["Signals"])
app.include_router(positions_router, prefix="/api/positions", tags=["Positions"])
app.include_router(orders_router, prefix="/api/orders", tags=["Orders"])
app.include_router(backtest_router, prefix="/api/backtest", tags=["Backtest"])
app.include_router(bot_router, prefix="/api/bot", tags=["Auto-Bot"])
app.include_router(settings_router, prefix="/api/settings", tags=["Settings"])

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    # Subscribe to Redis channels, forward to client
    async for message in redis_subscriber:
        await ws.send_json(message)
```

### 9.2 API Endpoints

```
Signals:
  GET  /api/signals              # List active signals (with filters)
  GET  /api/signals/{id}         # Get signal details
  GET  /api/signals/history      # Signal history with outcomes

Orders:
  POST /api/orders/execute       # Execute signal (one-click or advanced)
  POST /api/orders/cancel/{id}   # Cancel pending order
  GET  /api/orders               # List orders
  GET  /api/orders/{id}          # Order details

Positions:
  GET  /api/positions            # List open positions
  GET  /api/positions/{id}       # Position details with live P&L
  POST /api/positions/{id}/close # Close position (market)
  PUT  /api/positions/{id}/sl    # Update stop loss
  PUT  /api/positions/{id}/tp    # Update take profit

Auto-Bot:
  GET  /api/bot/status           # Bot status (running/paused/stopped)
  POST /api/bot/start            # Start bot
  POST /api/bot/pause            # Pause bot
  POST /api/bot/stop             # Stop bot
  PUT  /api/bot/paper-mode       # Toggle paper trading
  PUT  /api/bot/strategies       # Enable/disable strategies
  GET  /api/bot/performance      # Bot P&L and metrics
  GET  /api/bot/trades           # Bot trade history

Backtest:
  POST /api/backtest/run         # Run backtest (async, returns job_id)
  GET  /api/backtest/{job_id}    # Get backtest results
  GET  /api/backtest/history     # List past backtests
  POST /api/backtest/optimize    # Run parameter optimization
  POST /api/backtest/walkforward # Run walk-forward analysis

Settings:
  GET  /api/settings             # Get current settings
  PUT  /api/settings/exchange    # Update exchange API keys
  PUT  /api/settings/risk        # Update risk parameters
  PUT  /api/settings/notifications # Update notification prefs

WebSocket:
  WS   /ws                       # Real-time stream (signals, positions, prices)
```

### 9.3 WebSocket Message Types

```json
// Server → Client message types
{"type": "price_update", "data": {"symbol": "BTC/USDT", "price": 97250.5}}
{"type": "new_signal", "data": {/* full signal object */}}
{"type": "signal_expired", "data": {"id": "..."}}
{"type": "position_update", "data": {/* position with live P&L */}}
{"type": "position_closed", "data": {/* final position result */}}
{"type": "order_filled", "data": {/* order fill details */}}
{"type": "bot_status", "data": {"running": true, "paper": false}}
{"type": "risk_alert", "data": {"type": "drawdown_warning", "value": 0.08}}
{"type": "candle_update", "data": {/* latest candle for chart */}}
```

---

## 10. Notification System

### 10.1 Channels

| Channel | Use Case | Format |
|---------|----------|--------|
| Telegram Bot | Signal alerts, position updates, risk warnings | Rich text with markdown |
| Discord Webhook | Same as Telegram (alternative) | Embeds with colors |
| Web Push | In-app notifications | Toast notifications |
| Email | Daily summary report | HTML email |

### 10.2 Telegram Signal Format

```
NEW SIGNAL: BTC/USDT LONG
===========================
Grade: A (0.85) | Confidence: HIGH
Entry: $97,250 (Zone: $97,100-$97,400)
SL: $96,400 (-0.87%)
TP1: $98,500 (RR 1.5x) -> 50%
TP2: $99,800 (RR 3.0x) -> 30%
TP3: $101,500 (RR 5.0x) -> 20%
Size: 0.235 BTC | Risk: $200 (2%)
===========================
Strategies: SMC + Momentum + ML + Volume
```

---

## 11. Deployment Architecture

### 11.1 Docker Compose (Oracle Cloud Free Tier)

```yaml
# docker-compose.yml
version: '3.8'

services:
  trading-engine:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@timescaledb:5432/cryptoquant
      - REDIS_URL=redis://redis:6379
    depends_on:
      - timescaledb
      - redis
    restart: always
    deploy:
      resources:
        limits:
          memory: 8G

  api-server:
    build:
      context: ./backend
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@timescaledb:5432/cryptoquant
      - REDIS_URL=redis://redis:6379
    depends_on:
      - timescaledb
      - redis
    restart: always

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api-server:8000
      - NEXT_PUBLIC_WS_URL=ws://api-server:8000/ws
    depends_on:
      - api-server
    restart: always

  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      - POSTGRES_DB=cryptoquant
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - timescale_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: always
    deploy:
      resources:
        limits:
          memory: 6G

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: always
    deploy:
      resources:
        limits:
          memory: 2G

volumes:
  timescale_data:
  redis_data:
```

### 11.2 Oracle Cloud Resource Allocation

```
Total: 4 ARM Cores, 24GB RAM (Always Free)

Service          │ CPU │ RAM  │ Notes
─────────────────┼─────┼──────┼─────────────────
Trading Engine   │ 1.5 │ 8GB  │ Data streams + strategies + ML
API Server       │ 0.5 │ 2GB  │ FastAPI + WebSocket
Frontend         │ 0.5 │ 2GB  │ Next.js SSR
TimescaleDB      │ 1.0 │ 6GB  │ Time-series storage
Redis            │ 0.5 │ 2GB  │ Cache + event bus
OS + Overhead    │ 0   │ 4GB  │ Linux + Docker
─────────────────┼─────┼──────┤
Total            │ 4.0 │ 24GB │ Fits free tier exactly
```

---

## 12. Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
- [ ] Project setup: Git, pyproject.toml, Docker Compose
- [ ] Pydantic models for all core types
- [ ] TimescaleDB schema + migrations (Alembic)
- [ ] Redis connection + Pub/Sub wrapper
- [ ] Configuration system (Pydantic Settings, .env)
- [ ] Structured logging (structlog)
- [ ] Unit tests for config + models

### Phase 2: Data Collection (Weeks 3-4)
- [ ] CCXT 4.x async Binance connector
- [ ] WebSocket manager (auto-reconnect, heartbeat)
- [ ] Multi-timeframe OHLCV streaming
- [ ] Historical data loader (data.binance.vision bulk CSV)
- [ ] Data normalization layer
- [ ] Redis market data cache
- [ ] Integration tests with Binance testnet

### Phase 3: Indicators & Strategies (Weeks 5-7)
- [ ] Technical indicators (pandas-ta wrapper)
- [ ] Momentum RSI/EMA strategy
- [ ] Mean Reversion Bollinger strategy
- [ ] Smart Money Concepts (BOS, CHoCH, Order Blocks, FVG)
- [ ] Volume analysis strategy
- [ ] Signal aggregator + composite scoring
- [ ] Market regime detector
- [ ] Strategy unit tests

### Phase 4: Risk Management (Weeks 8-9)
- [ ] Position sizing (Fixed Fractional, Kelly)
- [ ] ATR-based dynamic SL
- [ ] Multi-level TP calculator
- [ ] RR ratio optimizer
- [ ] Portfolio heat tracker
- [ ] Circuit breakers
- [ ] Exposure manager

### Phase 5: Execution Engine (Week 10)
- [ ] Order manager (create, cancel, track)
- [ ] CCXT order execution (Binance USDM)
- [ ] Position tracker (SL/TP monitoring)
- [ ] Trailing stop logic
- [ ] Paper trading mode (simulated fills)
- [ ] Integration tests with Binance testnet

### Phase 6: Backtesting Engine (Weeks 11-12)
- [ ] Event-driven backtest engine
- [ ] Realistic trade simulation (slippage, fees, funding)
- [ ] Performance metrics calculator
- [ ] Walk-forward analysis
- [ ] Monte Carlo simulation
- [ ] Parameter optimizer (Optuna integration)
- [ ] Report generator (JSON/CSV export)

### Phase 7: FastAPI Backend + Frontend (Weeks 13-16)
- [ ] FastAPI REST endpoints (all routes)
- [ ] WebSocket real-time server
- [ ] JWT authentication
- [ ] Next.js 16 frontend setup (App Router)
- [ ] Signal Terminal page + TradingView charts
- [ ] Execute Modal (one-click + advanced)
- [ ] Auto-Bot Manager page
- [ ] Backtest Lab page
- [ ] Settings page (exchange keys, risk params)
- [ ] Real-time WebSocket integration

### Phase 8: ML/AI Layer (Weeks 17-18)
- [ ] Feature engineering pipeline
- [ ] XGBoost signal classifier
- [ ] GRU direction predictor
- [ ] Market regime ML model
- [ ] ONNX export + inference integration
- [ ] Model retraining pipeline

### Phase 9: Notifications + Polish (Weeks 19-20)
- [ ] Telegram bot notifications
- [ ] Discord webhook integration
- [ ] Email daily summary
- [ ] End-to-end testing
- [ ] Security audit
- [ ] Performance optimization

### Phase 10: Deploy + Go Live (Weeks 21-22)
- [ ] Docker images built and optimized
- [ ] Deploy to Oracle Cloud ARM
- [ ] SSL/HTTPS setup
- [ ] Monitoring (Grafana Cloud free tier)
- [ ] Paper trading validation (2 weeks minimum)
- [ ] Go live with small capital

---

## 13. Complete File Structure

```
D:\Users\BSI90966\Testing\Portfolio Project\TradingQuant\1\
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app entry
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── settings.py            # Pydantic Settings (env-based)
│   │   │   ├── constants.py           # Enums, constants
│   │   │   └── exchanges.py           # Exchange configs
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── models.py              # Pydantic models (Signal, Order, Position, etc.)
│   │   │   ├── events.py              # Redis Pub/Sub event bus
│   │   │   ├── exceptions.py          # Custom exceptions
│   │   │   └── engine.py              # Main orchestrator (async event loop)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── signals.py
│   │   │   │   ├── orders.py
│   │   │   │   ├── positions.py
│   │   │   │   ├── backtest.py
│   │   │   │   ├── bot.py
│   │   │   │   └── settings.py
│   │   │   ├── websocket.py           # WS endpoint
│   │   │   ├── auth.py                # JWT authentication
│   │   │   └── deps.py                # FastAPI dependencies
│   │   ├── data/
│   │   │   ├── __init__.py
│   │   │   ├── collector.py           # DataCollector (main orchestrator)
│   │   │   ├── providers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py            # BaseExchangeProvider
│   │   │   │   └── binance.py         # Binance adapter (CCXT 4.x)
│   │   │   ├── feed/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── websocket_manager.py
│   │   │   │   ├── rest_client.py
│   │   │   │   └── historical_loader.py
│   │   │   └── normalization/
│   │   │       ├── __init__.py
│   │   │       └── normalizer.py
│   │   ├── indicators/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── trend.py               # EMA, MACD, ADX, Ichimoku
│   │   │   ├── momentum.py            # RSI, Stochastic, CCI
│   │   │   ├── volatility.py          # ATR, Bollinger, Keltner
│   │   │   ├── volume.py              # VWAP, OBV, CVD, Volume Profile
│   │   │   └── orderflow.py           # Order flow delta
│   │   ├── strategies/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # BaseStrategy ABC
│   │   │   ├── technical/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── momentum_rsi_ema.py
│   │   │   │   └── mean_reversion_bb.py
│   │   │   ├── smart_money/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── market_structure.py  # BOS/CHoCH
│   │   │   │   ├── order_blocks.py
│   │   │   │   ├── fair_value_gaps.py
│   │   │   │   └── liquidity.py
│   │   │   ├── quantitative/
│   │   │   │   ├── __init__.py
│   │   │   │   └── funding_arb.py
│   │   │   └── composite/
│   │   │       ├── __init__.py
│   │   │       ├── signal_aggregator.py
│   │   │       └── regime_detector.py
│   │   ├── risk/
│   │   │   ├── __init__.py
│   │   │   ├── position_sizer.py
│   │   │   ├── stop_loss.py
│   │   │   ├── take_profit.py
│   │   │   ├── rr_optimizer.py
│   │   │   ├── portfolio_risk.py
│   │   │   ├── circuit_breaker.py
│   │   │   └── exposure_manager.py
│   │   ├── execution/
│   │   │   ├── __init__.py
│   │   │   ├── executor.py
│   │   │   ├── order_manager.py
│   │   │   ├── position_tracker.py
│   │   │   └── paper_trader.py
│   │   ├── backtesting/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   ├── simulator.py
│   │   │   ├── metrics.py
│   │   │   ├── walk_forward.py
│   │   │   ├── monte_carlo.py
│   │   │   ├── optimizer.py
│   │   │   └── report.py
│   │   ├── ml/
│   │   │   ├── __init__.py
│   │   │   ├── features/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── engineering.py
│   │   │   │   └── selection.py
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── signal_classifier.py   # XGBoost
│   │   │   │   ├── direction_predictor.py # GRU
│   │   │   │   ├── regime_classifier.py
│   │   │   │   └── anomaly_detector.py
│   │   │   ├── training/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── trainer.py
│   │   │   │   └── hyperopt.py
│   │   │   └── serving/
│   │   │       ├── __init__.py
│   │   │       └── predictor.py           # ONNX inference
│   │   ├── notifications/
│   │   │   ├── __init__.py
│   │   │   ├── telegram.py
│   │   │   ├── discord.py
│   │   │   └── email.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── database.py               # AsyncSession, engine
│   │   │   ├── models.py                 # SQLAlchemy models
│   │   │   ├── redis_client.py
│   │   │   └── migrations/               # Alembic
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── logger.py
│   │       └── crypto.py                 # Key encryption helpers
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── Dockerfile.api
│   └── .env.example
├── frontend/
│   ├── app/                              # Next.js 16 App Router
│   ├── components/
│   ├── hooks/
│   ├── lib/
│   ├── public/
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.dev.yml
├── .gitignore
├── .env.example
├── PLANNING.md
├── FREE_CRYPTO_DATA_SOURCES_REPORT.md
├── research/
│   ├── hft_quant_trading_report.md
│   ├── trading_strategies_signals_report.md
│   ├── risk_management_research.md
│   ├── 04_technical_architecture_infrastructure.md
│   └── ml_ai_crypto_trading_report.md
└── docs/
    └── plans/
        ├── 2025-02-10-cryptoquant-engine-design.md   # This file
        └── 2025-02-10-component-blueprint.md
```

---

## 14. Configuration Reference

### 14.1 Environment Variables (.env)

```bash
# Exchange
BINANCE_API_KEY=your_api_key
BINANCE_SECRET=your_secret
BINANCE_TESTNET=true

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/cryptoquant
REDIS_URL=redis://localhost:6379

# API
API_HOST=0.0.0.0
API_PORT=8000
JWT_SECRET=your-jwt-secret
CORS_ORIGINS=http://localhost:3000

# Notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
DISCORD_WEBHOOK_URL=your_webhook_url

# Risk Defaults
DEFAULT_RISK_PCT=0.02
MAX_POSITIONS=5
MAX_PORTFOLIO_HEAT=0.06
MAX_LEVERAGE=10
DEFAULT_LEVERAGE=3

# ML
ML_MODELS_DIR=./models
ML_RETRAIN_SCHEDULE=weekly

# Monitoring
GRAFANA_CLOUD_URL=your_grafana_url
```

### 14.2 Default Risk Configuration

```yaml
# risk_config.yaml
position_sizing:
  method: fixed_fractional
  risk_per_trade: 0.02
  max_risk_per_trade: 0.03

stop_loss:
  primary_method: atr_based
  atr_period: 14
  atr_multiplier:
    trending: 2.0
    ranging: 1.0
    volatile: 2.5
  max_sl_percent: 0.03

take_profit:
  method: multi_level
  tp1:
    rr_ratio: 1.5
    close_pct: 50
  tp2:
    rr_ratio: 3.0
    close_pct: 30
  tp3:
    rr_ratio: 5.0
    close_pct: 20
  move_sl_to_be_after: tp1
  activate_trailing_after: tp2

portfolio:
  max_positions: 5
  max_heat: 0.06
  max_correlated: 3
  max_daily_loss: 0.05
  max_weekly_loss: 0.10
  max_drawdown: 0.15

circuit_breakers:
  consecutive_losses_pause: 5
  daily_loss_reduce: 0.03
  daily_loss_stop: 0.05
  abnormal_spread_multiplier: 2.0

leverage:
  default: 3
  max: 10
  reduce_above_drawdown: 0.05
```

---

*Design Document v1.0 - Created 2025-02-10*
*Based on 5-agent deep research team + Context7 latest technology lookups*
*Ready for implementation starting Phase 1: Foundation*
