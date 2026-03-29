# CryptoQuant Engine - Staged Rollout Plan

> Version 0.1.0 | Last updated: 2026-02-13

## Rollout Stages

```
Stage 0: Local Demo    → Current state, all features verified
Stage 1: Paper Trading  → Real Binance data, simulated trades (no real money)
Stage 2: Shadow Trading → Real data, paper trades compared to would-be live trades
Stage 3: Live Micro     → Real trades with minimal capital ($100-500)
Stage 4: Live Standard  → Real trades with standard capital
```

---

## Stage 0: Local Demo (CURRENT - COMPLETE)

**Environment**: `ENVIRONMENT=demo`, `TRADING_ENABLED=false`

### Entry Gate
- [x] All 10 development phases complete
- [x] Backend: 1165 unit tests pass, 0 failures
- [x] Frontend: 37 E2E tests pass, 0 flaky
- [x] Frontend build compiles with 0 errors
- [x] All 8 pages render correctly
- [x] Binance Demo API verified (14/14 checks pass)
- [x] Safety guards verified (TRADING_ENABLED, ENVIRONMENT gate, circuit breaker)
- [x] Readiness scorecard: 68/68 PASS

### Configuration
```env
TRADING_ENABLED=false
ENVIRONMENT=demo
BINANCE_TESTNET=true
BINANCE_API_KEY=<demo.binance.com key>
BINANCE_SECRET=<demo.binance.com secret>
```

### What Works
- Full UI with seed data
- Real Binance prices on chart
- Bot start/stop/pause (paper mode)
- Signal generation from live candles
- All backtesting features

---

## Stage 1: Paper Trading (NEXT)

**Environment**: `ENVIRONMENT=demo`, `TRADING_ENABLED=false`
**Duration**: 2-4 weeks minimum

### Entry Gate
- [ ] Stage 0 complete
- [ ] Docker deployment on Oracle Cloud (or local server) running 24/7
- [ ] TimescaleDB and Redis persistent and backed up
- [ ] System runs for 24h without crashes
- [ ] At least 50 candles collected per symbol

### Actions
1. Deploy to always-on server (Oracle Cloud Free Tier)
2. Start bot in paper trading mode via UI
3. Configure: BTC/USDT, 1h timeframe, all 5 strategies
4. Monitor daily:
   - Signal generation rate
   - Trade execution quality (entry, SL, TP accuracy)
   - Circuit breaker triggers
   - Memory and CPU usage

### Success Criteria
- [ ] Bot runs continuously for 7+ days without manual restart
- [ ] 20+ paper trades executed
- [ ] Win rate > 40%
- [ ] No circuit breaker triggers from bugs (only from legitimate loss sequences)
- [ ] Paper P&L is positive or within acceptable drawdown (<15%)
- [ ] Memory usage stable (no leaks)

### Configuration
```env
TRADING_ENABLED=false
ENVIRONMENT=demo
BINANCE_TESTNET=true
```

### Monitoring Checklist (Daily)
- [ ] Check `GET /health` returns OK
- [ ] Check `GET /api/bot/status` returns RUNNING
- [ ] Review backend logs for errors
- [ ] Check TimescaleDB disk usage
- [ ] Check Redis memory usage
- [ ] Review signal and trade history in UI

---

## Stage 2: Shadow Trading

**Environment**: `ENVIRONMENT=demo`, `TRADING_ENABLED=false`
**Duration**: 2-4 weeks

### Entry Gate
- [ ] Stage 1 complete with all success criteria met
- [ ] Paper trading shows positive risk-adjusted returns
- [ ] No system stability issues for 14+ days
- [ ] Notification system configured (Telegram or Discord)

### Actions
1. Continue paper trading
2. Manually track what would have happened in live mode
3. Compare paper results vs actual market outcomes
4. Fine-tune strategy parameters based on data

### Success Criteria
- [ ] Paper results closely match theoretical live results
- [ ] Sharpe ratio > 1.0 over the period
- [ ] Max drawdown < 10% of paper balance
- [ ] 50+ trades analyzed
- [ ] Notifications working (trade alerts, circuit breaker alerts)

### Configuration
```env
TRADING_ENABLED=false
ENVIRONMENT=demo
BINANCE_TESTNET=true
TELEGRAM_BOT_TOKEN=<your_bot_token>
TELEGRAM_CHAT_ID=<your_chat_id>
```

---

## Stage 3: Live Micro

**Environment**: `ENVIRONMENT=live`, `TRADING_ENABLED=true`
**Duration**: 2-4 weeks
**Capital**: $100-500 (minimal risk)

### Entry Gate (ALL REQUIRED)
- [ ] Stage 2 complete with all success criteria met
- [ ] Unique `JWT_SECRET` set (not default)
- [ ] HTTPS enabled (reverse proxy)
- [ ] Binance LIVE API keys (not demo/testnet)
- [ ] `BINANCE_TESTNET=false`
- [ ] Risk parameters tightened:
  - `DEFAULT_RISK_PCT=0.01` (1% per trade)
  - `MAX_POSITIONS=2`
  - `MAX_LEVERAGE=3`
  - `DEFAULT_LEVERAGE=1`
- [ ] Telegram/Discord notifications active and tested
- [ ] Database backup procedure tested
- [ ] Emergency shutdown procedure documented and tested

### Actions
1. Fund Binance account with $100-500
2. Update `.env`:
   ```env
   TRADING_ENABLED=true
   ENVIRONMENT=live
   BINANCE_TESTNET=false
   BINANCE_API_KEY=<live_api_key>
   BINANCE_SECRET=<live_api_secret>
   DEFAULT_RISK_PCT=0.01
   MAX_POSITIONS=2
   MAX_LEVERAGE=3
   DEFAULT_LEVERAGE=1
   ```
3. Start bot with `is_paper=false`
4. Monitor every trade notification
5. Be ready to stop bot at any time

### Success Criteria
- [ ] First 10 live trades execute correctly
- [ ] P&L tracking matches Binance account
- [ ] No unexpected orders or position sizes
- [ ] Circuit breaker triggers correctly on loss sequences
- [ ] Notifications arrive within 5 seconds of trade
- [ ] System stable for 14+ days

### Risk Limits (Stage 3)
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max Risk Per Trade | 1% | Conservative start |
| Max Positions | 2 | Limit exposure |
| Max Leverage | 3x | Minimal leverage |
| Max Daily Loss | 5% ($5-25) | Circuit breaker protection |
| Capital at Risk | $100-500 | Affordable loss |

---

## Stage 4: Live Standard

**Environment**: `ENVIRONMENT=live`, `TRADING_ENABLED=true`
**Duration**: Ongoing
**Capital**: User's discretion

### Entry Gate (ALL REQUIRED)
- [ ] Stage 3 complete with positive results over 2+ weeks
- [ ] 50+ live trades with consistent execution
- [ ] Win rate and Sharpe ratio meet expectations
- [ ] No system bugs encountered during live trading
- [ ] User comfortable with risk level

### Actions
1. Gradually increase parameters:
   ```env
   DEFAULT_RISK_PCT=0.02    # 2% per trade
   MAX_POSITIONS=5           # Standard limit
   MAX_LEVERAGE=5            # Moderate leverage
   ```
2. Add more symbols: ETH/USDT, SOL/USDT, etc.
3. Add more timeframes: 15m, 4h alongside 1h
4. Consider enabling ML signal enhancement

### Risk Limits (Stage 4)
| Parameter | Value |
|-----------|-------|
| Max Risk Per Trade | 2% |
| Max Positions | 5 |
| Max Leverage | 5-10x |
| Max Daily Loss | 5% |
| Max Weekly Loss | 10% |
| Max Drawdown | 15% |

---

## Emergency Procedures

### Immediate Stop (Any Stage)

```bash
# Via API
curl -X POST http://localhost:8000/api/bot/stop \
  -H "Authorization: Bearer $JWT_TOKEN"

# Via UI
Navigate to Bot Manager → Click "Stop"

# Nuclear option (if API unresponsive)
# Kill the backend process
```

### Rollback to Previous Stage

1. Stop the bot
2. Update `.env` to previous stage's configuration
3. Set `TRADING_ENABLED=false` if rolling back from live
4. Restart backend
5. Verify with health check

### Capital Protection Rules

1. **Never risk more than you can afford to lose**
2. **Start with the minimum viable amount ($100)**
3. **Do not skip stages** — each stage builds confidence
4. **If any stage fails its success criteria, do NOT advance**
5. **Circuit breaker is your friend** — do not disable it
6. **Review every trade** during Stage 3 (Live Micro)

---

## Timeline Estimate

| Stage | Duration | Cumulative |
|-------|----------|------------|
| Stage 0: Local Demo | Complete | 0 weeks |
| Stage 1: Paper Trading | 2-4 weeks | 2-4 weeks |
| Stage 2: Shadow Trading | 2-4 weeks | 4-8 weeks |
| Stage 3: Live Micro | 2-4 weeks | 6-12 weeks |
| Stage 4: Live Standard | Ongoing | 8-14 weeks |

**Total time to full live trading: ~2-3 months minimum**

This timeline prioritizes safety over speed. Each stage must meet ALL its success criteria before advancing.
