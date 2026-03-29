"use client";

import { useState, useEffect, useMemo, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { fetchBacktest, type BacktestResult } from "@/lib/api";
import { ArrowLeft, GitCompareArrows } from "lucide-react";

/* =================================================================
   Constants
   ================================================================= */

const COLORS = ["#00F0FF", "#40E56C", "#FFB347", "#FF6B9D"];

const GRID_PROPS = {
  strokeDasharray: "3 3",
  stroke: "#2A2A2A",
  vertical: false as const,
};

const X_TICK = { fill: "#B9CACB", fontSize: 9, fontFamily: "monospace" };
const Y_TICK = { fill: "#B9CACB", fontSize: 9, fontFamily: "monospace" };
const AXIS_LINE = { stroke: "#2A2A2A" };

/* =================================================================
   Metric definitions — what to show in the comparison table
   ================================================================= */

interface MetricDef {
  label: string;
  /** Extract the value from a BacktestResult; return null when not available */
  extract: (bt: BacktestResult) => number | null;
  /** Format the number for display */
  format: (v: number) => string;
  /** "higher" = green for highest, "lower" = green for lowest */
  bestDirection: "higher" | "lower";
}

const METRIC_DEFS: MetricDef[] = [
  {
    label: "Net Return",
    extract: (bt) => bt.total_return ?? null,
    format: (v) => {
      const abs = Math.abs(v);
      const s = abs.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      return v >= 0 ? `+$${s}` : `-$${s}`;
    },
    bestDirection: "higher",
  },
  {
    label: "Sharpe Ratio",
    extract: (bt) => bt.sharpe_ratio ?? null,
    format: (v) => v.toFixed(2),
    bestDirection: "higher",
  },
  {
    label: "Sortino Ratio",
    extract: (bt) => bt.sortino_ratio ?? null,
    format: (v) => v.toFixed(2),
    bestDirection: "higher",
  },
  {
    label: "Max Drawdown",
    extract: (bt) => bt.max_drawdown != null ? bt.max_drawdown * 100 : null,
    format: (v) => `${v.toFixed(2)}%`,
    bestDirection: "lower",
  },
  {
    label: "Win Rate",
    extract: (bt) => bt.win_rate != null ? bt.win_rate * 100 : null,
    format: (v) => `${v.toFixed(1)}%`,
    bestDirection: "higher",
  },
  {
    label: "Profit Factor",
    extract: (bt) => bt.profit_factor ?? null,
    format: (v) => v.toFixed(2),
    bestDirection: "higher",
  },
  {
    label: "Avg Win",
    extract: (bt) => (bt.metrics?.avg_win as number) ?? null,
    format: (v) => `$${v.toFixed(2)}`,
    bestDirection: "higher",
  },
  {
    label: "Avg Loss",
    extract: (bt) => (bt.metrics?.avg_loss as number) ?? null,
    format: (v) => `$${Math.abs(v).toFixed(2)}`,
    bestDirection: "lower",
  },
  {
    label: "Expectancy",
    extract: (bt) => bt.expectancy ?? (bt.metrics?.expectancy as number) ?? null,
    format: (v) => `$${v.toFixed(2)}`,
    bestDirection: "higher",
  },
  {
    label: "Calmar Ratio",
    extract: (bt) => {
      if (bt.metrics?.calmar_ratio != null) return bt.metrics.calmar_ratio as number;
      if (bt.annual_return != null && bt.max_drawdown != null && bt.max_drawdown > 0)
        return bt.annual_return / bt.max_drawdown;
      return null;
    },
    format: (v) => v.toFixed(2),
    bestDirection: "higher",
  },
  {
    label: "Total Trades",
    extract: (bt) => bt.total_trades ?? null,
    format: (v) => String(Math.round(v)),
    bestDirection: "higher",
  },
];

/* =================================================================
   Helper: build backtest label
   ================================================================= */

function btLabel(bt: BacktestResult): string {
  const strat = bt.strategy_name.replace(/_/g, " ");
  return `${strat} ${bt.symbol} ${bt.timeframe}`;
}

/* =================================================================
   Inner component (reads searchParams)
   ================================================================= */

function ComparePageInner() {
  const searchParams = useSearchParams();
  const ids = searchParams.get("ids")?.split(",").filter(Boolean) ?? [];

  const [backtests, setBacktests] = useState<BacktestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* Fetch all backtests in parallel */
  useEffect(() => {
    if (ids.length < 2) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all(ids.map((id) => fetchBacktest(id)))
      .then((results) => {
        setBacktests(results);
        setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load backtests");
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---------------------------------------------------------------
     Equity overlay data: normalised to % return
     --------------------------------------------------------------- */
  const equityData = useMemo(() => {
    if (backtests.length === 0) return [];

    // Find max curve length
    const curves = backtests.map((bt) => bt.equity_curve ?? []);
    const maxLen = Math.max(...curves.map((c) => c.length));
    if (maxLen === 0) return [];

    const rows: Record<string, number | string>[] = [];
    for (let i = 0; i < maxLen; i++) {
      const row: Record<string, number | string> = { index: i };
      backtests.forEach((bt, bIdx) => {
        const curve = curves[bIdx];
        if (curve.length === 0) return;
        const initial = curve[0]?.equity ?? 1;
        const point = curve[Math.min(i, curve.length - 1)];
        row[`bt${bIdx}`] = initial !== 0 ? ((point.equity - initial) / initial) * 100 : 0;
      });
      rows.push(row);
    }
    return rows;
  }, [backtests]);

  /* ---------------------------------------------------------------
     Drawdown overlay data
     --------------------------------------------------------------- */
  const drawdownData = useMemo(() => {
    if (backtests.length === 0) return [];

    const curves = backtests.map((bt) => bt.equity_curve ?? []);
    const maxLen = Math.max(...curves.map((c) => c.length));
    if (maxLen === 0) return [];

    const rows: Record<string, number | string>[] = [];
    for (let i = 0; i < maxLen; i++) {
      const row: Record<string, number | string> = { index: i };
      backtests.forEach((bt, bIdx) => {
        const curve = curves[bIdx];
        if (curve.length === 0) return;
        // peak up to this point
        let peak = curve[0]?.equity ?? 1;
        for (let j = 0; j <= Math.min(i, curve.length - 1); j++) {
          if (curve[j].equity > peak) peak = curve[j].equity;
        }
        const eq = curve[Math.min(i, curve.length - 1)].equity;
        row[`bt${bIdx}`] = peak > 0 ? ((eq - peak) / peak) * 100 : 0;
      });
      rows.push(row);
    }
    return rows;
  }, [backtests]);

  /* ---------------------------------------------------------------
     Render
     --------------------------------------------------------------- */

  if (ids.length < 2 && !loading) {
    return (
      <div className="p-4 md:p-6 max-w-[1600px] mx-auto">
        <Link
          href="/backtest"
          className="inline-flex items-center gap-2 text-sm font-mono text-[#00F0FF] hover:text-[#00F0FF]/80 transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Backtest
        </Link>
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <p className="text-sm text-[#B9CACB]/50 font-mono">
            Select at least 2 backtests to compare.
          </p>
          <p className="text-xs text-[#B9CACB]/30 font-mono mt-1">
            Use the checkboxes in the Backtest History table.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-[1600px] mx-auto pb-20 md:pb-6">
      {/* ============================================================
          A) Top Bar
          ============================================================ */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <Link
            href="/backtest"
            className="inline-flex items-center gap-2 text-sm font-mono text-[#00F0FF] hover:text-[#00F0FF]/80 transition-colors mb-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Backtest
          </Link>
          <h2 className="font-mono text-xl font-black text-[#E5E2E1] uppercase tracking-tighter flex items-center gap-3">
            <GitCompareArrows className="w-6 h-6 text-[#00F0FF]" />
            Strategy Comparison
          </h2>
          <p className="font-mono text-[10px] text-[#B9CACB] uppercase tracking-widest mt-1">
            Comparing {ids.length} backtests side by side
          </p>
        </div>

        {/* Colored chips for each backtest */}
        {!loading && backtests.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {backtests.map((bt, idx) => (
              <span
                key={bt.id}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-[10px] font-mono font-bold uppercase tracking-wider border"
                style={{
                  color: COLORS[idx % COLORS.length],
                  backgroundColor: `${COLORS[idx % COLORS.length]}15`,
                  borderColor: `${COLORS[idx % COLORS.length]}30`,
                }}
              >
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: COLORS[idx % COLORS.length] }}
                />
                {btLabel(bt)}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-24">
          <div
            className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin"
            style={{ borderColor: "#00F0FF", borderTopColor: "transparent" }}
          />
          <span className="ml-3 font-mono text-sm text-[#B9CACB]/50">
            Loading backtests...
          </span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-sm bg-[#FFB4AB]/10 border border-[#FFB4AB]/20 p-4">
          <p className="text-xs font-mono text-[#FFB4AB]">{error}</p>
        </div>
      )}

      {/* Results */}
      {!loading && !error && backtests.length > 0 && (
        <>
          {/* ============================================================
              B) Metrics Comparison Table
              ============================================================ */}
          <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-4">
            <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase mb-4">
              Metrics Comparison
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse min-w-[540px]">
                <thead>
                  <tr className="border-b border-[#2A2A2A]/20">
                    <th className="px-4 py-3 text-left text-[10px] font-mono font-semibold uppercase tracking-widest text-[#B9CACB]/60 bg-[#201F1F]/50">
                      Metric
                    </th>
                    {backtests.map((bt, idx) => (
                      <th
                        key={bt.id}
                        className="px-4 py-3 text-right text-[10px] font-mono font-semibold uppercase tracking-widest bg-[#201F1F]/50"
                        style={{ color: COLORS[idx % COLORS.length] }}
                      >
                        {btLabel(bt)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#2A2A2A]/5">
                  {METRIC_DEFS.map((def) => {
                    const values = backtests.map((bt) => def.extract(bt));
                    const numericValues = values.filter((v): v is number => v !== null);

                    let bestIdx = -1;
                    let worstIdx = -1;
                    if (numericValues.length > 1) {
                      if (def.bestDirection === "higher") {
                        const maxVal = Math.max(...numericValues);
                        const minVal = Math.min(...numericValues);
                        bestIdx = values.indexOf(maxVal);
                        worstIdx = values.indexOf(minVal);
                      } else {
                        // "lower" is better (e.g. drawdown, avg loss)
                        const minVal = Math.min(...numericValues);
                        const maxVal = Math.max(...numericValues);
                        bestIdx = values.indexOf(minVal);
                        worstIdx = values.indexOf(maxVal);
                      }
                      // Don't highlight if best == worst
                      if (bestIdx === worstIdx) {
                        bestIdx = -1;
                        worstIdx = -1;
                      }
                    }

                    return (
                      <tr key={def.label} className="hover:bg-[#2A2A2A]/20 transition-colors">
                        <td className="px-4 py-3 text-[11px] font-mono font-medium text-[#B9CACB]/80">
                          {def.label}
                        </td>
                        {values.map((v, cIdx) => (
                          <td
                            key={cIdx}
                            className="px-4 py-3 text-right text-[13px] font-mono tabular-nums font-semibold"
                            style={{
                              color:
                                cIdx === bestIdx
                                  ? "#40E56C"
                                  : cIdx === worstIdx
                                    ? "#FFB4AB"
                                    : "#E5E2E1",
                            }}
                          >
                            {v !== null ? def.format(v) : "--"}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* ============================================================
              C) Overlay Equity Curves (normalized to % return)
              ============================================================ */}
          {equityData.length > 0 && (
            <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-4">
              <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase mb-4">
                Equity Curves (% Return)
              </h3>
              <ResponsiveContainer width="100%" height={350}>
                <LineChart data={equityData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                  <CartesianGrid {...GRID_PROPS} />
                  <XAxis
                    dataKey="index"
                    tick={X_TICK}
                    axisLine={AXIS_LINE}
                    tickLine={false}
                    tickFormatter={(v: number) => {
                      if (equityData.length <= 20) return String(v);
                      const step = Math.ceil(equityData.length / 10);
                      return v % step === 0 ? String(v) : "";
                    }}
                  />
                  <YAxis
                    tick={Y_TICK}
                    axisLine={AXIS_LINE}
                    tickLine={false}
                    tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                    width={55}
                  />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: "#1C1B1B",
                      border: "1px solid #3B494B",
                      borderRadius: "2px",
                      fontFamily: "monospace",
                      fontSize: 11,
                    }}
                    labelStyle={{ color: "#B9CACB", fontSize: 10 }}
                    formatter={(value: unknown, name: unknown) => {
                      const v = Number(value ?? 0);
                      const n = String(name ?? "");
                      const idx = parseInt(n.replace("bt", ""), 10);
                      const label = backtests[idx] ? btLabel(backtests[idx]) : n;
                      return [`${v.toFixed(2)}%`, label];
                    }}
                    labelFormatter={(label: unknown) => `Bar ${label}`}
                  />
                  <Legend
                    formatter={(_value: unknown, entry: unknown) => {
                      const e = entry as { dataKey?: string | number } | undefined;
                      const idx = parseInt(String(e?.dataKey ?? "").replace("bt", ""), 10);
                      return backtests[idx] ? btLabel(backtests[idx]) : String(e?.dataKey ?? "");
                    }}
                    wrapperStyle={{ fontFamily: "monospace", fontSize: 10 }}
                  />
                  {backtests.map((_bt, idx) => (
                    <Line
                      key={idx}
                      type="monotone"
                      dataKey={`bt${idx}`}
                      stroke={COLORS[idx % COLORS.length]}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4, fill: COLORS[idx % COLORS.length] }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* ============================================================
              D) Overlay Drawdown
              ============================================================ */}
          {drawdownData.length > 0 && (
            <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-4">
              <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase mb-4">
                Drawdown Comparison
              </h3>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={drawdownData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                  <CartesianGrid {...GRID_PROPS} />
                  <XAxis
                    dataKey="index"
                    tick={X_TICK}
                    axisLine={AXIS_LINE}
                    tickLine={false}
                    tickFormatter={(v: number) => {
                      if (drawdownData.length <= 20) return String(v);
                      const step = Math.ceil(drawdownData.length / 10);
                      return v % step === 0 ? String(v) : "";
                    }}
                  />
                  <YAxis
                    tick={Y_TICK}
                    axisLine={AXIS_LINE}
                    tickLine={false}
                    tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                    width={55}
                  />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: "#1C1B1B",
                      border: "1px solid #3B494B",
                      borderRadius: "2px",
                      fontFamily: "monospace",
                      fontSize: 11,
                    }}
                    labelStyle={{ color: "#B9CACB", fontSize: 10 }}
                    formatter={(value: unknown, name: unknown) => {
                      const v = Number(value ?? 0);
                      const n = String(name ?? "");
                      const idx = parseInt(n.replace("bt", ""), 10);
                      const label = backtests[idx] ? btLabel(backtests[idx]) : n;
                      return [`${v.toFixed(2)}%`, label];
                    }}
                    labelFormatter={(label: unknown) => `Bar ${label}`}
                  />
                  <Legend
                    formatter={(_value: unknown, entry: unknown) => {
                      const e = entry as { dataKey?: string | number } | undefined;
                      const idx = parseInt(String(e?.dataKey ?? "").replace("bt", ""), 10);
                      return backtests[idx] ? btLabel(backtests[idx]) : String(e?.dataKey ?? "");
                    }}
                    wrapperStyle={{ fontFamily: "monospace", fontSize: 10 }}
                  />
                  {backtests.map((_bt, idx) => (
                    <Area
                      key={idx}
                      type="monotone"
                      dataKey={`bt${idx}`}
                      stroke={COLORS[idx % COLORS.length]}
                      fill={`${COLORS[idx % COLORS.length]}15`}
                      strokeWidth={1.5}
                      activeDot={{ r: 3, fill: COLORS[idx % COLORS.length] }}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* =================================================================
   Page export — wrap in Suspense for useSearchParams
   ================================================================= */

export default function BacktestComparePage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-24">
          <div
            className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin"
            style={{ borderColor: "#00F0FF", borderTopColor: "transparent" }}
          />
          <span className="ml-3 font-mono text-sm text-[#B9CACB]/50">
            Loading...
          </span>
        </div>
      }
    >
      <ComparePageInner />
    </Suspense>
  );
}
