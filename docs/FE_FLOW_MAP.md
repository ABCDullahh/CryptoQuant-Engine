# Frontend Flow Map — Route/Screen Map + Data Dependencies

## Routes Overview

| Route | Page Component | Auth | Purpose |
|-------|---------------|------|---------|
| `/login` | LoginPage | No | Login / Register (tab switcher) |
| `/` | OverviewPage | Yes | Dashboard: live prices, signals, positions, bot perf |
| `/chart` | ChartPage | Yes | Interactive chart + indicators + order book |
| `/signals` | SignalsPage | Yes | Signal terminal with filtering + execution |
| `/bot` | BotPage | Yes | Bot manager: start/stop/pause, config, activity feed |
| `/backtest` | BacktestLabPage | Yes | Strategy backtesting + optimization |
| `/positions` | PositionsPage | Yes | Position manager: SL/TP controls, close |
| `/settings` | SettingsPage | Yes | Exchange keys, risk params, notifications |
| `/analytics` | AnalyticsPage | Yes | Performance analytics (placeholder) |
| `/system` | SystemPage | Yes | System health dashboard |

## Data Flow per Page

### `/` — Dashboard
```
REST (on mount + 30s polling):
  fetchSignals()              → GET /api/signals
  fetchPositions()            → GET /api/positions
  fetchBotPerformance()       → GET /api/bot/performance
  fetchExchangePositions()    → GET /api/positions/exchange-positions
  fetchBalance()              → GET /api/markets/balance
  fetchMarkets()              → GET /api/markets  (ticker symbols)

WebSocket:
  price_update    → live price ticker + position P&L
  signal_new      → scheduleRefetch (2s debounce)
  position_update → scheduleRefetch (2s debounce)
  bot_status      → scheduleRefetch (2s debounce)
```

### `/chart` — Chart
```
REST (on symbol/timeframe change):
  fetchMarkets()                    → GET /api/markets
  fetchCandles(sym, tf, limit)      → GET /api/candles?symbol=...&timeframe=...&limit=...
  fetchIndicators(sym, tf, limit, inds) → GET /api/indicators?...
  fetchOrderBook(sym, limit)        → GET /api/markets/orderbook?symbol=...&limit=...

WebSocket:
  price_update     → update last candle + ticker
  orderbook_update → real-time order book panel

localStorage:
  cq_selected_indicators  → persisted indicator selection
  cq_indicator_settings   → persisted indicator periods/colors
```

### `/signals` — Signal Terminal
```
REST (10s polling):
  fetchSignals(filters)   → GET /api/signals?status=...&direction=...&symbol=...&grade=...
  executeSignal(id)       → POST /api/signals/{id}/execute

WebSocket:
  signal_new    → prepend to list
  signal_update → update existing signal
```

### `/bot` — Bot Manager
```
REST:
  fetchBotStatus()        → GET /api/bot/status  (5s polling)
  fetchBotPerformance()   → GET /api/bot/performance  (30s polling)
  fetchMarkets()          → GET /api/markets  (one-shot, for symbol selector)
  startBot(config)        → POST /api/bot/start
  stopBot()               → POST /api/bot/stop
  pauseBot()              → POST /api/bot/pause
  updatePaperMode(mode)   → PUT /api/bot/paper-mode
  updateStrategies(map)   → PUT /api/bot/strategies

WebSocket:
  bot_status      → refetch status
  signal_new      → activity feed entry
  position_update → activity feed entry
```

### `/backtest` — Backtest Lab
```
REST:
  fetchMarkets()             → GET /api/markets  (one-shot, for symbol selector)
  fetchBacktestHistory()     → GET /api/backtest/history
  runBacktest(config)        → POST /api/backtest/run
  fetchBacktest(id)          → GET /api/backtest/{id}  (3s poll for results)

WebSocket:
  backtest_progress → progress bar update {job_id, progress, status}
```

### `/positions` — Position Manager
```
REST (5s polling):
  fetchPositions(filters)       → GET /api/positions?status=...&symbol=...&mode=...
  fetchExchangePositions()      → GET /api/positions/exchange-positions
  fetchBotStatus()              → GET /api/bot/status  (for mode display)
  closePosition(id)             → POST /api/positions/{id}/close
  updateStopLoss(id, sl)        → PUT /api/positions/{id}/sl
  updateTakeProfit(id, tps)     → PUT /api/positions/{id}/tp

WebSocket:
  position_update → refetch positions
  price_update    → live unrealized P&L calculation
```

### `/settings` — Settings
```
REST:
  fetchSettings()               → GET /api/settings
  updateExchangeKeys(data)      → PUT /api/settings/exchange
  updateRiskParams(data)        → PUT /api/settings/risk
  updateNotifications(data)     → PUT /api/settings/notifications
```

### `/system` — System Health
```
REST (one-shot):
  fetchSystemStatus()   → GET /api/system/status

WebSocket:
  system_status → real-time health updates (every 2s)
```

### `/analytics` — Analytics
```
REST (one-shot + 15s polling):
  fetchSignals()        → GET /api/signals
  fetchPositions()      → GET /api/positions

WebSocket:
  signal_new      → refetch
  position_update → refetch
```

## WebSocket Event Types

| Event | Payload | Pages |
|-------|---------|-------|
| `price_update` | `{symbol, price, change24h, volume, candle?}` | Dashboard, Chart, Positions |
| `signal_new` | Signal object | Dashboard, Signals, Bot, Analytics |
| `signal_update` | Signal object | Signals |
| `position_update` | Position object | Dashboard, Positions, Bot, Analytics |
| `bot_status` | `{status, paper_mode, active_strategies, ...}` | Dashboard, Bot |
| `system_status` | `{components[], overall_status}` | System |
| `orderbook_update` | `{symbol, bids[][], asks[][]}` | Chart |
| `backtest_progress` | `{job_id, progress, status}` | Backtest |

## Auth Flow

1. `POST /api/auth/login` or `/register` → JWT token
2. Token stored in `localStorage("token")`
3. `apiFetch()` injects `Authorization: Bearer ${token}` on every request
4. 401 response → clear token → redirect to `/login`
5. `AuthGuard` component blocks protected routes if no token
