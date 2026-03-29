# Frontend UX Notes — Quant Trader Perspective

## Critical UX Findings (Discovered During Hardcode Audit)

### 1. Bot Strategies Were Silently Broken (FIXED)

**Impact:** HIGH — Bot would appear to start but trade with 0 strategies.

The bot page sent strategy keys `smc`, `volume_profile`, `market_structure` to the backend. These don't exist in `STRATEGY_REGISTRY`. The backend would silently ignore unknown keys, meaning:
- User enables 3 strategies in UI
- Backend starts bot with 0 active strategies
- No signals generated, no trades executed
- User sees "Running" status but nothing happens
- No error shown to user

**Fix:** Strategy keys aligned to match backend: `momentum`, `mean_reversion`, `smart_money`, `volume_analysis`, `funding_arb`.

**UX recommendation:** Backend should return a validation error when unknown strategy names are submitted, rather than silently ignoring them.

---

### 2. WebSocket Would Fail on Production Deploy (FIXED)

**Impact:** HIGH — All real-time features dead on any non-localhost deployment.

Hardcoded `ws://localhost:8000/ws` means:
- Deploy to Oracle Cloud → WS connection fails
- Deploy behind HTTPS → mixed content blocked by browser
- No error shown to user (silent reconnect loop)

**Fix:** Auto-detect protocol from page origin. `wss://` for HTTPS, `ws://` for HTTP. Env override available.

---

### 3. No Request Timeout (FIXED)

**Impact:** MEDIUM — UI hangs indefinitely on network issues.

If Binance API is slow or network drops mid-request:
- Loading spinner never stops
- User clicks buttons repeatedly
- No feedback that something is wrong

**Fix:** 30s AbortController timeout on all API requests. Throws `ApiRequestError` with clear message.

---

### 4. Ticker Shows Fixed 5 Symbols Regardless of Market (FIXED)

**Impact:** LOW — Cosmetic but misleading for active traders.

Dashboard ticker always showed BTC/ETH/BNB/SOL/XRP even if user trades other pairs. Now loads top 5 from `/api/markets`.

---

## UX Observations (Not Bugs, But Improvement Opportunities)

### 5. No Client-Side P&L Calculation on Positions Page

Open positions show unrealized P&L from the last API poll (5s). Between polls, P&L is stale. A quant trader expects sub-second P&L updates.

**Recommendation:** Calculate `unrealizedPnl = (currentPrice - entryPrice) * size * direction` client-side using `price_update` WebSocket events. The data is already flowing — just needs the math.

### 6. Order Book Depth Visualization

Current order book shows raw price/quantity numbers. Professional trading UIs show:
- Cumulative depth bars (horizontal, proportional to total)
- Spread percentage in the middle
- Color-coded bid/ask walls

The data is there (`orderbook_update` WebSocket), but visualization could be enhanced.

### 7. No Keyboard Shortcuts

Quant traders expect:
- `Esc` to close modals
- `1-9` for timeframe quick-switch
- `Enter` to confirm dialogs
- `Ctrl+K` for symbol search

### 8. Chart Indicator Panel Heights

RSI, MACD, Stochastic sub-panels have fixed heights. Traders often want to resize these dynamically (drag-to-resize divider). Current implementation uses fixed `100px` panels.

### 9. Backtest Equity Curve Scale

The equity curve chart doesn't auto-scale Y-axis on extreme drawdowns. If a backtest goes from 10000 to 500, the curve is barely visible. Should use dynamic Y-axis scaling.

### 10. No Sound/Desktop Notifications

Real-time signals arrive via WebSocket but there's no audio alert or browser notification. A live trader may have multiple windows open and miss a Grade A signal.

**Recommendation:** Add optional browser `Notification` API + audio beep for Grade A/B signals.

### 11. Error Toast Positioning

Error toasts appear at bottom-right and can overlap with the order book panel on the chart page. Consider top-center placement for critical errors (like "Bot failed to start").

### 12. Mobile Responsiveness

The grid layout (`grid-cols-4`) doesn't collapse well on tablets. The chart page is essentially unusable on mobile. For a professional trading platform, this is acceptable (traders use desktop), but the login page should work on mobile for quick monitoring.

---

## Summary

| Finding | Severity | Status |
|---------|----------|--------|
| Strategy keys mismatch (bot silently broken) | CRITICAL | **FIXED** |
| WS fails on production deploy | CRITICAL | **FIXED** |
| No API request timeout | HIGH | **FIXED** |
| Hardcoded ticker symbols | LOW | **FIXED** |
| Client-side P&L calculation | MEDIUM | Enhancement |
| Order book depth visualization | LOW | Enhancement |
| Keyboard shortcuts | LOW | Enhancement |
| Sound/notifications for signals | LOW | Enhancement |
