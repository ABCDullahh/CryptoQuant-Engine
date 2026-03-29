"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  LineChart as LineChartIcon,
  Download,
  Calendar,
  TrendingUp,
  Activity,
  Target,
  Shield,
  BarChart3,
  AlertTriangle,
  ChevronDown,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  PieChart,
  Pie,
} from "recharts";
import { GradeBadge } from "@/components/ui/Badge";
import { DirectionBadge } from "@/components/ui/Badge";
import { usePolling, useWebSocket } from "@/hooks/useApi";
import {
  fetchLivePerformance,
  fetchSignals,
  fetchSignalHistory,
  type LivePerformance,
  type Signal,
} from "@/lib/api";
import { formatPrice, formatPnl, timeAgo } from "@/lib/utils";

// =============================================================================
// Time Range Filter
// =============================================================================
type TimeRange = "30d" | "90d" | "ytd" | "all";

function timeRangeToDays(range: TimeRange): number {
  switch (range) {
    case "30d":
      return 30;
    case "90d":
      return 90;
    case "ytd": {
      const now = new Date();
      const jan1 = new Date(now.getFullYear(), 0, 1);
      return Math.ceil((now.getTime() - jan1.getTime()) / 86400000);
    }
    case "all":
      return 365;
  }
}

// =============================================================================
// Custom Tooltip — Quant Obsidian Style
// =============================================================================
function ObsidianTooltip({
  active,
  payload,
  label,
  formatter,
}: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string; dataKey: string }>;
  label?: string;
  formatter?: (value: number, name: string) => [string, string];
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="bg-[#1C1B1B] border border-[#3B494B]/40 rounded-sm px-3 py-2 shadow-lg">
      {label && (
        <p className="font-mono text-[10px] text-[#B9CACB] mb-1">{label}</p>
      )}
      {payload.map((entry, i) => {
        const [val, name] = formatter
          ? formatter(entry.value, entry.name)
          : [String(entry.value), entry.name];
        return (
          <p
            key={i}
            className="font-mono text-xs font-bold tabular-nums"
            style={{ color: entry.color || "#00F0FF" }}
          >
            {name}: {val}
          </p>
        );
      })}
    </div>
  );
}

// =============================================================================
// Equity Growth Curve — Recharts AreaChart
// =============================================================================
function EquityCurve({
  equityCurve,
}: {
  equityCurve: LivePerformance["equity_curve"];
}) {
  const chartData = useMemo(() => {
    if (!equityCurve || equityCurve.length === 0) return [];
    return equityCurve.map((pt) => ({
      date: pt.date
        ? new Date(pt.date).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
          })
        : "",
      balance: pt.balance,
      trade_pnl: pt.trade_pnl,
    }));
  }, [equityCurve]);

  if (chartData.length === 0) {
    return (
      <section className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10 h-80 flex flex-col items-center justify-center">
        <h3 className="font-mono text-xs font-black tracking-widest text-[#00F0FF] uppercase mb-4">
          Equity Growth Curve
        </h3>
        <span className="text-[#B9CACB]/40 font-mono text-xs">
          No equity data
        </span>
      </section>
    );
  }

  const balances = chartData.map((d) => d.balance);
  const yMin = Math.min(...balances);
  const yMax = Math.max(...balances);
  const yPadding = (yMax - yMin) * 0.1 || 10;

  return (
    <section className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10 h-80 flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-mono text-xs font-black tracking-widest text-[#00F0FF] uppercase">
          Equity Growth Curve
        </h3>
        <div className="flex items-center gap-2 text-[9px] font-mono text-[#B9CACB]/60">
          <span>
            {formatPnl(yMin)} &mdash; {formatPnl(yMax)}
          </span>
        </div>
      </div>
      <div className="flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chartData}
            margin={{ top: 5, right: 10, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00F0FF" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#00F0FF" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#2A2A2A"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tick={{ fill: "#B9CACB", fontSize: 9, fontFamily: "monospace" }}
              tickLine={false}
              axisLine={{ stroke: "#2A2A2A" }}
              interval="preserveStartEnd"
              minTickGap={40}
            />
            <YAxis
              domain={[yMin - yPadding, yMax + yPadding]}
              tick={{ fill: "#B9CACB", fontSize: 9, fontFamily: "monospace" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `$${v.toFixed(0)}`}
              width={55}
            />
            <RechartsTooltip
              content={
                <ObsidianTooltip
                  formatter={(value, name) => {
                    if (name === "balance")
                      return [formatPnl(value), "Balance"];
                    return [formatPnl(value), "Trade P&L"];
                  }}
                />
              }
              cursor={{ stroke: "#00F0FF", strokeWidth: 1, strokeDasharray: "4 4" }}
            />
            <Area
              type="monotone"
              dataKey="balance"
              stroke="#00F0FF"
              strokeWidth={2}
              fill="url(#equityGrad)"
              dot={chartData.length <= 50 ? { r: 2, fill: "#00F0FF", strokeWidth: 0 } : false}
              activeDot={{ r: 5, fill: "#00F0FF", stroke: "#0D0D0D", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

// =============================================================================
// Win/Loss Donut — Recharts PieChart with Active Sector
// =============================================================================
function WinLossDonut({
  wins,
  losses,
  winRate,
}: {
  wins: number;
  losses: number;
  winRate: number;
}) {
  const safeWins = wins ?? 0;
  const safeLosses = losses ?? 0;
  const safeWinRate = winRate ?? 0;

  const pieData = useMemo(() => {
    if (safeWins === 0 && safeLosses === 0) {
      return [{ name: "No Data", value: 1, fill: "#353534" }];
    }
    return [
      { name: "Wins", value: safeWins, fill: "#40E56C" },
      { name: "Losses", value: safeLosses, fill: "#FFB4AB" },
    ];
  }, [safeWins, safeLosses]);

  return (
    <section className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10">
      <h3 className="font-mono text-[10px] font-black tracking-widest text-[#B9CACB] uppercase mb-2">
        Win/Loss Distribution
      </h3>
      <div className="relative h-44 flex items-center justify-center">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              innerRadius={38}
              outerRadius={58}
              dataKey="value"
              stroke="none"
              style={{ cursor: "pointer" }}
            >
              {pieData.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
              ))}
            </Pie>
            <RechartsTooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const d = payload[0];
                return (
                  <div className="bg-[#1C1B1B] border border-[#3B494B]/40 rounded-sm px-3 py-2 shadow-lg">
                    <p
                      className="font-mono text-xs font-bold"
                      style={{ color: (d.payload as Record<string, string>)?.fill || "#E5E2E1" }}
                    >
                      {d.name}: {d.value} trades
                    </p>
                  </div>
                );
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="font-mono text-lg font-black text-[#E5E2E1]">
            {(safeWinRate * 100).toFixed(1)}%
          </span>
          <span className="text-[8px] font-mono text-[#B9CACB] uppercase">
            Win Rate
          </span>
        </div>
      </div>
      <div className="flex justify-center gap-4 mt-2 text-[10px] font-mono text-[#B9CACB]">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 bg-[#40E56C] rounded-full" />
          Win ({safeWins})
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 bg-[#FFB4AB] rounded-full" />
          Loss ({safeLosses})
        </div>
      </div>
    </section>
  );
}

// =============================================================================
// P&L Distribution Histogram — Recharts BarChart
// =============================================================================
function PnlHistogram({ tradePnls }: { tradePnls: number[] }) {
  const safePnls = tradePnls ?? [];

  const buckets = useMemo(() => {
    if (safePnls.length === 0) return [];

    const min = Math.min(...safePnls);
    const max = Math.max(...safePnls);
    const numBins = Math.min(15, Math.max(5, safePnls.length));

    if (min === max) {
      return [
        {
          range: formatPnl(min),
          count: safePnls.length,
          positive: min >= 0,
          pnl: min,
        },
      ];
    }

    const binWidth = (max - min) / numBins;
    const bins = new Array(numBins).fill(0);

    safePnls.forEach((pnl) => {
      let idx = Math.floor((pnl - min) / binWidth);
      if (idx >= numBins) idx = numBins - 1;
      bins[idx]++;
    });

    return bins.map((count, i) => {
      const binCenter = min + (i + 0.5) * binWidth;
      return {
        range: formatPnl(binCenter),
        count,
        positive: binCenter >= 0,
        pnl: binCenter,
      };
    });
  }, [safePnls]);

  if (safePnls.length === 0) {
    return (
      <section className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10">
        <h3 className="font-mono text-[10px] font-black tracking-widest text-[#B9CACB] uppercase mb-4">
          P&L Distribution
        </h3>
        <div className="h-40 flex items-center justify-center">
          <span className="text-[#B9CACB]/40 font-mono text-xs">
            No trade data
          </span>
        </div>
      </section>
    );
  }

  return (
    <section className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10">
      <h3 className="font-mono text-[10px] font-black tracking-widest text-[#B9CACB] uppercase mb-2">
        P&L Distribution
      </h3>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={buckets}
            margin={{ top: 5, right: 5, left: 5, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#2A2A2A"
              vertical={false}
            />
            <XAxis
              dataKey="range"
              tick={{ fill: "#B9CACB", fontSize: 8, fontFamily: "monospace" }}
              tickLine={false}
              axisLine={{ stroke: "#2A2A2A" }}
              interval="preserveStartEnd"
            />
            <YAxis hide />
            <RechartsTooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const d = payload[0].payload as { range: string; count: number; pnl: number };
                return (
                  <div className="bg-[#1C1B1B] border border-[#3B494B]/40 rounded-sm px-3 py-2 shadow-lg">
                    <p className="font-mono text-[10px] text-[#B9CACB]">
                      Range: {d.range}
                    </p>
                    <p className="font-mono text-xs font-bold text-[#00F0FF]">
                      {d.count} trade{d.count !== 1 ? "s" : ""}
                    </p>
                  </div>
                );
              }}
              cursor={{ fill: "rgba(0, 240, 255, 0.05)" }}
            />
            <Bar dataKey="count" radius={[2, 2, 0, 0]}>
              {buckets.map((entry, i) => (
                <Cell
                  key={i}
                  fill={
                    entry.positive
                      ? "rgba(64, 229, 108, 0.75)"
                      : "rgba(255, 180, 171, 0.75)"
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

// =============================================================================
// Monthly Returns — Recharts BarChart
// =============================================================================
function MonthlyReturnsChart({
  monthlyReturns,
}: {
  monthlyReturns: LivePerformance["monthly_returns"];
}) {
  const chartData = useMemo(() => {
    if (!monthlyReturns || monthlyReturns.length === 0) return [];

    return monthlyReturns.map((mr) => {
      let label = mr.month;
      if (mr.month.includes("-")) {
        const parts = mr.month.split("-");
        const monthIdx = parseInt(parts[1], 10) - 1;
        const monthNames = [
          "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ];
        label = monthNames[monthIdx] ?? mr.month;
      }
      return {
        month: label,
        pnl: mr.pnl,
        positive: mr.pnl >= 0,
      };
    });
  }, [monthlyReturns]);

  if (chartData.length === 0) {
    return (
      <section className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10">
        <h3 className="font-mono text-[10px] font-black tracking-widest text-[#B9CACB] uppercase mb-4 flex items-center gap-2">
          <Calendar className="w-3 h-3" />
          Monthly Returns
        </h3>
        <div className="h-48 flex items-center justify-center">
          <span className="text-[#B9CACB]/40 font-mono text-xs">
            No monthly data
          </span>
        </div>
      </section>
    );
  }

  return (
    <section className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10">
      <h3 className="font-mono text-[10px] font-black tracking-widest text-[#B9CACB] uppercase mb-2 flex items-center gap-2">
        <Calendar className="w-3 h-3" />
        Monthly Returns
      </h3>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 5, right: 5, left: 0, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#2A2A2A"
              vertical={false}
            />
            <XAxis
              dataKey="month"
              tick={{ fill: "#B9CACB", fontSize: 9, fontFamily: "monospace" }}
              tickLine={false}
              axisLine={{ stroke: "#2A2A2A" }}
            />
            <YAxis
              tick={{ fill: "#B9CACB", fontSize: 9, fontFamily: "monospace" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `$${v}`}
              width={50}
            />
            <RechartsTooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const d = payload[0].payload as { month: string; pnl: number };
                return (
                  <div className="bg-[#1C1B1B] border border-[#3B494B]/40 rounded-sm px-3 py-2 shadow-lg">
                    <p className="font-mono text-[10px] text-[#B9CACB]">
                      {d.month}
                    </p>
                    <p
                      className="font-mono text-sm font-bold tabular-nums"
                      style={{ color: d.pnl >= 0 ? "#40E56C" : "#FFB4AB" }}
                    >
                      {formatPnl(d.pnl)}
                    </p>
                  </div>
                );
              }}
              cursor={{ fill: "rgba(0, 240, 255, 0.05)" }}
            />
            <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
              {chartData.map((entry, i) => (
                <Cell
                  key={i}
                  fill={entry.positive ? "#40E56C" : "#FFB4AB"}
                  fillOpacity={0.8}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

// =============================================================================
// Key Statistics — REAL data from API
// =============================================================================
function KeyStatistics({ data }: { data: LivePerformance }) {
  const stats = useMemo(() => {
    const sharpe = data?.sharpe_ratio ?? 0;
    const sortino = data?.sortino_ratio ?? 0;
    const maxDd = data?.max_drawdown_pct ?? 0;
    const pf = data?.profit_factor ?? 0;
    const avgWin = data?.avg_win ?? 0;
    const avgLoss = data?.avg_loss ?? 0;
    const best = data?.best_trade ?? 0;
    const worst = data?.worst_trade ?? 0;
    const expect = data?.expectancy ?? 0;
    const holdHrs = data?.avg_holding_hours ?? 0;

    return [
      {
        label: "Sharpe Ratio",
        val: sharpe.toFixed(2),
        color:
          sharpe >= 1
            ? "#40E56C"
            : sharpe >= 0
              ? "#E5E2E1"
              : "#FFB4AB",
      },
      {
        label: "Sortino Ratio",
        val: sortino.toFixed(2),
        color:
          sortino >= 1
            ? "#40E56C"
            : sortino >= 0
              ? "#E5E2E1"
              : "#FFB4AB",
      },
      {
        label: "Max Drawdown",
        val: `-${maxDd.toFixed(2)}%`,
        color: "#FFB4AB",
      },
      {
        label: "Profit Factor",
        val: pf.toFixed(2),
        color: pf >= 1 ? "#40E56C" : "#FFB4AB",
      },
      {
        label: "Avg Win",
        val: formatPnl(avgWin),
        color: "#40E56C",
      },
      {
        label: "Avg Loss",
        val: formatPnl(avgLoss),
        color: "#FFB4AB",
      },
      {
        label: "Best Trade",
        val: formatPnl(best),
        color: "#40E56C",
      },
      {
        label: "Worst Trade",
        val: formatPnl(worst),
        color: "#FFB4AB",
      },
      {
        label: "Expectancy",
        val: formatPnl(expect),
        color: expect >= 0 ? "#40E56C" : "#FFB4AB",
      },
      {
        label: "Avg Holding",
        val: `${holdHrs.toFixed(1)}h`,
        color: "#E5E2E1",
      },
    ];
  }, [data]);

  return (
    <section className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10">
      <h3 className="font-mono text-[10px] font-black tracking-widest text-[#B9CACB] uppercase mb-4">
        Key Statistics
      </h3>
      <div className="space-y-3">
        {stats.map((stat, i) => (
          <div
            key={i}
            className="flex justify-between items-center border-b border-[#3B494B]/10 pb-2 last:border-0 last:pb-0"
          >
            <span className="text-[10px] font-mono text-[#B9CACB]">
              {stat.label}
            </span>
            <span
              className="text-[11px] font-mono font-bold tabular-nums"
              style={{ color: stat.color }}
            >
              {stat.val}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

// =============================================================================
// Compact Stat Card (top row)
// =============================================================================
function StatCard({
  icon,
  label,
  value,
  valueColor,
  accentColor,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  valueColor?: string;
  accentColor?: string;
}) {
  return (
    <div
      className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm px-3 py-2 flex items-center gap-2.5 min-w-0"
      style={{ borderLeftWidth: "2px", borderLeftColor: accentColor || "#3B494B" }}
    >
      <span className="text-[#00F0FF]/60 shrink-0">{icon}</span>
      <div className="min-w-0">
        <div className="text-[9px] font-mono text-[#B9CACB]/60 uppercase tracking-widest truncate">
          {label}
        </div>
        <div
          className="font-mono text-sm font-black tabular-nums tracking-tight truncate"
          style={{ color: valueColor || "#E5E2E1" }}
        >
          {value}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Loading Skeleton
// =============================================================================
function AnalyticsSkeleton() {
  return (
    <div className="p-4 md:p-6 space-y-6 max-w-[1600px] mx-auto pb-20 md:pb-6 animate-pulse">
      <div className="h-8 w-64 bg-[#1C1B1B] rounded-sm" />
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-16 bg-[#1C1B1B] rounded-sm" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="h-80 bg-[#1C1B1B] rounded-sm" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="h-52 bg-[#1C1B1B] rounded-sm" />
            <div className="h-52 bg-[#1C1B1B] rounded-sm" />
          </div>
        </div>
        <div className="space-y-6">
          <div className="h-52 bg-[#1C1B1B] rounded-sm" />
          <div className="h-80 bg-[#1C1B1B] rounded-sm" />
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Analytics Page
// =============================================================================

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>("all");

  const {
    data: perfData,
    loading: perfLoading,
    error: perfError,
    refetch: refetchPerf,
  } = usePolling(
    () => fetchLivePerformance(timeRangeToDays(timeRange)),
    30_000,
    [timeRange]
  );

  const {
    data: history,
    loading: histLoading,
    error: histError,
    refetch: refetchHistory,
  } = usePolling(
    async () => {
      const [active, closed] = await Promise.all([
        fetchSignals(),
        fetchSignalHistory(),
      ]);
      const map = new Map<string, Signal>();
      for (const s of active) map.set(s.id, s);
      for (const s of closed) map.set(s.id, s);
      return Array.from(map.values());
    },
    15_000,
    []
  );

  useWebSocket(
    "signal_new",
    useCallback(() => {
      refetchHistory();
    }, [refetchHistory])
  );

  useWebSocket(
    "position_update",
    useCallback(() => {
      refetchPerf();
    }, [refetchPerf])
  );

  const trades = history ?? (histError ? [] : null);

  useEffect(() => {
    if (perfError) console.error("Failed to fetch live performance:", perfError);
  }, [perfError]);

  useEffect(() => {
    if (histError) console.error("Failed to fetch signal history:", histError);
  }, [histError]);

  const filteredTrades = useMemo(() => {
    if (!trades) return [];
    const now = Date.now();
    return trades.filter((t) => {
      if (!t.created_at) return true;
      const created = new Date(t.created_at).getTime();
      switch (timeRange) {
        case "30d":
          return now - created < 30 * 86400000;
        case "90d":
          return now - created < 90 * 86400000;
        case "ytd": {
          const jan1 = new Date(new Date().getFullYear(), 0, 1).getTime();
          return created >= jan1;
        }
        case "all":
        default:
          return true;
      }
    });
  }, [trades, timeRange]);

  const [expandedSignalId, setExpandedSignalId] = useState<string | null>(null);

  const sortedTrades = filteredTrades
    ? [...filteredTrades].sort(
        (a, b) =>
          (new Date(b.created_at ?? "").getTime() || 0) -
          (new Date(a.created_at ?? "").getTime() || 0)
      )
    : [];

  // ---------- Loading State ----------
  if (perfLoading && !perfData) {
    return <AnalyticsSkeleton />;
  }

  // ---------- Error State ----------
  if (perfError && !perfData) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <AlertTriangle className="w-12 h-12 text-[#FFB4AB]/40" />
        <h3 className="font-mono font-bold text-lg text-[#E5E2E1]">
          Failed to Load Analytics
        </h3>
        <p className="text-[#B9CACB] text-sm text-center max-w-md">
          {perfError}
        </p>
        <button
          onClick={refetchPerf}
          className="bg-[#201F1F] text-[#00F0FF] font-mono text-xs px-4 py-2 rounded-sm border border-[#00F0FF]/20 hover:border-[#00F0FF]/50 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  const data = perfData;

  // ---------- No Data State ----------
  if (data && !data.has_data) {
    return (
      <div className="p-4 md:p-6 space-y-6 max-w-[1600px] mx-auto pb-20 md:pb-6">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-2">
          <div>
            <h2 className="font-mono text-lg font-black tracking-tighter text-[#E5E2E1] uppercase flex items-center gap-2">
              <LineChartIcon className="w-5 h-5 text-[#00F0FF]" />
              Performance Analytics
            </h2>
            <p className="text-[10px] font-mono text-[#B9CACB] uppercase tracking-widest">
              Real-Time Analysis & Metrics
            </p>
          </div>
          <div className="flex gap-2">
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value as TimeRange)}
              className="bg-[#201F1F] text-[#E5E2E1] font-mono text-[10px] px-3 py-1.5 rounded-sm outline-none border border-[#3B494B]/20 focus:border-[#00F0FF]/30"
            >
              <option value="30d">Last 30 Days</option>
              <option value="90d">Last 90 Days</option>
              <option value="ytd">Year to Date</option>
              <option value="all">All Time</option>
            </select>
          </div>
        </div>

        <div className="flex flex-col items-center justify-center py-24">
          <LineChartIcon className="w-16 h-16 text-[#B9CACB]/20 mb-4" />
          <h3 className="font-mono font-bold text-lg text-[#E5E2E1] mb-2">
            No Performance Data Yet
          </h3>
          <p className="text-[#B9CACB] text-sm text-center max-w-md">
            {data.message ||
              "Run a backtest or wait for live trades to close to see real analytics."}
          </p>
        </div>

        {sortedTrades.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase">
                Signal History
              </h2>
              <span className="text-[10px] font-mono text-[#B9CACB]/40 tabular-nums">
                {sortedTrades.length} signals
              </span>
            </div>
            <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-4 space-y-2">
              {sortedTrades.slice(0, 10).map((sig) => (
                <div key={sig.id} className="flex items-center justify-between text-xs font-mono py-1 border-b border-[#2A2A2A]/10 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[#E5E2E1]">{sig.symbol}</span>
                    <DirectionBadge direction={sig.direction} size="sm" />
                    <GradeBadge grade={sig.signal_grade} size="sm" />
                  </div>
                  <div className="flex items-center gap-3 text-[#B9CACB]/60">
                    <span>{sig.status}</span>
                    <span>{sig.created_at ? timeAgo(sig.created_at) : "--"}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  if (!data || !data.has_data) {
    return (
      <div className="flex items-center justify-center h-96">
        <span className="font-mono text-sm text-[#B9CACB]/40">Loading analytics...</span>
      </div>
    );
  }

  // ---------- Main Render (has_data === true) ----------
  return (
    <div className="p-4 md:p-6 space-y-6 max-w-[1600px] mx-auto pb-20 md:pb-6">
      {/* ===== Header ===== */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-2">
        <div>
          <h2 className="font-mono text-lg font-black tracking-tighter text-[#E5E2E1] uppercase flex items-center gap-2">
            <LineChartIcon className="w-5 h-5 text-[#00F0FF]" />
            Performance Analytics
          </h2>
          <p className="text-[10px] font-mono text-[#B9CACB] uppercase tracking-widest">
            Real-Time Analysis & Metrics
          </p>
        </div>
        <div className="flex gap-2">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as TimeRange)}
            className="bg-[#201F1F] text-[#E5E2E1] font-mono text-[10px] px-3 py-1.5 rounded-sm outline-none border border-[#3B494B]/20 focus:border-[#00F0FF]/30"
          >
            <option value="30d">Last 30 Days</option>
            <option value="90d">Last 90 Days</option>
            <option value="ytd">Year to Date</option>
            <option value="all">All Time</option>
          </select>
          <button
            className="bg-[#201F1F] text-[#B9CACB] hover:text-[#E5E2E1] p-1.5 rounded-sm border border-[#3B494B]/20 transition-colors duration-150"
            title="Download report as CSV"
            onClick={() => {
              if (!data || !data.has_data) return;
              const rows = [
                ["Metric", "Value"],
                ["Total P&L", String(data.total_pnl ?? 0)],
                ["Win Rate", String(data.win_rate ?? 0)],
                ["Total Trades", String(data.total_trades ?? 0)],
                ["Wins", String(data.wins ?? 0)],
                ["Losses", String(data.losses ?? 0)],
                ["Profit Factor", String(data.profit_factor ?? 0)],
                ["Sharpe Ratio", String(data.sharpe_ratio ?? 0)],
                ["Sortino Ratio", String(data.sortino_ratio ?? 0)],
                ["Max Drawdown %", String(data.max_drawdown_pct ?? 0)],
                ["Expectancy", String(data.expectancy ?? 0)],
                ["Best Trade", String(data.best_trade ?? 0)],
                ["Worst Trade", String(data.worst_trade ?? 0)],
                ["Total Fees", String(data.total_fees ?? 0)],
              ];
              const csv = rows.map((r) => r.join(",")).join("\n");
              const blob = new Blob([csv], { type: "text/csv" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `analytics-report-${timeRange}.csv`;
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ===== Key Metrics Row ===== */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatCard
          icon={<TrendingUp size={16} />}
          label="Total P&L"
          value={formatPnl(data.total_pnl ?? 0)}
          valueColor={(data.total_pnl ?? 0) >= 0 ? "#40E56C" : "#FFB4AB"}
          accentColor={(data.total_pnl ?? 0) >= 0 ? "#40E56C" : "#FFB4AB"}
        />
        <StatCard
          icon={<Target size={16} />}
          label="Win Rate"
          value={`${((data.win_rate ?? 0) * 100).toFixed(1)}%`}
          valueColor="#00F0FF"
          accentColor="#00F0FF"
        />
        <StatCard
          icon={<Activity size={16} />}
          label="Total Trades"
          value={String(data.total_trades ?? 0)}
          accentColor="#B9CACB"
        />
        <StatCard
          icon={<BarChart3 size={16} />}
          label="Wins / Losses"
          value={`${data.wins ?? 0} / ${data.losses ?? 0}`}
          valueColor="#E5E2E1"
          accentColor="#40E56C"
        />
        <StatCard
          icon={<Shield size={16} />}
          label="Profit Factor"
          value={(data.profit_factor ?? 0).toFixed(2)}
          valueColor={(data.profit_factor ?? 0) >= 1 ? "#40E56C" : "#FFB4AB"}
          accentColor={(data.profit_factor ?? 0) >= 1 ? "#40E56C" : "#FFB4AB"}
        />
      </div>

      {/* ===== Main 3-Column Grid ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* -- Left: Charts (col-span-2) -- */}
        <div className="lg:col-span-2 space-y-6">
          <EquityCurve equityCurve={data.equity_curve ?? []} />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <WinLossDonut
              wins={data.wins ?? 0}
              losses={data.losses ?? 0}
              winRate={data.win_rate ?? 0}
            />
            <PnlHistogram tradePnls={data.trade_pnls ?? []} />
          </div>
        </div>

        {/* -- Right: Stats Sidebar (col-span-1) -- */}
        <div className="space-y-6">
          <MonthlyReturnsChart monthlyReturns={data.monthly_returns ?? []} />
          <KeyStatistics data={data} />
        </div>
      </div>

      {/* ===== Signal History Table (Expandable) ===== */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase">
            Signal History
          </h2>
          <span className="text-[10px] font-mono text-[#B9CACB]/40 tabular-nums">
            {sortedTrades.length} signals
          </span>
        </div>
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px] border-collapse text-[12px]">
              <thead>
                <tr className="border-b border-[#2A2A2A]/20">
                  {["Symbol","Dir","Grade","Strategy","Entry","SL","TP1","R:R","Strength","ML","Outcome","Status","Time",""].map((h) => (
                    <th key={h} className="px-3 py-2.5 text-[9px] font-mono font-semibold uppercase tracking-widest text-[#B9CACB]/60 bg-[#201F1F]/50 text-left">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2A2A2A]/5">
                {sortedTrades.length === 0 ? (
                  <tr><td colSpan={14} className="px-4 py-12 text-center text-sm text-[#B9CACB]/40">No signal history available</td></tr>
                ) : sortedTrades.map((sig) => {
                  const isExpanded = expandedSignalId === sig.id;
                  const topStrategy = sig.strategy_scores
                    ? Object.entries(sig.strategy_scores).sort(([,a],[,b]) => Number(b) - Number(a))[0]?.[0]
                    : null;
                  const entry = sig.entry_price;
                  const sl = sig.stop_loss;
                  const tp1 = sig.tp1_price;
                  let rr: number | null = null;
                  if (entry && sl && entry !== sl && tp1) {
                    rr = Math.abs(tp1 - entry) / Math.abs(entry - sl);
                  }
                  return (
                    <React.Fragment key={sig.id}>
                      <tr
                        className="hover:bg-[#2A2A2A]/40 transition-colors cursor-pointer"
                        onClick={() => setExpandedSignalId(isExpanded ? null : sig.id)}
                      >
                        <td className="px-3 py-2.5 font-mono font-medium text-[#E5E2E1]">{sig.symbol}</td>
                        <td className="px-3 py-2.5"><DirectionBadge direction={sig.direction} size="sm" /></td>
                        <td className="px-3 py-2.5"><GradeBadge grade={sig.signal_grade} size="sm" /></td>
                        <td className="px-3 py-2.5">
                          {topStrategy ? (
                            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-[#00F0FF]/8 text-[#00F0FF] border border-[#00F0FF]/15">{topStrategy}</span>
                          ) : <span className="text-[#B9CACB]/20">&mdash;</span>}
                        </td>
                        <td className="px-3 py-2.5 font-mono tabular-nums text-[#E5E2E1]/85">{entry != null ? formatPrice(entry, entry < 10 ? 4 : 2) : "--"}</td>
                        <td className="px-3 py-2.5 font-mono tabular-nums text-[#FFB4AB]/80">{sl != null ? formatPrice(sl, sl < 10 ? 4 : 2) : "--"}</td>
                        <td className="px-3 py-2.5 font-mono tabular-nums text-[#40E56C]/80">{tp1 != null ? formatPrice(tp1, tp1 < 10 ? 4 : 2) : "--"}</td>
                        <td className="px-3 py-2.5 font-mono tabular-nums">
                          {rr != null ? (
                            <span className={`font-bold ${rr >= 2 ? "text-[#40E56C]" : rr >= 1 ? "text-[#E5E2E1]" : "text-[#FFB4AB]"}`}>1:{rr.toFixed(1)}</span>
                          ) : <span className="text-[#B9CACB]/20">&mdash;</span>}
                        </td>
                        <td className="px-3 py-2.5 font-mono tabular-nums text-[#E5E2E1]/85">
                          {sig.signal_strength != null ? `${(sig.signal_strength * 100).toFixed(0)}%` : "--"}
                        </td>
                        <td className="px-3 py-2.5 font-mono tabular-nums text-[#E5E2E1]/70">
                          {sig.ml_confidence != null ? `${(sig.ml_confidence * 100).toFixed(0)}%` : "--"}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="font-mono text-xs font-semibold" style={{
                            color: sig.outcome === "WIN" ? "#40E56C" : sig.outcome === "LOSS" ? "#FFB4AB" : "rgba(185,202,203,0.5)"
                          }}>{sig.outcome ?? "--"}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-sm ${
                            sig.status === "EXECUTED" ? "bg-[#40E56C]/10 text-[#40E56C]" :
                            sig.status === "REJECTED" ? "bg-[#FFB4AB]/10 text-[#FFB4AB]" :
                            sig.status === "ACTIVE" ? "bg-[#00F0FF]/10 text-[#00F0FF]" :
                            "bg-[#B9CACB]/10 text-[#B9CACB]/60"
                          }`}>{sig.status}</span>
                        </td>
                        <td className="px-3 py-2.5 font-mono text-xs text-[#B9CACB]/45">{sig.created_at ? timeAgo(sig.created_at) : "--"}</td>
                        <td className="px-3 py-2.5">
                          <ChevronDown size={12} className={`text-[#B9CACB]/30 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr>
                          <td colSpan={14} className="px-4 py-3 bg-[#181818]">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-[11px] font-mono">
                              {/* Price Levels */}
                              <div className="space-y-1.5">
                                <div className="text-[9px] font-bold uppercase tracking-widest text-[#B9CACB]/50 mb-2">Price Levels</div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Entry</span><span className="text-[#E5E2E1] tabular-nums">{entry != null ? formatPrice(entry) : "--"}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Stop Loss</span><span className="text-[#FFB4AB] tabular-nums">{sl != null ? formatPrice(sl) : "--"}</span></div>
                                {sig.tp1_price && <div className="flex justify-between"><span className="text-[#B9CACB]">TP1</span><span className="text-[#40E56C] tabular-nums">{formatPrice(sig.tp1_price)}</span></div>}
                                {sig.tp2_price && <div className="flex justify-between"><span className="text-[#B9CACB]">TP2</span><span className="text-[#40E56C] tabular-nums">{formatPrice(sig.tp2_price)}</span></div>}
                                {sig.tp3_price && <div className="flex justify-between"><span className="text-[#B9CACB]">TP3</span><span className="text-[#40E56C] tabular-nums">{formatPrice(sig.tp3_price)}</span></div>}
                                <div className="flex justify-between"><span className="text-[#B9CACB]">SL Type</span><span className="text-[#00F0FF]">{sig.sl_type ?? "--"}</span></div>
                              </div>
                              {/* Signal Quality */}
                              <div className="space-y-1.5">
                                <div className="text-[9px] font-bold uppercase tracking-widest text-[#B9CACB]/50 mb-2">Signal Quality</div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Grade</span><span className="text-[#E5E2E1]">{sig.signal_grade}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Strength</span><span className="text-[#E5E2E1]">{sig.signal_strength != null ? `${(sig.signal_strength * 100).toFixed(1)}%` : "--"}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">ML Confidence</span><span className="text-[#E5E2E1]">{sig.ml_confidence != null ? `${(sig.ml_confidence * 100).toFixed(1)}%` : "--"}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Leverage</span><span className="text-[#00F0FF]">{sig.leverage}x</span></div>
                                {rr != null && <div className="flex justify-between"><span className="text-[#B9CACB]">Risk:Reward</span><span className={rr >= 2 ? "text-[#40E56C] font-bold" : "text-[#E5E2E1]"}>1:{rr.toFixed(2)}</span></div>}
                              </div>
                              {/* Strategy Scores */}
                              <div className="space-y-1.5">
                                <div className="text-[9px] font-bold uppercase tracking-widest text-[#B9CACB]/50 mb-2">Strategy Scores</div>
                                {sig.strategy_scores && Object.entries(sig.strategy_scores).sort(([,a],[,b]) => Number(b) - Number(a)).map(([k,v]) => (
                                  <div key={k} className="flex justify-between items-center gap-2">
                                    <span className="text-[#B9CACB] truncate">{k}</span>
                                    <div className="flex items-center gap-1.5">
                                      <div className="w-12 h-1 bg-[#2A2A2A] rounded-full overflow-hidden">
                                        <div className="h-full rounded-full bg-[#00F0FF]" style={{ width: `${Math.min(100, Number(v) * 100)}%` }} />
                                      </div>
                                      <span className="text-[#E5E2E1]/70 tabular-nums">{typeof v === "number" ? (v * 100).toFixed(0) + "%" : String(v)}</span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                              {/* Market Context */}
                              <div className="space-y-1.5">
                                <div className="text-[9px] font-bold uppercase tracking-widest text-[#B9CACB]/50 mb-2">Market Context</div>
                                {sig.market_context ? Object.entries(sig.market_context).slice(0, 7).map(([k,v]) => (
                                  <div key={k} className="flex justify-between"><span className="text-[#B9CACB] truncate">{k.replace(/_/g, " ")}</span><span className="text-[#E5E2E1]/70 truncate max-w-[80px]">{typeof v === "number" ? v.toFixed(4) : String(v)}</span></div>
                                )) : <span className="text-[#B9CACB]/30">No context</span>}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
