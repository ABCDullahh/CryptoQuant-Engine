// =============================================================================
// CryptoQuant Engine - WebSocket Manager
// =============================================================================
// Manages a single WebSocket connection to the FastAPI backend with:
// - Automatic reconnect with exponential backoff
// - Typed event subscriptions
// - Heartbeat / ping-pong keep-alive
// =============================================================================

// ---------------------------------------------------------------------------
// WebSocket event types
// ---------------------------------------------------------------------------

import type { Signal, Position, BotStatus, OrderBookResponse } from "./api";

export interface PriceUpdate {
  symbol: string;
  price: number;
  change_24h?: number;
  change_24h_percent?: number;
  volume_24h?: number;
  high_24h?: number;
  low_24h?: number;
  timestamp?: string;
  // Candle fields from live bot pipeline
  timeframe?: string;
  time?: string | number;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
}

/** System status data pushed via WebSocket every 2s. */
export interface SystemStatusData {
  overall_status: "ready" | "degraded" | "offline";
  timestamp: string;
  components: Array<{
    name: string;
    status: "ok" | "degraded" | "error";
    latency_ms: number | null;
    message: string;
    details: Record<string, unknown>;
  }>;
  data_freshness: {
    latest_candle_time: string | null;
    latest_signal_time: string | null;
    candle_count: number;
    signal_count: number;
    candle_age_seconds: number | null;
    signal_age_seconds: number | null;
  };
  system_info: {
    uptime_seconds: number;
    python_version: string;
    environment: string;
    trading_enabled: boolean;
    version: string;
    started_at: string | null;
  };
}

/** Real-time order book update pushed via WebSocket. */
export interface OrderBookUpdate {
  symbol: string;
  bids: number[][];
  asks: number[][];
  timestamp: number | null;
}

/** Backtest progress event pushed via WebSocket. */
export interface BacktestProgress {
  job_id: string;
  progress: number;
  status: string;
}

/** Discriminated-union of all possible WS messages from the server. */
export type WsMessage =
  | { type: "signal_new"; data: Signal }
  | { type: "signal_update"; data: Signal }
  | { type: "position_update"; data: Position }
  | { type: "price_update"; data: PriceUpdate }
  | { type: "bot_status"; data: BotStatus }
  | { type: "system_status"; data: SystemStatusData }
  | { type: "orderbook_update"; data: OrderBookUpdate }
  | { type: "backtest_progress"; data: BacktestProgress }
  | { type: "heartbeat"; data: null }
  | { type: "pong"; data: null }
  | { type: "error"; data: { message: string } };

export type WsEventType = WsMessage["type"];

/** Extract the data type for a given event type. */
export type WsDataFor<T extends WsEventType> = Extract<WsMessage, { type: T }>["data"];

export type EventCallback<T extends WsEventType> = (data: WsDataFor<T>) => void;

// We store callbacks keyed by event type. The value is a Set of callbacks.
// Using `unknown` internally because the map holds heterogeneous callback types;
// each public method narrows with generics so callers always get type safety.
type ListenerMap = {
  [K in WsEventType]?: Set<EventCallback<K>>;
};

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

interface WsManagerConfig {
  /** Full WebSocket URL. Defaults to ws://localhost:8001/ws. */
  url: string;
  /** Initial reconnect delay in ms. Defaults to 1 000. */
  reconnectBaseMs: number;
  /** Maximum reconnect delay in ms. Defaults to 30 000. */
  reconnectMaxMs: number;
  /** Heartbeat interval in ms. Defaults to 30 000. */
  heartbeatIntervalMs: number;
  /** Timeout waiting for pong before considering the connection dead. */
  heartbeatTimeoutMs: number;
}

function resolveWsUrl(): string {
  // 1) Explicit env override (set at build time)
  if (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL;
  }
  // 2) Auto-detect from page origin (works for any deployment)
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/ws`;
  }
  // 3) Fallback for SSR / tests
  return "ws://localhost:8001/ws";
}

const DEFAULT_CONFIG: WsManagerConfig = {
  url: "",  // resolved lazily in createSocket() to support SSR
  reconnectBaseMs: 1_000,
  reconnectMaxMs: 30_000,
  heartbeatIntervalMs: 30_000,
  heartbeatTimeoutMs: 10_000,
};

// ---------------------------------------------------------------------------
// WebSocket Manager
// ---------------------------------------------------------------------------

export class WebSocketManager {
  private config: WsManagerConfig;
  private socket: WebSocket | null = null;
  private listeners: ListenerMap = {};
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private heartbeatTimeout: ReturnType<typeof setTimeout> | null = null;
  private intentionallyClosed = false;

  constructor(config?: Partial<WsManagerConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  // -----------------------------------------------------------------------
  // Public API
  // -----------------------------------------------------------------------

  /** Open the WebSocket connection (idempotent). */
  connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return; // already connected or connecting
    }
    this.intentionallyClosed = false;
    this.createSocket();
  }

  /** Gracefully close the connection. Will NOT auto-reconnect. */
  disconnect(): void {
    this.intentionallyClosed = true;
    this.clearTimers();
    if (this.socket) {
      this.socket.close(1000, "Client disconnect");
      this.socket = null;
    }
  }

  /** Whether the underlying WebSocket is currently open. */
  get connected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  /** Subscribe to a specific event type. Returns an unsubscribe function. */
  subscribe<T extends WsEventType>(event: T, callback: EventCallback<T>): () => void {
    if (!this.listeners[event]) {
      // The cast is safe: we are creating a Set for the exact event type.
      (this.listeners as Record<string, Set<EventCallback<T>>>)[event] = new Set();
    }
    const set = this.listeners[event] as Set<EventCallback<T>>;
    set.add(callback);

    return () => {
      this.unsubscribe(event, callback);
    };
  }

  /** Remove a previously registered callback. */
  unsubscribe<T extends WsEventType>(event: T, callback: EventCallback<T>): void {
    const set = this.listeners[event] as Set<EventCallback<T>> | undefined;
    if (set) {
      set.delete(callback);
      if (set.size === 0) {
        delete this.listeners[event];
      }
    }
  }

  /** Send a raw JSON message to the server (e.g. subscribe commands). */
  send(message: Record<string, unknown>): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }

  // -----------------------------------------------------------------------
  // Internal – connection lifecycle
  // -----------------------------------------------------------------------

  private createSocket(): void {
    // Resolve URL lazily so window.location is available (not during SSR)
    let url = this.config.url || resolveWsUrl();
    // Append JWT token for server-side authentication
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (token) {
      const separator = url.includes("?") ? "&" : "?";
      url = `${url}${separator}token=${encodeURIComponent(token)}`;
    }
    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.startHeartbeat();
    };

    this.socket.onmessage = (event: MessageEvent) => {
      this.handleMessage(event);
    };

    this.socket.onclose = () => {
      this.stopHeartbeat();
      if (!this.intentionallyClosed) {
        this.scheduleReconnect();
      }
    };

    this.socket.onerror = () => {
      // The browser will fire onclose after onerror, so reconnect is handled there.
    };
  }

  private handleMessage(event: MessageEvent): void {
    let msg: WsMessage;
    try {
      msg = JSON.parse(event.data as string) as WsMessage;
    } catch {
      return; // ignore non-JSON frames
    }

    // Reset heartbeat timeout on any message
    this.resetHeartbeatTimeout();

    // Dispatch to listeners
    const set = this.listeners[msg.type];
    if (set) {
      // Each callback is typed to the correct event via subscribe()
      for (const cb of set) {
        try {
          // The cast is necessary because the map stores heterogeneous callbacks.
          (cb as (data: unknown) => void)(msg.data);
        } catch (err) {
          console.error(`[WS] Error in ${msg.type} listener:`, err);
        }
      }
    }
  }

  // -----------------------------------------------------------------------
  // Internal – reconnect
  // -----------------------------------------------------------------------

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;

    const delay = Math.min(
      this.config.reconnectBaseMs * Math.pow(2, this.reconnectAttempt),
      this.config.reconnectMaxMs,
    );

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectAttempt++;
      this.createSocket();
    }, delay);
  }

  // -----------------------------------------------------------------------
  // Internal – heartbeat
  // -----------------------------------------------------------------------

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: "ping" }));
        this.startHeartbeatTimeout();
      }
    }, this.config.heartbeatIntervalMs);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    this.clearHeartbeatTimeout();
  }

  private startHeartbeatTimeout(): void {
    this.clearHeartbeatTimeout();
    this.heartbeatTimeout = setTimeout(() => {
      // No pong received – consider connection dead and force reconnect
      this.socket?.close();
    }, this.config.heartbeatTimeoutMs);
  }

  private clearHeartbeatTimeout(): void {
    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }

  private resetHeartbeatTimeout(): void {
    // Any message from the server proves liveness
    this.clearHeartbeatTimeout();
  }

  // -----------------------------------------------------------------------
  // Internal – cleanup
  // -----------------------------------------------------------------------

  private clearTimers(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.stopHeartbeat();
  }
}

// ---------------------------------------------------------------------------
// Singleton export
// ---------------------------------------------------------------------------

export const wsManager = new WebSocketManager();
