"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import {
  Wallet,
  WifiOff,
  Zap,
  MoreVertical,
} from "lucide-react";
import Link from "next/link";
import {
  fetchSignals,
  fetchBotPerformance,
  fetchExchangePositions,
  fetchBalance,
  fetchMarkets,
  type Signal as ApiSignal,
  type BotPerformance as ApiBotPerformance,
  type ExchangePosition,
  type BalanceResponse,
} from "@/lib/api";
import { useWebSocket } from "@/hooks/useApi";
import type { PriceUpdate } from "@/lib/websocket";

type Signal = ApiSignal;
type BotPerformance = ApiBotPerformance;

// Fallback symbols for the live price ticker (used while API loads)
const FALLBACK_TICKER_SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"];

export default function OverviewPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [performance, setPerformance] = useState<BotPerformance | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [exchangePositions, setExchangePositions] = useState<ExchangePosition[]>([]);
  const [balance, setBalance] = useState<BalanceResponse | null>(null);
  const [tickerSymbols, setTickerSymbols] = useState<string[]>(FALLBACK_TICKER_SYMBOLS);

  // Live prices from WebSocket
  const [livePrices, setLivePrices] = useState<Record<string, PriceUpdate>>({});

  const loadData = useCallback(async () => {
    try {
      const [sigs, perfRes, exchPos, bal] = await Promise.all([
        fetchSignals(),
        fetchBotPerformance(),
        fetchExchangePositions(),
        fetchBalance(),
      ]);
      setSignals(sigs || []);
      setPerformance(perfRes);
      setExchangePositions(exchPos?.positions || []);
      setBalance(bal);
      setApiError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setApiError(message);
      console.error("Failed to load overview data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15_000);
    return () => clearInterval(interval);
  }, [loadData]);

  useEffect(() => {
    // Load top ticker symbols from exchange (by volume / market cap)
    fetchMarkets()
      .then((res) => {
        if (res.markets && res.markets.length > 0) {
          const top = res.markets
            .filter((m: { active: boolean; quote: string }) => m.active && m.quote === "USDT")
            .slice(0, 5)
            .map((m: { symbol: string }) => m.symbol);
          if (top.length > 0) setTickerSymbols(top);
        }
      })
      .catch(console.error);
  }, []);

  // -- WebSocket: live price updates --
  useWebSocket("price_update", useCallback((data: PriceUpdate) => {
    setLivePrices((prev) => ({ ...prev, [data.symbol]: data }));
  }, []));

  // -- WebSocket: signal/position triggers refetch --
  const refetchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scheduleRefetch = useCallback(() => {
    if (refetchTimeout.current) return;
    refetchTimeout.current = setTimeout(() => {
      refetchTimeout.current = null;
      loadData();
    }, 2_000);
  }, [loadData]);

  useWebSocket("signal_new", useCallback(() => { scheduleRefetch(); }, [scheduleRefetch]));
  useWebSocket("position_update", useCallback(() => { scheduleRefetch(); }, [scheduleRefetch]));
  useWebSocket("bot_status", useCallback(() => { scheduleRefetch(); }, [scheduleRefetch]));

  const totalPnl = exchangePositions.reduce((s, p) => s + (p.unrealized_pnl || 0), 0);

  // Margin used % calculation
  const marginUsedPct = useMemo(() => {
    if (!balance || balance.total <= 0) return 0;
    return (balance.used / balance.total) * 100;
  }, [balance]);

  // Signal direction counts
  const signalCounts = useMemo(() => {
    let longs = 0;
    let shorts = 0;
    signals.forEach((s) => {
      if (s.direction === "LONG") longs++;
      else shorts++;
    });
    return { longs, shorts };
  }, [signals]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex items-center gap-3">
          <div
            className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin"
            style={{ borderColor: "#00F0FF", borderTopColor: "transparent" }}
          />
          <span className="font-mono text-sm text-[#B9CACB]">
            Loading terminal...
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-[1600px] mx-auto">
      {/* API Error Banner */}
      {apiError && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-sm bg-[#FFB4AB]/5 border border-[#FFB4AB]/20">
          <WifiOff size={18} className="text-[#FFB4AB] flex-shrink-0" />
          <div>
            <p className="font-mono text-xs font-bold text-[#FFB4AB]">
              Unable to connect to backend
            </p>
            <p className="font-mono text-[10px] mt-0.5 text-[#FFB4AB]/60">
              Dashboard data may be stale or incomplete. Check that the backend server is running.
            </p>
          </div>
        </div>
      )}

      {/* Live Price Ticker */}
      {Object.keys(livePrices).length > 0 && (
        <div className="flex items-center gap-6 px-4 py-2.5 rounded-sm overflow-x-auto bg-[#1C1B1B] border border-[#3B494B]/10">
          <span className="text-[10px] font-mono uppercase tracking-widest flex-shrink-0 text-[#B9CACB]/50">
            Live
          </span>
          {tickerSymbols.map((sym) => {
            const p = livePrices[sym];
            if (!p) return null;
            const pctChange = p.change_24h_percent ?? 0;
            const isUp = pctChange >= 0;
            return (
              <div key={sym} className="flex items-center gap-2 flex-shrink-0">
                <span className="text-[11px] font-mono font-bold text-[#E5E2E1]">
                  {sym.replace("/USDT", "")}
                </span>
                <span className="text-xs font-mono font-bold tabular-nums text-[#E5E2E1]">
                  ${p.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: p.price < 10 ? 4 : 2 })}
                </span>
                <span
                  className="text-[11px] font-mono tabular-nums"
                  style={{ color: isUp ? "#40E56C" : "#FFB4AB" }}
                >
                  {isUp ? "+" : ""}{pctChange.toFixed(2)}%
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Hero Stat Grid — 5 columns */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {/* Portfolio Balance */}
        <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4 border-l-2 border-l-[#00F0FF]">
          <p className="text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-1">
            Portfolio Balance
          </p>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-xl font-black text-[#E5E2E1] tabular-nums">
              {balance ? balance.total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "---"}
            </span>
            <span className="text-[10px] font-mono text-[#B9CACB]">USDT</span>
          </div>
          <div className="mt-2 flex items-center gap-1 text-[10px] font-mono text-[#B9CACB]">
            <Wallet className="w-3 h-3" />
            <span>Free: {balance ? balance.free.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "---"}</span>
          </div>
        </div>

        {/* Unrealized P&L */}
        <div className={`bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4 border-l-2 ${totalPnl >= 0 ? "border-l-[#40E56C]" : "border-l-[#FFB4AB]"}`}>
          <p className="text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-1">
            Unrealized P&L
          </p>
          <div className="flex items-baseline gap-2">
            <span className={`font-mono text-xl font-black tabular-nums ${totalPnl >= 0 ? "text-[#40E56C]" : "text-[#FFB4AB]"}`}>
              {totalPnl >= 0 ? "+" : ""}{Math.abs(totalPnl).toFixed(2)}
            </span>
            <span className={`text-[10px] font-mono ${totalPnl >= 0 ? "text-[#40E56C]/70" : "text-[#FFB4AB]/70"}`}>USDT</span>
          </div>
          <div className="mt-2 text-[10px] font-mono text-[#B9CACB]">
            {exchangePositions.length} ACTIVE POSITION{exchangePositions.length !== 1 ? "S" : ""}
          </div>
        </div>

        {/* Margin Used */}
        <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4 border-l-2 border-l-[#00F0FF]">
          <p className="text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-1">
            Margin Used
          </p>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-xl font-black text-[#E5E2E1] tabular-nums">
              {marginUsedPct.toFixed(1)}
            </span>
            <span className="text-[10px] font-mono text-[#B9CACB]">%</span>
          </div>
          <div className="mt-2 h-1 bg-[#353534] w-full overflow-hidden rounded-sm">
            <div className="h-full bg-[#00F0FF]" style={{ width: `${Math.min(marginUsedPct, 100)}%` }} />
          </div>
        </div>

        {/* Active Signals */}
        <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4 border-l-2 border-l-[#E5E2E1]/10">
          <p className="text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-1">
            Active Signals
          </p>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-xl font-black text-[#E5E2E1] tabular-nums">
              {signals.length}
            </span>
            <span className="text-[10px] font-mono text-[#B9CACB]">SIGNALS</span>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#40E56C] animate-pulse" />
            <span className="text-[10px] font-mono text-[#40E56C]">{signalCounts.longs} LONG</span>
            <span className="text-[10px] font-mono text-[#FFB4AB]">{signalCounts.shorts} SHORT</span>
          </div>
        </div>

        {/* 30D Win Rate */}
        <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4 border-l-2 border-l-[#00F0FF]">
          <p className="text-[10px] font-mono font-bold text-[#B9CACB] uppercase tracking-widest mb-1">
            30D Win Rate
          </p>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-xl font-black text-[#00F0FF] tabular-nums">
              {performance ? (performance.win_rate * 100).toFixed(1) : "---"}
            </span>
            <span className="text-[10px] font-mono text-[#00F0FF]/70">%</span>
          </div>
          <div className="mt-2 text-[10px] font-mono text-[#B9CACB]">
            {performance ? `${performance.wins}W / ${performance.losses}L` : "---"}
          </div>
        </div>
      </div>

      {/* Main Grid — 12 columns */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column */}
        <div className="lg:col-span-4 space-y-6">
          {/* Live Signals Feed */}
          <section className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10">
            <div className="flex justify-between items-center mb-6">
              <h3 className="font-mono text-xs font-black tracking-widest text-[#00F0FF] uppercase flex items-center gap-2">
                <Zap className="w-4 h-4 fill-current" />
                Live Signals
              </h3>
              <Link
                href="/signals"
                className="text-[9px] font-mono font-bold text-[#B9CACB] hover:text-[#E5E2E1] uppercase tracking-wider transition-colors"
              >
                View All
              </Link>
            </div>

            {signals.length === 0 ? (
              <p className="text-xs font-mono py-8 text-center text-[#B9CACB]/40">
                No active signals
              </p>
            ) : (
              <div className="space-y-1">
                {signals.slice(0, 5).map((s) => (
                  <div
                    key={s.id}
                    className="bg-[#2A2A2A] p-3 flex justify-between items-center cursor-pointer hover:bg-[#353534] transition-colors"
                  >
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono font-bold text-[#E5E2E1]">
                          {s.symbol}
                        </span>
                        <span
                          className={`text-[9px] px-1.5 py-0.5 font-bold rounded-sm ${
                            s.direction === "LONG"
                              ? "bg-[#40E56C]/10 text-[#40E56C]"
                              : "bg-[#FFB4AB]/10 text-[#FFB4AB]"
                          }`}
                        >
                          {s.direction}
                        </span>
                        <span
                          className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-sm"
                          style={{
                            background:
                              s.signal_grade === "A"
                                ? "rgba(0,240,255,0.12)"
                                : s.signal_grade === "B"
                                  ? "rgba(64,229,108,0.12)"
                                  : "rgba(185,202,203,0.12)",
                            color:
                              s.signal_grade === "A"
                                ? "#00F0FF"
                                : s.signal_grade === "B"
                                  ? "#40E56C"
                                  : "#B9CACB",
                          }}
                        >
                          {s.signal_grade}
                        </span>
                      </div>
                      <div className="text-[10px] font-mono text-[#B9CACB]">
                        Strength: {((s.signal_strength || 0) * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[11px] font-mono font-bold text-[#E5E2E1] tabular-nums">
                        ${s.entry_price?.toLocaleString()}
                      </div>
                      <div className="text-[9px] font-mono text-[#B9CACB]/50">
                        {s.created_at
                          ? new Date(s.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                          : "---"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <Link
              href="/signals"
              className="block w-full mt-4 py-2 text-center text-[10px] font-bold font-mono tracking-widest text-[#B9CACB] hover:text-[#E5E2E1] border border-[#3B494B]/20 hover:bg-[#201F1F] transition-all rounded-sm"
            >
              VIEW ALL SIGNALS
            </Link>
          </section>

          {/* Performance Metrics */}
          {performance && performance.total_trades > 0 && (
            <section className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10">
              <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase mb-4">
                Performance Metrics
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <p className="text-[10px] text-[#B9CACB] font-bold uppercase tracking-wider">Total Trades</p>
                  <p className="font-mono text-xl font-black text-[#E5E2E1] tabular-nums">
                    {performance.total_trades}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-[10px] text-[#B9CACB] font-bold uppercase tracking-wider">W/L Ratio</p>
                  <p className="font-mono text-xl font-black text-[#E5E2E1] tabular-nums">
                    {performance.losses > 0
                      ? (performance.wins / performance.losses).toFixed(2)
                      : performance.wins > 0
                        ? "INF"
                        : "0.00"}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-[10px] text-[#B9CACB] font-bold uppercase tracking-wider">Total P&L</p>
                  <p className={`font-mono text-xl font-black tabular-nums ${performance.total_pnl >= 0 ? "text-[#40E56C]" : "text-[#FFB4AB]"}`}>
                    {performance.total_pnl >= 0 ? "+" : ""}{Math.abs(performance.total_pnl).toFixed(2)}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-[10px] text-[#B9CACB] font-bold uppercase tracking-wider">Win Rate</p>
                  <p className="font-mono text-xl font-black text-[#00F0FF] tabular-nums">
                    {(performance.win_rate * 100).toFixed(1)}%
                  </p>
                </div>
              </div>
            </section>
          )}
        </div>

        {/* Right Column */}
        <div className="lg:col-span-8 space-y-6">
          {/* Open Positions Table */}
          <section className="bg-[#1C1B1B] rounded-sm border border-[#3B494B]/10">
            <div className="p-4 border-b border-[#2A2A2A]/20 flex justify-between items-center">
              <h3 className="font-mono text-xs font-black tracking-widest text-[#00F0FF] uppercase flex items-center gap-2">
                <Wallet className="w-4 h-4" />
                Open Positions
              </h3>
              <Link
                href="/positions"
                className="text-[9px] font-mono font-bold text-[#B9CACB] hover:text-[#E5E2E1] uppercase tracking-wider transition-colors"
              >
                View All
              </Link>
            </div>
            {exchangePositions.length === 0 ? (
              <p className="text-xs font-mono py-12 text-center text-[#B9CACB]/40">
                No open positions on Binance
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono">
                  <thead>
                    <tr className="text-[10px] text-[#B9CACB]/60 border-b border-[#2A2A2A]/10 bg-[#201F1F]/50">
                      <th className="px-4 py-3 font-bold uppercase tracking-widest">Asset</th>
                      <th className="px-4 py-3 font-bold uppercase tracking-widest">Side</th>
                      <th className="px-4 py-3 font-bold uppercase tracking-widest">Size</th>
                      <th className="px-4 py-3 font-bold uppercase tracking-widest">Entry</th>
                      <th className="px-4 py-3 font-bold uppercase tracking-widest">Mark</th>
                      <th className="px-4 py-3 font-bold uppercase tracking-widest">Liq. Price</th>
                      <th className="px-4 py-3 font-bold uppercase tracking-widest text-right">PnL / ROI</th>
                      <th className="px-4 py-3" />
                    </tr>
                  </thead>
                  <tbody className="text-xs divide-y divide-[#2A2A2A]/5">
                    {exchangePositions.slice(0, 8).map((p, idx) => {
                      const roi = p.margin > 0 ? (p.unrealized_pnl / p.margin) * 100 : 0;
                      const isProfit = p.unrealized_pnl >= 0;
                      const livePrice = livePrices[p.symbol];
                      const markPrice = livePrice ? livePrice.price : p.current_price;
                      return (
                        <tr key={`${p.symbol}-${idx}`} className="hover:bg-[#2A2A2A]/40 transition-colors">
                          <td className="px-4 py-4 font-bold text-[#E5E2E1]">
                            {p.symbol}{" "}
                            <span className="text-[9px] text-[#B9CACB] font-normal">{p.leverage}x</span>
                          </td>
                          <td className="px-4 py-4">
                            <span className={`font-bold ${p.direction === "LONG" ? "text-[#40E56C]" : "text-[#FFB4AB]"}`}>
                              {p.direction}
                            </span>
                          </td>
                          <td className="px-4 py-4 text-[#E5E2E1] tabular-nums">
                            {p.notional.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-4 text-[#B9CACB] tabular-nums">
                            {p.entry_price?.toLocaleString()}
                          </td>
                          <td className="px-4 py-4 text-[#E5E2E1] tabular-nums">
                            {markPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: markPrice < 10 ? 4 : 2 })}
                          </td>
                          <td className="px-4 py-4 text-[#FFB4AB]/70 tabular-nums">
                            {p.liquidation_price > 0 ? p.liquidation_price.toLocaleString() : "---"}
                          </td>
                          <td className="px-4 py-4 text-right">
                            <div className={`font-bold tabular-nums ${isProfit ? "text-[#40E56C]" : "text-[#FFB4AB]"}`}>
                              {isProfit ? "+" : ""}{p.unrealized_pnl.toFixed(2)}
                            </div>
                            <div className={`text-[10px] tabular-nums ${isProfit ? "text-[#40E56C]/70" : "text-[#FFB4AB]/70"}`}>
                              {isProfit ? "+" : ""}{roi.toFixed(2)}%
                            </div>
                          </td>
                          <td className="px-4 py-4 text-right">
                            <Link href="/positions" className="text-[#B9CACB] hover:text-[#00F0FF] transition-colors text-[10px] font-mono">
                              Detail
                            </Link>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Portfolio Info Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Account Breakdown */}
            <div className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10">
              <h3 className="font-mono text-[10px] font-black tracking-widest text-[#B9CACB] uppercase mb-4">
                Account Breakdown
              </h3>
              <div className="space-y-3">
                {[
                  {
                    label: "TOTAL",
                    val: balance ? `${balance.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "---",
                    pct: "100%",
                    color: "bg-[#00F0FF]",
                  },
                  {
                    label: "FREE",
                    val: balance ? `${balance.free.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "---",
                    pct: balance && balance.total > 0 ? `${((balance.free / balance.total) * 100).toFixed(1)}%` : "0%",
                    color: "bg-[#40E56C]",
                  },
                  {
                    label: "MARGIN",
                    val: balance ? `${balance.used.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "---",
                    pct: balance && balance.total > 0 ? `${((balance.used / balance.total) * 100).toFixed(1)}%` : "0%",
                    color: "bg-[#B9CACB]",
                  },
                ].map((item, i) => (
                  <div key={i}>
                    <div className="flex justify-between text-[10px] font-mono mb-1">
                      <span className="text-[#B9CACB]">{item.label}</span>
                      <span className="text-[#E5E2E1] tabular-nums">{item.val}</span>
                    </div>
                    <div className="h-1 w-full bg-[#353534] overflow-hidden rounded-sm">
                      <div className={`h-full ${item.color}`} style={{ width: item.pct }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Risk Exposure */}
            <div className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10">
              <h3 className="font-mono text-[10px] font-black tracking-widest text-[#B9CACB] uppercase mb-4">
                Risk Exposure
              </h3>
              {exchangePositions.length === 0 ? (
                <p className="text-xs font-mono py-6 text-center text-[#B9CACB]/40">
                  No active exposure
                </p>
              ) : (
                <div className="space-y-3">
                  {(() => {
                    const totalNotional = exchangePositions.reduce((sum, p) => sum + Math.abs(p.notional), 0);
                    // Group by base symbol
                    const grouped: Record<string, number> = {};
                    exchangePositions.forEach((p) => {
                      const base = p.symbol.replace("/USDT", "").replace("USDT", "");
                      grouped[base] = (grouped[base] || 0) + Math.abs(p.notional);
                    });
                    const sorted = Object.entries(grouped).sort((a, b) => b[1] - a[1]);
                    const colors = ["bg-[#00F0FF]", "bg-[#40E56C]", "bg-[#B9CACB]", "bg-[#FFB4AB]", "bg-[#E5E2E1]/50"];
                    return sorted.map(([sym, notional], i) => {
                      const pct = totalNotional > 0 ? (notional / totalNotional) * 100 : 0;
                      return (
                        <div key={sym}>
                          <div className="flex justify-between text-[10px] font-mono mb-1">
                            <span className="text-[#B9CACB]">{sym}</span>
                            <span className="text-[#E5E2E1] tabular-nums">{pct.toFixed(1)}%</span>
                          </div>
                          <div className="h-1 w-full bg-[#353534] overflow-hidden rounded-sm">
                            <div className={`h-full ${colors[i % colors.length]}`} style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    });
                  })()}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
