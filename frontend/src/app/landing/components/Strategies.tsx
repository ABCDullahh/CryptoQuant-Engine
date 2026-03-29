"use client";

import { motion } from "framer-motion";

/* ══════════════════════════════════════════════
   Strategies — 6 cards in a responsive grid
   Animated weight bars + stagger reveal
   ══════════════════════════════════════════════ */

const STRATEGIES = [
  {
    name: "Momentum",
    weight: 15,
    color: "#00F0FF",
    desc: "EMA crossovers, RSI divergence, ADX trend strength confirmation",
    indicators: ["EMA 9/21", "RSI 14", "ADX"],
  },
  {
    name: "Mean Reversion",
    weight: 10,
    color: "#40E56C",
    desc: "Bollinger Band squeeze, RSI oversold/overbought with mean regression",
    indicators: ["BB 20", "RSI 14", "SMA 50"],
  },
  {
    name: "Smart Money",
    weight: 25,
    color: "#00F0FF",
    desc: "Institutional order flow, liquidity sweeps, fair value gap detection",
    indicators: ["Order Flow", "FVG", "BOS/CHoCH"],
  },
  {
    name: "Volume Analysis",
    weight: 15,
    color: "#40E56C",
    desc: "OBV divergence, volume profile analysis, VWAP band positioning",
    indicators: ["OBV", "VWAP", "Vol SMA"],
  },
  {
    name: "Funding Arb",
    weight: 5,
    color: "#B9CACB",
    desc: "Funding rate extremes, open interest shifts, basis trade signals",
    indicators: ["Funding Rate", "OI Delta"],
  },
  {
    name: "Order Blocks",
    weight: 20,
    color: "#FFB3B6",
    desc: "Supply/demand zones, structure breaks, multi-timeframe confirmation",
    indicators: ["Zones", "BOS", "MTF"],
  },
];

export default function Strategies() {
  return (
    <section id="strategies" className="py-24 px-6 md:px-12 max-w-6xl mx-auto">
      {/* Header */}
      <motion.div
        className="text-center mb-16"
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.2 }}
        transition={{ type: "spring" as const, stiffness: 100, damping: 15 }}
      >
        <p className="font-mono text-[10px] text-[#00F0FF]/60 uppercase tracking-[0.3em] mb-3">
          Signal Pipeline
        </p>
        <h2 className="font-mono font-black text-3xl md:text-4xl text-[#E5E2E1] tracking-tight mb-4">
          6 Trading Strategies
        </h2>
        <p className="text-[#B9CACB] text-base max-w-lg mx-auto">
          Each strategy evaluates independently. Signals are aggregated, weighted, and graded A through D.
        </p>
      </motion.div>

      {/* Strategy Grid — 2 cols on desktop */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {STRATEGIES.map((s, i) => (
          <motion.div
            key={s.name}
            className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-5 hover:border-[#00F0FF]/10 transition-colors duration-300 group"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{
              type: "spring" as const,
              stiffness: 100,
              damping: 15,
              delay: i * 0.08,
            }}
          >
            {/* Top: name + weight */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div
                  className="w-1 h-8 rounded-sm"
                  style={{ background: s.color }}
                />
                <div>
                  <h3 className="font-mono font-bold text-sm text-[#E5E2E1] tracking-tight">
                    {s.name}
                  </h3>
                  <p className="font-mono text-[9px] text-[#B9CACB]/40 uppercase tracking-widest">
                    Strategy
                  </p>
                </div>
              </div>
              <span
                className="font-mono text-2xl font-black tabular-nums"
                style={{ color: s.color }}
              >
                {s.weight}%
              </span>
            </div>

            {/* Description */}
            <p className="text-xs text-[#B9CACB]/70 leading-relaxed mb-3 pl-4">
              {s.desc}
            </p>

            {/* Indicator tags */}
            <div className="flex flex-wrap gap-1.5 mb-3 pl-4">
              {s.indicators.map((ind) => (
                <span
                  key={ind}
                  className="font-mono text-[9px] px-2 py-0.5 rounded-sm bg-[#2A2A2A] text-[#B9CACB]/60"
                >
                  {ind}
                </span>
              ))}
            </div>

            {/* Weight bar */}
            <div className="h-1 w-full bg-[#2A2A2A] rounded-sm overflow-hidden ml-4" style={{ width: "calc(100% - 16px)" }}>
              <motion.div
                className="h-full rounded-sm"
                style={{ background: s.color }}
                initial={{ width: 0 }}
                whileInView={{ width: `${(s.weight / 25) * 100}%` }}
                viewport={{ once: true, amount: 0.5 }}
                transition={{ duration: 1, ease: "easeOut", delay: 0.3 + i * 0.08 }}
              />
            </div>
          </motion.div>
        ))}
      </div>

      {/* Total weight summary */}
      <motion.div
        className="mt-8 text-center"
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ delay: 0.6 }}
      >
        <span className="font-mono text-xs text-[#B9CACB]/30">
          Total weight: {STRATEGIES.reduce((sum, s) => sum + s.weight, 0)}% &middot; Missing 10% reserved for ML ensemble override
        </span>
      </motion.div>
    </section>
  );
}
