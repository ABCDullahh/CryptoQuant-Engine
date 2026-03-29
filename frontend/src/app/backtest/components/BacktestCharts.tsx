"use client";

import { useMemo } from "react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";
import { ObsidianTooltip } from "./ObsidianChartTooltip";

/* ═══════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════ */

interface BacktestChartsProps {
  equityCurve: Array<{ index: number; equity: number }>;
  trades: Array<{
    id?: string;
    direction: string;
    pnl: number;
    fees: number;
    holding_periods: number;
    entry_price: number;
    exit_price: number;
    close_reason: string;
    quantity?: number;
  }>;
  monthlyReturns: Record<string, number>;
  initialCapital: number;
}

/* ═══════════════════════════════════════════════════════
   Shared axis/grid props
   ═══════════════════════════════════════════════════════ */

const GRID_PROPS = {
  strokeDasharray: "3 3",
  stroke: "#2A2A2A",
  vertical: false as const,
};

const X_TICK = { fill: "#B9CACB", fontSize: 9, fontFamily: "monospace" };
const Y_TICK = { fill: "#B9CACB", fontSize: 9, fontFamily: "monospace" };

const AXIS_LINE = { stroke: "#2A2A2A" };

/* ═══════════════════════════════════════════════════════
   Chart wrapper
   ═══════════════════════════════════════════════════════ */

function ChartSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4">
      <h4 className="font-mono text-[10px] font-bold uppercase tracking-widest text-[#B9CACB]/60 mb-3">
        {title}
      </h4>
      <ResponsiveContainer width="100%" height={250}>
        {children as React.ReactElement}
      </ResponsiveContainer>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   1. Equity Curve — AreaChart
   ═══════════════════════════════════════════════════════ */

function EquityCurveChart({
  data,
}: {
  data: Array<{ index: number; equity: number }>;
}) {
  if (data.length < 2) return null;

  const yMin = Math.min(...data.map((d) => d.equity));
  const yMax = Math.max(...data.map((d) => d.equity));
  const pad = (yMax - yMin) * 0.05 || 10;

  return (
    <ChartSection title="Equity Curve">
      <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="btEquityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#00F0FF" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#00F0FF" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis
          dataKey="index"
          tick={X_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          interval="preserveStartEnd"
          minTickGap={50}
        />
        <YAxis
          domain={[yMin - pad, yMax + pad]}
          tick={Y_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          width={55}
          tickFormatter={(v: number) => `$${(v / 1000).toFixed(1)}k`}
        />
        <RechartsTooltip
          content={
            <ObsidianTooltip
              formatter={(v, n) => [`$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`, n]}
            />
          }
        />
        <Area
          type="monotone"
          dataKey="equity"
          stroke="#00F0FF"
          strokeWidth={2}
          fill="url(#btEquityGrad)"
          activeDot={{ r: 4, stroke: "#00F0FF", strokeWidth: 1, fill: "#1C1B1B" }}
        />
      </AreaChart>
    </ChartSection>
  );
}

/* ═══════════════════════════════════════════════════════
   2. Drawdown Chart — AreaChart (negative)
   ═══════════════════════════════════════════════════════ */

function DrawdownChart({
  data,
}: {
  data: Array<{ index: number; equity: number }>;
}) {
  const ddData = useMemo(() => {
    if (data.length < 2) return [];
    let peak = data[0].equity;
    return data.map((d) => {
      peak = Math.max(peak, d.equity);
      const dd = peak > 0 ? ((d.equity - peak) / peak) * 100 : 0;
      return { index: d.index, drawdown: dd };
    });
  }, [data]);

  if (ddData.length < 2) return null;

  const yMin = Math.min(...ddData.map((d) => d.drawdown));

  return (
    <ChartSection title="Drawdown">
      <AreaChart data={ddData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="btDdGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FFB4AB" stopOpacity={0.05} />
            <stop offset="100%" stopColor="#FFB4AB" stopOpacity={0.3} />
          </linearGradient>
        </defs>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis
          dataKey="index"
          tick={X_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          interval="preserveStartEnd"
          minTickGap={50}
        />
        <YAxis
          domain={[yMin * 1.1, 0]}
          tick={Y_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          width={50}
          tickFormatter={(v: number) => `${v.toFixed(1)}%`}
        />
        <RechartsTooltip
          content={
            <ObsidianTooltip
              formatter={(v, n) => [`${v.toFixed(2)}%`, n]}
            />
          }
        />
        <ReferenceLine y={0} stroke="#3B494B" strokeDasharray="3 3" />
        <Area
          type="monotone"
          dataKey="drawdown"
          stroke="#FFB4AB"
          strokeWidth={1.5}
          fill="url(#btDdGrad)"
          activeDot={{ r: 3, stroke: "#FFB4AB", strokeWidth: 1, fill: "#1C1B1B" }}
        />
      </AreaChart>
    </ChartSection>
  );
}

/* ═══════════════════════════════════════════════════════
   3. Monthly Returns — BarChart green/red
   ═══════════════════════════════════════════════════════ */

function MonthlyReturnsChart({
  monthlyReturns,
}: {
  monthlyReturns: Record<string, number>;
}) {
  const chartData = useMemo(() => {
    return Object.entries(monthlyReturns)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([month, pnl]) => ({ month, pnl: pnl * 100 }));
  }, [monthlyReturns]);

  if (chartData.length === 0) return null;

  return (
    <ChartSection title="Monthly Returns (%)">
      <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis
          dataKey="month"
          tick={X_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          interval="preserveStartEnd"
          minTickGap={30}
        />
        <YAxis
          tick={Y_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          width={50}
          tickFormatter={(v: number) => `${v.toFixed(1)}%`}
        />
        <RechartsTooltip
          content={
            <ObsidianTooltip
              formatter={(v, n) => [`${v.toFixed(2)}%`, n]}
            />
          }
        />
        <ReferenceLine y={0} stroke="#3B494B" strokeDasharray="3 3" />
        <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
          {chartData.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.pnl >= 0 ? "#40E56C" : "#FFB4AB"}
              fillOpacity={0.75}
            />
          ))}
        </Bar>
      </BarChart>
    </ChartSection>
  );
}

/* ═══════════════════════════════════════════════════════
   4. Rolling Sharpe — LineChart
   ═══════════════════════════════════════════════════════ */

function RollingSharpeChart({
  equityCurve,
}: {
  equityCurve: Array<{ index: number; equity: number }>;
}) {
  const chartData = useMemo(() => {
    if (equityCurve.length < 22) return [];
    const returns: number[] = [];
    for (let i = 1; i < equityCurve.length; i++) {
      const prev = equityCurve[i - 1].equity;
      if (prev !== 0) {
        returns.push((equityCurve[i].equity - prev) / prev);
      }
    }
    const window = 20;
    if (returns.length < window + 2) return [];
    const result: Array<{ index: number; sharpe: number }> = [];
    for (let i = window - 1; i < returns.length; i++) {
      const slice = returns.slice(i - window + 1, i + 1);
      const mean = slice.reduce((s, v) => s + v, 0) / slice.length;
      const variance =
        slice.reduce((s, v) => s + (v - mean) ** 2, 0) / slice.length;
      const std = Math.sqrt(variance);
      const sharpe = std > 0 ? (mean / std) * Math.sqrt(252) : 0;
      result.push({ index: i, sharpe });
    }
    return result;
  }, [equityCurve]);

  if (chartData.length < 2) return null;

  return (
    <ChartSection title="Rolling Sharpe (20-period)">
      <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis
          dataKey="index"
          tick={X_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          interval="preserveStartEnd"
          minTickGap={40}
        />
        <YAxis
          tick={Y_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          width={50}
          tickFormatter={(v: number) => v.toFixed(1)}
        />
        <RechartsTooltip
          content={
            <ObsidianTooltip
              formatter={(v, n) => [v.toFixed(2), n]}
            />
          }
        />
        <ReferenceLine y={0} stroke="#B9CACB" strokeOpacity={0.25} strokeDasharray="4 4" />
        <Line
          type="monotone"
          dataKey="sharpe"
          stroke="#00F0FF"
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3, stroke: "#00F0FF", fill: "#1C1B1B" }}
        />
      </LineChart>
    </ChartSection>
  );
}

/* ═══════════════════════════════════════════════════════
   5. Trade P&L Scatter
   ═══════════════════════════════════════════════════════ */

function TradePnlScatterChart({
  trades,
}: {
  trades: BacktestChartsProps["trades"];
}) {
  const { wins, losses } = useMemo(() => {
    const w: Array<{ index: number; pnl: number }> = [];
    const l: Array<{ index: number; pnl: number }> = [];
    trades.forEach((t, i) => {
      const pt = { index: i + 1, pnl: t.pnl };
      if (t.pnl >= 0) w.push(pt);
      else l.push(pt);
    });
    return { wins: w, losses: l };
  }, [trades]);

  if (trades.length === 0) return null;

  const allPnl = trades.map((t) => t.pnl);
  const maxAbs = Math.max(...allPnl.map(Math.abs), 0.01);

  return (
    <ChartSection title="Trade P&L Scatter">
      <ScatterChart margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis
          dataKey="index"
          type="number"
          name="Trade #"
          tick={X_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          domain={[1, trades.length]}
        />
        <YAxis
          dataKey="pnl"
          type="number"
          name="P&L"
          tick={Y_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          width={50}
          domain={[-maxAbs * 1.15, maxAbs * 1.15]}
          tickFormatter={(v: number) => `$${v.toFixed(0)}`}
        />
        <RechartsTooltip
          content={
            <ObsidianTooltip
              formatter={(v, n) => [
                n === "P&L" ? `$${v.toFixed(2)}` : String(v),
                n,
              ]}
            />
          }
        />
        <ReferenceLine y={0} stroke="#B9CACB" strokeOpacity={0.25} strokeDasharray="4 4" />
        <Scatter name="Wins" data={wins} fill="#40E56C" fillOpacity={0.7} r={3} />
        <Scatter name="Losses" data={losses} fill="#FFB4AB" fillOpacity={0.7} r={3} />
      </ScatterChart>
    </ChartSection>
  );
}

/* ═══════════════════════════════════════════════════════
   6. Win/Loss Distribution — histogram BarChart
   ═══════════════════════════════════════════════════════ */

function WinLossDistribution({
  trades,
}: {
  trades: BacktestChartsProps["trades"];
}) {
  const chartData = useMemo(() => {
    if (trades.length === 0) return [];
    const pnls = trades.map((t) => t.pnl);
    const min = Math.min(...pnls);
    const max = Math.max(...pnls);
    const range = max - min;
    if (range === 0) return [{ bin: `$${min.toFixed(0)}`, count: trades.length, midValue: min }];
    const nBins = Math.min(Math.max(Math.ceil(Math.sqrt(trades.length)), 5), 20);
    const binWidth = range / nBins;
    const bins: Array<{ bin: string; count: number; midValue: number }> = [];
    for (let i = 0; i < nBins; i++) {
      const lo = min + i * binWidth;
      const hi = lo + binWidth;
      const mid = (lo + hi) / 2;
      const count = pnls.filter(
        (p) => (i === nBins - 1 ? p >= lo && p <= hi : p >= lo && p < hi)
      ).length;
      bins.push({ bin: `$${lo.toFixed(0)}`, count, midValue: mid });
    }
    return bins;
  }, [trades]);

  if (chartData.length === 0) return null;

  return (
    <ChartSection title="P&L Distribution">
      <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis
          dataKey="bin"
          tick={X_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          interval="preserveStartEnd"
          minTickGap={30}
        />
        <YAxis
          tick={Y_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          width={35}
          allowDecimals={false}
        />
        <RechartsTooltip
          content={
            <ObsidianTooltip
              formatter={(v, n) => [String(v), n]}
            />
          }
        />
        <Bar dataKey="count" radius={[2, 2, 0, 0]}>
          {chartData.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.midValue >= 0 ? "#40E56C" : "#FFB4AB"}
              fillOpacity={0.7}
            />
          ))}
        </Bar>
      </BarChart>
    </ChartSection>
  );
}

/* ═══════════════════════════════════════════════════════
   7. P&L by Direction — BarChart LONG vs SHORT
   ═══════════════════════════════════════════════════════ */

function PnlByDirectionChart({
  trades,
}: {
  trades: BacktestChartsProps["trades"];
}) {
  const chartData = useMemo(() => {
    const longTrades = trades.filter((t) => t.direction === "LONG");
    const shortTrades = trades.filter((t) => t.direction === "SHORT");
    return [
      {
        direction: "LONG",
        pnl: longTrades.reduce((s, t) => s + t.pnl, 0),
        count: longTrades.length,
      },
      {
        direction: "SHORT",
        pnl: shortTrades.reduce((s, t) => s + t.pnl, 0),
        count: shortTrades.length,
      },
    ];
  }, [trades]);

  if (trades.length === 0) return null;

  return (
    <ChartSection title="P&L by Direction">
      <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis
          dataKey="direction"
          tick={X_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
        />
        <YAxis
          tick={Y_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          width={55}
          tickFormatter={(v: number) => `$${v.toFixed(0)}`}
        />
        <RechartsTooltip
          content={
            <ObsidianTooltip
              formatter={(v, n) => [
                n === "count" ? `${v} trades` : `$${v.toFixed(2)}`,
                n === "count" ? "Trades" : "P&L",
              ]}
            />
          }
        />
        <ReferenceLine y={0} stroke="#3B494B" strokeDasharray="3 3" />
        <Bar dataKey="pnl" name="P&L" radius={[2, 2, 0, 0]}>
          {chartData.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.pnl >= 0 ? "#40E56C" : "#FFB4AB"}
              fillOpacity={0.8}
            />
          ))}
        </Bar>
        <Bar dataKey="count" name="Trades" fill="#00F0FF" fillOpacity={0.3} radius={[2, 2, 0, 0]} />
      </BarChart>
    </ChartSection>
  );
}

/* ═══════════════════════════════════════════════════════
   8. Consecutive Win/Loss Streaks — BarChart
   ═══════════════════════════════════════════════════════ */

function ConsecutiveStreaksChart({
  trades,
}: {
  trades: BacktestChartsProps["trades"];
}) {
  const chartData = useMemo(() => {
    if (trades.length === 0) return [];
    const streaks: Array<{ index: number; streak: number; type: "win" | "loss" }> = [];
    let currentStreak = 0;
    let currentType: "win" | "loss" | null = null;

    for (let i = 0; i < trades.length; i++) {
      const isWin = trades[i].pnl >= 0;
      const type = isWin ? "win" : "loss";
      if (type === currentType) {
        currentStreak++;
      } else {
        if (currentType !== null) {
          streaks.push({
            index: streaks.length + 1,
            streak: currentType === "win" ? currentStreak : -currentStreak,
            type: currentType,
          });
        }
        currentType = type;
        currentStreak = 1;
      }
    }
    if (currentType !== null) {
      streaks.push({
        index: streaks.length + 1,
        streak: currentType === "win" ? currentStreak : -currentStreak,
        type: currentType,
      });
    }
    return streaks;
  }, [trades]);

  if (chartData.length === 0) return null;

  return (
    <ChartSection title="Consecutive Win/Loss Streaks">
      <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis
          dataKey="index"
          tick={X_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          label={{ value: "Streak #", position: "insideBottomRight", offset: -5, fill: "#B9CACB", fontSize: 8, fontFamily: "monospace" }}
        />
        <YAxis
          tick={Y_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          width={35}
          allowDecimals={false}
        />
        <RechartsTooltip
          content={
            <ObsidianTooltip
              formatter={(v, n) => [
                `${Math.abs(v)} ${v >= 0 ? "wins" : "losses"}`,
                n,
              ]}
            />
          }
        />
        <ReferenceLine y={0} stroke="#3B494B" strokeDasharray="3 3" />
        <Bar dataKey="streak" radius={[2, 2, 0, 0]}>
          {chartData.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.type === "win" ? "#40E56C" : "#FFB4AB"}
              fillOpacity={0.75}
            />
          ))}
        </Bar>
      </BarChart>
    </ChartSection>
  );
}

/* ═══════════════════════════════════════════════════════
   9. Cumulative Fees — AreaChart (orange)
   ═══════════════════════════════════════════════════════ */

function CumulativeFeesChart({
  trades,
}: {
  trades: BacktestChartsProps["trades"];
}) {
  const chartData = useMemo(() => {
    let cumFees = 0;
    return trades.map((t, i) => {
      cumFees += t.fees;
      return { index: i + 1, fees: cumFees };
    });
  }, [trades]);

  if (chartData.length === 0) return null;

  return (
    <ChartSection title="Cumulative Fees">
      <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="btFeesGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FFB347" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#FFB347" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis
          dataKey="index"
          tick={X_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          interval="preserveStartEnd"
          minTickGap={40}
        />
        <YAxis
          tick={Y_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          width={50}
          tickFormatter={(v: number) => `$${v.toFixed(0)}`}
        />
        <RechartsTooltip
          content={
            <ObsidianTooltip
              formatter={(v, n) => [`$${v.toFixed(2)}`, n]}
            />
          }
        />
        <Area
          type="monotone"
          dataKey="fees"
          stroke="#FFB347"
          strokeWidth={1.5}
          fill="url(#btFeesGrad)"
          activeDot={{ r: 3, stroke: "#FFB347", fill: "#1C1B1B" }}
        />
      </AreaChart>
    </ChartSection>
  );
}

/* ═══════════════════════════════════════════════════════
   10. Duration vs P&L — ScatterChart
   ═══════════════════════════════════════════════════════ */

function DurationVsPnlChart({
  trades,
}: {
  trades: BacktestChartsProps["trades"];
}) {
  const { wins, losses } = useMemo(() => {
    const w: Array<{ holding_periods: number; pnl: number }> = [];
    const l: Array<{ holding_periods: number; pnl: number }> = [];
    trades.forEach((t) => {
      const pt = { holding_periods: t.holding_periods, pnl: t.pnl };
      if (t.pnl >= 0) w.push(pt);
      else l.push(pt);
    });
    return { wins: w, losses: l };
  }, [trades]);

  if (trades.length === 0) return null;

  return (
    <ChartSection title="Duration vs P&L">
      <ScatterChart margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis
          dataKey="holding_periods"
          type="number"
          name="Bars"
          tick={X_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          label={{ value: "Holding Periods (bars)", position: "insideBottomRight", offset: -5, fill: "#B9CACB", fontSize: 8, fontFamily: "monospace" }}
        />
        <YAxis
          dataKey="pnl"
          type="number"
          name="P&L"
          tick={Y_TICK}
          tickLine={false}
          axisLine={AXIS_LINE}
          width={50}
          tickFormatter={(v: number) => `$${v.toFixed(0)}`}
        />
        <RechartsTooltip
          content={
            <ObsidianTooltip
              formatter={(v, n) => [
                n === "P&L" ? `$${v.toFixed(2)}` : `${v} bars`,
                n,
              ]}
            />
          }
        />
        <ReferenceLine y={0} stroke="#B9CACB" strokeOpacity={0.25} strokeDasharray="4 4" />
        <Scatter name="Wins" data={wins} fill="#40E56C" fillOpacity={0.7} r={3} />
        <Scatter name="Losses" data={losses} fill="#FFB4AB" fillOpacity={0.7} r={3} />
      </ScatterChart>
    </ChartSection>
  );
}

/* ═══════════════════════════════════════════════════════
   Main export — 10 charts in layout
   ═══════════════════════════════════════════════════════ */

export function BacktestCharts({
  equityCurve,
  trades,
  monthlyReturns,
  initialCapital,
}: BacktestChartsProps) {
  return (
    <div className="space-y-6">
      {/* Row 1: Full width */}
      <EquityCurveChart data={equityCurve} />
      <DrawdownChart data={equityCurve} />

      {/* Row 2: 2-col */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <MonthlyReturnsChart monthlyReturns={monthlyReturns} />
        <RollingSharpeChart equityCurve={equityCurve} />
      </div>

      {/* Row 3: 2-col */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <TradePnlScatterChart trades={trades} />
        <WinLossDistribution trades={trades} />
      </div>

      {/* Row 4: 2-col */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <PnlByDirectionChart trades={trades} />
        <ConsecutiveStreaksChart trades={trades} />
      </div>

      {/* Row 5: 2-col */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <CumulativeFeesChart trades={trades} />
        <DurationVsPnlChart trades={trades} />
      </div>
    </div>
  );
}
