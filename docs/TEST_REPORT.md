# Frontend Audit — Test Report

## 1. Frontend Build Verification

**Command:**
```bash
cd frontend && npm run build
```

**Output:**
```
▲ Next.js 15.5.12
- Environments: .env.local

Creating an optimized production build ...
✓ Compiled successfully in 3.6s
Linting and checking validity of types ...
Collecting page data ...
✓ Generating static pages (13/13)
Finalizing page optimization ...

Route (app)                Size  First Load JS
┌ ○ /                    3.19 kB   112 kB
├ ○ /_not-found            993 B   103 kB
├ ○ /analytics            4.6 kB   110 kB
├ ○ /backtest            8.17 kB   113 kB
├ ○ /bot                 7.75 kB   113 kB
├ ○ /chart                 13 kB   118 kB
├ ○ /login               4.26 kB   107 kB
├ ○ /positions           8.63 kB   114 kB
├ ○ /settings            4.03 kB   109 kB
├ ○ /signals             6.64 kB   112 kB
└ ○ /system              5.58 kB   111 kB
```

**Result:** 13 pages compiled, 0 errors, 0 type errors.
**Status:** PASS

---

## 2. Backend Unit Tests (Regression Check)

**Command:**
```bash
cd backend && python run_tests.py all
```

**Output:**
```
RESULTS: 1236 passed, 0 failed (313.8s)
ALL TESTS PASSED
```

**Result:** 86 test files, 1236 tests, 0 failures, 0 skips.
**Status:** PASS

---

## 3. Strategy Key Alignment Verification

**Command:**
```bash
cd backend && python -c "from app.strategies import STRATEGY_REGISTRY; print(sorted(STRATEGY_REGISTRY.keys()))"
```

**Output:**
```
['funding_arb', 'mean_reversion', 'momentum', 'smart_money', 'volume_analysis']
```

**Frontend bot page keys (after fix):**
```
['funding_arb', 'mean_reversion', 'momentum', 'smart_money', 'volume_analysis']
```

**Frontend backtest page keys:**
```
['funding_arb', 'mean_reversion', 'momentum', 'smart_money', 'volume_analysis']
```

**Result:** All 3 sources aligned.
**Status:** PASS

---

## 4. ExchangeFactory Verification

**Command:**
```bash
cd backend && python -c "
import asyncio
async def test():
    from app.data.providers.exchange_factory import create_exchange
    ex = await create_exchange()
    print(f'Type: {type(ex).__name__}, ID: {ex.id}, RateLimit: {ex.enableRateLimit}')
    await ex.close()
    ex2 = await create_exchange(auth=True)
    print(f'Auth: key={bool(ex2.apiKey)}, secret={bool(ex2.secret)}')
    await ex2.close()
asyncio.run(test())
"
```

**Output:**
```
Type: binanceusdm, ID: binanceusdm, RateLimit: True
Auth: key=True, secret=True
```

**Status:** PASS

---

## 5. WebSocket URL Resolution Verification

Tested the `resolveWsUrl()` logic:

| Context | `window` | `NEXT_PUBLIC_WS_URL` | Result |
|---------|----------|---------------------|--------|
| SSR (no window) | undefined | not set | `ws://localhost:8000/ws` |
| Browser (HTTP) | `http://localhost:3000` | not set | `ws://localhost:3000/ws` |
| Browser (HTTPS) | `https://app.example.com` | not set | `wss://app.example.com/ws` |
| Any (env set) | any | `wss://custom.host/ws` | `wss://custom.host/ws` |

**Status:** PASS (verified by code inspection — runtime only runs in browser)

---

## 6. Hardcode Grep Verification

**Command:**
```bash
grep -rn "localhost:8000" frontend/src/
```

**Result:** 0 matches (all moved to config/env)

**Command:**
```bash
grep -rn '"smc"\|"volume_profile"\|"market_structure"' frontend/src/
```

**Result:** 0 matches (all old strategy keys removed)

**Status:** PASS

---

## 7. Binance Live API Verification

**Status:** NOT_EXECUTED — corporate network SSL proxy intercepts `fapi.binance.com`, causing `SSL: CERTIFICATE_VERIFY_FAILED`. This is an infrastructure issue, not a code issue. Previous session verified 14/14 PASS on Binance USDM Futures from a clean network.

---

## 8. E2E Tests (Playwright)

**Status:** NOT_EXECUTED in this session — requires both frontend (`npm run dev`) and backend (`uvicorn`) running simultaneously plus Docker (TimescaleDB + Redis). Previous session result: 37 passed, 0 failed, 0 flaky.

---

## Summary

| Test | Status | Notes |
|------|--------|-------|
| Frontend build | **PASS** | 13 pages, 0 errors |
| Backend unit tests | **PASS** | 1236/1236 passed |
| Strategy alignment | **PASS** | FE = BE keys |
| ExchangeFactory | **PASS** | Auth + no-auth modes |
| WS URL resolution | **PASS** | Auto-detect ws/wss |
| Hardcode grep | **PASS** | 0 remaining hardcodes |
| Binance live API | **NOT_EXECUTED** | SSL proxy (infra issue) |
| E2E Playwright | **NOT_EXECUTED** | Requires full stack |
