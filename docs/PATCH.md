# Frontend Audit — Patch Summary (PR-Style Diffs)

## Files Changed: 6
## Files Created: 2

---

### 1. `frontend/next.config.ts` — Environment-driven API URL

**Before:**
```typescript
destination: "http://localhost:8000/api/:path*",
// ...
destination: "http://localhost:8000/health",
```

**After:**
```typescript
const API_URL = process.env.API_URL || "http://localhost:8000";
// ...
destination: `${API_URL}/api/:path*`,
destination: `${API_URL}/health`,
```

**Why:** Hardcoded localhost breaks staging/production deployments.

---

### 2. `frontend/src/lib/websocket.ts` — Auto-detect WS protocol + lazy URL resolution

**Before:**
```typescript
const DEFAULT_CONFIG: WsManagerConfig = {
  url: "ws://localhost:8000/ws",
```

**After:**
```typescript
function resolveWsUrl(): string {
  if (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL;
  }
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/ws`;
  }
  return "ws://localhost:8000/ws";
}

const DEFAULT_CONFIG: WsManagerConfig = {
  url: "",  // resolved lazily in createSocket()
```

Plus in `createSocket()`:
```typescript
const url = this.config.url || resolveWsUrl();
this.socket = new WebSocket(url);
```

**Why:** (1) Hardcoded ws:// breaks on HTTPS. (2) Module-level resolution during SSR misses `window`. Lazy resolution at connect-time ensures correct URL.

---

### 3. `frontend/src/lib/api.ts` — Request timeout via AbortController

**Before:**
```typescript
const response = await fetch(url, { ...options, headers });
```

**After:**
```typescript
const API_TIMEOUT_MS = 30_000;

const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

let response: Response;
try {
  response = await fetch(url, { ...options, headers, signal: controller.signal });
} catch (err) {
  clearTimeout(timeoutId);
  if (err instanceof DOMException && err.name === "AbortError") {
    throw new ApiRequestError(0, `Request timed out after ${API_TIMEOUT_MS / 1000}s`);
  }
  throw err;
} finally {
  clearTimeout(timeoutId);
}
```

**Why:** No timeout meant hung requests could block the UI indefinitely.

---

### 4. `frontend/src/app/page.tsx` — Dynamic ticker symbols from API

**Before:**
```typescript
const TICKER_SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"];
// ...
{TICKER_SYMBOLS.map((sym) => { ... })}
```

**After:**
```typescript
const FALLBACK_TICKER_SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"];
// ...
const [tickerSymbols, setTickerSymbols] = useState<string[]>(FALLBACK_TICKER_SYMBOLS);
// On mount: fetch top 5 USDT pairs from /api/markets
fetchMarkets().then((res) => { ... setTickerSymbols(top) ... });
// ...
{tickerSymbols.map((sym) => { ... })}
```

**Why:** Ticker should show actual top symbols from exchange, not hardcoded 5.

---

### 5. `frontend/src/app/bot/page.tsx` — Strategy name alignment + dynamic Top 20

**Before (strategy keys):**
```typescript
const AVAILABLE_STRATEGIES = [
  { key: "smc", label: "Smart Money Concepts (SMC)" },
  { key: "volume_profile", label: "Volume Profile" },
  { key: "market_structure", label: "Market Structure" },
  { key: "momentum", label: "Momentum" },
  { key: "funding", label: "Funding Rate" },
];
```

**After:**
```typescript
const AVAILABLE_STRATEGIES = [
  { key: "momentum", label: "Momentum" },
  { key: "mean_reversion", label: "Mean Reversion" },
  { key: "smart_money", label: "Smart Money Concepts" },
  { key: "volume_analysis", label: "Volume Analysis" },
  { key: "funding_arb", label: "Funding Arbitrage" },
];
```

**Before (Top 20):**
```typescript
.filter((s) => ["BTC/USDT", "ETH/USDT", ... 20 hardcoded ...].includes(s))
```

**After:**
```typescript
marketSymbols.slice(0, 20)
```

**Why:** (1) Strategy keys `smc`, `volume_profile`, `market_structure` don't exist in backend `STRATEGY_REGISTRY`. Bot would silently ignore them. (2) "Top 20" now uses first 20 from API-sorted list instead of hardcoded.

---

### 6. `frontend/src/app/bot/page.tsx` — Default strategy toggles aligned

**Before:**
```typescript
{ smc: true, volume_profile: true, market_structure: true, momentum: false, funding: false }
```

**After:**
```typescript
{ momentum: true, mean_reversion: true, smart_money: true, volume_analysis: false, funding_arb: false }
```

---

### NEW: `frontend/.env.example` — Environment variable documentation

```env
API_URL=http://localhost:8000
# NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

### NEW: `frontend/.env.local` — Local development defaults

```env
API_URL=http://localhost:8000
```
