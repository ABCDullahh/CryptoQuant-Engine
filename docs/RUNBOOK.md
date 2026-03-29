# CryptoQuant Engine - Operational Runbook

> Version 0.1.0 | Last updated: 2026-02-13

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Startup Procedure](#startup-procedure)
4. [Shutdown Procedure](#shutdown-procedure)
5. [Bot Operations](#bot-operations)
6. [Health Checks](#health-checks)
7. [Incident Response](#incident-response)
8. [Recovery Procedures](#recovery-procedures)
9. [Log Reference](#log-reference)
10. [Configuration Reference](#configuration-reference)

---

## Architecture Overview

```
Frontend (Next.js 15.5) :3000
  ├── /api/* → proxied to Backend :8000
  └── /ws   → WebSocket to Backend

Backend (FastAPI + Uvicorn) :8000
  ├── REST API (JWT-authenticated)
  ├── WebSocket (real-time events)
  ├── BotService (orchestrator singleton)
  │   ├── DataCollector → Binance WS/REST via CCXT
  │   ├── SignalAggregator → 5 strategies
  │   └── Executor → Paper/Live trades
  └── EventBus → Redis Pub/Sub

TimescaleDB (PostgreSQL 16) :5433
  └── Candles, signals, orders, positions

Redis 7 :6379
  └── Pub/Sub channels, cache, rate limiting
```

## Prerequisites

| Dependency | Version | Required |
|-----------|---------|----------|
| Docker & Docker Compose | 20+ | Yes |
| Python | 3.13+ | Yes (backend) |
| Node.js | 20+ | Yes (frontend) |
| Binance API Keys | Demo or Live | Yes (demo.binance.com for testing) |

## Startup Procedure

### 1. Infrastructure Services

```bash
# Start TimescaleDB and Redis
docker compose up -d timescaledb redis

# Verify health
docker compose ps   # Both should be "healthy"
docker exec cryptoquant-redis redis-cli ping    # → PONG
docker exec cryptoquant-timescaledb pg_isready -U cryptoquant  # → accepting connections
```

### 2. Backend

```bash
cd backend

# Activate virtual environment
.venv\Scripts\activate   # Windows
source .venv/bin/activate # Linux/Mac

# Verify .env is present
cat .env  # Check DATABASE_URL, REDIS_URL, BINANCE_API_KEY

# Initialize database (auto-runs on startup, but can run manually)
python -c "import asyncio; from app.db.database import init_db; asyncio.run(init_db())"

# Seed data (first-time only)
python scripts/seed_data.py

# Start server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Verify
curl http://localhost:8000/health  # → {"status":"ok","uptime_seconds":...}
```

### 3. Frontend

```bash
cd frontend
npm run dev    # Development
# or
npm run build && npm start  # Production
```

### 4. Full Docker Stack (Alternative)

```bash
docker compose up -d
# Includes: timescaledb, redis, backend, frontend
```

## Shutdown Procedure

### Graceful Shutdown

```bash
# 1. Stop bot FIRST (via API or UI)
curl -X POST http://localhost:8000/api/bot/stop \
  -H "Authorization: Bearer $JWT_TOKEN"

# 2. Wait for bot to fully stop (check logs for "bot.stopped")

# 3. Stop backend (Ctrl+C or SIGTERM)
# Lifespan handler will:
#   - Stop bot_service if still running
#   - Stop WebSocket bridge
#   - Close DB connection pool
#   - Close Redis connections

# 4. Stop infrastructure
docker compose down          # Stop services, keep data
docker compose down -v       # Stop services AND delete volumes (DATA LOSS)
```

### Emergency Shutdown

If the bot is unresponsive:
```bash
# Kill the backend process
# Windows: taskkill /f /im python.exe
# Linux: kill -9 $(pgrep -f uvicorn)

# Bot will be stopped when process exits
# No trades will be left hanging (paper mode is stateless)
# For live mode: positions remain open on exchange - manual close required!
```

## Bot Operations

### Start Bot (Paper Mode)

Via API:
```bash
curl -X POST http://localhost:8000/api/bot/start \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTC/USDT"],
    "timeframes": ["1h"],
    "strategies": ["smc", "volume_profile", "market_structure", "momentum", "funding_rate"],
    "is_paper": true,
    "paper_balance": 10000
  }'
```

Via UI: Navigate to Bot Manager page, configure settings, click "Start".

### Stop Bot

```bash
curl -X POST http://localhost:8000/api/bot/stop \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Pause Bot (Keeps SL/TP Monitoring)

```bash
curl -X POST http://localhost:8000/api/bot/pause \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Check Bot Status

```bash
curl http://localhost:8000/api/bot/status \
  -H "Authorization: Bearer $JWT_TOKEN"
# Response: {"status": "RUNNING", "symbols": [...], ...}
```

## Health Checks

### Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /health` | No | Basic health + uptime |
| `GET /api/bot/status` | JWT | Bot running state |
| `GET /api/bot/live-status` | JWT | Real-time service status |

### Docker Health Checks

TimescaleDB and Redis have built-in healthchecks in `docker-compose.yml`:
- TimescaleDB: `pg_isready -U cryptoquant` every 10s
- Redis: `redis-cli ping` every 10s

### Manual Diagnostics

```bash
# Check TimescaleDB connection
docker exec cryptoquant-timescaledb psql -U cryptoquant -c "SELECT 1"

# Check Redis connection
docker exec cryptoquant-redis redis-cli info server | grep uptime

# Check candle data exists
docker exec cryptoquant-timescaledb psql -U cryptoquant -c \
  "SELECT symbol, timeframe, COUNT(*) FROM candles GROUP BY symbol, timeframe"

# Check recent signals
docker exec cryptoquant-timescaledb psql -U cryptoquant -c \
  "SELECT * FROM signals ORDER BY created_at DESC LIMIT 5"
```

## Incident Response

### IR-001: Bot Not Generating Signals

**Symptoms**: Bot shows RUNNING but no signals appear.

**Checklist**:
1. Check backend logs for `bot.no_signal` — strategies may not have enough data
2. Verify candle data: `docker exec cryptoquant-timescaledb psql -U cryptoquant -c "SELECT COUNT(*) FROM candles WHERE symbol='BTC/USDT'"`
3. Check if candle events are flowing: Look for `event_bus.published market.candle.1h` in logs
4. Verify Redis Pub/Sub is working: `docker exec cryptoquant-redis redis-cli PUBSUB CHANNELS '*'`
5. Wait for enough historical data (strategies need 14+ candles minimum)

**Resolution**: If no candles coming in, check Binance API connection. Restart bot to trigger `load_historical(days_back=14)`.

### IR-002: Circuit Breaker Tripped

**Symptoms**: Bot logs show `circuit_breaker.tripped`, no new trades.

**Triggers**:
- Daily loss > 5% (`MAX_DAILY_LOSS`)
- Weekly loss > 10% (`MAX_WEEKLY_LOSS`)
- Drawdown > 15% (`MAX_DRAWDOWN`)
- 5 consecutive losses (`CONSECUTIVE_LOSS_PAUSE`)

**Resolution**:
1. Circuit breaker auto-recovers after 4h cooldown (`CIRCUIT_BREAKER_COOLDOWN_HOURS`)
2. Goes to HALF_OPEN state (reduced position sizes)
3. If trade succeeds → CLOSED (normal)
4. If trade fails → OPEN again (another cooldown)
5. DO NOT manually override — the circuit breaker exists for protection

### IR-003: Database Connection Failures

**Symptoms**: API returns 500 errors, logs show `db.init_failed`.

**Checklist**:
1. Verify TimescaleDB is running: `docker compose ps timescaledb`
2. Check port: `.env` has `DATABASE_URL=...@localhost:5433/...` (NOT 5432)
3. Check if local PostgreSQL is conflicting on port 5432
4. Check connection pool: pool_size=10, max_overflow=20

**Resolution**: Restart TimescaleDB, then restart backend.

### IR-004: Redis Connection Failures

**Symptoms**: WebSocket events not flowing, bot price updates missing.

**Checklist**:
1. Verify Redis is running: `docker compose ps redis`
2. Check memory: `docker exec cryptoquant-redis redis-cli info memory`
3. Redis is configured with `maxmemory 512mb` and LRU eviction

**Resolution**: Restart Redis. EventBus and WS bridge will auto-reconnect on next request.

### IR-005: Exchange API Errors (Binance)

**Symptoms**: Bot logs show CCXT errors, no candle data.

**Checklist**:
1. Check API key validity at demo.binance.com
2. Check rate limits (CCXT handles this, but verify)
3. Verify `BINANCE_TESTNET=true` for demo mode
4. Check network connectivity to api.binance.com

**Resolution**: Regenerate API keys if expired. Restart bot.

## Recovery Procedures

### Full System Recovery

1. Stop all processes
2. `docker compose down`
3. `docker compose up -d timescaledb redis`
4. Wait for healthy status
5. Start backend
6. Run seed data if database was wiped: `python scripts/seed_data.py`
7. Start frontend
8. Verify health endpoint
9. Start bot via UI

### Database Recovery

TimescaleDB data is persisted in Docker volume `timescale_data`.

```bash
# Backup
docker exec cryptoquant-timescaledb pg_dump -U cryptoquant cryptoquant > backup.sql

# Restore (after docker compose up -d timescaledb)
docker exec -i cryptoquant-timescaledb psql -U cryptoquant cryptoquant < backup.sql
```

## Log Reference

All backend logs use structured JSON format (structlog).

### Key Log Events

| Log Event | Level | Meaning |
|-----------|-------|---------|
| `app.starting` | INFO | Application starting up |
| `app.shutdown` | INFO | Application shutting down |
| `bot.starting` | INFO | Bot service starting |
| `bot.started` | INFO | Bot fully started, collecting data |
| `bot.stopped` | INFO | Bot fully stopped |
| `bot.paused` | INFO | Bot paused (SL/TP still active) |
| `bot.resumed` | INFO | Bot resumed from pause |
| `bot.executing_signal` | INFO | Signal qualified, executing trade |
| `bot.signal_executed` | INFO | Trade executed successfully |
| `bot.signal_below_min_grade` | INFO | Signal grade too low, skipped |
| `bot.no_signal` | DEBUG | No signal generated this candle |
| `bot.strategy_error` | ERROR | Strategy execution failed |
| `bot.start_failed` | ERROR | Bot failed to start |
| `circuit_breaker.tripped` | WARNING | Circuit breaker activated |
| `db.init_failed` | WARNING | Database init failed |
| `ws_bridge.start_failed` | WARNING | WebSocket bridge failed |

## Configuration Reference

### Environment Variables (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...localhost:5432/...` | TimescaleDB connection |
| `DATABASE_POOL_SIZE` | 10 | Connection pool size |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `TRADING_ENABLED` | `false` | **Master kill switch** — must be `true` for live trading |
| `ENVIRONMENT` | `demo` | Must be `live` for real trading |
| `BINANCE_API_KEY` | (empty) | Binance API key |
| `BINANCE_SECRET` | (empty) | Binance API secret |
| `BINANCE_TESTNET` | `true` | Use Binance testnet/demo |
| `JWT_SECRET` | (auto-generated) | JWT signing secret |
| `API_PORT` | 8000 | Backend port |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins |
| `DEFAULT_RISK_PCT` | 0.02 | Risk per trade (2%) |
| `MAX_POSITIONS` | 5 | Maximum concurrent positions |
| `MAX_LEVERAGE` | 10 | Maximum leverage allowed |
| `DEFAULT_LEVERAGE` | 3 | Default leverage |
| `LOG_LEVEL` | `INFO` | Logging level |

### Safety Guards

| Guard | Location | Condition |
|-------|----------|-----------|
| Trading kill switch | `settings.py` | `TRADING_ENABLED=false` blocks all live trades |
| Environment gate | `bot/service.py` | `ENVIRONMENT != "live"` blocks live mode |
| Circuit breaker | `risk/circuit_breaker.py` | Auto-pauses on loss thresholds |
| Position limits | `risk/portfolio.py` | Max 5 concurrent positions |
| Leverage cap | `settings.py` | Max 10x leverage |
| Grade filter | `bot/service.py` | Only executes A/B grade signals |
