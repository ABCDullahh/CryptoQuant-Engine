"use client";

import { useState, useCallback, useEffect, useRef, type MouseEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { useApi, useWebSocket } from "@/hooks/useApi";
import {
  runBacktest,
  fetchBacktestHistory,
  fetchBacktest,
  fetchMarkets,
  fetchMetadata,
  type BacktestResult,
  type BacktestTrade,
  type BacktestJobResponse,
  type BacktestHistoryEntry,
  type MarketInfo,
  type PlatformMetadata,
} from "@/lib/api";
import type { BacktestProgress } from "@/lib/websocket";
import { formatPnl, formatPercent, formatPrice } from "@/lib/utils";
import {
  History,
  Play,
  Settings2,
  BarChart2,
  Download,
  Calendar,
  Activity,
  GitCompareArrows,
} from "lucide-react";
import { BacktestCharts } from "./components/BacktestCharts";

/* ═══════════════════════════════════════════════════════
   Constants
   ═══════════════════════════════════════════════════════ */

const FALLBACK_STRATEGIES = [
  { value: "momentum", label: "Momentum" },
  { value: "mean_reversion", label: "Mean Reversion" },
  { value: "smart_money", label: "Smart Money" },
  { value: "volume_analysis", label: "Volume Analysis" },
  { value: "funding_arb", label: "Funding Arbitrage" },
];

const FALLBACK_SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"];

const FALLBACK_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1D"];

const INPUT_CLASS =
  "w-full bg-[#2A2A2A] border border-[#3B494B]/10 rounded-sm px-3 py-2 text-sm font-mono text-[#E5E2E1] focus:outline-none focus:border-[#00F0FF] focus:ring-1 focus:ring-[#00F0FF]/30 placeholder:text-[#B9CACB]/30";

const SELECT_CLASS =
  "w-full bg-[#2A2A2A] border border-[#3B494B]/10 rounded-sm px-3 py-2 text-sm font-mono text-[#E5E2E1] focus:outline-none focus:border-[#00F0FF] focus:ring-1 focus:ring-[#00F0FF]/30 appearance-none cursor-pointer";

/* ═══════════════════════════════════════════════════════
   Win/Loss Bar
   ═══════════════════════════════════════════════════════ */

function WinLossBar({
  wins,
  losses,
}: {
  wins: number;
  losses: number;
}) {
  const total = wins + losses;
  if (total === 0) return null;
  const winPct = (wins / total) * 100;
  const lossPct = (losses / total) * 100;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs font-mono">
        <span className="text-[#40E56C]">
          {wins} Wins ({winPct.toFixed(1)}%)
        </span>
        <span className="text-[#FFB4AB]">
          {losses} Losses ({lossPct.toFixed(1)}%)
        </span>
      </div>
      <div className="flex h-3 rounded-sm overflow-hidden bg-[#2A2A2A]">
        <div
          className="h-full rounded-l-sm transition-all duration-500"
          style={{
            width: `${winPct}%`,
            background: "linear-gradient(90deg, #40E56C, #2fb857)",
          }}
        />
        <div
          className="h-full rounded-r-sm transition-all duration-500"
          style={{
            width: `${lossPct}%`,
            background: "linear-gradient(90deg, #d94a3f, #FFB4AB)",
          }}
        />
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Mini Stat
   ═══════════════════════════════════════════════════════ */

function MiniStat({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-3">
      <p className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/60 mb-1">
        {label}
      </p>
      <p
        className="text-lg font-mono font-semibold tabular-nums"
        style={{ color: color || "#E5E2E1" }}
      >
        {value}
      </p>
    </div>
  );
}

/* EquityCurve SVG — removed, replaced by BacktestCharts Recharts component */

/* ═══════════════════════════════════════════════════════
   Monthly Returns Heatmap
   ═══════════════════════════════════════════════════════ */

function MonthlyReturnsGrid({
  monthlyReturns,
}: {
  monthlyReturns: Record<string, number>;
}) {
  const entries = Object.entries(monthlyReturns).sort(([a], [b]) => a.localeCompare(b));
  if (entries.length === 0) return null;

  // Group by year
  const byYear: Record<string, Array<{ month: string; value: number }>> = {};
  for (const [key, value] of entries) {
    const [year, month] = key.split("-");
    if (!byYear[year]) byYear[year] = [];
    byYear[year].push({ month, value });
  }

  const months = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"];
  const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // Find max absolute value for color scaling
  const maxAbs = Math.max(...entries.map(([, v]) => Math.abs(v)), 0.01);

  const getCellColor = (value: number) => {
    const intensity = Math.min(Math.abs(value) / maxAbs, 1);
    if (value >= 0) {
      return `rgba(64, 229, 108, ${0.1 + intensity * 0.5})`;
    }
    return `rgba(255, 180, 171, ${0.1 + intensity * 0.5})`;
  };

  const getTextColor = (value: number) => {
    if (value >= 0) return "#40E56C";
    return "#FFB4AB";
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th className="text-left text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40 px-2 py-1.5">
              Year
            </th>
            {monthLabels.map((m) => (
              <th
                key={m}
                className="text-center text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40 px-1 py-1.5"
              >
                {m}
              </th>
            ))}
            <th className="text-center text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40 px-2 py-1.5">
              Total
            </th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(byYear).map(([year, yearData]) => {
            const yearTotal = yearData.reduce((sum, d) => sum + d.value, 0);
            const monthMap = new Map(yearData.map((d) => [d.month, d.value]));
            return (
              <tr key={year}>
                <td className="text-xs font-mono font-semibold text-[#E5E2E1]/60 px-2 py-1">
                  {year}
                </td>
                {months.map((m) => {
                  const val = monthMap.get(m);
                  return (
                    <td
                      key={m}
                      className="text-center px-1 py-1"
                    >
                      {val !== undefined ? (
                        <div
                          className="rounded-sm px-1 py-0.5 text-[10px] font-mono tabular-nums font-medium"
                          style={{
                            background: getCellColor(val),
                            color: getTextColor(val),
                          }}
                          title={`${year}-${m}: ${(val * 100).toFixed(2)}%`}
                        >
                          {(val * 100).toFixed(1)}%
                        </div>
                      ) : (
                        <span className="text-[10px] text-[#B9CACB]/20">--</span>
                      )}
                    </td>
                  );
                })}
                <td className="text-center px-2 py-1">
                  <span
                    className="text-[10px] font-mono tabular-nums font-bold"
                    style={{ color: getTextColor(yearTotal) }}
                  >
                    {(yearTotal * 100).toFixed(1)}%
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Verification Badge
   ═══════════════════════════════════════════════════════ */

function VerificationBadge({
  verification,
}: {
  verification: { valid: boolean; trade_pnl_sum: number; equity_delta: number; difference: number } | null;
}) {
  if (!verification) return null;

  return verification.valid ? (
    <div className="flex items-center gap-2 bg-[#40E56C]/10 border border-[#40E56C]/20 rounded-sm px-4 py-2.5">
      <span className="text-sm">&#10003;</span>
      <span className="text-xs font-mono font-semibold text-[#40E56C] uppercase tracking-widest">
        VERIFIED &mdash; P&amp;L cross-check passed
      </span>
      <span className="text-[10px] font-mono text-[#40E56C]/60 ml-auto tabular-nums">
        &Delta; ${verification.difference.toFixed(2)}
      </span>
    </div>
  ) : (
    <div className="flex items-center gap-2 bg-[#FFB4AB]/10 border border-[#FFB4AB]/20 rounded-sm px-4 py-2.5">
      <span className="text-sm">&#9888;</span>
      <span className="text-xs font-mono font-semibold text-[#FFB4AB] uppercase tracking-widest">
        MISMATCH &mdash; difference: ${verification.difference.toFixed(2)}
      </span>
      <span className="text-[10px] font-mono text-[#FFB4AB]/60 ml-auto tabular-nums">
        Trades: ${verification.trade_pnl_sum.toFixed(2)} | Equity: ${verification.equity_delta.toFixed(2)}
      </span>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Metric Card — border-l-2 accent, 10px mono label
   ═══════════════════════════════════════════════════════ */

function MetricCard({
  label,
  value,
  color,
  borderColor,
}: {
  label: string;
  value: string;
  color?: string;
  borderColor?: string;
}) {
  return (
    <div
      className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-3"
      style={{ borderLeftWidth: "2px", borderLeftColor: borderColor || "#00F0FF" }}
    >
      <p className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/60 mb-1">
        {label}
      </p>
      <p
        className="text-xl font-mono font-black tabular-nums leading-tight"
        style={{ color: color || "#E5E2E1" }}
      >
        {value}
      </p>
    </div>
  );
}

/* TradePnlScatter SVG — removed, replaced by BacktestCharts Recharts component */

/* MonthlyReturnsBarChart SVG — removed, replaced by BacktestCharts Recharts component */

/* RollingSharpeChart SVG — removed, replaced by BacktestCharts Recharts component */

/* ═══════════════════════════════════════════════════════
   Progress Bar for live backtest tracking
   ═══════════════════════════════════════════════════════ */

function BacktestProgressBar({
  progress,
  status,
}: {
  progress: number;
  status: string;
}) {
  const pct = Math.min(Math.max(progress * 100, 0), 100);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-[#B9CACB]/60">
          {status === "RUNNING" ? "Running backtest..." : status}
        </span>
        <span className="text-xs font-mono font-semibold tabular-nums text-[#00F0FF]">
          {pct.toFixed(0)}%
        </span>
      </div>
      <div
        className="h-2 rounded-sm overflow-hidden bg-[#2A2A2A]"
      >
        <div
          className="h-full rounded-sm transition-all duration-500 ease-out"
          style={{
            width: `${pct}%`,
            background: "linear-gradient(90deg, #00F0FF, #00C0CC)",
          }}
        />
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Trade Table Columns — with P&L color coding and
   net P&L (pnl - fees) column
   ═══════════════════════════════════════════════════════ */

const tradeColumns: Column<BacktestTrade & Record<string, unknown>>[] = [
  {
    key: "id",
    label: "#",
    render: (row) => (
      <span className="font-mono text-[10px] text-[#B9CACB]/40">
        {String(row.id).slice(0, 6)}
      </span>
    ),
  },
  {
    key: "direction",
    label: "Dir",
    render: (row) => (
      <span
        className="inline-block px-1.5 py-0.5 rounded-sm text-[9px] font-mono font-bold"
        style={{
          color: row.direction === "LONG" ? "#40E56C" : "#FFB4AB",
          backgroundColor:
            row.direction === "LONG"
              ? "rgba(64,229,108,0.1)"
              : "rgba(255,180,171,0.1)",
        }}
      >
        {row.direction}
      </span>
    ),
  },
  {
    key: "strategy",
    label: "Strategy",
    render: (row) => (
      <span className="font-mono text-[10px] text-[#00F0FF]/70 capitalize">
        {((row as BacktestTrade).strategy ?? "--").replace(/_/g, " ")}
      </span>
    ),
  },
  {
    key: "entry_price",
    label: "Entry",
    align: "right",
    render: (row) => (
      <span className="font-mono text-[11px] tabular-nums text-[#E5E2E1]/80">{formatPrice(row.entry_price)}</span>
    ),
  },
  {
    key: "exit_price",
    label: "Exit",
    align: "right",
    render: (row) => (
      <span className="font-mono text-[11px] tabular-nums text-[#E5E2E1]/80">{formatPrice(row.exit_price)}</span>
    ),
  },
  {
    key: "quantity",
    label: "Qty",
    align: "right",
    render: (row) => (
      <span className="font-mono text-[11px] tabular-nums text-[#B9CACB]/70">{Number(row.quantity).toPrecision(4)}</span>
    ),
  },
  {
    key: "pnl",
    label: "P&L",
    align: "right",
    render: (row) => (
      <span
        className="font-mono text-[11px] font-bold tabular-nums"
        style={{ color: row.pnl >= 0 ? "#40E56C" : "#FFB4AB" }}
      >
        {formatPnl(row.pnl)}
      </span>
    ),
  },
  {
    key: "fees",
    label: "Fees",
    align: "right",
    render: (row) => (
      <span className="font-mono text-[10px] tabular-nums text-[#B9CACB]/50">
        ${row.fees.toFixed(2)}
      </span>
    ),
  },
  {
    key: "holding_periods",
    label: "Hold",
    align: "right",
    render: (row) => (
      <span className="font-mono text-[10px] tabular-nums text-[#B9CACB]/50">
        {row.holding_periods}b
      </span>
    ),
  },
  {
    key: "close_reason",
    label: "Reason",
    render: (row) => (
      <span className={`font-mono text-[9px] px-1.5 py-0.5 rounded-sm ${
        row.close_reason?.includes("TP") ? "text-[#40E56C] bg-[#40E56C]/8" :
        row.close_reason === "SL_HIT" ? "text-[#FFB4AB] bg-[#FFB4AB]/8" :
        "text-[#B9CACB]/60 bg-[#B9CACB]/5"
      }`}>
        {row.close_reason}
      </span>
    ),
  },
];

/* ═══════════════════════════════════════════════════════
   Sort types for trade table
   ═══════════════════════════════════════════════════════ */

type SortField = "pnl" | "entry_price" | "exit_price" | "quantity" | "fees" | "holding_periods" | null;
type SortDir = "asc" | "desc";

/* ═══════════════════════════════════════════════════════
   History Table Columns
   ═══════════════════════════════════════════════════════ */

const historyColumns: Column<BacktestHistoryEntry>[] = [
  {
    key: "strategy_name",
    label: "Strategy",
    render: (row) => (
      <span className="font-mono text-sm capitalize">
        {row.strategy_name.replace(/_/g, " ")}
      </span>
    ),
  },
  { key: "symbol", label: "Symbol" },
  { key: "timeframe", label: "Timeframe" },
  {
    key: "total_return",
    label: "Return",
    align: "right",
    render: (row) => (
      <span
        className="font-mono text-sm font-medium"
        style={{
          color:
            (row.total_return ?? 0) >= 0
              ? "#40E56C"
              : "#FFB4AB",
        }}
      >
        {row.total_return != null ? formatPnl(row.total_return) : "--"}
      </span>
    ),
  },
  {
    key: "win_rate",
    label: "Win Rate",
    align: "right",
    render: (row) => (
      <span className="font-mono text-sm">
        {row.win_rate != null ? `${(row.win_rate * 100).toFixed(1)}%` : "--"}
      </span>
    ),
  },
  {
    key: "sharpe_ratio",
    label: "Sharpe",
    align: "right",
    render: (row) => (
      <span className="font-mono text-sm">
        {row.sharpe_ratio != null ? row.sharpe_ratio.toFixed(2) : "--"}
      </span>
    ),
  },
  {
    key: "total_trades",
    label: "Trades",
    align: "right",
    render: (row) => (
      <span className="font-mono text-sm">
        {row.total_trades ?? "--"}
      </span>
    ),
  },
  {
    key: "created_at",
    label: "Date",
    render: (row) => (
      <span className="font-mono text-xs text-[#B9CACB]/70">
        {row.created_at ? new Date(row.created_at).toLocaleDateString() : "--"}
      </span>
    ),
  },
];

/* ═══════════════════════════════════════════════════════
   Backtest Lab Page
   ═══════════════════════════════════════════════════════ */

export default function BacktestLabPage() {
  const router = useRouter();

  // -- Comparison state --
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());

  const toggleCompareId = useCallback((id: string) => {
    setCompareIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // -- Form state --
  const [strategy, setStrategy] = useState("momentum");
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-06-01");
  const [initialCapital, setInitialCapital] = useState(10000);

  // -- Metadata from /api/metadata (strategies, timeframes) --
  const [metadata, setMetadata] = useState<PlatformMetadata | null>(null);
  useEffect(() => {
    fetchMetadata().then(setMetadata).catch(console.error);
  }, []);

  // -- Dynamic symbols from /api/markets --
  const [marketSymbols, setMarketSymbols] = useState<string[]>(FALLBACK_SYMBOLS);
  useEffect(() => {
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
  }, []);

  // -- Results state --
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [jobInfo, setJobInfo] = useState<BacktestJobResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [polling, setPolling] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  // -- Trade sort state --
  const [sortField, setSortField] = useState<SortField>(null);
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // -- Live progress from WebSocket --
  const [wsProgress, setWsProgress] = useState<{ progress: number; status: string } | null>(null);
  const activeJobIdRef = useRef<string | null>(null);

  useWebSocket("backtest_progress", useCallback((data: BacktestProgress) => {
    // Only handle progress for the current job
    if (activeJobIdRef.current && data.job_id === activeJobIdRef.current) {
      setWsProgress({ progress: data.progress, status: data.status });

      // If completed or failed via WS, fetch the full result
      if (data.status === "COMPLETED" || data.status === "FAILED") {
        fetchBacktest(data.job_id).then((detail) => {
          setResult(detail);
          setPolling(false);
          setWsProgress(null);
          activeJobIdRef.current = null;
          if (data.status === "FAILED") {
            setRunError(detail.error_message ?? "Backtest job failed");
          }
        }).catch(console.error);
      }
    }
  }, []));

  // -- History --
  const {
    data: history,
    loading: historyLoading,
    refetch: refetchHistory,
  } = useApi(() => fetchBacktestHistory(), []);

  // -- Poll for backtest result (fallback if WS doesn't deliver) --
  const pollForResult = useCallback(async (jobId: string) => {
    setPolling(true);
    const maxAttempts = 60;
    let attempts = 0;
    try {
      while (attempts < maxAttempts) {
        attempts++;
        await new Promise((r) => setTimeout(r, 3000));
        // If WS already resolved this job, stop polling
        if (activeJobIdRef.current !== jobId) return;
        const detail = await fetchBacktest(jobId);
        if (detail.status === "COMPLETED" || detail.status === null) {
          setResult(detail);
          setPolling(false);
          setWsProgress(null);
          activeJobIdRef.current = null;
          return;
        }
        if (detail.status === "FAILED") {
          setResult(detail);
          setRunError(detail.error_message ?? "Backtest job failed");
          setPolling(false);
          setWsProgress(null);
          activeJobIdRef.current = null;
          return;
        }
        // RUNNING or QUEUED — update progress from poll as fallback
        if (!wsProgress) {
          setJobInfo((prev) => prev ? { ...prev, progress: detail.progress ?? prev.progress } : prev);
        }
      }
      setRunError("Backtest timed out");
    } catch {
      setRunError("Failed to fetch backtest result");
    } finally {
      setPolling(false);
    }
  }, [wsProgress]);

  // -- Run backtest handler --
  const handleRun = useCallback(async () => {
    setRunning(true);
    setRunError(null);
    setResult(null);
    setJobInfo(null);
    setWsProgress(null);
    setSortField(null);
    try {
      const job = await runBacktest({
        strategy_name: strategy,
        symbol,
        timeframe,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        parameters: {},
      });
      setJobInfo(job);
      activeJobIdRef.current = job.job_id;
      setRunning(false);
      // Poll for results (fallback; WS progress will also track)
      pollForResult(job.job_id);
      refetchHistory();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Backtest failed";
      setRunError(message);
      setRunning(false);
    }
  }, [strategy, symbol, timeframe, startDate, endDate, initialCapital, refetchHistory, pollForResult]);

  // -- Load history entry --
  const handleHistoryClick = useCallback(
    async (entry: BacktestHistoryEntry) => {
      try {
        const full = await fetchBacktest(entry.id);
        setResult(full);
      } catch {
        // silent
      }
    },
    []
  );

  const isRunning = running || polling;

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-[1600px] mx-auto pb-20 md:pb-6 h-full flex flex-col">
      {/* -- Header -- */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 shrink-0">
        <div>
          <h2 className="font-mono text-xl font-black text-[#E5E2E1] uppercase tracking-tighter flex items-center gap-3">
            <History className="w-6 h-6 text-[#00F0FF]" />
            Backtest Engine
          </h2>
          <p className="font-mono text-[10px] text-[#B9CACB] uppercase tracking-widest mt-1">
            Historical Strategy Validation
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            className="bg-[#353534] border border-[#3B494B]/10 p-2 rounded-sm text-[#B9CACB] hover:text-[#E5E2E1] hover:bg-[#2A2A2A] transition-colors"
            title="Download results as CSV"
            onClick={() => {
              if (!result) return;
              const rows = [["Metric", "Value"]];
              if (result.metrics) {
                Object.entries(result.metrics).forEach(([k, v]) => rows.push([k, String(v)]));
              }
              const csv = rows.map((r) => r.join(",")).join("\n");
              const blob = new Blob([csv], { type: "text/csv" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `backtest-${result.strategy_name ?? "result"}.csv`;
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            <Download className="w-4 h-4" />
          </button>
          <Button
            variant="primary"
            size="sm"
            loading={isRunning}
            onClick={handleRun}
          >
            <Play className="w-4 h-4 fill-current" />
            {running ? "SUBMITTING..." : polling ? "RUNNING..." : "RUN SIMULATION"}
          </Button>
        </div>
      </div>

      {/* -- Two-column layout -- */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-0">
        {/* -- Left: Configuration Panel -- */}
        <div className={`${result && result.status === "COMPLETED" ? "lg:col-span-3" : "lg:col-span-4"} bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm flex flex-col overflow-hidden`}>
          <div className="p-4 border-b border-[#2A2A2A]/20 flex justify-between items-center shrink-0">
            <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase flex items-center gap-2">
              <Settings2 className="w-4 h-4 text-[#00F0FF]" />
              Parameters
            </h3>
          </div>

          <div className="flex-1 overflow-auto p-4 space-y-5">
            {/* Strategy */}
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/60 mb-2">
                Strategy Model
              </label>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                className={SELECT_CLASS}
              >
                {(metadata?.strategies.map(s => ({ value: s.id, label: s.label })) ?? FALLBACK_STRATEGIES).map((s) => (
                  <option
                    key={s.value}
                    value={s.value}
                    className="bg-[#201F1F] text-[#E5E2E1]"
                  >
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Symbol */}
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/60 mb-2">
                Trading Pair
              </label>
              <select
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className={SELECT_CLASS}
              >
                {marketSymbols.map((s) => (
                  <option
                    key={s}
                    value={s}
                    className="bg-[#201F1F] text-[#E5E2E1]"
                  >
                    {s}
                  </option>
                ))}
              </select>
            </div>

            {/* Timeframe */}
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/60 mb-2">
                Timeframe
              </label>
              <div className="flex flex-wrap gap-2">
                {(metadata?.timeframes.map(t => t.value) ?? FALLBACK_TIMEFRAMES).map((tf) => (
                  <button
                    key={tf}
                    type="button"
                    onClick={() => setTimeframe(tf)}
                    className={`
                      px-3 py-1.5 rounded-sm text-xs font-mono font-medium transition-all duration-200 border
                      ${
                        timeframe === tf
                          ? "bg-[#00F0FF]/15 text-[#00F0FF] border-[#00F0FF]/40"
                          : "bg-[#2A2A2A] text-[#B9CACB]/60 border-[#3B494B]/10 hover:border-[#B9CACB]/20 hover:text-[#E5E2E1]/70"
                      }
                    `}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>

            {/* Date Range */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/60 mb-2">
                  Start Date
                </label>
                <div className="relative">
                  <Calendar className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[#B9CACB]" />
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className={`${INPUT_CLASS} pl-7`}
                  />
                </div>
              </div>
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/60 mb-2">
                  End Date
                </label>
                <div className="relative">
                  <Calendar className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[#B9CACB]" />
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className={`${INPUT_CLASS} pl-7`}
                  />
                </div>
              </div>
            </div>

            {/* Initial Capital */}
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/60 mb-2">
                Initial Capital (USDT)
              </label>
              <input
                type="number"
                min={100}
                step={100}
                value={initialCapital}
                onChange={(e) =>
                  setInitialCapital(Number(e.target.value) || 0)
                }
                className={INPUT_CLASS}
                placeholder="10000"
              />
            </div>

            {/* Advanced Settings */}
            <div className="pt-4 border-t border-[#3B494B]/10">
              <h4 className="font-mono text-[10px] font-bold text-[#E5E2E1] uppercase tracking-widest mb-3">Advanced Settings</h4>
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input type="checkbox" defaultChecked className="w-3 h-3 bg-[#2A2A2A] border-[#3B494B]/30 rounded-sm text-[#00F0FF] focus:ring-0 focus:ring-offset-0" />
                  <span className="font-mono text-[10px] text-[#B9CACB] group-hover:text-[#E5E2E1] transition-colors">Include Trading Fees (0.04%)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input type="checkbox" defaultChecked className="w-3 h-3 bg-[#2A2A2A] border-[#3B494B]/30 rounded-sm text-[#00F0FF] focus:ring-0 focus:ring-offset-0" />
                  <span className="font-mono text-[10px] text-[#B9CACB] group-hover:text-[#E5E2E1] transition-colors">Simulate Slippage (0.1%)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input type="checkbox" className="w-3 h-3 bg-[#2A2A2A] border-[#3B494B]/30 rounded-sm text-[#00F0FF] focus:ring-0 focus:ring-offset-0" />
                  <span className="font-mono text-[10px] text-[#B9CACB] group-hover:text-[#E5E2E1] transition-colors">Reinvest Profits (Compounding)</span>
                </label>
              </div>
            </div>

            {/* Run Button (mobile) */}
            <Button
              variant="primary"
              size="lg"
              loading={isRunning}
              onClick={handleRun}
              className="w-full lg:hidden"
            >
              {running
                ? "Submitting..."
                : polling
                  ? "Running..."
                  : "Run Backtest"}
            </Button>

            {/* Live Progress Bar */}
            {polling && (
              <BacktestProgressBar
                progress={wsProgress?.progress ?? jobInfo?.progress ?? 0}
                status={wsProgress?.status ?? "RUNNING"}
              />
            )}

            {/* Error */}
            {runError && (
              <div className="rounded-sm bg-[#FFB4AB]/10 border border-[#FFB4AB]/20 p-3">
                <p className="text-xs font-mono text-[#FFB4AB]">
                  {runError}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* -- Right: Results Panel -- */}
        <div className={`${result && result.status === "COMPLETED" ? "lg:col-span-9" : "lg:col-span-8"} bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm flex flex-col overflow-hidden relative`}>
          {/* Simulation Overlay */}
          {isRunning && (
            <div className="absolute inset-0 bg-[#1C1B1B]/80 z-20 flex flex-col items-center justify-center">
              <Activity className="w-12 h-12 text-[#00F0FF] animate-pulse mb-4" />
              <h3 className="font-mono text-sm font-black tracking-widest text-[#E5E2E1] uppercase mb-2">Running Simulation</h3>
              <p className="font-mono text-[10px] text-[#B9CACB] uppercase tracking-widest">Processing candles...</p>
              <div className="w-64 h-1 bg-[#353534] mt-4 rounded-sm overflow-hidden">
                <div
                  className="h-full bg-[#00F0FF] animate-pulse"
                  style={{ width: `${Math.max((wsProgress?.progress ?? 0) * 100, 10)}%` }}
                />
              </div>
            </div>
          )}

          <div className="p-4 border-b border-[#2A2A2A]/20 flex justify-between items-center shrink-0">
            <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-[#00F0FF]" />
              Simulation Results
            </h3>
            {result && result.status !== "FAILED" && (
              <span className="text-[9px] font-mono text-[#40E56C] bg-[#40E56C]/10 px-2 py-1 rounded-sm font-bold">COMPLETED</span>
            )}
          </div>

          <div className="flex-1 overflow-auto p-4 space-y-5">
            {!result ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="w-16 h-16 rounded-sm bg-[#00F0FF]/10 flex items-center justify-center mb-4">
                  <svg
                    className="w-8 h-8 text-[#00F0FF]/40"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611l-.772.129A12.957 12.957 0 0 1 12 21a12.957 12.957 0 0 1-7.363-1.058l-.772-.129c-1.717-.293-2.299-2.379-1.067-3.61L5 14.5"
                    />
                  </svg>
                </div>
                <p className="text-sm text-[#B9CACB]/50 font-mono">
                  Configure parameters and run a backtest
                </p>
                <p className="text-xs text-[#B9CACB]/30 font-mono mt-1">
                  Results will appear here
                </p>
              </div>
            ) : result.status === "FAILED" ? (
              <div className="rounded-sm bg-[#FFB4AB]/10 border border-[#FFB4AB]/20 p-5">
                <p className="text-sm font-mono font-semibold text-[#FFB4AB] mb-2">
                  Backtest Failed
                </p>
                <p className="text-xs font-mono text-[#B9CACB]/70">
                  {result.error_message ?? "An unknown error occurred during the backtest."}
                </p>
              </div>
            ) : (
              <>
                {/* 1. Verification Badge */}
                <VerificationBadge verification={result.verification ?? null} />

                {/* 2. Metrics Grid — 4 columns x 3 rows = 12 cards */}
                <div>
                  <h4 className="font-mono text-[11px] font-black uppercase tracking-widest text-[#B9CACB] mb-3">
                    Performance Metrics
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {/* Row 1 */}
                    <MetricCard
                      label="Net Return"
                      value={result.total_return != null ? formatPnl(result.total_return) : "--"}
                      color={(result.total_return ?? 0) >= 0 ? "#40E56C" : "#FFB4AB"}
                      borderColor={(result.total_return ?? 0) >= 0 ? "#40E56C" : "#FFB4AB"}
                    />
                    <MetricCard
                      label="Annual Return"
                      value={result.annual_return != null ? formatPercent(result.annual_return * 100) : "--"}
                      color={(result.annual_return ?? 0) >= 0 ? "#40E56C" : "#FFB4AB"}
                      borderColor={(result.annual_return ?? 0) >= 0 ? "#40E56C" : "#FFB4AB"}
                    />
                    <MetricCard
                      label="Sharpe Ratio"
                      value={result.sharpe_ratio != null ? result.sharpe_ratio.toFixed(2) : "--"}
                      color={(result.sharpe_ratio ?? 0) >= 1 ? "#40E56C" : (result.sharpe_ratio ?? 0) >= 0 ? "#00F0FF" : "#FFB4AB"}
                      borderColor="#00F0FF"
                    />
                    <MetricCard
                      label="Sortino Ratio"
                      value={result.sortino_ratio != null ? result.sortino_ratio.toFixed(2) : "--"}
                      color={(result.sortino_ratio ?? 0) >= 1 ? "#40E56C" : (result.sortino_ratio ?? 0) >= 0 ? "#00F0FF" : "#FFB4AB"}
                      borderColor="#00F0FF"
                    />

                    {/* Row 2 */}
                    <MetricCard
                      label="Calmar Ratio"
                      value={
                        result.metrics?.calmar_ratio != null
                          ? (result.metrics.calmar_ratio as number).toFixed(2)
                          : result.annual_return != null && result.max_drawdown != null && result.max_drawdown > 0
                            ? (result.annual_return / result.max_drawdown).toFixed(2)
                            : "--"
                      }
                      color="#00F0FF"
                      borderColor="#00F0FF"
                    />
                    <MetricCard
                      label="Max Drawdown"
                      value={result.max_drawdown != null ? `${(result.max_drawdown * 100).toFixed(2)}%` : "--"}
                      color="#FFB4AB"
                      borderColor="#FFB4AB"
                    />
                    <MetricCard
                      label="Recovery Factor"
                      value={
                        result.metrics?.recovery_factor != null
                          ? (result.metrics.recovery_factor as number).toFixed(2)
                          : result.total_return != null && result.max_drawdown != null && result.max_drawdown > 0
                            ? (Math.abs(result.total_return) / (result.max_drawdown * (result.initial_capital ?? 10000))).toFixed(2)
                            : "--"
                      }
                      color="#00F0FF"
                      borderColor="#00F0FF"
                    />
                    <MetricCard
                      label="Profit Factor"
                      value={result.profit_factor != null ? result.profit_factor.toFixed(2) : "--"}
                      color={(result.profit_factor ?? 0) > 1 ? "#40E56C" : "#FFB4AB"}
                      borderColor={(result.profit_factor ?? 0) > 1 ? "#40E56C" : "#FFB4AB"}
                    />

                    {/* Row 3 */}
                    <MetricCard
                      label="Win Rate"
                      value={result.win_rate != null ? `${(result.win_rate * 100).toFixed(1)}%` : "--"}
                      color={(result.win_rate ?? 0) >= 0.5 ? "#40E56C" : "#FFB4AB"}
                      borderColor="#00F0FF"
                    />
                    <MetricCard
                      label="Expectancy"
                      value={
                        result.expectancy != null
                          ? `$${result.expectancy.toFixed(2)}`
                          : result.metrics?.expectancy != null
                            ? `$${(result.metrics.expectancy as number).toFixed(2)}`
                            : "--"
                      }
                      color={
                        (result.expectancy ?? result.metrics?.expectancy ?? 0) as number >= 0 ? "#40E56C" : "#FFB4AB"
                      }
                      borderColor="#00F0FF"
                    />
                    <MetricCard
                      label="Avg Holding Time"
                      value={result.avg_holding_period ?? "--"}
                      color="#E5E2E1"
                      borderColor="#B9CACB"
                    />
                    <MetricCard
                      label="Total Trades"
                      value={result.total_trades != null ? String(result.total_trades) : "--"}
                      color="#E5E2E1"
                      borderColor="#B9CACB"
                    />
                  </div>
                </div>

                {/* Trade Summary Win/Loss Bar */}
                {result.win_rate != null && result.total_trades != null && (
                  <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4">
                    <h4 className="font-mono text-[11px] font-black uppercase tracking-widest text-[#B9CACB] mb-3">
                      Trade Summary
                    </h4>
                    <WinLossBar
                      wins={Math.round(result.win_rate * result.total_trades)}
                      losses={result.total_trades - Math.round(result.win_rate * result.total_trades)}
                    />
                    <div className="mt-3 grid grid-cols-3 gap-3 text-center">
                      <div>
                        <p className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40">Final Capital</p>
                        <p className="text-sm font-mono font-semibold tabular-nums" style={{ color: (result.final_capital ?? 0) >= (result.initial_capital ?? 0) ? "#40E56C" : "#FFB4AB" }}>
                          {result.final_capital != null ? `$${result.final_capital.toLocaleString()}` : "--"}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40">Avg Win</p>
                        <p className="text-sm font-mono font-semibold tabular-nums text-[#40E56C]">
                          {result.metrics?.avg_win != null ? `$${(result.metrics.avg_win as number).toFixed(2)}` : "--"}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40">Avg Loss</p>
                        <p className="text-sm font-mono font-semibold tabular-nums text-[#FFB4AB]">
                          {result.metrics?.avg_loss != null ? `$${(result.metrics.avg_loss as number).toFixed(2)}` : "--"}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* 3. Interactive Recharts — 10 charts */}
                <BacktestCharts
                  equityCurve={result.equity_curve ?? []}
                  trades={result.trade_list ?? result.trades ?? []}
                  monthlyReturns={result.monthly_returns ?? {}}
                  initialCapital={result.initial_capital ?? 10000}
                />

                {/* Monthly Returns Heatmap (table view) */}
                {result.monthly_returns && Object.keys(result.monthly_returns).length > 0 && (
                  <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4">
                    <h4 className="font-mono text-[10px] font-bold uppercase tracking-widest text-[#B9CACB]/50 mb-3">
                      Monthly Returns Heatmap
                    </h4>
                    <MonthlyReturnsGrid monthlyReturns={result.monthly_returns} />
                  </div>
                )}

                {/* 6. Trade History Table */}
                {(() => {
                  const tradeData = result.trade_list ?? result.trades;
                  return tradeData && tradeData.length > 0 ? (
                    <div>
                      <div className="flex items-center justify-between px-1 py-2 mb-1">
                        <h4 className="font-mono text-[11px] font-black uppercase tracking-widest text-[#B9CACB]">
                          Trade History
                        </h4>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono text-[#B9CACB]/40 uppercase tracking-widest">
                            Sort by
                          </span>
                          {(["pnl", "entry_price", "quantity", "holding_periods"] as SortField[]).map((field) => (
                            <button
                              key={field}
                              onClick={() => {
                                if (sortField === field) {
                                  setSortDir((prev) => prev === "asc" ? "desc" : "asc");
                                } else {
                                  setSortField(field);
                                  setSortDir("desc");
                                }
                              }}
                              className={`px-2 py-1 rounded-sm text-[10px] font-mono transition-all duration-200 border ${
                                sortField === field
                                  ? "text-[#00F0FF] bg-[#00F0FF]/10 border-[#00F0FF]/25"
                                  : "text-[#B9CACB]/50 bg-transparent border-[#3B494B]/10 hover:border-[#B9CACB]/20"
                              }`}
                            >
                              {field === "pnl" ? "P&L" : field === "entry_price" ? "Entry" : field === "holding_periods" ? "Bars" : "Qty"}
                              {sortField === field && (sortDir === "asc" ? " \u2191" : " \u2193")}
                            </button>
                          ))}
                          {sortField && (
                            <button
                              onClick={() => setSortField(null)}
                              className="text-[10px] font-mono text-[#B9CACB]/40 hover:text-[#E5E2E1]/60 transition-colors"
                            >
                              Clear
                            </button>
                          )}
                        </div>
                      </div>
                      <DataTable<BacktestTrade & Record<string, unknown>>
                        columns={tradeColumns}
                        data={
                          (() => {
                            let trades = [...tradeData];
                            if (sortField) {
                              trades.sort((a, b) => {
                                const aVal = ((a as unknown as Record<string, unknown>)[sortField] as number) ?? 0;
                                const bVal = ((b as unknown as Record<string, unknown>)[sortField] as number) ?? 0;
                                return sortDir === "asc" ? aVal - bVal : bVal - aVal;
                              });
                            }
                            return trades.slice(0, 50).map((t) => ({
                              ...t,
                            })) as (BacktestTrade & Record<string, unknown>)[];
                          })()
                        }
                        emptyMessage="No trades"
                      />
                      {tradeData.length > 50 && (
                        <p className="text-center text-xs font-mono text-[#B9CACB]/40 mt-3">
                          Showing 50 of {tradeData.length} trades
                        </p>
                      )}
                    </div>
                  ) : null;
                })()}

                {/* Configuration summary */}
                <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4">
                  <h4 className="font-mono text-[11px] font-black uppercase tracking-widest text-[#B9CACB] mb-3">Configuration</h4>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40 mb-1">
                        Strategy
                      </p>
                      <p className="text-sm font-mono capitalize text-[#E5E2E1]/80">
                        {result.strategy_name.replace(/_/g, " ")}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40 mb-1">
                        Symbol
                      </p>
                      <p className="text-sm font-mono text-[#E5E2E1]/80">
                        {result.symbol}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40 mb-1">
                        Timeframe
                      </p>
                      <p className="text-sm font-mono text-[#E5E2E1]/80">
                        {result.timeframe}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40 mb-1">
                        Initial Capital
                      </p>
                      <p className="text-sm font-mono text-[#E5E2E1]/80">
                        {result.initial_capital != null ? `$${result.initial_capital.toLocaleString()}` : "--"}
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* -- Bottom: Backtest History -- */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-mono text-sm font-black tracking-widest text-[#E5E2E1] uppercase">
            Backtest History
          </h2>
          {compareIds.size >= 2 && (
            <button
              onClick={() => {
                const idsParam = Array.from(compareIds).join(",");
                router.push(`/backtest/compare?ids=${idsParam}`);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-sm text-xs font-mono font-bold uppercase tracking-wider bg-[#00F0FF]/15 text-[#00F0FF] border border-[#00F0FF]/30 hover:bg-[#00F0FF]/25 transition-colors"
            >
              <GitCompareArrows className="w-4 h-4" />
              Compare Selected ({compareIds.size})
            </button>
          )}
        </div>
        {historyLoading ? (
          <div className="flex items-center justify-center py-12">
            <div
              className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin"
              style={{
                borderColor: "#00F0FF",
                borderTopColor: "transparent",
              }}
            />
            <span className="ml-3 font-mono text-sm text-[#B9CACB]/50">
              Loading history...
            </span>
          </div>
        ) : (
          <DataTable<BacktestHistoryEntry & Record<string, unknown>>
            columns={[
              {
                key: "_compare",
                label: "",
                render: (row) => {
                  const entry = row as unknown as BacktestHistoryEntry;
                  return (
                    <input
                      type="checkbox"
                      checked={compareIds.has(entry.id)}
                      onChange={() => toggleCompareId(entry.id)}
                      onClick={(e: MouseEvent) => e.stopPropagation()}
                      className="w-3.5 h-3.5 rounded-sm bg-[#2A2A2A] border-[#3B494B]/40 text-[#00F0FF] focus:ring-0 focus:ring-offset-0 cursor-pointer accent-[#00F0FF]"
                    />
                  );
                },
              },
              ...historyColumns,
            ] as Column<BacktestHistoryEntry & Record<string, unknown>>[]}
            data={
              (history ?? []).map((h) => ({
                ...h,
              })) as (BacktestHistoryEntry & Record<string, unknown>)[]
            }
            onRowClick={(row) =>
              handleHistoryClick(row as unknown as BacktestHistoryEntry)
            }
            emptyMessage="No previous backtests"
          />
        )}
      </div>
    </div>
  );
}
