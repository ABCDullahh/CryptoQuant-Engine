"use client";

import { useState, useCallback, useMemo, useRef } from "react";
import {
  Activity,
  Search,
  Target,
  Filter,
  ChevronUp,
  Shield,
  Clock,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { usePolling, useWebSocket } from "@/hooks/useApi";
import { fetchSignals, executeSignal, type Signal, type SignalDirection, type SignalStatus, type SignalGrade } from "@/lib/api";
import { formatPrice, formatPercent, timeAgo, cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Filter options                                                     */
/* ------------------------------------------------------------------ */

const DIRECTION_OPTIONS: Array<{ label: string; value: SignalDirection | "ALL" }> = [
  { label: "All", value: "ALL" },
  { label: "Long", value: "LONG" },
  { label: "Short", value: "SHORT" },
];

const GRADE_OPTIONS: Array<{ label: string; value: SignalGrade | "ALL" }> = [
  { label: "All", value: "ALL" },
  { label: "A", value: "A" },
  { label: "B", value: "B" },
  { label: "C", value: "C" },
  { label: "D", value: "D" },
];

const STATUS_OPTIONS: Array<{ label: string; value: SignalStatus | "ALL" }> = [
  { label: "All", value: "ALL" },
  { label: "Active", value: "ACTIVE" },
  { label: "Executed", value: "EXECUTED" },
  { label: "Rejected", value: "REJECTED" },
  { label: "Expired", value: "EXPIRED" },
];

/* ------------------------------------------------------------------ */
/*  Grade badge                                                        */
/* ------------------------------------------------------------------ */

const gradeBadgeStyle: Record<string, string> = {
  A: "bg-[#00F0FF]/10 text-[#00F0FF]",
  B: "bg-[#40E56C]/10 text-[#40E56C]",
  C: "bg-[#FFB3B6]/10 text-[#FFB3B6]",
  D: "bg-[#849495]/10 text-[#849495]",
};

function InlineGradeBadge({ grade }: { grade: SignalGrade }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider",
        gradeBadgeStyle[grade] ?? "bg-[#849495]/10 text-[#849495]"
      )}
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "currentColor" }} />
      {grade}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Direction badge                                                    */
/* ------------------------------------------------------------------ */

function InlineDirectionBadge({ direction }: { direction: SignalDirection }) {
  const isLong = direction === "LONG";
  const Icon = isLong ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded-sm",
        isLong ? "bg-[#40E56C]/10 text-[#40E56C]" : "bg-[#FFB4AB]/10 text-[#FFB4AB]"
      )}
    >
      <Icon className="w-3 h-3" />
      {direction}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Status badge                                                       */
/* ------------------------------------------------------------------ */

const statusBadgeStyle: Record<string, string> = {
  ACTIVE: "text-[#00F0FF]",
  EXECUTING: "text-[#00F0FF]",
  EXECUTED: "text-[#40E56C]",
  REJECTED: "text-[#849495]",
  EXPIRED: "text-[#849495]",
};

function InlineStatusBadge({ status }: { status: SignalStatus }) {
  return (
    <span className={cn("text-[10px] font-mono font-bold", statusBadgeStyle[status] ?? "text-[#849495]")}>
      {status}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Signal Detail Panel                                                */
/* ------------------------------------------------------------------ */

function calcRR(signal: Signal): { rr: number | null; slPct: number | null } {
  const entry = signal.entry_price;
  const sl = signal.stop_loss;
  const tp1 = signal.tp1_price;
  if (!entry || !sl || entry === sl) return { rr: null, slPct: null };
  const risk = Math.abs(entry - sl);
  const slPct = (risk / entry) * 100;
  if (!tp1) return { rr: null, slPct };
  const reward = Math.abs(tp1 - entry);
  return { rr: reward / risk, slPct };
}

function SignalDetailPanel({
  signal,
  onExecute,
  executing,
}: {
  signal: Signal;
  onExecute: () => void;
  executing: boolean;
}) {
  const tpPrices = [signal.tp1_price, signal.tp2_price, signal.tp3_price].filter(
    (tp): tp is number => tp != null
  );

  const { rr, slPct } = calcRR(signal);

  // RR for each TP level
  const tpRRs = tpPrices.map((tp) => {
    if (!signal.entry_price || !signal.stop_loss || signal.entry_price === signal.stop_loss) return null;
    const risk = Math.abs(signal.entry_price - signal.stop_loss);
    const reward = Math.abs(tp - signal.entry_price);
    return reward / risk;
  });

  // Market context extraction
  const ctx = signal.market_context;
  const regime = ctx?.regime_label ?? ctx?.regime ?? null;
  const volatility = ctx?.volatility ?? ctx?.atr_pct ?? null;
  const trend = ctx?.trend ?? ctx?.trend_strength ?? null;

  return (
    <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-5 mt-3">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Price levels + RR */}
        <div className="space-y-3">
          <h4 className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/60">
            Price Levels
          </h4>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs font-mono text-[#B9CACB]">Entry</span>
              <span className="font-mono text-sm tabular-nums text-[#E5E2E1]">
                {formatPrice(signal.entry_price ?? 0)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs font-mono text-[#B9CACB]">Stop Loss</span>
              <div className="flex items-center gap-1.5">
                <span className="font-mono text-sm tabular-nums text-[#FFB4AB]">
                  {formatPrice(signal.stop_loss ?? 0)}
                </span>
                {slPct != null && (
                  <span className="text-[9px] font-mono text-[#FFB4AB]/60">
                    ({slPct.toFixed(2)}%)
                  </span>
                )}
              </div>
            </div>
            {tpPrices.map((tp, i) => (
              <div key={i} className="flex justify-between items-center">
                <span className="text-xs font-mono text-[#B9CACB]">
                  TP{i + 1}
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-sm tabular-nums text-[#40E56C]">
                    {formatPrice(tp)}
                  </span>
                  {tpRRs[i] != null && (
                    <span className="text-[9px] font-mono text-[#40E56C]/60">
                      ({tpRRs[i]!.toFixed(1)}R)
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Signal details */}
        <div className="space-y-3">
          <h4 className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/60">
            Signal Details
          </h4>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs font-mono text-[#B9CACB]">SL Type</span>
              <span className="font-mono text-sm tabular-nums text-[#00F0FF]">
                {signal.sl_type ?? "N/A"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs font-mono text-[#B9CACB]">Strength</span>
              <span className="font-mono text-sm tabular-nums text-[#E5E2E1]">
                {signal.signal_strength != null ? formatPercent(signal.signal_strength * 100) : "N/A"}
              </span>
            </div>
            {signal.ml_confidence != null && (
              <div className="flex justify-between items-center">
                <span className="text-xs font-mono text-[#B9CACB]">ML Confidence</span>
                <span className="font-mono text-sm tabular-nums text-[#E5E2E1]">
                  {formatPercent(signal.ml_confidence * 100)}
                </span>
              </div>
            )}
            {rr != null && (
              <div className="flex justify-between items-center">
                <span className="text-xs font-mono text-[#B9CACB]">Risk:Reward</span>
                <span className={`font-mono text-sm tabular-nums font-bold ${rr >= 2 ? "text-[#40E56C]" : rr >= 1 ? "text-[#E5E2E1]" : "text-[#FFB4AB]"}`}>
                  1:{rr.toFixed(2)}
                </span>
              </div>
            )}
            <div className="flex justify-between items-center">
              <span className="text-xs font-mono text-[#B9CACB]">Leverage</span>
              <span className="font-mono text-sm tabular-nums text-[#00F0FF]">
                {signal.leverage}x
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs font-mono text-[#B9CACB]">Status</span>
              <InlineStatusBadge status={signal.status} />
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs font-mono text-[#B9CACB]">Created</span>
              <span className="font-mono text-xs text-[#B9CACB]">
                {signal.created_at ? new Date(signal.created_at).toLocaleString() : "N/A"}
              </span>
            </div>
            {signal.outcome && (
              <div className="flex justify-between items-center">
                <span className="text-xs font-mono text-[#B9CACB]">Outcome</span>
                <span className="font-mono text-xs text-[#B9CACB]">
                  {signal.outcome}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Strategy Scores with visual bars */}
        <div className="space-y-3">
          <h4 className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/60">
            Strategy Scores
          </h4>
          <div className="space-y-2">
            {Object.keys(signal.strategy_scores).length === 0 ? (
              <p className="text-xs font-mono text-[#B9CACB]/40">No scores</p>
            ) : (
              Object.entries(signal.strategy_scores)
                .sort(([, a], [, b]) => Number(b) - Number(a))
                .map(([key, value]) => {
                  const numVal = Number(value);
                  const pct = Math.min(100, Math.max(0, numVal * 100));
                  return (
                    <div key={key} className="space-y-0.5">
                      <div className="flex justify-between items-center">
                        <span className="text-[10px] font-mono text-[#B9CACB] truncate max-w-[100px]">
                          {key}
                        </span>
                        <span className="font-mono text-[10px] text-[#E5E2E1]/70 tabular-nums">
                          {typeof value === "number" ? (value * 100).toFixed(0) + "%" : String(value)}
                        </span>
                      </div>
                      {typeof value === "number" && (
                        <div className="h-1 bg-[#2A2A2A] rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${pct}%`,
                              backgroundColor: pct >= 70 ? "#40E56C" : pct >= 40 ? "#00F0FF" : "#FFB4AB",
                            }}
                          />
                        </div>
                      )}
                    </div>
                  );
                })
            )}
          </div>
        </div>

        {/* Market Context */}
        <div className="space-y-3">
          <h4 className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/60">
            Market Context
          </h4>
          <div className="space-y-2">
            {regime != null && (
              <div className="flex justify-between items-center">
                <span className="text-xs font-mono text-[#B9CACB]">Regime</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-sm bg-[#00F0FF]/10 text-[#00F0FF] border border-[#00F0FF]/15">
                  {String(regime)}
                </span>
              </div>
            )}
            {volatility != null && (
              <div className="flex justify-between items-center">
                <span className="text-xs font-mono text-[#B9CACB]">Volatility</span>
                <span className="font-mono text-sm tabular-nums text-[#E5E2E1]">
                  {typeof volatility === "number" ? volatility.toFixed(4) : String(volatility)}
                </span>
              </div>
            )}
            {trend != null && (
              <div className="flex justify-between items-center">
                <span className="text-xs font-mono text-[#B9CACB]">Trend</span>
                <span className="font-mono text-sm tabular-nums text-[#E5E2E1]">
                  {typeof trend === "number" ? trend.toFixed(4) : String(trend)}
                </span>
              </div>
            )}
            {ctx && Object.entries(ctx)
              .filter(([k]) => !["regime_label", "regime", "volatility", "atr_pct", "trend", "trend_strength"].includes(k))
              .slice(0, 5)
              .map(([key, value]) => (
                <div key={key} className="flex justify-between items-center">
                  <span className="text-[10px] font-mono text-[#B9CACB] truncate max-w-[80px]">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span className="font-mono text-[10px] text-[#E5E2E1]/60 tabular-nums truncate max-w-[100px]">
                    {typeof value === "number" ? value.toFixed(4) : String(value)}
                  </span>
                </div>
              ))
            }
            {!ctx && (
              <p className="text-xs font-mono text-[#B9CACB]/40">No context data</p>
            )}
          </div>
        </div>
      </div>

      {/* Execute Button or status text */}
      {signal.status === "ACTIVE" ? (
        <div className="mt-4 pt-4 border-t border-[#2A2A2A]/20">
          <button
            disabled={executing}
            onClick={onExecute}
            className={cn(
              "w-full flex items-center justify-center gap-2 rounded-sm py-2.5 text-sm font-mono font-bold transition-all duration-150",
              executing
                ? "bg-[#00F0FF]/20 text-[#00F0FF]/50 cursor-not-allowed"
                : "bg-[#00F0FF] text-[#002022] hover:opacity-90 active:opacity-80 cursor-pointer"
            )}
          >
            {executing ? (
              <svg className="h-4 w-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <Target size={16} />
            )}
            {executing ? "EXECUTING..." : "EXECUTE SIGNAL"}
          </button>
        </div>
      ) : (
        <div className="mt-4 pt-4 border-t border-[#2A2A2A]/20">
          <p className="text-[10px] font-mono text-center text-[#B9CACB]/40">
            {signal.status === "EXECUTED"
              ? "This signal was auto-executed by the trading engine."
              : signal.status === "REJECTED"
                ? "This signal was rejected by risk management filters."
                : signal.status === "EXPIRED"
                  ? "This signal expired before execution."
                  : `Status: ${signal.status}`}
          </p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Signals Page                                                  */
/* ------------------------------------------------------------------ */

export default function SignalsPage() {
  // -- Filter state --
  const [directionFilter, setDirectionFilter] = useState<SignalDirection | "ALL">("ALL");
  const [gradeFilter, setGradeFilter] = useState<SignalGrade | "ALL">("ALL");
  const [statusFilter, setStatusFilter] = useState<SignalStatus | "ALL">("ALL");
  const [symbolSearch, setSymbolSearch] = useState("");
  const [selectedSignalId, setSelectedSignalId] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(true);

  // -- Data fetching with polling (30s fallback) --
  const {
    data: signals,
    loading,
    error,
    refetch,
  } = usePolling(() => fetchSignals(), 30_000, []);

  // -- Real-time WebSocket updates (optimistic) --
  const refetchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // signal_new: prepend new signal optimistically, then refetch after 2s
  useWebSocket("signal_new", useCallback((data: Signal) => {
    if (data && data.id) {
      refetch();
    } else {
      refetch();
    }
    if (refetchTimeout.current) clearTimeout(refetchTimeout.current);
    refetchTimeout.current = setTimeout(() => {
      refetchTimeout.current = null;
      refetch();
    }, 2_000);
  }, [refetch]));

  // signal_update: update matching signal in array by ID
  useWebSocket("signal_update", useCallback((data: Signal) => {
    if (data && data.id) {
      refetch();
    }
  }, [refetch]));

  // -- Client-side filtering --
  const filteredSignals = useMemo(() => {
    if (!signals) return [];

    return signals.filter((s) => {
      if (directionFilter !== "ALL" && s.direction !== directionFilter) return false;
      if (gradeFilter !== "ALL" && s.signal_grade !== gradeFilter) return false;
      if (statusFilter !== "ALL" && s.status !== statusFilter) return false;
      if (
        symbolSearch &&
        !s.symbol.toLowerCase().includes(symbolSearch.toLowerCase())
      )
        return false;
      return true;
    });
  }, [signals, directionFilter, gradeFilter, statusFilter, symbolSearch]);

  // -- Stats computation --
  const stats = useMemo(() => {
    const all = signals ?? [];
    const total = all.length;
    const executed = all.filter((s) => s.status === "EXECUTED").length;
    const avgStrength =
      total > 0
        ? all.reduce((sum, s) => sum + (s.signal_strength ?? 0), 0) / total
        : 0;
    const gradeA = all.filter((s) => s.signal_grade === "A").length;

    return { total, executed, avgStrength, gradeA };
  }, [signals]);

  // -- Selected signal for detail panel --
  const selectedSignal = useMemo(
    () => filteredSignals.find((s) => s.id === selectedSignalId) ?? null,
    [filteredSignals, selectedSignalId]
  );

  // -- Execute signal handler --
  const [executing, setExecuting] = useState(false);
  const handleExecuteSignal = useCallback(async () => {
    if (!selectedSignalId) return;
    setExecuting(true);
    try {
      const result = await executeSignal(selectedSignalId);
      if (result.success) {
        refetch();
      }
    } catch {
      // Error handled by API layer
    } finally {
      setExecuting(false);
    }
  }, [selectedSignalId, refetch]);

  // -- Row click handler --
  const handleRowClick = useCallback(
    (row: Signal) => {
      setSelectedSignalId((prev) => (prev === row.id ? null : row.id));
    },
    []
  );

  // -- Loading state --
  if (loading && !signals) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-[#00F0FF] border-t-transparent rounded-full animate-spin" />
          <span className="font-mono text-sm text-[#B9CACB]/60">
            Loading signals...
          </span>
        </div>
      </div>
    );
  }

  // -- Error state --
  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center space-y-3">
          <div className="w-12 h-12 rounded-sm bg-[#FFB4AB]/10 flex items-center justify-center mx-auto">
            <Shield size={24} className="text-[#FFB4AB]" />
          </div>
          <p className="font-mono text-sm text-[#FFB4AB]">
            Failed to load signals
          </p>
          <p className="text-xs font-mono text-[#B9CACB]/40">{error}</p>
          <button
            onClick={refetch}
            className="mt-2 px-4 py-2 rounded-sm text-xs font-mono font-bold bg-[#00F0FF]/10 text-[#00F0FF] hover:bg-[#00F0FF]/20 transition-colors cursor-pointer"
          >
            RETRY
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-[1600px] mx-auto pb-20 md:pb-6 h-full flex flex-col">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 shrink-0">
        <div>
          <h2 className="font-mono text-xl font-black text-[#E5E2E1] uppercase tracking-tighter flex items-center gap-3">
            <Activity className="w-6 h-6 text-[#00F0FF]" />
            Signal Terminal
          </h2>
          <p className="font-mono text-[10px] text-[#B9CACB] uppercase tracking-widest mt-1">
            Algorithmic Trade Opportunities
          </p>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#B9CACB]" />
            <input
              type="text"
              value={symbolSearch}
              onChange={(e) => setSymbolSearch(e.target.value)}
              placeholder="SEARCH PAIR..."
              className="w-full bg-[#2A2A2A] border-0 rounded-sm py-2 pl-9 pr-4 text-xs font-mono text-[#E5E2E1] placeholder:text-[#B9CACB]/50 focus:outline-none focus:ring-1 focus:ring-[#00F0FF] transition-colors"
            />
          </div>
          <button
            onClick={() => setShowFilters((v) => !v)}
            className={cn(
              "p-2 rounded-sm transition-colors cursor-pointer",
              showFilters
                ? "bg-[#00F0FF]/10 text-[#00F0FF] border border-[#00F0FF]/30"
                : "bg-[#2A2A2A] border border-[#3B494B]/10 text-[#B9CACB] hover:text-[#E5E2E1] hover:bg-[#353534]"
            )}
          >
            <Filter className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ── Stat Cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 shrink-0">
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 p-4 rounded-sm">
          <div className="text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-2">
            Signal Accuracy
          </div>
          <div className="flex items-end gap-3">
            <span className="font-mono text-3xl font-black text-[#00F0FF] tabular-nums">
              {stats.total > 0 ? Math.round((stats.executed / stats.total) * 100) : 0}%
            </span>
            <span className="font-mono text-xs text-[#40E56C] mb-1">
              {stats.executed}/{stats.total}
            </span>
          </div>
        </div>
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 p-4 rounded-sm">
          <div className="text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-2">
            Active Opportunities
          </div>
          <div className="flex items-end gap-3">
            <span className="font-mono text-3xl font-black text-[#E5E2E1] tabular-nums">
              {stats.gradeA}
            </span>
            <span className="font-mono text-xs text-[#B9CACB] mb-1">GRADE A</span>
          </div>
        </div>
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 p-4 rounded-sm">
          <div className="text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-2">
            Avg. Signal Strength
          </div>
          <div className="flex items-end gap-3">
            <span className="font-mono text-3xl font-black text-[#E5E2E1] tabular-nums">
              {Math.round(stats.avgStrength * 100)}
            </span>
            <span className="font-mono text-xs text-[#B9CACB] mb-1">%</span>
          </div>
        </div>
      </div>

      {/* ── Filter Bar ── */}
      {showFilters && (
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-3 shrink-0">
          <div className="flex items-center gap-4 flex-wrap">
            {/* Direction filter */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/60 mr-1">
                Dir
              </span>
              {DIRECTION_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setDirectionFilter(opt.value)}
                  className={cn(
                    "px-3 py-1.5 rounded-sm text-[11px] font-mono font-bold transition-colors duration-150 cursor-pointer",
                    directionFilter === opt.value
                      ? "bg-[#00F0FF]/15 text-[#00F0FF]"
                      : "bg-[#2A2A2A] text-[#B9CACB]/60 hover:text-[#E5E2E1] hover:bg-[#353534]"
                  )}
                >
                  {opt.label.toUpperCase()}
                </button>
              ))}
            </div>

            {/* Divider */}
            <div className="w-px h-6 bg-[#2A2A2A]" />

            {/* Grade filter */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/60 mr-1">
                Grade
              </span>
              {GRADE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setGradeFilter(opt.value)}
                  className={cn(
                    "px-3 py-1.5 rounded-sm text-[11px] font-mono font-bold transition-colors duration-150 cursor-pointer",
                    gradeFilter === opt.value
                      ? "bg-[#00F0FF]/15 text-[#00F0FF]"
                      : "bg-[#2A2A2A] text-[#B9CACB]/60 hover:text-[#E5E2E1] hover:bg-[#353534]"
                  )}
                >
                  {opt.label.toUpperCase()}
                </button>
              ))}
            </div>

            {/* Divider */}
            <div className="w-px h-6 bg-[#2A2A2A]" />

            {/* Status filter */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/60 mr-1">
                Status
              </span>
              {STATUS_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setStatusFilter(opt.value)}
                  className={cn(
                    "px-3 py-1.5 rounded-sm text-[11px] font-mono font-bold transition-colors duration-150 cursor-pointer",
                    statusFilter === opt.value
                      ? "bg-[#00F0FF]/15 text-[#00F0FF]"
                      : "bg-[#2A2A2A] text-[#B9CACB]/60 hover:text-[#E5E2E1] hover:bg-[#353534]"
                  )}
                >
                  {opt.label.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Data Table ── */}
      <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm flex-1 overflow-hidden flex flex-col">
        {/* Table header bar */}
        <div className="p-4 border-b border-[#2A2A2A]/20 flex justify-between items-center shrink-0">
          <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#00F0FF] fill-current" />
            Live Feed
          </h3>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#40E56C] animate-pulse" />
            <span className="text-[9px] font-mono text-[#B9CACB] uppercase">
              {filteredSignals.length} signal{filteredSignals.length !== 1 ? "s" : ""}
            </span>
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto">
          <table className="w-full text-left font-mono whitespace-nowrap">
            <thead className="sticky top-0 bg-[#201F1F]/90 z-10">
              <tr className="text-[10px] text-[#B9CACB]/60 border-b border-[#2A2A2A]/10">
                <th className="px-4 py-3 font-bold uppercase tracking-widest">Time</th>
                <th className="px-4 py-3 font-bold uppercase tracking-widest">Pair</th>
                <th className="px-4 py-3 font-bold uppercase tracking-widest">Direction</th>
                <th className="px-4 py-3 font-bold uppercase tracking-widest">Grade</th>
                <th className="px-4 py-3 font-bold uppercase tracking-widest">Strategy</th>
                <th className="px-4 py-3 font-bold uppercase tracking-widest text-right">Entry</th>
                <th className="px-4 py-3 font-bold uppercase tracking-widest text-right">Target</th>
                <th className="px-4 py-3 font-bold uppercase tracking-widest text-right">Stop Loss</th>
                <th className="px-4 py-3 font-bold uppercase tracking-widest text-right">R:R</th>
                <th className="px-4 py-3 font-bold uppercase tracking-widest">Status</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="text-xs divide-y divide-[#2A2A2A]/5">
              {filteredSignals.length === 0 ? (
                <tr>
                  <td colSpan={11} className="px-4 py-12 text-center text-sm text-[#B9CACB]/40">
                    No signals match your filters
                  </td>
                </tr>
              ) : (
                filteredSignals.map((sig) => {
                  const isSelected = selectedSignalId === sig.id;
                  const topStrategy = Object.keys(sig.strategy_scores)[0] ?? "N/A";

                  return (
                    <tr
                      key={sig.id}
                      onClick={() => handleRowClick(sig)}
                      className={cn(
                        "transition-colors duration-150 cursor-pointer group",
                        isSelected ? "bg-[#2A2A2A]/60" : "hover:bg-[#2A2A2A]/40"
                      )}
                    >
                      <td className="px-4 py-4 text-[#B9CACB] flex items-center gap-2">
                        <Clock className="w-3 h-3" />
                        {sig.created_at ? timeAgo(sig.created_at) : "N/A"}
                      </td>
                      <td className="px-4 py-4 font-bold text-[#E5E2E1]">{sig.symbol}</td>
                      <td className="px-4 py-4">
                        <InlineDirectionBadge direction={sig.direction} />
                      </td>
                      <td className="px-4 py-4">
                        <InlineGradeBadge grade={sig.signal_grade} />
                      </td>
                      <td className="px-4 py-4 text-[#B9CACB]">{topStrategy}</td>
                      <td className="px-4 py-4 font-bold text-[#E5E2E1] text-right tabular-nums">
                        {formatPrice(sig.entry_price ?? 0)}
                      </td>
                      <td className="px-4 py-4 text-[#40E56C] text-right tabular-nums">
                        {formatPrice(sig.tp1_price ?? 0)}
                      </td>
                      <td className="px-4 py-4 text-[#FFB4AB] text-right tabular-nums">
                        {formatPrice(sig.stop_loss ?? 0)}
                      </td>
                      <td className="px-4 py-4 text-right tabular-nums">
                        {(() => {
                          const { rr: sigRR } = calcRR(sig);
                          if (sigRR == null) return <span className="text-[#B9CACB]/20">&mdash;</span>;
                          return (
                            <span className={`font-mono text-xs font-bold ${sigRR >= 2 ? "text-[#40E56C]" : sigRR >= 1 ? "text-[#E5E2E1]" : "text-[#FFB4AB]"}`}>
                              1:{sigRR.toFixed(1)}
                            </span>
                          );
                        })()}
                      </td>
                      <td className="px-4 py-4">
                        <InlineStatusBadge status={sig.status} />
                      </td>
                      <td className="px-4 py-4 text-right">
                        {sig.status === "ACTIVE" && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedSignalId(sig.id);
                            }}
                            className="opacity-0 group-hover:opacity-100 bg-[#00F0FF] text-[#002022] text-[9px] font-bold px-3 py-1.5 rounded-sm transition-all hover:scale-105 active:scale-95 cursor-pointer"
                          >
                            EXECUTE
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Detail Panel ── */}
      {selectedSignal && (
        <div className="shrink-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/60">
              Signal Detail
            </span>
            <span className="font-mono text-xs text-[#00F0FF]">
              {selectedSignal.symbol}
            </span>
            <InlineDirectionBadge direction={selectedSignal.direction} />
            <InlineGradeBadge grade={selectedSignal.signal_grade} />
            <div className="flex-1" />
            <button
              onClick={() => setSelectedSignalId(null)}
              className="text-[#B9CACB]/40 hover:text-[#E5E2E1] transition-colors cursor-pointer"
            >
              <ChevronUp size={16} />
            </button>
          </div>
          <SignalDetailPanel signal={selectedSignal} onExecute={handleExecuteSignal} executing={executing} />
        </div>
      )}
    </div>
  );
}
