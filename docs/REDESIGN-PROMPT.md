# CryptoQuant Engine — UI Redesign Brief

## Context

CryptoQuant Engine is a **crypto quantitative trading terminal** for Binance USDM Futures. It runs automated trading bots with AI-powered signals, real-time charts, position management, wallet management, backtesting, and system monitoring.

**Tech stack**: Next.js 15 (App Router), TradingView Lightweight Charts, Tailwind CSS, lucide-react icons, WebSocket real-time updates.

**Current design**: Dark theme (#1A1A1A background), cream text (#FAF3E1), orange accent (#FA8112), glass-morphism cards. Functional but looks AI-generated/generic.

**Target**: Redesign to look like a **world-class Web3 CEX** (think Bybit Pro, dYdX, Hyperliquid, or Vertex) — premium, distinctive, professional. NOT generic AI/template aesthetic. Simple but powerful. Every pixel intentional.

---

## Design Requirements

### Overall Vibe
- **Web3 CEX professional** — like Bybit Pro or Hyperliquid interface
- **Dark mode only** — deep blacks, not gray-dark
- **Minimal but information-dense** — traders need data, not decoration
- **NOT generic AI** — no gradient blobs, no generic dashboard templates
- **Simple** — clean lines, purposeful whitespace, clear hierarchy
- **Premium feel** — subtle micro-interactions, refined typography

### Color Direction
- Primary background: Near-black (#0D0D0D or #111111)
- Card/surface: Slightly lighter (#1A1A1A or #161616)
- Accent: Pick ONE distinctive color (not the overused orange — consider electric blue, cyan, emerald, or keep orange but make it more refined)
- Long/profit: Green spectrum
- Short/loss: Red spectrum
- Text: White/light gray hierarchy (100%, 70%, 40%, 20% opacity)
- Borders: Ultra-subtle (2-4% opacity)

### Typography
- Headings: Clean sans-serif (Inter, Geist, or similar)
- Data/numbers: Monospace (JetBrains Mono, Fira Code, or SF Mono)
- Hierarchy through weight + opacity, NOT size bloat

---

## Pages to Redesign (11 total)

### Page 1: Login (`/login`)
**Purpose**: Authentication gate

**Current elements**:
- Centered card on dark background
- Logo (Zap icon + "CryptoQuant Engine")
- Tab toggle: Login / Register
- Username input + Password input (with show/hide toggle)
- Submit button
- Error banner (red)

**Design notes**:
- Keep minimal — logo, form, done
- Consider subtle animated background (particles, grid, or gradient mesh)
- The logo should feel premium, not clipart

---

### Page 2: Dashboard Overview (`/`)
**Purpose**: At-a-glance portfolio overview — first thing trader sees after login

**Current elements**:
- Live price ticker bar (BTC, ETH, BNB, SOL, XRP with prices + 24h change %)
- 5 stat cards: Account Balance, Unrealized P&L, Open Positions, Active Signals, Win Rate
- Active Signals list (grade badge, symbol, direction, entry price, strength %)
- Open Positions list (symbol, direction+leverage, P&L, entry price, quantity)
- Trading Performance section (Total Trades, Total P&L, Win Rate, W/L ratio)

**Design notes**:
- This is the "cockpit" — should feel like a mission control
- Stat cards should have clear visual hierarchy (balance = most prominent)
- P&L coloring (green/red) must be instantly scannable
- Price ticker should feel alive (subtle animation on price changes)
- Consider a mini portfolio allocation chart (donut/pie)

---

### Page 3: Signal Terminal (`/signals`)
**Purpose**: View AI-generated trading signals with filters

**Current elements**:
- 4 stat cards: Total Signals, Executed, Avg Strength, Grade A count
- Filter bar: Direction (All/Long/Short), Grade (All/A/B/C/D), Status (All/Active/Executed/Rejected/Expired), Symbol search
- Signals data table with columns: Symbol, Direction (badge), Grade (badge), Entry, Stop Loss, Strength (progress bar %), Leverage, Status (badge), Time
- Expandable detail panel: Price levels (Entry/SL/TP1-3), Signal details (strength, ML confidence), Strategy scores

**Design notes**:
- Table is the hero — needs to be scannable at a glance
- Grade badges should have clear visual differentiation (A=best, D=worst)
- Strength bars should be visually meaningful
- The filter bar should not feel cluttered
- Detail panel needs clear information architecture

---

### Page 4: Bot Manager (`/bot`)
**Purpose**: Start/stop/configure the trading bot

**Current elements**:
- Bot status card: Status badge (Running/Stopped/Paused), Mode (Paper/Live), Uptime, Balance, Active Strategies count
- Control buttons: Start, Stop, Pause, Resume
- Performance stats: Total P&L, Win Rate, Total Trades, W/L
- Configuration section: Symbol selector (multi-select with search), Timeframe selector (1m-1d), Strategy toggles (6 strategies with checkboxes), Paper/Live mode toggle
- Binance Account Balance display (per-asset breakdown: USDT, USDC, BTC)
- Live Activity Feed (event log)
- Active Strategies sidebar (list with status)

**Design notes**:
- Bot status should be THE most prominent element (is it running or not?)
- Controls should feel like physical buttons (satisfying to click)
- Configuration should be organized but not overwhelming
- Activity feed should feel like a live terminal/log

---

### Page 5: Position Manager (`/positions`)
**Purpose**: View and manage all open positions on Binance

**Current elements**:
- 4 stat cards: Total Unrealized P&L (with %), Open Positions count, Total Margin, Best/Worst P&L
- "BINANCE LIVE" badge + "auto-refresh 15s" indicator
- Unified positions table: Symbol (with BOT badge if bot-managed), Direction, Entry, Mark Price, Qty, Leverage, Unrealized P&L, Margin, Liq. Price, Stop Loss, Take Profits (TP1/TP2/TP3 badges)
- Symbol search
- Expandable detail panel with SL/TP editor + Close Position button

**Design notes**:
- P&L is king here — needs to pop visually
- Liquidation price should feel "dangerous" (subtle warning indicator)
- BOT badge should clearly distinguish bot-managed vs manual positions
- The SL/TP editor in detail panel should feel intuitive
- Row hover should highlight meaningfully

---

### Page 6: Wallet (`/wallet`)
**Purpose**: View all assets across wallets, transfer between wallets

**Current elements**:
- 4 stat cards: Total Portfolio Value, Free Balance, In Positions, Asset count
- Asset Balances table: Currency, Total, Free, Used, Futures balance, Spot balance, Funding balance
- Internal Transfer form: From Wallet dropdown, To Wallet dropdown, Currency dropdown, Amount input + Max button, Transfer button
- Demo mode warning banner (amber)
- Transfer History table: Time, From, To, Currency, Amount, Status

**Design notes**:
- Think Binance/Bybit wallet page but cleaner
- The transfer form should feel like a flow (step 1 → step 2 → confirm)
- Asset table should show allocation % or mini bar for each asset
- Stablecoins vs crypto should be visually grouped or distinguished

---

### Page 7: Analytics (`/analytics`)
**Purpose**: Trading performance analytics and signal history

**Current elements**:
- Performance stat cards: Total Trades, Win Rate, Total P&L, W/L ratio
- Win/Loss distribution bar (horizontal stacked bar — green wins, red losses)
- Trade/Signal history table: Symbol, Direction, Grade, Entry, Strength, Status, P&L, Time

**Design notes**:
- This page needs proper data visualization — not just numbers
- Consider: equity curve chart, monthly P&L heatmap, strategy performance comparison
- The win/loss bar is a good start but could be more sophisticated
- History table should clearly show profitable vs unprofitable trades

---

### Page 8: Chart (`/chart`)
**Purpose**: TradingView-style chart with technical indicators + manual trading

**Current elements**:
- Symbol selector (dropdown with search, 545 pairs)
- Timeframe selector (1m to 1M, 14 options)
- Indicator panel (16 indicators with color/period customization)
- Price display: Current price, 24h change %, Bid/Ask/Spread
- Candle countdown timer ("Next 05:32")
- Main TradingView Lightweight Chart (candlesticks + volume)
- Sub-panels: RSI, MACD, Stochastic (below main chart)
- Right sidebar tabs: [Order Book] / [Trade]
  - Order Book: 20-level bid/ask with size
  - Trade Panel: LONG/SHORT toggle, Order type (Market/Limit/Stop Market/Stop Limit), Quantity, Leverage buttons (dynamic max from API), SL/TP checkboxes, Calculated fields (margin, liq price, risk, R:R), Place Order button
- Position lines overlay on chart (entry, SL, TP levels)
- Bottom status bar: Source, Symbol, Timeframe, Price, Markets count, Indicators count

**Design notes**:
- This is THE most important page for a trader
- Chart area must be maximized — controls compact
- The right sidebar (orderbook + trade) should feel integrated, not bolted on
- Trade form should feel like Bybit's order panel — clean, efficient
- Leverage selector should feel premium (not just plain buttons)
- Consider chart toolbar (drawing tools, zoom controls) even if non-functional initially

---

### Page 9: Backtest Lab (`/backtest`)
**Purpose**: Test strategies on historical data

**Current elements**:
- Configuration form: Symbol, Timeframe, Date range, Strategy, Initial Capital, Leverage
- Run Backtest button (with progress indicator)
- Results section: Summary stats (Total Trades, P&L, Win Rate, Drawdown, Sharpe, Sortino, Profit Factor)
- Equity Curve (SVG line chart with area fill)
- Win/Loss distribution bar
- Trade history table (entry/exit/P&L per trade)
- Backtest history (past runs)

**Design notes**:
- The equity curve is the hero visualization
- Results should feel like a professional report
- Configuration form should be clean (not wall of inputs)
- Consider tabs: Configure | Results | History

---

### Page 10: Settings (`/settings`)
**Purpose**: Configure exchange, risk management, notifications, signal policy

**Current sections**:
1. Exchange Configuration: API Key/Secret inputs, Testnet toggle, connection status
2. Risk Management: Risk Per Trade %, Max Leverage, Default Leverage, Max Positions, Max Portfolio Heat, Max Daily Loss, Max Drawdown
3. Notifications: Telegram toggle + token/chat ID, Discord toggle + webhook URL
4. Signal Execution Policy: Preset buttons (Conservative/Balanced/Aggressive), Strategy x Grade matrix (6x4 grid, each cell cycles: Auto/Alert/Queue/Skip), Max Auto-Executions/Hour

**Design notes**:
- The Signal Policy Matrix is the most interesting UI element — make it shine
- Group settings logically (don't overwhelm)
- Consider card-per-section with collapse/expand
- Input labels should be clear about units (%, $, x)

---

### Page 11: System Status (`/system`)
**Purpose**: Platform health monitoring

**Current elements**:
- Overall system status badge (Online/Degraded/Error)
- Component status cards: Database, Redis, Exchange API, WebSocket, Bot Service — each with status badge + latency
- Ping latency sparkline chart (last 60 measurements)
- Manual refresh button
- RTT and Jitter values

**Design notes**:
- Think Grafana/Datadog but simpler
- Status indicators should be immediately clear (green = good)
- Sparklines should be subtle but informative
- Consider a status timeline or uptime bar

---

## Sidebar Navigation
**Fixed left sidebar (currently 220px)**

Items in order:
1. Overview (Dashboard icon)
2. Signals (Radio/broadcast icon)
3. Bot Manager (Bot/robot icon)
4. Positions (Wallet icon)
5. Wallet (Banknote icon)
6. Analytics (Bar chart icon)
7. Chart (Candlestick icon)
8. Backtest (Flask icon)
9. Settings (Gear icon)
10. System (Activity/pulse icon)

Bottom: System health indicator (pulsing dot + "System Online")

**Design notes**:
- Active state needs clear differentiation
- Icons should be crisp and consistent
- Consider collapsible sidebar (icon-only mode)
- The logo at top should set the premium tone

---

## Top Header Bar
**Fixed top bar across all pages**

Currently shows:
- Current time (HH:MM:SS)
- Bot status badge (RUNNING/STOPPED with icon)
- WebSocket connection status (Connected/Offline)
- Notification bell icon
- "Binance Futures" label with icon

**Design notes**:
- Keep minimal — time + status is enough
- Connection status should be subtle (just a dot) unless disconnected

---

## Key Design Principles

1. **Data density over decoration** — traders want information, not artwork
2. **Green = money/profit, Red = loss/danger** — universal trading colors
3. **Monospace for numbers** — alignment matters for scanning prices
4. **Subtle animations only** — no bouncing, no distracting motion
5. **Consistent spacing** — 4px/8px/16px/24px grid
6. **Accessible contrast** — text must be readable on dark backgrounds
7. **One accent color** — don't rainbow the interface
8. **Responsive but desktop-first** — traders use monitors, not phones
9. **Glass-morphism sparingly** — only where it adds depth, not everywhere
10. **Negative space is design** — let elements breathe

---

## Reference Interfaces (for inspiration, not copying)

- **Bybit Pro**: Clean dark UI, excellent order form, good use of space
- **Hyperliquid**: Minimal, Web3-native, fast-feeling, distinctive
- **dYdX v4**: Modern, clean, great chart integration
- **Vertex Protocol**: Unique design language, good color usage
- **Aevo**: Sleek, professional, distinctive sidebar

---

## Deliverables

Please redesign ALL 11 pages + sidebar + header maintaining:
- All existing functionality (don't remove features)
- All data points (don't hide information)
- The dark theme requirement
- Desktop-first layout (1920x1080 primary viewport)

Focus on:
- Visual hierarchy and information architecture
- Typography scale and consistency
- Color system refinement
- Component library consistency
- Micro-interactions and state transitions
- Making it feel like a $100M product, not a weekend project
