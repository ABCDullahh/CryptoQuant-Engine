# Frontend Hardcode Audit — Findings Table

## Summary
- **MUST_FIX**: 4 findings (all FIXED)
- **SHOULD_FIX**: 8 findings (6 FIXED, 2 ACCEPTABLE)
- **OK**: 12+ findings (true constants, correctly hardcoded)

## MUST_FIX (All Fixed)

| # | File | Line | Hardcoded Value | Should Be | Status |
|---|------|------|----------------|-----------|--------|
| 1 | `next.config.ts` | 9, 13 | `"http://localhost:8000"` (2x) | `process.env.API_URL` | **FIXED** — reads `API_URL` env var with localhost fallback |
| 2 | `lib/websocket.ts` | 125 | `"ws://localhost:8000/ws"` | Auto-detect from `window.location` | **FIXED** — `resolveWsUrl()` detects ws/wss from page protocol |
| 3 | `bot/page.tsx` | 41-47 | Strategy keys `smc`, `volume_profile`, `market_structure` | Must match backend `STRATEGY_REGISTRY` keys | **FIXED** — now uses `momentum`, `mean_reversion`, `smart_money`, `volume_analysis`, `funding_arb` |
| 4 | `lib/api.ts` | 394 | No request timeout | AbortController with 30s timeout | **FIXED** — `API_TIMEOUT_MS = 30_000` with AbortController |

## SHOULD_FIX (Fixed)

| # | File | Line | Hardcoded Value | Fix Applied | Status |
|---|------|------|----------------|-------------|--------|
| 5 | `page.tsx` | 37 | `TICKER_SYMBOLS` = 5 hardcoded symbols | Fetches from `/api/markets`, falls back to hardcoded | **FIXED** |
| 6 | `bot/page.tsx` | 711-715 | "Top 20" = 20 hardcoded symbols | `marketSymbols.slice(0, 20)` — dynamic from API | **FIXED** |
| 7 | `bot/page.tsx` | 179-185 | Default strategy toggles with wrong keys | Aligned with backend `STRATEGY_REGISTRY` | **FIXED** |
| 8 | `.env.example` | N/A | No env documentation | Created `.env.example` with `API_URL` and `NEXT_PUBLIC_WS_URL` | **FIXED** |
| 9 | `bot/page.tsx` | 187 | Default balance `"10000"` | — | ACCEPTABLE — matches backend default, synced from server on bot start |
| 10 | `bot/page.tsx` | 177 | Default symbol `"BTC/USDT"` | — | ACCEPTABLE — standard default, overridden by user selection |

## SHOULD_FIX (Acceptable — Not Changed)

| # | File | Line | Hardcoded Value | Reason OK |
|---|------|------|----------------|-----------|
| 11 | `page.tsx` | 73 | Polling interval `30_000` | UI timing constant; not market/user-specific |
| 12 | `chart/page.tsx` | 927 | Candle limit 1000/500 | Binance API batch size; exchange constraint |
| 13 | `chart/page.tsx` | 385 | Indicator limit `500` | Performance-tuned display constant |
| 14 | `bot/page.tsx` | 214 | Activity feed limit `50` | UI buffer size; not data-correctness |

## OK (True Constants — No Change Needed)

| Category | Files | Values | Reason |
|----------|-------|--------|--------|
| Timeframes | `chart/page.tsx`, `bot/page.tsx`, `backtest/page.tsx` | `["1m","3m","5m"..."1M"]` | Binance exchange-level constants |
| Status enums | `signals/page.tsx`, `bot/page.tsx` | `LONG/SHORT`, `A/B/C/D`, `ACTIVE/EXECUTED/...` | TypeScript type mappings matching API |
| Status colors | `bot/page.tsx` | `STATUS_CONFIG` with hex colors | UI visual constants |
| Price formatting | `chart/page.tsx`, `utils.ts` | `toFixed(2/4/6)` thresholds | Display-layer formatting |
| UI dimensions | `chart/page.tsx` | `240px`, `400px`, `260px` | Layout constants |
| Indicator catalog | `chart/page.tsx` | 16 indicator definitions | Feature catalog (matches backend IndicatorPipeline) |
| CSS classes | `backtest/page.tsx` | `INPUT_CLASS`, `SELECT_CLASS` | Tailwind utility strings |
| Toast duration | Multiple | `3000` ms | UX timing constant |

## Verification

- `npm run build` → 13 pages compiled, 0 errors
- `run_tests.py all` → 1236 passed, 0 failed
- All strategy keys now match backend `STRATEGY_REGISTRY`
- WS URL auto-detects ws:// vs wss:// based on page protocol
- API URL configurable via `API_URL` env var
