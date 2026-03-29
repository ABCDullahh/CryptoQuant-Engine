"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Bot,
  Play,
  Square,
  Pause,
  RotateCcw,
  Activity,
  Zap,
  Shield,
  ChevronDown,
  Search,
  X,
  Plus,
  Cpu,
  AlertTriangle,
} from "lucide-react";
import { usePolling, useWebSocket } from "@/hooks/useApi";
import {
  fetchBotStatus,
  fetchBotPerformance,
  fetchMarkets,
  fetchMetadata,
  fetchBalance,
  startBot,
  stopBot,
  pauseBot,
  updatePaperMode,
  updateStrategies,
  type BotStatusValue,
  type MarketInfo,
  type PlatformMetadata,
  type BalanceResponse,
} from "@/lib/api";

// =============================================================================
// Constants
// =============================================================================

const FALLBACK_STRATEGIES = [
  { key: "momentum", label: "Momentum" },
  { key: "mean_reversion", label: "Mean Reversion" },
  { key: "smart_money", label: "Smart Money Concepts" },
  { key: "volume_analysis", label: "Volume Analysis" },
  { key: "funding_arb", label: "Funding Arbitrage" },
  { key: "ob_zones", label: "Order Block Zones" },
];

const FALLBACK_SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"];

const FALLBACK_TIMEFRAMES = [
  { value: "1m", label: "1m" },
  { value: "5m", label: "5m" },
  { value: "15m", label: "15m" },
  { value: "1h", label: "1h" },
  { value: "4h", label: "4h" },
];

const STATUS_CONFIG: Record<BotStatusValue, { color: string; bg: string; label: string }> = {
  STOPPED: { color: "#95A5A6", bg: "rgba(149, 165, 166, 0.12)", label: "Stopped" },
  STARTING: { color: "#00F0FF", bg: "rgba(0, 240, 255, 0.12)", label: "Starting..." },
  RUNNING: { color: "#40E56C", bg: "rgba(64, 229, 108, 0.12)", label: "Running" },
  PAUSED: { color: "#FFB4AB", bg: "rgba(255, 180, 171, 0.12)", label: "Paused" },
  STOPPING: { color: "#FFB4AB", bg: "rgba(255, 180, 171, 0.12)", label: "Stopping..." },
};

// =============================================================================
// Toast Component (local)
// =============================================================================

type ToastType = "success" | "error";

interface ToastState {
  message: string;
  type: ToastType;
  visible: boolean;
}

function Toast({ toast }: { toast: ToastState }) {
  if (!toast.visible) return null;

  return (
    <div
      className={`
        fixed top-4 right-4 z-50 px-4 py-3 rounded-sm border font-mono text-xs
        animate-fade-in-up
        ${
          toast.type === "success"
            ? "bg-[#40E56C]/10 border-[#40E56C]/30 text-[#40E56C]"
            : "bg-[#FFB4AB]/10 border-[#FFB4AB]/30 text-[#FFB4AB]"
        }
      `}
    >
      {toast.message}
    </div>
  );
}

// =============================================================================
// Activity Event Type
// =============================================================================

interface ActivityEvent {
  id: number;
  time: string;
  message: string;
  type: "signal" | "order" | "status" | "error";
}

// =============================================================================
// Bot Manager Page
// =============================================================================

export default function BotPage() {
  // -- Toast --
  const [toast, setToast] = useState<ToastState>({
    message: "",
    type: "success",
    visible: false,
  });
  const showToast = useCallback((message: string, type: ToastType) => {
    setToast({ message, type, visible: true });
    setTimeout(() => setToast((prev) => ({ ...prev, visible: false })), 3000);
  }, []);

  // -- Bot status polling (5s fallback, WS provides instant updates) --
  const {
    data: botStatus,
    loading: statusLoading,
    error: statusError,
    refetch: refetchStatus,
  } = usePolling(() => fetchBotStatus(), 5_000, []);

  // -- Performance polling (30s fallback) --
  const { data: performance } = usePolling(() => fetchBotPerformance(), 30_000, []);

  // -- Platform metadata (strategies, timeframes from backend) --
  const [metadata, setMetadata] = useState<PlatformMetadata | null>(null);
  const [metadataError, setMetadataError] = useState<string | null>(null);

  // -- Dynamic market symbols (ALL USDT pairs from Binance) --
  const [marketSymbols, setMarketSymbols] = useState<string[]>(FALLBACK_SYMBOLS);
  useEffect(() => {
    fetchMetadata()
      .then((data) => {
        setMetadata(data);
        setMetadataError(null);
      })
      .catch((err) => {
        console.error(err);
        setMetadataError(err instanceof Error ? err.message : "Failed to load platform metadata");
      });
    fetchMarkets()
      .then((res) => {
        if (res.markets && res.markets.length > 0) {
          const syms = res.markets
            .filter((m: MarketInfo) => m.active && m.quote === "USDT")
            .map((m: MarketInfo) => m.symbol)
            .sort();
          if (syms.length > 0) setMarketSymbols(syms);
        }
      })
      .catch(console.error);
    fetchBalance().then(setLiveBalance).catch(console.error);
  }, []);

  // -- Symbol selector modal state --
  const [symbolModalOpen, setSymbolModalOpen] = useState(false);
  const [symbolSearch, setSymbolSearch] = useState("");
  const [pendingSymbols, setPendingSymbols] = useState<string[]>([]);
  const symbolModalRef = useRef<HTMLDivElement>(null);

  // Click-outside to close symbol modal
  useEffect(() => {
    if (!symbolModalOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (symbolModalRef.current && !symbolModalRef.current.contains(e.target as Node)) {
        setSymbolModalOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [symbolModalOpen]);

  // -- Action loading states --
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // -- Configuration state --
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>(["BTC/USDT"]);
  const [selectedTimeframe, setSelectedTimeframe] = useState("1h");
  const [enabledStrategies, setEnabledStrategies] = useState<Record<string, boolean>>({
    momentum: true,
    mean_reversion: true,
    smart_money: true,
    volume_analysis: false,
    funding_arb: false,
  });
  const [paperMode, setPaperMode] = useState(true);
  const [startingBalance, setStartingBalance] = useState("10000");
  const [liveBalance, setLiveBalance] = useState<BalanceResponse | null>(null);

  // -- Derived: strategies & timeframes from metadata or fallback --
  const availableStrategies: { key: string; label: string }[] = metadata
    ? metadata.strategies.map((s) => ({ key: s.id, label: s.label }))
    : FALLBACK_STRATEGIES;

  const availableTimeframes: { value: string; label: string }[] = metadata
    ? metadata.timeframes
    : FALLBACK_TIMEFRAMES;

  // -- Sync config from server --
  useEffect(() => {
    if (!botStatus) return;
    setPaperMode(botStatus.paper_mode);
    if (botStatus.active_strategies.length > 0) {
      const stratList = metadata
        ? metadata.strategies.map((s) => s.id)
        : FALLBACK_STRATEGIES.map((s) => s.key);
      const serverStrategies: Record<string, boolean> = {};
      for (const key of stratList) {
        serverStrategies[key] = botStatus.active_strategies.includes(key);
      }
      setEnabledStrategies(serverStrategies);
    }
  }, [botStatus, metadata]);

  // -- Activity feed --
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const eventIdRef = useRef(0);

  const addEvent = useCallback((message: string, type: ActivityEvent["type"]) => {
    eventIdRef.current += 1;
    const evt: ActivityEvent = {
      id: eventIdRef.current,
      time: new Date().toLocaleTimeString(),
      message,
      type,
    };
    setEvents((prev) => [evt, ...prev].slice(0, 50));
  }, []);

  // -- WebSocket listeners for live feed --
  const handleBotStatusWs = useCallback(
    (data: { status?: string; data?: { status?: string } }) => {
      const status = data?.data?.status ?? data?.status ?? "unknown";
      addEvent(`Bot status changed to ${status}`, "status");
      refetchStatus();
    },
    [addEvent, refetchStatus]
  );

  const handleSignalNew = useCallback(
    (data: { symbol?: string; direction?: string; data?: { symbol?: string; direction?: string } }) => {
      const inner = data?.data ?? data;
      addEvent(
        `New signal: ${inner?.symbol ?? "?"} ${inner?.direction ?? ""}`,
        "signal"
      );
    },
    [addEvent]
  );

  const handlePositionUpdate = useCallback(
    (data: { symbol?: string; status?: string; data?: { symbol?: string; status?: string } }) => {
      const inner = data?.data ?? data;
      addEvent(
        `Position update: ${inner?.symbol ?? "?"} - ${inner?.status ?? ""}`,
        "order"
      );
    },
    [addEvent]
  );

  useWebSocket("bot_status", handleBotStatusWs);
  useWebSocket("signal_new", handleSignalNew);
  useWebSocket("position_update", handlePositionUpdate);

  // -- Action handlers --
  const handleStart = useCallback(async () => {
    setActionLoading("start");
    try {
      const activeStrats = Object.entries(enabledStrategies)
        .filter(([, v]) => v)
        .map(([k]) => k);
      await startBot({
        symbols: selectedSymbols,
        timeframes: [selectedTimeframe],
        strategies: activeStrats,
        initial_balance: paperMode
          ? (parseFloat(startingBalance) || 10000)
          : (liveBalance?.free || 5000),
        is_paper: paperMode,
      });
      addEvent("Bot started", "status");
      showToast("Bot started successfully", "success");
      refetchStatus();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start bot";
      addEvent(`Start failed: ${msg}`, "error");
      showToast(msg, "error");
    } finally {
      setActionLoading(null);
    }
  }, [addEvent, showToast, refetchStatus, selectedSymbols, selectedTimeframe, enabledStrategies, startingBalance, paperMode, liveBalance]);

  const handleStop = useCallback(async () => {
    setActionLoading("stop");
    try {
      await stopBot();
      addEvent("Bot stopped", "status");
      showToast("Bot stopped", "success");
      refetchStatus();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to stop bot";
      addEvent(`Stop failed: ${msg}`, "error");
      showToast(msg, "error");
    } finally {
      setActionLoading(null);
    }
  }, [addEvent, showToast, refetchStatus]);

  const handlePause = useCallback(async () => {
    setActionLoading("pause");
    try {
      await pauseBot();
      addEvent("Bot paused", "status");
      showToast("Bot paused", "success");
      refetchStatus();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to pause bot";
      addEvent(`Pause failed: ${msg}`, "error");
      showToast(msg, "error");
    } finally {
      setActionLoading(null);
    }
  }, [addEvent, showToast, refetchStatus]);

  const handleTogglePaperMode = useCallback(
    async (newMode: boolean) => {
      try {
        await updatePaperMode(newMode);
        setPaperMode(newMode);
        addEvent(`Switched to ${newMode ? "Paper" : "Live"} mode`, "status");
        showToast(`Switched to ${newMode ? "paper" : "live"} trading`, "success");
        if (!newMode) {
          fetchBalance().then(setLiveBalance).catch(console.error);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to update mode";
        showToast(msg, "error");
      }
    },
    [addEvent, showToast]
  );

  const handleSaveStrategies = useCallback(async () => {
    setActionLoading("strategies");
    try {
      await updateStrategies(enabledStrategies);
      addEvent("Strategies updated", "status");
      showToast("Strategies updated successfully", "success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to update strategies";
      showToast(msg, "error");
    } finally {
      setActionLoading(null);
    }
  }, [enabledStrategies, addEvent, showToast]);

  // -- Derived values --
  const status = botStatus?.status ?? "STOPPED";
  const statusCfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.STOPPED;
  const isRunning = status === "RUNNING";
  const isPaused = status === "PAUSED";
  const isStopped = status === "STOPPED";

  // Uptime
  let uptimeStr = "--";
  if (botStatus?.started_at) {
    const startMs = new Date(botStatus.started_at).getTime();
    const diffMs = Date.now() - startMs;
    if (diffMs > 0) {
      const hours = Math.floor(diffMs / 3_600_000);
      const minutes = Math.floor((diffMs % 3_600_000) / 60_000);
      uptimeStr = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
    }
  }

  // -- Loading state --
  if (statusLoading && !botStatus) {
    return (
      <div className="flex items-center justify-center h-96 bg-[#0D0D0D]">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-[#00F0FF] border-t-transparent rounded-full animate-spin" />
          <span className="font-mono text-sm text-[#B9CACB]">
            Loading bot status...
          </span>
        </div>
      </div>
    );
  }

  // -- Error state --
  if (statusError && !botStatus) {
    return (
      <div className="flex items-center justify-center h-96 bg-[#0D0D0D]">
        <div className="text-center space-y-3">
          <div className="w-12 h-12 rounded-sm bg-[#FFB4AB]/10 flex items-center justify-center mx-auto">
            <Shield size={24} className="text-[#FFB4AB]" />
          </div>
          <p className="font-mono text-sm text-[#FFB4AB]">
            Unable to connect to backend
          </p>
          <p className="text-xs text-[#B9CACB]/50">
            Make sure the backend server is running
          </p>
        </div>
      </div>
    );
  }

  const activeStratCount = botStatus?.active_strategies.length ?? 0;

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-[1600px] mx-auto pb-20 md:pb-6 bg-[#0D0D0D] min-h-screen">
      <Toast toast={toast} />

      {/* ============================================================ */}
      {/* Header */}
      {/* ============================================================ */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="font-mono text-xl font-black text-[#E5E2E1] uppercase tracking-tighter flex items-center gap-3">
            <Bot className="w-6 h-6 text-[#00F0FF]" />
            Bot Manager
          </h2>
          <p className="font-mono text-[10px] text-[#B9CACB] uppercase tracking-widest mt-1">
            Automated Execution Fleet
          </p>
        </div>

        <button
          onClick={handleStart}
          disabled={isRunning || !isStopped || actionLoading === "start"}
          className="bg-[#00F0FF]/10 text-[#00F0FF] border border-[#00F0FF]/20 px-4 py-2 rounded-sm text-xs font-mono font-bold hover:bg-[#00F0FF]/20 transition-all flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {actionLoading === "start" ? (
            <div className="w-4 h-4 border-2 border-[#00F0FF] border-t-transparent rounded-full animate-spin" />
          ) : (
            <Plus className="w-4 h-4" />
          )}
          DEPLOY BOT
        </button>
      </div>

      {/* ============================================================ */}
      {/* 4 Stat Cards Row */}
      {/* ============================================================ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        {/* Active Bots / Status */}
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 p-4 rounded-sm">
          <div className="text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-2">Bot Status</div>
          <div className="flex items-end gap-3">
            <span className="font-mono text-3xl font-black" style={{ color: statusCfg.color }}>
              {isRunning ? "ON" : isPaused ? "PSE" : "OFF"}
            </span>
            <span
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-[9px] font-mono font-bold uppercase mb-1"
              style={{ color: statusCfg.color, background: statusCfg.bg }}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${isRunning ? "animate-pulse" : ""}`}
                style={{ background: statusCfg.color }}
              />
              {statusCfg.label}
            </span>
          </div>
        </div>

        {/* Fleet PnL */}
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 p-4 rounded-sm">
          <div className="text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-2">Fleet PnL</div>
          <div className="flex items-end gap-3">
            <span
              className="font-[JetBrains_Mono,monospace] text-3xl font-black"
              style={{ color: performance && performance.total_pnl >= 0 ? "#40E56C" : "#FFB4AB" }}
            >
              {performance
                ? `${performance.total_pnl >= 0 ? "+" : ""}${Math.abs(performance.total_pnl).toFixed(2)}`
                : "--"}
            </span>
            <span className="font-mono text-xs text-[#B9CACB] mb-1">USDT</span>
          </div>
        </div>

        {/* Total Trades */}
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 p-4 rounded-sm">
          <div className="text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-2">Total Trades</div>
          <div className="flex items-end gap-3">
            <span className="font-[JetBrains_Mono,monospace] text-3xl font-black text-[#E5E2E1]">
              {performance ? performance.total_trades : "--"}
            </span>
            <span className="font-mono text-xs text-[#B9CACB] mb-1">EXECUTIONS</span>
          </div>
        </div>

        {/* Win Rate / System Load */}
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 p-4 rounded-sm">
          <div className="text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-2">Win Rate</div>
          <div className="flex items-end gap-3">
            <span className="font-[JetBrains_Mono,monospace] text-3xl font-black text-[#E5E2E1]">
              {performance ? `${(performance.win_rate * 100).toFixed(1)}%` : "--%"}
            </span>
            <span className="font-mono text-xs text-[#B9CACB] mb-1">
              {performance ? `${performance.wins}W / ${performance.losses}L` : "W / L"}
            </span>
          </div>
        </div>
      </div>

      {/* ============================================================ */}
      {/* Main: lg:grid-cols-3 (2/3 + 1/3) */}
      {/* ============================================================ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* ---------------------------------------------------------- */}
        {/* Left Column (col-span-2): Bot Status + Configuration */}
        {/* ---------------------------------------------------------- */}
        <div className="lg:col-span-2 space-y-6">

          {/* Bot Status Card */}
          <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm overflow-hidden">
            <div className="p-4 border-b border-[#2A2A2A]/40 flex justify-between items-center">
              <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase flex items-center gap-2">
                <Cpu className="w-4 h-4 text-[#00F0FF]" />
                Bot Engine
              </h3>
              <span
                className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold uppercase"
                style={{ color: paperMode ? "#FFB4AB" : "#40E56C", background: paperMode ? "rgba(255,180,171,0.1)" : "rgba(64,229,108,0.1)" }}
              >
                <Shield size={10} />
                {paperMode ? "PAPER" : "LIVE"}
              </span>
            </div>

            <div className="p-4 space-y-5">
              {/* Large status indicator */}
              <div className="flex items-center gap-4">
                <div
                  className="w-14 h-14 rounded-sm flex items-center justify-center"
                  style={{ background: statusCfg.bg }}
                >
                  <div
                    className={`w-4 h-4 rounded-full ${isRunning ? "animate-pulse" : ""}`}
                    style={{ background: statusCfg.color }}
                  />
                </div>
                <div>
                  <div className="font-mono text-lg font-black uppercase" style={{ color: statusCfg.color }}>
                    {statusCfg.label}
                  </div>
                  <div className="font-mono text-[10px] text-[#B9CACB] mt-0.5">
                    Uptime: <span className="font-[JetBrains_Mono,monospace] text-[#E5E2E1]">{uptimeStr}</span>
                    {activeStratCount > 0 && (
                      <> &middot; <span className="text-[#00F0FF]">{activeStratCount} strategies</span></>
                    )}
                  </div>
                </div>
              </div>

              {/* Balance Row */}
              {(botStatus?.current_balance != null || botStatus?.current_equity != null) && (
                <div className="flex items-center gap-4 px-3 py-2.5 bg-[#201F1F] rounded-sm border border-[#3B494B]/10">
                  {botStatus?.current_balance != null && (
                    <div>
                      <div className="text-[9px] font-mono text-[#B9CACB] uppercase tracking-widest">Balance</div>
                      <div className="font-[JetBrains_Mono,monospace] text-sm font-bold text-[#00F0FF]">
                        ${botStatus.current_balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                    </div>
                  )}
                  {botStatus?.current_equity != null && botStatus.current_equity !== botStatus.current_balance && (
                    <div>
                      <div className="text-[9px] font-mono text-[#B9CACB] uppercase tracking-widest">Equity</div>
                      <div
                        className="font-[JetBrains_Mono,monospace] text-sm font-bold"
                        style={{ color: (botStatus.current_equity ?? 0) >= (botStatus.current_balance ?? 0) ? "#40E56C" : "#FFB4AB" }}
                      >
                        ${botStatus.current_equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Control Buttons Row */}
              <div className="grid grid-cols-4 gap-2">
                <button
                  onClick={handleStart}
                  disabled={isRunning || !isStopped || actionLoading === "start"}
                  className="flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-sm text-xs font-mono font-bold transition-all bg-[#40E56C]/10 text-[#40E56C] border border-[#40E56C]/20 hover:bg-[#40E56C]/20 disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  {actionLoading === "start" && !isPaused ? (
                    <div className="w-3.5 h-3.5 border-2 border-[#40E56C] border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Play size={14} className="fill-current" />
                  )}
                  START
                </button>
                <button
                  onClick={handleStop}
                  disabled={isStopped || actionLoading === "stop"}
                  className="flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-sm text-xs font-mono font-bold transition-all bg-[#FFB4AB]/10 text-[#FFB4AB] border border-[#FFB4AB]/20 hover:bg-[#FFB4AB]/20 disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  {actionLoading === "stop" ? (
                    <div className="w-3.5 h-3.5 border-2 border-[#FFB4AB] border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Square size={14} className="fill-current" />
                  )}
                  STOP
                </button>
                <button
                  onClick={handlePause}
                  disabled={!isRunning || actionLoading === "pause"}
                  className="flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-sm text-xs font-mono font-bold transition-all bg-[#2A2A2A] text-[#B9CACB] border border-[#3B494B]/10 hover:bg-[#353534] hover:text-[#E5E2E1] disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  {actionLoading === "pause" ? (
                    <div className="w-3.5 h-3.5 border-2 border-[#B9CACB] border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Pause size={14} />
                  )}
                  PAUSE
                </button>
                <button
                  onClick={handleStart}
                  disabled={!isPaused || actionLoading === "start"}
                  className="flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-sm text-xs font-mono font-bold transition-all bg-[#2A2A2A] text-[#B9CACB] border border-[#3B494B]/10 hover:bg-[#353534] hover:text-[#E5E2E1] disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  {actionLoading === "start" && isPaused ? (
                    <div className="w-3.5 h-3.5 border-2 border-[#B9CACB] border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <RotateCcw size={14} />
                  )}
                  RESUME
                </button>
              </div>

              {/* Active Strategies Badges */}
              {(botStatus?.active_strategies ?? []).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {botStatus?.active_strategies.map((key) => {
                    const label = availableStrategies.find((s) => s.key === key)?.label ?? key;
                    return (
                      <span
                        key={key}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[9px] font-mono font-bold uppercase bg-[#00F0FF]/8 text-[#00F0FF] border border-[#00F0FF]/15"
                      >
                        <Zap size={9} />
                        {label}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Configuration Section */}
          <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm overflow-hidden">
            <div className="p-4 border-b border-[#2A2A2A]/40">
              <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase flex items-center gap-2">
                <Activity className="w-4 h-4 text-[#00F0FF]" />
                Configuration
              </h3>
            </div>

            <div className="p-4 space-y-5">
              {/* Symbols — Dropdown Modal Selector */}
              <div className="relative">
                <label className="block text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-2">
                  Symbols ({selectedSymbols.length} selected)
                </label>

                <button
                  onClick={() => {
                    setPendingSymbols([...selectedSymbols]);
                    setSymbolSearch("");
                    setSymbolModalOpen(!symbolModalOpen);
                  }}
                  className="w-full flex items-center justify-between px-3 py-2.5 rounded-sm text-xs font-mono transition-all cursor-pointer bg-[#201F1F] text-[#E5E2E1] border hover:border-[#00F0FF]/30"
                  style={{
                    borderColor: symbolModalOpen ? "rgba(0, 240, 255, 0.4)" : "rgba(59, 73, 75, 0.1)",
                  }}
                >
                  <span className="truncate text-[#B9CACB]">
                    {selectedSymbols.length === 0
                      ? "Select symbols..."
                      : selectedSymbols.slice(0, 5).join(", ") +
                        (selectedSymbols.length > 5
                          ? ` +${selectedSymbols.length - 5} more`
                          : "")}
                  </span>
                  <ChevronDown
                    size={16}
                    className={`transition-transform duration-200 flex-shrink-0 ml-2 text-[#B9CACB] ${symbolModalOpen ? "rotate-180" : ""}`}
                  />
                </button>

                {/* Dropdown modal */}
                {symbolModalOpen && (
                  <div
                    ref={symbolModalRef}
                    className="absolute z-50 mt-2 left-0 right-0 rounded-sm overflow-hidden bg-[#1C1B1B] border border-[#00F0FF]/20"
                    style={{ maxHeight: "420px" }}
                  >
                    {/* Search bar */}
                    <div className="p-3 border-b border-[#2A2A2A]/40">
                      <div className="relative">
                        <Search
                          size={14}
                          className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#B9CACB]/50"
                        />
                        <input
                          type="text"
                          value={symbolSearch}
                          onChange={(e) => setSymbolSearch(e.target.value)}
                          placeholder="Search symbols..."
                          autoFocus
                          className="w-full bg-[#201F1F] border border-[#3B494B]/10 rounded-sm pl-8 pr-3 py-2 text-xs font-mono text-[#E5E2E1] focus:outline-none focus:border-[#00F0FF]/40 placeholder:text-[#B9CACB]/30"
                        />
                      </div>
                    </div>

                    {/* Quick action buttons */}
                    <div className="flex items-center gap-2 px-3 py-2 border-b border-[#2A2A2A]/40">
                      <button
                        onClick={() => setPendingSymbols([])}
                        className="px-2.5 py-1 rounded-sm text-[10px] font-mono uppercase tracking-wider transition-colors cursor-pointer text-[#B9CACB] bg-[#2A2A2A] border border-[#3B494B]/10 hover:bg-[#353534]"
                      >
                        Clear All
                      </button>
                      <button
                        onClick={() => setPendingSymbols(marketSymbols.slice(0, 20))}
                        className="px-2.5 py-1 rounded-sm text-[10px] font-mono uppercase tracking-wider transition-colors cursor-pointer text-[#00F0FF] bg-[#00F0FF]/8 border border-[#00F0FF]/15 hover:bg-[#00F0FF]/15"
                      >
                        Top 20
                      </button>
                      <span className="ml-auto text-[10px] font-mono text-[#B9CACB]/50">
                        {pendingSymbols.length} / {marketSymbols.length}
                      </span>
                    </div>

                    {/* Checkbox grid */}
                    <div className="overflow-y-auto p-3" style={{ maxHeight: "260px" }}>
                      <div className="grid grid-cols-3 gap-1">
                        {marketSymbols
                          .filter((s) =>
                            s.toLowerCase().includes(symbolSearch.toLowerCase())
                          )
                          .map((sym) => {
                            const checked = pendingSymbols.includes(sym);
                            return (
                              <label
                                key={sym}
                                className={`flex items-center gap-2 px-2 py-1.5 rounded-sm cursor-pointer transition-colors ${
                                  checked ? "bg-[#00F0FF]/8" : "hover:bg-[#201F1F]"
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={() =>
                                    setPendingSymbols((prev) =>
                                      checked
                                        ? prev.filter((s) => s !== sym)
                                        : [...prev, sym]
                                    )
                                  }
                                  className="sr-only peer"
                                />
                                <div
                                  className="w-3.5 h-3.5 rounded-sm border flex-shrink-0 flex items-center justify-center"
                                  style={{
                                    borderColor: checked ? "#00F0FF" : "rgba(59, 73, 75, 0.3)",
                                    background: checked ? "#00F0FF" : "transparent",
                                  }}
                                >
                                  {checked && (
                                    <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                                      <path
                                        d="M1.5 4L3 5.5L6.5 2"
                                        stroke="#0D0D0D"
                                        strokeWidth="1.5"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                      />
                                    </svg>
                                  )}
                                </div>
                                <span
                                  className="text-xs font-mono truncate"
                                  style={{
                                    color: checked ? "#00F0FF" : "#B9CACB",
                                  }}
                                >
                                  {sym.replace("/USDT", "")}
                                </span>
                              </label>
                            );
                          })}
                      </div>
                    </div>

                    {/* Apply / Cancel footer */}
                    <div className="flex items-center justify-end gap-2 px-3 py-2.5 border-t border-[#2A2A2A]/40">
                      <button
                        onClick={() => setSymbolModalOpen(false)}
                        className="px-3 py-1.5 rounded-sm text-xs font-mono transition-colors cursor-pointer text-[#B9CACB] bg-[#2A2A2A] border border-[#3B494B]/10 hover:bg-[#353534]"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => {
                          setSelectedSymbols(pendingSymbols);
                          setSymbolModalOpen(false);
                        }}
                        className="px-4 py-1.5 rounded-sm text-xs font-mono font-bold transition-colors cursor-pointer text-[#0D0D0D] bg-[#00F0FF] hover:opacity-90"
                      >
                        Apply ({pendingSymbols.length})
                      </button>
                    </div>
                  </div>
                )}

                {/* Selected symbols display chips */}
                {selectedSymbols.length > 0 && !symbolModalOpen && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {selectedSymbols.map((sym) => (
                      <span
                        key={sym}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] font-mono text-[#00F0FF] bg-[#00F0FF]/8 border border-[#00F0FF]/15"
                      >
                        {sym.replace("/USDT", "")}
                        <button
                          onClick={() =>
                            setSelectedSymbols((prev) =>
                              prev.filter((s) => s !== sym)
                            )
                          }
                          className="hover:text-[#FFB4AB] transition-colors cursor-pointer"
                        >
                          <X size={10} />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Timeframe */}
              <div>
                <label className="block text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-2">
                  Timeframe
                </label>
                <div className="flex gap-2">
                  {availableTimeframes.map((tf) => {
                    const isActive = tf.value === selectedTimeframe;
                    return (
                      <button
                        key={tf.value}
                        onClick={() => setSelectedTimeframe(tf.value)}
                        className={`px-3 py-1.5 rounded-sm text-xs font-mono font-bold transition-all cursor-pointer border ${
                          isActive
                            ? "text-[#00F0FF] bg-[#00F0FF]/10 border-[#00F0FF]/30"
                            : "text-[#B9CACB] bg-[#2A2A2A] border-[#3B494B]/10 hover:bg-[#353534] hover:text-[#E5E2E1]"
                        }`}
                      >
                        {tf.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Metadata fetch error banner */}
              {metadataError && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-sm text-xs font-mono bg-[#FFB4AB]/8 border border-[#FFB4AB]/20 text-[#FFB4AB]">
                  <AlertTriangle size={14} className="flex-shrink-0" />
                  <span>Using fallback strategies/timeframes -- backend metadata unavailable</span>
                </div>
              )}

              {/* Strategies */}
              <div>
                <label className="block text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-2">
                  Strategies
                </label>
                <div className="space-y-1">
                  {availableStrategies.map((strat) => {
                    const isEnabled = enabledStrategies[strat.key] ?? false;
                    return (
                      <label
                        key={strat.key}
                        className={`flex items-center justify-between py-2 px-3 rounded-sm cursor-pointer transition-colors border ${
                          isEnabled
                            ? "bg-[#00F0FF]/5 border-[#00F0FF]/15"
                            : "bg-transparent border-transparent hover:bg-[#201F1F]"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <div
                            className="w-3.5 h-3.5 rounded-sm border flex-shrink-0 flex items-center justify-center"
                            style={{
                              borderColor: isEnabled ? "#00F0FF" : "rgba(59, 73, 75, 0.3)",
                              background: isEnabled ? "#00F0FF" : "transparent",
                            }}
                          >
                            {isEnabled && (
                              <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                                <path
                                  d="M1.5 4L3 5.5L6.5 2"
                                  stroke="#0D0D0D"
                                  strokeWidth="1.5"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                />
                              </svg>
                            )}
                          </div>
                          <span className={`text-xs font-mono ${isEnabled ? "text-[#E5E2E1]" : "text-[#B9CACB]"}`}>
                            {strat.label}
                          </span>
                        </div>
                        <input
                          type="checkbox"
                          className="sr-only"
                          checked={isEnabled}
                          onChange={(e) =>
                            setEnabledStrategies((prev) => ({
                              ...prev,
                              [strat.key]: e.target.checked,
                            }))
                          }
                        />
                        <span
                          className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm"
                          style={{
                            color: isEnabled ? "#40E56C" : "#B9CACB",
                            background: isEnabled ? "rgba(64, 229, 108, 0.1)" : "rgba(59, 73, 75, 0.1)",
                          }}
                        >
                          {isEnabled ? "ON" : "OFF"}
                        </span>
                      </label>
                    );
                  })}
                </div>
                <button
                  onClick={handleSaveStrategies}
                  disabled={actionLoading === "strategies"}
                  className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-2 rounded-sm text-xs font-mono font-bold transition-all bg-[#2A2A2A] text-[#E5E2E1] border border-[#3B494B]/10 hover:bg-[#353534] disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {actionLoading === "strategies" ? (
                    <div className="w-3.5 h-3.5 border-2 border-[#E5E2E1] border-t-transparent rounded-full animate-spin" />
                  ) : null}
                  SAVE STRATEGIES
                </button>
              </div>

              {/* Divider */}
              <div className="border-t border-[#2A2A2A]/40" />

              {/* Paper / Live Mode Toggle */}
              <div>
                <label className="block text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-2">
                  Trading Mode
                </label>
                <div className="flex rounded-sm overflow-hidden border border-[#3B494B]/10">
                  <button
                    type="button"
                    onClick={() => { if (!paperMode) handleTogglePaperMode(true); }}
                    className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-mono font-bold transition-all border-r border-[#3B494B]/10 ${
                      paperMode
                        ? "bg-[#FFB4AB]/10 text-[#FFB4AB]"
                        : "bg-transparent text-[#B9CACB]/50 hover:text-[#B9CACB]"
                    }`}
                  >
                    <Shield size={14} />
                    PAPER
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (paperMode) {
                        if (window.confirm(
                          "SWITCH TO LIVE TRADING?\n\n" +
                          "This will use REAL funds from your Binance account.\n" +
                          "Make sure your API key is configured in Settings.\n\n" +
                          "Are you sure?"
                        )) {
                          handleTogglePaperMode(false);
                        }
                      }
                    }}
                    className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-mono font-bold transition-all ${
                      !paperMode
                        ? "bg-[#40E56C]/10 text-[#40E56C]"
                        : "bg-transparent text-[#B9CACB]/50 hover:text-[#B9CACB]"
                    }`}
                  >
                    <Zap size={14} />
                    LIVE
                  </button>
                </div>
                <p className="text-[10px] font-mono mt-1.5" style={{ color: paperMode ? "#FFB4AB" : "#40E56C", opacity: 0.7 }}>
                  {paperMode ? "Simulated trades -- no real funds used" : "Real funds -- orders sent to Binance"}
                </p>
              </div>

              {/* Balance -- Paper: manual input, Live: real from Binance */}
              <div>
                <label className="block text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-2">
                  {paperMode ? "Starting Balance (USDT)" : "Binance Account Balance"}
                </label>
                {paperMode ? (
                  <input
                    type="number"
                    value={startingBalance}
                    onChange={(e) => setStartingBalance(e.target.value)}
                    min={100}
                    step={100}
                    className="w-full bg-[#201F1F] border border-[#3B494B]/10 rounded-sm px-3 py-2 text-sm font-[JetBrains_Mono,monospace] text-[#E5E2E1] focus:outline-none focus:border-[#00F0FF]/40 focus:ring-1 focus:ring-[#00F0FF]/20 placeholder:text-[#B9CACB]/30"
                    placeholder="10000"
                  />
                ) : (
                  <div className="w-full rounded-sm overflow-hidden border border-[#40E56C]/20">
                    <div className="px-3 py-2 flex items-center justify-between bg-[#40E56C]/8">
                      <span className="font-[JetBrains_Mono,monospace] text-base font-bold text-[#40E56C]">
                        ${liveBalance ? liveBalance.total_usd_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "--"}
                      </span>
                      <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-sm bg-[#40E56C]/15 text-[#40E56C]">
                        {liveBalance?.source === "binance" ? "LIVE" : "Fetching..."}
                      </span>
                    </div>
                    {liveBalance?.assets && liveBalance.assets.length > 0 && (
                      <div className="px-3 py-1.5 bg-[#0D0D0D]/50">
                        {liveBalance.assets.map((asset) => (
                          <div key={asset.currency} className="flex items-center justify-between py-1 text-[10px] font-[JetBrains_Mono,monospace] border-b border-[#2A2A2A]/20 last:border-0">
                            <span className="text-[#E5E2E1] font-bold">{asset.currency}</span>
                            <div className="flex gap-3 text-[#B9CACB]">
                              <span>Total: <span className="text-[#E5E2E1]">{asset.total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 8 })}</span></span>
                              <span>Free: <span className="text-[#40E56C]">{asset.free.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 8 })}</span></span>
                              {asset.used > 0 && (
                                <span>Margin: <span className="text-[#00F0FF]">{asset.used.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 8 })}</span></span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ---------------------------------------------------------- */}
        {/* Right Column (col-span-1): Activity Feed / System Logs */}
        {/* ---------------------------------------------------------- */}
        <div className="lg:col-span-1 space-y-6">

          {/* Activity Feed */}
          <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm flex flex-col overflow-hidden">
            <div className="p-4 border-b border-[#2A2A2A]/40">
              <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-[#FFB4AB]" />
                System Logs
              </h3>
            </div>

            <div
              className="flex-1 overflow-y-auto bg-[#0A0A0A] font-[JetBrains_Mono,monospace] text-[10px] leading-relaxed"
              style={{ maxHeight: "480px", minHeight: "320px" }}
            >
              {events.length === 0 ? (
                <div className="text-center py-12 px-4">
                  <Activity
                    size={28}
                    className="mx-auto mb-3 text-[#B9CACB]/20"
                  />
                  <p className="text-[10px] font-mono text-[#B9CACB]/40">
                    No activity yet
                  </p>
                  <p className="text-[9px] font-mono text-[#B9CACB]/20 mt-1">
                    Start the bot to see live events
                  </p>
                </div>
              ) : (
                <div className="p-3 space-y-1">
                  {events.map((evt) => (
                    <div
                      key={evt.id}
                      className={`py-0.5 ${evt.type === "error" ? "bg-[#FFB4AB]/5 -mx-1 px-1 rounded-sm" : ""}`}
                    >
                      <span className="text-[#00F0FF]">[{evt.time}]</span>{" "}
                      <span
                        style={{
                          color:
                            evt.type === "error"
                              ? "#FFB4AB"
                              : evt.type === "signal"
                              ? "#00F0FF"
                              : evt.type === "order"
                              ? "#40E56C"
                              : "#B9CACB",
                        }}
                      >
                        {evt.message}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Active Strategies Display */}
          <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm overflow-hidden">
            <div className="p-4 border-b border-[#2A2A2A]/40">
              <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase flex items-center gap-2">
                <Zap className="w-4 h-4 text-[#00F0FF]" />
                Active Strategies
              </h3>
            </div>

            <div className="p-4 space-y-2">
              {(botStatus?.active_strategies ?? []).length === 0 ? (
                <p className="text-[10px] font-mono py-4 text-center text-[#B9CACB]/40">
                  No strategies active
                </p>
              ) : (
                botStatus?.active_strategies.map((key) => {
                  const label =
                    availableStrategies.find((s) => s.key === key)?.label ?? key;
                  return (
                    <div
                      key={key}
                      className="flex items-center justify-between py-2 px-3 rounded-sm bg-[#00F0FF]/5 border border-[#00F0FF]/10"
                    >
                      <div className="flex items-center gap-2">
                        <Zap size={12} className="text-[#00F0FF]" />
                        <span className="text-xs font-mono text-[#E5E2E1]">
                          {label}
                        </span>
                      </div>
                      <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#40E56C]/10 text-[#40E56C]">
                        Active
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
