// =============================================================================
// CryptoQuant Engine - API Client
// =============================================================================
// Typed fetch wrapper for all backend endpoints.
// Uses relative paths because Next.js rewrites proxy /api/* to localhost:8000.
// =============================================================================

// ---------------------------------------------------------------------------
// Shared / Common types
// ---------------------------------------------------------------------------

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiError {
  detail: string;
  status: number;
}

// ---------------------------------------------------------------------------
// Metadata (single source of truth for strategies, timeframes, config)
// ---------------------------------------------------------------------------

export interface StrategyDef {
  id: string;
  label: string;
}

export interface TimeframeDef {
  value: string;
  label: string;
}

export interface TpDefault {
  rr_ratio: number;
  close_pct: number;
}

export interface PlatformMetadata {
  strategies: StrategyDef[];
  timeframes: TimeframeDef[];
  risk_defaults: RiskSettings;
  tp_defaults: {
    tp1: TpDefault;
    tp2: TpDefault;
    tp3: TpDefault;
  };
  entry_zone_pct: number;
  version: string;
  environment: string;
  trading_enabled: boolean;
}

export function fetchMetadata(): Promise<PlatformMetadata> {
  return apiFetch<PlatformMetadata>("/api/metadata");
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds: number;
}

// ---------------------------------------------------------------------------
// Signal types
// ---------------------------------------------------------------------------

export type SignalDirection = "LONG" | "SHORT";
export type SignalStatus = "ACTIVE" | "EXECUTING" | "EXECUTED" | "EXPIRED" | "REJECTED";
export type SignalGrade = "A" | "B" | "C" | "D";

export interface Signal {
  id: string;
  created_at: string | null;
  symbol: string;
  direction: SignalDirection;
  signal_grade: SignalGrade;
  signal_strength: number | null;
  entry_price: number | null;
  stop_loss: number | null;
  sl_type: string | null;
  tp1_price: number | null;
  tp2_price: number | null;
  tp3_price: number | null;
  leverage: number;
  strategy_scores: Record<string, unknown>;
  market_context: Record<string, unknown> | null;
  ml_confidence: number | null;
  status: SignalStatus;
  outcome: string | null;
}

export interface SignalFilterParams {
  status?: SignalStatus;
  direction?: SignalDirection;
  symbol?: string;
  grade?: SignalGrade;
}

// ---------------------------------------------------------------------------
// Order types
// ---------------------------------------------------------------------------

export type OrderSide = "BUY" | "SELL";
export type OrderType = "MARKET" | "LIMIT" | "STOP_MARKET" | "STOP_LIMIT";
export type OrderStatus =
  | "PENDING"
  | "SUBMITTED"
  | "NEW"
  | "PARTIALLY_FILLED"
  | "FILLED"
  | "CANCELLED"
  | "REJECTED"
  | "EXPIRED";

export interface Order {
  id: string;
  signal_id: string | null;
  exchange_order_id: string | null;
  created_at: string | null;
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  price: number | null;
  quantity: number | null;
  filled_qty: number;
  avg_fill_price: number | null;
  status: OrderStatus;
  fees: number;
}

export interface ExecuteOrderRequest {
  signal_id: string;
  mode?: string;
  entry_price?: number;
  stop_loss?: number;
  position_size?: number;
  leverage?: number;
  order_type?: string;
}

export interface ExecuteOrderResponse {
  order_id: string;
  signal_id: string;
  symbol: string;
  side: string;
  order_type: string;
  price: number | null;
  quantity: number;
  status: string;
}

// ---------------------------------------------------------------------------
// Position types
// ---------------------------------------------------------------------------

export type PositionStatus = "OPEN" | "MONITORING" | "REDUCING" | "CLOSED";

export interface Position {
  id: string;
  signal_id: string | null;
  opened_at: string | null;
  closed_at: string | null;
  symbol: string;
  direction: SignalDirection;
  entry_price: number | null;
  current_price: number | null;
  quantity: number | null;
  remaining_qty: number | null;
  leverage: number;
  stop_loss: number | null;
  tp1_price: number | null;
  tp2_price: number | null;
  tp3_price: number | null;
  unrealized_pnl: number;
  realized_pnl: number;
  total_fees: number;
  status: PositionStatus;
  close_reason: string | null;
  trading_mode: "paper" | "live";
  exchange_order_id: string | null;
  strategy_name: string | null;
}

export type TradingMode = "paper" | "live";

export interface PositionFilterParams {
  status?: string;
  symbol?: string;
  mode?: TradingMode;
}

export interface UpdateStopLossRequest {
  new_sl: number;
}

export interface UpdateTakeProfitRequest {
  take_profits: Array<{ level: string; price: number }>;
}

export interface ClosePositionResponse {
  position_id: string;
  status: string;
  close_reason: string | null;
  close_pct: number;
  closed_qty: number;
  realized_pnl: number;
  remaining_qty: number;
}

// ---------------------------------------------------------------------------
// Bot types
// ---------------------------------------------------------------------------

export type BotStatusValue = "STOPPED" | "STARTING" | "RUNNING" | "PAUSED" | "STOPPING";

export interface BotStatus {
  status: BotStatusValue;
  paper_mode: boolean;
  active_strategies: string[];
  started_at: string | null;
  total_pnl: number;
  current_balance: number | null;
  current_equity: number | null;
  paper_initial_balance: number | null;
  paper_saved_balance: number | null;
}

export interface BotPerformance {
  total_trades: number;
  total_pnl: number;
  win_rate: number;
  wins: number;
  losses: number;
}

export interface UpdatePaperModeRequest {
  paper_mode: boolean;
}

export interface UpdateStrategiesRequest {
  strategies: Record<string, boolean>;
}

// ---------------------------------------------------------------------------
// Backtest types
// ---------------------------------------------------------------------------

export interface RunBacktestRequest {
  strategy_name: string;
  symbol?: string;
  timeframe?: string;
  start_date: string;
  end_date: string;
  initial_capital?: number;
  slippage_bps?: number;
  taker_fee?: number;
  parameters?: Record<string, unknown>;
}

export interface BacktestJobResponse {
  job_id: string;
  status: string;
  progress: number;
}

export interface BacktestTrade {
  id: string;
  symbol?: string;
  direction: string;
  strategy?: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  fees: number;
  close_reason: string;
  holding_periods: number;
}

export interface EquityCurvePoint {
  index: number;
  equity: number;
}

export interface BacktestResult {
  id: string;
  created_at: string | null;
  strategy_name: string;
  symbol: string;
  timeframe: string;
  start_date: string | null;
  end_date: string | null;
  initial_capital: number | null;
  final_capital: number | null;
  total_return: number | null;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  win_rate: number | null;
  total_trades: number | null;
  parameters: Record<string, unknown> | null;
  // Enhanced fields
  sortino_ratio: number | null;
  profit_factor: number | null;
  expectancy: number | null;
  annual_return: number | null;
  avg_holding_period: string | null;
  equity_curve: EquityCurvePoint[] | null;
  trades: BacktestTrade[] | null;
  trade_list: BacktestTrade[] | null;
  monthly_returns: Record<string, number> | null;
  metrics: Record<string, number | null> | null;
  verification: { valid: boolean; trade_pnl_sum: number; equity_delta: number; difference: number } | null;
  status: string | null;
  error_message: string | null;
  // These may come from the detail endpoint
  job_status?: string;
  progress?: number;
}

export interface BacktestHistoryEntry {
  id: string;
  created_at: string | null;
  strategy_name: string;
  symbol: string;
  timeframe: string;
  start_date: string | null;
  end_date: string | null;
  initial_capital: number | null;
  final_capital: number | null;
  total_return: number | null;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  win_rate: number | null;
  total_trades: number | null;
  parameters: Record<string, unknown> | null;
}

export interface RunOptimizationRequest {
  strategy_name: string;
  symbol?: string;
  timeframe?: string;
  start_date: string;
  end_date: string;
  initial_capital?: number;
  param_ranges: Record<string, Record<string, unknown>>;
  optimization_metric?: string;
  max_trials?: number;
}

export interface RunWalkForwardRequest {
  strategy_name: string;
  symbol?: string;
  timeframe?: string;
  start_date: string;
  end_date: string;
  initial_capital?: number;
  in_sample_size?: number;
  oos_size?: number;
}

// ---------------------------------------------------------------------------
// Settings types
// ---------------------------------------------------------------------------

export interface Settings {
  exchange: ExchangeSettings;
  risk_params: RiskSettings;
  strategy_config: Record<string, unknown>;
  notification_config: NotificationSettings;
}

export interface ExchangeSettings {
  api_key_masked: string | null;
  configured: boolean;
  source?: "database" | "env" | null;
  testnet?: boolean | null;
}

export interface UpdateExchangeKeysRequest {
  api_key: string;
  api_secret: string;
  testnet?: boolean;
}

export interface RiskSettings {
  default_risk_pct?: number;
  max_leverage?: number;
  default_leverage?: number;
  max_positions?: number;
  max_portfolio_heat?: number;
  max_daily_loss?: number;
  max_drawdown?: number;
  auto_kill_switch?: boolean;
  strict_sizing?: boolean;
  dca_config?: DCAConfig;
}

export interface DCAConfig {
  enabled: boolean;
  max_dca_orders: number;
  trigger_drop_pct: number[];
  qty_multiplier: number[];
  max_total_risk_pct: number;
  sl_recalc_mode: "fixed" | "follow";
  tp_recalc_mode: "fixed" | "recalculate";
}

export interface NotificationSettings {
  telegram_enabled?: boolean;
  telegram_bot_token?: string;
  telegram_chat_id?: string;
  discord_enabled?: boolean;
  discord_webhook_url?: string;
}

// ---------------------------------------------------------------------------
// Base fetch helper
// ---------------------------------------------------------------------------

class ApiRequestError extends Error {
  public status: number;
  public detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

const API_TIMEOUT_MS = 30_000;

async function apiFetch<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  // Request timeout via AbortController
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiRequestError(0, `Request timed out after ${API_TIMEOUT_MS / 1000}s`);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    // Auto-redirect to login on 401 (expired/invalid token)
    if (response.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("token");
      document.cookie = "token=; path=/; max-age=0";
      window.location.href = "/login";
      throw new ApiRequestError(401, "Session expired, redirecting to login");
    }

    let detail = `Request failed with status ${response.status}`;
    try {
      const errorBody: ApiError = await response.json();
      detail = errorBody.detail ?? detail;
    } catch {
      // response body was not JSON -- use default message
    }
    throw new ApiRequestError(response.status, detail);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Query-string builder
// ---------------------------------------------------------------------------

function buildQuery(params: Record<string, string | undefined>): string {
  const filtered = Object.entries(params).filter(
    (entry): entry is [string, string] => entry[1] !== undefined && entry[1] !== "",
  );
  if (filtered.length === 0) return "";
  return "?" + new URLSearchParams(filtered).toString();
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}

// ---------------------------------------------------------------------------
// System Status (real-time dashboard)
// ---------------------------------------------------------------------------

export interface ComponentStatusDetail {
  name: string;
  status: "ok" | "degraded" | "error";
  latency_ms: number | null;
  message: string;
  details: Record<string, unknown>;
}

export interface DataFreshness {
  latest_candle_time: string | null;
  latest_signal_time: string | null;
  candle_count: number;
  signal_count: number;
  candle_age_seconds: number | null;
  signal_age_seconds: number | null;
}

export interface SystemInfo {
  uptime_seconds: number;
  python_version: string;
  environment: string;
  trading_enabled: boolean;
  version: string;
  started_at: string | null;
}

export interface SystemStatusResponse {
  overall_status: "ready" | "degraded" | "offline";
  timestamp: string;
  components: ComponentStatusDetail[];
  data_freshness: DataFreshness;
  system_info: SystemInfo;
}

export interface PingResponse {
  timestamp: number;
  server_time: string;
}

export function fetchSystemStatus(): Promise<SystemStatusResponse> {
  return apiFetch<SystemStatusResponse>("/api/system/status");
}

export function fetchPing(): Promise<PingResponse> {
  return apiFetch<PingResponse>("/api/system/ping");
}

// ---------------------------------------------------------------------------
// Markets
// ---------------------------------------------------------------------------

export interface MarketInfo {
  symbol: string;
  base: string;
  quote: string;
  exchange_symbol?: string;
  active: boolean;
  price_precision?: number;
  amount_precision?: number;
  min_notional?: number;
  contract_size?: number;
}

export interface MarketsResponse {
  markets: MarketInfo[];
  cached: boolean;
  count: number;
}

export function fetchMarkets(): Promise<MarketsResponse> {
  return apiFetch<MarketsResponse>("/api/markets");
}

// ---------------------------------------------------------------------------
// Leverage Tiers
// ---------------------------------------------------------------------------

export interface LeverageTiersResponse {
  symbol: string;
  max_leverage: number;
  tiers: Array<{ min_notional: number; max_notional: number; max_leverage: number }>;
}

export function fetchLeverageTiers(symbol: string = "BTC/USDT"): Promise<LeverageTiersResponse> {
  const query = buildQuery({ symbol });
  return apiFetch<LeverageTiersResponse>(`/api/markets/leverage-tiers${query}`);
}

// ---------------------------------------------------------------------------
// Candles
// ---------------------------------------------------------------------------

export interface CandleData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface CandleResponse {
  candles: CandleData[];
  symbol: string;
  timeframe: string;
}

export function fetchCandles(
  symbol: string = "BTC/USDT",
  timeframe: string = "1h",
  limit: number = 300,
  endTime?: number,
): Promise<CandleResponse> {
  const query = buildQuery({
    symbol,
    timeframe,
    limit: String(limit),
    end_time: endTime != null ? String(endTime) : undefined,
  });
  return apiFetch<CandleResponse>(`/api/candles${query}`);
}

// ---------------------------------------------------------------------------
// Signals
// ---------------------------------------------------------------------------

export async function fetchSignals(params?: SignalFilterParams): Promise<Signal[]> {
  const query = params
    ? buildQuery({
        status: params.status,
        direction: params.direction,
        symbol: params.symbol,
        grade: params.grade,
      })
    : "";
  const response = await apiFetch<PaginatedResponse<Signal>>(`/api/signals${query}`);
  return response.items;
}

export function fetchSignal(id: string): Promise<Signal> {
  return apiFetch<Signal>(`/api/signals/${id}`);
}

export function executeSignal(signalId: string): Promise<{ success: boolean; message: string; position_id?: string }> {
  return apiFetch<{ success: boolean; message: string; position_id?: string }>(`/api/signals/${signalId}/execute`, {
    method: "POST",
  });
}

export async function fetchSignalHistory(): Promise<Signal[]> {
  const response = await apiFetch<PaginatedResponse<Signal>>("/api/signals/history");
  return response.items;
}

// ---------------------------------------------------------------------------
// Orders
// ---------------------------------------------------------------------------

export async function fetchOrders(): Promise<Order[]> {
  const response = await apiFetch<PaginatedResponse<Order>>("/api/orders");
  return response.items;
}

export function fetchOrder(id: string): Promise<Order> {
  return apiFetch<Order>(`/api/orders/${id}`);
}

export function executeOrder(data: ExecuteOrderRequest): Promise<ExecuteOrderResponse> {
  return apiFetch<ExecuteOrderResponse>("/api/orders/execute", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function cancelOrder(id: string): Promise<{ order_id: string; status: string }> {
  return apiFetch<{ order_id: string; status: string }>(`/api/orders/${id}/cancel`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Positions
// ---------------------------------------------------------------------------

export async function fetchPositions(params?: PositionFilterParams): Promise<Position[]> {
  const query = params
    ? buildQuery({
        status: params.status,
        symbol: params.symbol,
        mode: params.mode,
      })
    : "";
  const response = await apiFetch<PaginatedResponse<Position>>(`/api/positions${query}`);
  return response.items;
}

export function fetchPosition(id: string): Promise<Position> {
  return apiFetch<Position>(`/api/positions/${id}`);
}

export function closePosition(id: string): Promise<ClosePositionResponse> {
  return apiFetch<ClosePositionResponse>(`/api/positions/${id}/close`, {
    method: "POST",
  });
}

export function updateStopLoss(id: string, newSl: number): Promise<{ position_id: string; stop_loss: number }> {
  const body: UpdateStopLossRequest = { new_sl: newSl };
  return apiFetch<{ position_id: string; stop_loss: number }>(`/api/positions/${id}/sl`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function updateTakeProfit(
  id: string,
  tps: Array<{ level: string; price: number }>,
): Promise<{ position_id: string; tp1_price: number | null; tp2_price: number | null; tp3_price: number | null }> {
  const body: UpdateTakeProfitRequest = { take_profits: tps };
  return apiFetch<{ position_id: string; tp1_price: number | null; tp2_price: number | null; tp3_price: number | null }>(
    `/api/positions/${id}/tp`,
    {
      method: "PUT",
      body: JSON.stringify(body),
    },
  );
}

// ---------------------------------------------------------------------------
// Bot
// ---------------------------------------------------------------------------

export function fetchBotStatus(): Promise<BotStatus> {
  return apiFetch<BotStatus>("/api/bot/status");
}

export interface BotStartConfig {
  symbols?: string[];
  timeframes?: string[];
  strategies?: string[];
  initial_balance?: number;
  is_paper?: boolean;
}

export function startBot(config?: BotStartConfig): Promise<{ status: string; started_at: string }> {
  return apiFetch<{ status: string; started_at: string }>("/api/bot/start", {
    method: "POST",
    body: config ? JSON.stringify(config) : undefined,
  });
}

export function pauseBot(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/api/bot/pause", { method: "POST" });
}

export function stopBot(): Promise<{ status: string; stopped_at: string }> {
  return apiFetch<{ status: string; stopped_at: string }>("/api/bot/stop", { method: "POST" });
}

export function updatePaperMode(mode: boolean): Promise<{ paper_mode: boolean }> {
  const body: UpdatePaperModeRequest = { paper_mode: mode };
  return apiFetch<{ paper_mode: boolean }>("/api/bot/paper-mode", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function updateStrategies(strategies: Record<string, boolean>): Promise<{ active_strategies: string[] }> {
  const body: UpdateStrategiesRequest = { strategies };
  return apiFetch<{ active_strategies: string[] }>("/api/bot/strategies", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function fetchBotPerformance(): Promise<BotPerformance> {
  return apiFetch<BotPerformance>("/api/bot/performance");
}

// ---------------------------------------------------------------------------
// Backtest
// ---------------------------------------------------------------------------

export function runBacktest(data: RunBacktestRequest): Promise<BacktestJobResponse> {
  return apiFetch<BacktestJobResponse>("/api/backtest/run", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function fetchBacktestHistory(): Promise<BacktestHistoryEntry[]> {
  const response = await apiFetch<PaginatedResponse<BacktestHistoryEntry>>("/api/backtest/history");
  return response.items;
}

export function fetchBacktest(id: string): Promise<BacktestResult> {
  return apiFetch<BacktestResult>(`/api/backtest/${id}`);
}

export function runOptimization(data: RunOptimizationRequest): Promise<BacktestJobResponse> {
  return apiFetch<BacktestJobResponse>("/api/backtest/optimize", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function runWalkForward(data: RunWalkForwardRequest): Promise<BacktestJobResponse> {
  return apiFetch<BacktestJobResponse>("/api/backtest/walkforward", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export function fetchSettings(): Promise<Settings> {
  return apiFetch<Settings>("/api/settings");
}

export function updateExchangeKeys(data: UpdateExchangeKeysRequest): Promise<{ status: string; testnet: boolean }> {
  return apiFetch<{ status: string; testnet: boolean }>("/api/settings/exchange", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function updateRiskParams(data: RiskSettings): Promise<{ risk_params: RiskSettings }> {
  return apiFetch<{ risk_params: RiskSettings }>("/api/settings/risk", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function updateNotifications(data: NotificationSettings): Promise<{ notification_config: NotificationSettings }> {
  return apiFetch<{ notification_config: NotificationSettings }>("/api/settings/notifications", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function fetchDCAConfig(): Promise<{ dca_config: DCAConfig }> {
  return apiFetch<{ dca_config: DCAConfig }>("/api/settings/dca");
}

export function updateDCAConfig(data: Partial<DCAConfig>): Promise<{ dca_config: DCAConfig }> {
  return apiFetch<{ dca_config: DCAConfig }>("/api/settings/dca", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Signal Execution Policy
// ---------------------------------------------------------------------------

export interface SignalPolicy {
  preset: string;
  matrix: Record<string, Record<string, string>>;
  max_auto_per_hour: number;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
}

export function fetchSignalPolicy(): Promise<{ signal_policy: SignalPolicy }> {
  return apiFetch<{ signal_policy: SignalPolicy }>("/api/settings/signal-policy");
}

export function updateSignalPolicy(policy: SignalPolicy): Promise<{ signal_policy: SignalPolicy }> {
  return apiFetch<{ signal_policy: SignalPolicy }>("/api/settings/signal-policy", {
    method: "PUT",
    body: JSON.stringify(policy),
  });
}

export function applySignalPolicyPreset(preset: string): Promise<{ signal_policy: SignalPolicy }> {
  return apiFetch<{ signal_policy: SignalPolicy }>("/api/settings/signal-policy/preset", {
    method: "POST",
    body: JSON.stringify({ preset }),
  });
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface AuthResponse {
  access_token: string;
  expires_in: number;
}

export async function loginUser(username: string, password: string): Promise<AuthResponse> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    let detail = "Login failed";
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch { /* ignore */ }
    throw new ApiRequestError(res.status, detail);
  }
  return res.json();
}

export async function registerUser(username: string, password: string): Promise<AuthResponse> {
  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    let detail = "Registration failed";
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch { /* ignore */ }
    throw new ApiRequestError(res.status, detail);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Indicators
// ---------------------------------------------------------------------------

export interface IndicatorDataPoint {
  time: number;
  close: number;
  [key: string]: number | null;
}

export interface IndicatorResponse {
  symbol: string;
  timeframe: string;
  indicators: string[];
  data: IndicatorDataPoint[];
  source: string;
  count: number;
}

export function fetchIndicators(
  symbol: string = "BTC/USDT",
  timeframe: string = "1h",
  limit: number = 300,
  indicators: string = "ema_9,rsi_14,macd,bb",
): Promise<IndicatorResponse> {
  const query = buildQuery({
    symbol,
    timeframe,
    limit: String(limit),
    indicators,
  });
  return apiFetch<IndicatorResponse>(`/api/indicators${query}`);
}

// ---------------------------------------------------------------------------
// Order Book
// ---------------------------------------------------------------------------

export interface OrderBookEntry {
  /** [price, quantity] */
  0: number;
  1: number;
}

export interface OrderBookResponse {
  symbol: string;
  bids: number[][];
  asks: number[][];
  timestamp: number | null;
}

export function fetchOrderBook(
  symbol: string = "BTC/USDT",
  limit: number = 20,
): Promise<OrderBookResponse> {
  const query = buildQuery({
    symbol,
    limit: String(limit),
  });
  return apiFetch<OrderBookResponse>(`/api/markets/orderbook${query}`);
}

// ---------------------------------------------------------------------------
// Exchange Positions (Real Binance)
// ---------------------------------------------------------------------------

export interface ExchangePosition {
  symbol: string;
  direction: string;
  entry_price: number;
  current_price: number;
  quantity: number;
  leverage: number;
  unrealized_pnl: number;
  margin: number;
  liquidation_price: number;
  notional: number;
}

export interface ExchangePositionsResponse {
  positions: ExchangePosition[];
  count: number;
  source: string;
}

export function fetchExchangePositions(): Promise<ExchangePositionsResponse> {
  return apiFetch<ExchangePositionsResponse>('/api/positions/exchange-positions');
}

// ---------------------------------------------------------------------------
// Account Balance (Real Binance)
// ---------------------------------------------------------------------------

export interface AssetBalance {
  currency: string;
  total: number;
  free: number;
  used: number;
}

export interface BalanceResponse {
  total: number;
  free: number;
  used: number;
  currency: string;
  assets: AssetBalance[];
  total_usd_value: number;
  source: string;
}

export function fetchBalance(): Promise<BalanceResponse> {
  return apiFetch<BalanceResponse>('/api/markets/balance');
}

// ---------------------------------------------------------------------------
// Wallet
// ---------------------------------------------------------------------------

export interface WalletAsset {
  currency: string;
  total: number;
  free: number;
  used: number;
  wallets: Record<string, { total: number; free: number; used: number }>;
}

export interface WalletBalancesResponse {
  assets: WalletAsset[];
  total_usd_value: number;
  wallet_count: number;
}

export interface TransferRequest {
  from_wallet: string;
  to_wallet: string;
  currency: string;
  amount: number;
}

export interface TransferResponse {
  id: string;
  from_wallet: string;
  to_wallet: string;
  currency: string;
  amount: number;
  status: string;
  timestamp: string;
}

export interface TransferHistoryEntry {
  id: string;
  from: string;
  to: string;
  currency: string;
  amount: number;
  status: string;
  timestamp: string;
}

export interface TransferHistoryResponse {
  transfers: TransferHistoryEntry[];
  count: number;
  note?: string;
}

export function fetchWalletBalances(): Promise<WalletBalancesResponse> {
  return apiFetch<WalletBalancesResponse>('/api/wallet/balances');
}

export function transferFunds(data: TransferRequest): Promise<TransferResponse> {
  return apiFetch<TransferResponse>('/api/wallet/transfer', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function fetchTransferHistory(limit: number = 50): Promise<TransferHistoryResponse> {
  const query = buildQuery({ limit: String(limit) });
  return apiFetch<TransferHistoryResponse>(`/api/wallet/transfers${query}`);
}

// ---------------------------------------------------------------------------
// Manual Trade
// ---------------------------------------------------------------------------

export interface ManualOrderRequest {
  symbol: string;
  direction: "LONG" | "SHORT";
  order_type: "MARKET" | "LIMIT" | "STOP_MARKET" | "STOP_LIMIT";
  quantity: number;
  price?: number | null;
  stop_price?: number | null;
  leverage?: number;
  stop_loss?: number | null;
  take_profit?: number | null;
  reduce_only?: boolean;
  time_in_force?: string;
}

export interface ManualOrderResponse {
  order_id: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  price: number | null;
  stop_price: number | null;
  status: string;
  executed_price: number;
  executed_qty: number;
  leverage: number;
  sl_order_id: string | null;
  tp_order_id: string | null;
  timestamp: string;
}

export function placeManualOrder(data: ManualOrderRequest): Promise<ManualOrderResponse> {
  return apiFetch<ManualOrderResponse>('/api/orders/manual', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Analytics — Real Performance Metrics
// ---------------------------------------------------------------------------

export interface AnalyticsEquityCurvePoint {
  date: string | null;
  balance: number;
  trade_pnl: number;
}

export interface MonthlyReturn {
  month: string;
  pnl: number;
}

export interface LivePerformance {
  has_data: boolean;
  message?: string;
  days: number;
  total_trades: number;
  total_pnl: number;
  total_fees: number;
  win_rate: number;
  wins: number;
  losses: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  expectancy: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  avg_holding_hours: number;
  best_trade: number;
  worst_trade: number;
  equity_curve: AnalyticsEquityCurvePoint[];
  monthly_returns: MonthlyReturn[];
  trade_pnls: number[];
}

export interface AnalyticsBacktestTrade {
  symbol: string;
  direction: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  fees: number;
  strategy: string;
  holding_periods: number;
  close_reason: string;
}

export interface BacktestVerification {
  valid: boolean;
  trade_pnl_sum: number;
  equity_delta: number;
  difference: number;
}

export interface BacktestFullResult {
  id: string;
  strategy: string;
  symbol: string;
  timeframe: string;
  status: string;
  config: Record<string, unknown>;
  net_return?: number;
  win_rate?: number;
  sharpe?: number;
  total_trades?: number;
  created_at: string;
  equity_curve: Array<{ date?: string; equity: number }>;
  trade_list: AnalyticsBacktestTrade[];
  metrics: Record<string, number | null>;
  monthly_returns: Record<string, number>;
  verification: BacktestVerification;
}

export function fetchLivePerformance(days?: number): Promise<LivePerformance> {
  const params = days ? `?days=${days}` : "";
  return apiFetch<LivePerformance>(`/api/analytics/live-performance${params}`);
}

export function fetchBacktestFull(jobId: string): Promise<BacktestFullResult> {
  return apiFetch<BacktestFullResult>(`/api/backtest/${jobId}`);
}

export function fetchBacktestVerification(jobId: string): Promise<BacktestVerification> {
  return apiFetch<BacktestVerification>(`/api/backtest/verify/${jobId}`);
}
