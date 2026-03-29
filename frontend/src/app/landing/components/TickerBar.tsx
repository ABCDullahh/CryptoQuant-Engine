"use client";

import { useState, useEffect, useCallback } from "react";

/* ══════════════════════════════════════════════
   TickerBar — Always-fixed crypto price ticker
   Top 10 movers from Binance public API (real-time)
   ══════════════════════════════════════════════ */

interface TickerItem {
  symbol: string;
  price: string;
  change: number;
}

function formatPrice(price: number): string {
  if (price >= 1000) return price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (price >= 1) return price.toFixed(2);
  if (price >= 0.01) return price.toFixed(4);
  return price.toFixed(6);
}

function TickerItemEl({ item }: { item: TickerItem }) {
  const isPositive = item.change >= 0;
  return (
    <div className="flex items-center gap-3 px-5 shrink-0">
      <span className="font-mono text-[11px] font-bold text-[#E5E2E1] whitespace-nowrap">
        {item.symbol}
      </span>
      <span className="font-mono text-[11px] text-[#B9CACB] whitespace-nowrap tabular-nums">
        ${item.price}
      </span>
      <span
        className="font-mono text-[11px] font-bold whitespace-nowrap tabular-nums"
        style={{ color: isPositive ? "#40E56C" : "#FFB4AB" }}
      >
        {isPositive ? "+" : ""}
        {item.change.toFixed(2)}%
      </span>
      {/* Sparkle for top gainers */}
      {item.change > 5 && <span className="text-[10px]" style={{ color: "#40E56C" }}>&#10038;</span>}
      {item.change < -5 && <span className="text-[10px]" style={{ color: "#FFB4AB" }}>&#10038;</span>}
    </div>
  );
}

export default function TickerBar() {
  const [isPaused, setIsPaused] = useState(false);
  const [tickers, setTickers] = useState<TickerItem[]>([]);

  const fetchTopMovers = useCallback(async () => {
    try {
      // Binance public API — fetch ALL USDT futures tickers
      const res = await fetch("https://fapi.binance.com/fapi/v1/ticker/24hr");
      if (!res.ok) return;

      const data: Array<{
        symbol: string;
        lastPrice: string;
        priceChangePercent: string;
        quoteVolume: string;
      }> = await res.json();

      // Top 10 by market cap (always shown first, in order)
      const TOP_MCAP = [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
      ];

      const allPairs = data
        .filter((d) => d.symbol.endsWith("USDT") && parseFloat(d.quoteVolume) > 1_000_000)
        .map((d) => ({
          symbol: d.symbol.replace("USDT", "/USDT"),
          rawSymbol: d.symbol,
          price: formatPrice(parseFloat(d.lastPrice)),
          change: parseFloat(d.priceChangePercent),
          absChange: Math.abs(parseFloat(d.priceChangePercent)),
          volume: parseFloat(d.quoteVolume),
        }));

      // First: top 10 market cap coins in order
      const mcapCoins = TOP_MCAP
        .map((sym) => allPairs.find((p) => p.rawSymbol === sym))
        .filter((p): p is NonNullable<typeof p> => p != null)
        .map((p) => ({ symbol: p.symbol, price: p.price, change: p.change }));

      // Then: top 6 movers (excluding already-shown mcap coins)
      const mcapSet = new Set(TOP_MCAP);
      const topMovers = allPairs
        .filter((p) => !mcapSet.has(p.rawSymbol))
        .sort((a, b) => b.absChange - a.absChange)
        .slice(0, 6)
        .map(({ symbol, price, change }) => ({ symbol, price, change }));

      const usdtPairs = [...mcapCoins, ...topMovers];

      if (usdtPairs.length > 0) setTickers(usdtPairs);
    } catch {
      // Silently fail
    }
  }, []);

  useEffect(() => {
    fetchTopMovers();
    const interval = setInterval(fetchTopMovers, 15_000);
    return () => clearInterval(interval);
  }, [fetchTopMovers]);

  // 4x duplication for seamless loop
  const items = tickers.length > 0
    ? [...tickers, ...tickers, ...tickers, ...tickers]
    : [];

  if (items.length === 0) {
    // Loading state — minimal bar
    return (
      <>
        <div className="fixed top-0 left-0 right-0 z-50 bg-[#0A0A0A]/95 border-b border-[#3B494B]/10 py-2.5 overflow-hidden backdrop-blur-sm">
          <div className="flex items-center justify-center">
            <span className="font-mono text-[10px] text-[#B9CACB]/30 uppercase tracking-widest">Loading market data...</span>
          </div>
        </div>
        <div className="h-[40px]" />
      </>
    );
  }

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes tickerScroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-25%); }
        }
      `}} />

      <div
        className="fixed top-0 left-0 right-0 z-50 bg-[#0A0A0A]/95 border-b border-[#3B494B]/10 py-2.5 overflow-hidden backdrop-blur-sm"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        {/* Edge fades */}
        <div className="absolute left-0 top-0 bottom-0 w-16 z-10 pointer-events-none"
          style={{ background: "linear-gradient(to right, #0A0A0A, transparent)" }} />
        <div className="absolute right-0 top-0 bottom-0 w-16 z-10 pointer-events-none"
          style={{ background: "linear-gradient(to left, #0A0A0A, transparent)" }} />

        {/* "TOP MOVERS" label */}
        <div className="absolute left-4 top-1/2 -translate-y-1/2 z-20 font-mono text-[8px] text-[#00F0FF]/40 uppercase tracking-[0.2em] hidden lg:block">
          &#10038; Live
        </div>

        <div
          className="flex"
          style={{
            width: "max-content",
            animation: "tickerScroll 50s linear infinite",
            animationPlayState: isPaused ? "paused" : "running",
            willChange: "transform",
          }}
        >
          {items.map((item, i) => (
            <TickerItemEl key={i} item={item} />
          ))}
        </div>
      </div>

      <div className="h-[40px]" />
    </>
  );
}
