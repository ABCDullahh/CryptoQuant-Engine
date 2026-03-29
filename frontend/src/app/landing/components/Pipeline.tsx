"use client";

import { useRef, useState, useEffect } from "react";
import { motion } from "framer-motion";

/* ══════════════════════════════════════════════
   Pipeline — "How It Works" scroll-triggered
   step sequence using sticky positioning,
   native scroll progress, and Framer Motion
   AnimatePresence for smooth step transitions.

   Two-column layout:
   Left (40%):  step number, icon, title, subtitle
   Right (60%): rich animated visual per step
   ══════════════════════════════════════════════ */

const STEPS = [
  {
    id: 1,
    title: "Real-Time Market Data",
    subtitle: "Binance USDM Futures WebSocket stream delivers live candlestick data, order flow, and market depth in sub-100ms latency.",
  },
  {
    id: 2,
    title: "16 Technical Indicators",
    subtitle: "EMA, RSI, MACD, Bollinger Bands, VWAP, OBV, ADX, ATR and more — computed in real-time on every incoming candle.",
  },
  {
    id: 3,
    title: "6 Strategies Score",
    subtitle: "Each strategy independently evaluates current market conditions and assigns a confidence score. Aggregate consensus drives the signal.",
  },
  {
    id: 4,
    title: "Signal Aggregated & Graded",
    subtitle: "Multi-strategy consensus produces a graded signal with precise entry, stop-loss, and take-profit levels.",
  },
  {
    id: 5,
    title: "Order Executed on Binance",
    subtitle: "Market order routed via dual-exchange architecture — ccxt.pro for WebSocket, ccxt.async_support for REST execution.",
  },
  {
    id: 6,
    title: "Real-Time P&L Tracking",
    subtitle: "Position tracked with live SL/TP management, circuit breakers, and portfolio-level risk controls.",
  },
];

const STRATEGIES = [
  { name: "Momentum", pct: 75, color: "#00F0FF" },
  { name: "Mean Reversion", pct: 45, color: "#40E56C" },
  { name: "SMC", pct: 88, color: "#00F0FF" },
  { name: "Volume Profile", pct: 62, color: "#40E56C" },
  { name: "Funding Arb", pct: 30, color: "#B9CACB" },
  { name: "Order Block", pct: 70, color: "#FFB3B6" },
];

const INDICATORS_DATA = [
  { label: "RSI", value: "67.4", spark: "M0 8 L3 6 L6 9 L9 4 L12 7 L15 3 L18 6", color: "#00F0FF" },
  { label: "EMA 9", value: "70,521", spark: "M0 10 L3 8 L6 7 L9 5 L12 4 L15 3 L18 2", color: "#40E56C" },
  { label: "MACD", value: "+12.8", spark: "M0 9 L3 7 L6 10 L9 5 L12 3 L15 6 L18 2", color: "#00F0FF" },
  { label: "VWAP", value: "70,488", spark: "M0 6 L3 5 L6 7 L9 4 L12 5 L15 3 L18 4", color: "#B9CACB" },
  { label: "ADX", value: "34.2", spark: "M0 10 L3 9 L6 6 L9 4 L12 5 L15 3 L18 4", color: "#FFB3B6" },
  { label: "BB Width", value: "0.032", spark: "M0 5 L3 7 L6 4 L9 8 L12 6 L15 9 L18 7", color: "#40E56C" },
  { label: "ATR", value: "285.4", spark: "M0 8 L3 5 L6 9 L9 3 L12 7 L15 4 L18 6", color: "#FFB4AB" },
  { label: "OBV", value: "+1.4M", spark: "M0 10 L3 8 L6 9 L9 6 L12 5 L15 3 L18 2", color: "#00F0FF" },
];

/* ── Step visual components (Right Column — 60%) ── */

function StepMarketData({ isActive }: { isActive: boolean }) {
  const candles = [
    { h: 56, color: "#40E56C", bodyTop: 16, bodyH: 26, vol: 32 },
    { h: 44, color: "#FFB4AB", bodyTop: 10, bodyH: 22, vol: 24 },
    { h: 68, color: "#40E56C", bodyTop: 14, bodyH: 36, vol: 40 },
    { h: 38, color: "#FFB4AB", bodyTop: 8, bodyH: 20, vol: 18 },
    { h: 72, color: "#40E56C", bodyTop: 18, bodyH: 38, vol: 44 },
    { h: 50, color: "#40E56C", bodyTop: 12, bodyH: 28, vol: 28 },
    { h: 42, color: "#FFB4AB", bodyTop: 10, bodyH: 20, vol: 22 },
    { h: 80, color: "#40E56C", bodyTop: 20, bodyH: 42, vol: 48 },
    { h: 54, color: "#FFB4AB", bodyTop: 14, bodyH: 26, vol: 30 },
    { h: 64, color: "#40E56C", bodyTop: 16, bodyH: 32, vol: 38 },
  ];

  const prices = ["70,850", "70,720", "70,640", "70,520", "70,400"];

  return (
    <motion.div
      className="w-full bg-[#1C1B1B] border border-[#3B494B]/20 rounded-sm overflow-hidden"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={isActive ? { opacity: 1, scale: 1 } : undefined}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      {/* Chart header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#3B494B]/15">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold text-[#E5E2E1]">ETHUSDT</span>
          <span className="font-mono text-[10px] text-[#00F0FF]">Perpetual</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] text-[#B9CACB]/50">5m</span>
          <span className="font-mono text-[10px] text-[#B9CACB]/50">15m</span>
          <span className="font-mono text-[10px] text-[#00F0FF] border-b border-[#00F0FF]">1h</span>
          <span className="font-mono text-[10px] text-[#B9CACB]/50">4h</span>
        </div>
        <motion.div
          className="flex items-center gap-1.5"
          initial={{ opacity: 0 }}
          animate={isActive ? { opacity: 1 } : undefined}
          transition={{ delay: 0.1, duration: 0.3 }}
        >
          <div className="w-1.5 h-1.5 rounded-full bg-[#40E56C] animate-pulse" />
          <span className="font-mono text-[10px] text-[#40E56C]">LIVE</span>
        </motion.div>
      </div>

      {/* Chart body */}
      <div className="flex">
        {/* Candle area */}
        <div className="flex-1 p-4">
          {/* Candlesticks */}
          <div className="flex items-end gap-[6px] mb-2" style={{ height: 120 }}>
            {candles.map((c, i) => (
              <motion.div
                key={i}
                className="flex flex-col items-center flex-1"
                initial={{ opacity: 0, scaleY: 0 }}
                animate={isActive ? { opacity: 1, scaleY: 1 } : undefined}
                transition={{ delay: i * 0.06, duration: 0.35, ease: "easeOut" }}
                style={{ originY: 1 }}
              >
                <div className="relative w-full" style={{ height: c.h }}>
                  {/* Wick */}
                  <div
                    className="absolute left-1/2 -translate-x-1/2 w-[1.5px]"
                    style={{ backgroundColor: c.color, height: "100%", opacity: 0.5 }}
                  />
                  {/* Body */}
                  <div
                    className="absolute left-[15%] w-[70%] rounded-[1px]"
                    style={{ backgroundColor: c.color, top: c.bodyTop, height: c.bodyH }}
                  />
                </div>
              </motion.div>
            ))}
          </div>

          {/* Volume bars */}
          <div className="flex items-end gap-[6px] border-t border-[#3B494B]/10 pt-2" style={{ height: 36 }}>
            {candles.map((c, i) => (
              <motion.div
                key={i}
                className="flex-1 rounded-[1px]"
                style={{ backgroundColor: c.color, opacity: 0.25 }}
                initial={{ height: 0 }}
                animate={isActive ? { height: c.vol } : undefined}
                transition={{ delay: i * 0.06 + 0.3, duration: 0.3, ease: "easeOut" }}
              />
            ))}
          </div>
        </div>

        {/* Price axis */}
        <div className="w-[72px] border-l border-[#3B494B]/10 py-4 pr-3 flex flex-col justify-between">
          {prices.map((p, i) => (
            <motion.span
              key={i}
              className="font-mono text-[9px] text-[#B9CACB]/40 text-right block"
              initial={{ opacity: 0, x: 8 }}
              animate={isActive ? { opacity: 1, x: 0 } : undefined}
              transition={{ delay: i * 0.08 + 0.5, duration: 0.25 }}
            >
              {p}
            </motion.span>
          ))}
        </div>
      </div>

      {/* Bottom ticker */}
      <motion.div
        className="flex items-center gap-4 px-4 py-2 border-t border-[#3B494B]/10 bg-[#131313]"
        initial={{ opacity: 0 }}
        animate={isActive ? { opacity: 1 } : undefined}
        transition={{ delay: 0.04, duration: 0.3 }}
      >
        <span className="font-mono text-xs font-bold text-[#40E56C]">70,521.40</span>
        <span className="font-mono text-[10px] text-[#40E56C]">+1.24%</span>
        <span className="font-mono text-[10px] text-[#B9CACB]/40">Vol 24h: 847.2K</span>
        <span className="font-mono text-[10px] text-[#B9CACB]/40">OI: $2.4B</span>
      </motion.div>
    </motion.div>
  );
}

function StepIndicators({ isActive }: { isActive: boolean }) {
  return (
    <motion.div
      className="w-full bg-[#1C1B1B] border border-[#3B494B]/20 rounded-sm overflow-hidden"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={isActive ? { opacity: 1, scale: 1 } : undefined}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#3B494B]/15">
        <span className="font-mono text-xs font-bold text-[#E5E2E1]">Indicator Dashboard</span>
        <span className="font-mono text-[10px] text-[#B9CACB]/40">16 active</span>
      </div>

      {/* Indicator grid */}
      <div className="grid grid-cols-2 gap-[1px] bg-[#3B494B]/10">
        {INDICATORS_DATA.map((ind, i) => (
          <motion.div
            key={i}
            className="bg-[#1C1B1B] p-3 flex items-center gap-3"
            initial={{ opacity: 0, y: 12 }}
            animate={isActive ? { opacity: 1, y: 0 } : undefined}
            transition={{ delay: i * 0.07, duration: 0.3, ease: "easeOut" }}
          >
            {/* Colored dot */}
            <div
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: ind.color, boxShadow: `0 0 6px ${ind.color}40` }}
            />
            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="font-mono text-[9px] text-[#B9CACB]/50 uppercase tracking-widest">
                {ind.label}
              </div>
              <div className="font-mono text-sm font-bold" style={{ color: ind.color }}>
                {ind.value}
              </div>
            </div>
            {/* Mini sparkline */}
            <svg width="40" height="16" viewBox="0 0 18 12" className="shrink-0">
              <motion.path
                d={ind.spark}
                fill="none"
                stroke={ind.color}
                strokeWidth="1.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={isActive ? { pathLength: 1, opacity: 0.6 } : undefined}
                transition={{ delay: i * 0.07 + 0.2, duration: 0.25, ease: "easeOut" }}
              />
            </svg>
          </motion.div>
        ))}
      </div>

      {/* Footer */}
      <motion.div
        className="flex items-center justify-between px-4 py-2 border-t border-[#3B494B]/10 bg-[#131313]"
        initial={{ opacity: 0 }}
        animate={isActive ? { opacity: 1 } : undefined}
        transition={{ delay: 0.1, duration: 0.3 }}
      >
        <span className="font-mono text-[10px] text-[#B9CACB]/40">Updated 0.2s ago</span>
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-[#40E56C] animate-pulse" />
          <span className="font-mono text-[10px] text-[#40E56C]">Streaming</span>
        </div>
      </motion.div>
    </motion.div>
  );
}

function StepStrategies({ isActive }: { isActive: boolean }) {
  const aggregate = Math.round(
    STRATEGIES.reduce((sum, s) => sum + s.pct, 0) / STRATEGIES.length
  );

  return (
    <motion.div
      className="w-full bg-[#1C1B1B] border border-[#3B494B]/20 rounded-sm overflow-hidden"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={isActive ? { opacity: 1, scale: 1 } : undefined}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#3B494B]/15">
        <span className="font-mono text-xs font-bold text-[#E5E2E1]">Strategy Evaluation</span>
        <span className="font-mono text-[10px] text-[#B9CACB]/40">6 active</span>
      </div>

      <div className="p-4 space-y-3">
        {STRATEGIES.map((s, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -20 }}
            animate={isActive ? { opacity: 1, x: 0 } : undefined}
            transition={{ delay: i * 0.08, duration: 0.35, ease: "easeOut" }}
          >
            <div className="relative h-7 bg-[#0D0D0D] rounded-sm overflow-hidden">
              {/* Fill bar */}
              <motion.div
                className="absolute inset-y-0 left-0 rounded-sm"
                style={{ backgroundColor: s.color, opacity: 0.2 }}
                initial={{ width: "0%" }}
                animate={isActive ? { width: `${s.pct}%` } : undefined}
                transition={{ delay: i * 0.08 + 0.1, duration: 0.25, ease: "easeOut" }}
              />
              {/* Brighter leading edge */}
              <motion.div
                className="absolute inset-y-0 left-0 rounded-sm"
                style={{
                  background: `linear-gradient(90deg, transparent ${Math.max(s.pct - 8, 0)}%, ${s.color}40 ${s.pct}%)`,
                }}
                initial={{ width: "0%" }}
                animate={isActive ? { width: `${s.pct}%` } : undefined}
                transition={{ delay: i * 0.08 + 0.1, duration: 0.25, ease: "easeOut" }}
              />
              {/* Strategy name (inside bar) */}
              <div className="absolute inset-0 flex items-center justify-between px-3">
                <span className="font-mono text-[11px] font-bold text-[#E5E2E1] z-10">
                  {s.name}
                </span>
                <motion.span
                  className="font-mono text-[11px] font-bold z-10"
                  style={{ color: s.color }}
                  initial={{ opacity: 0 }}
                  animate={isActive ? { opacity: 1 } : undefined}
                  transition={{ delay: i * 0.08 + 0.3, duration: 0.3 }}
                >
                  {s.pct}%
                </motion.span>
              </div>
            </div>
          </motion.div>
        ))}

        {/* Aggregate score */}
        <motion.div
          className="mt-4 pt-3 border-t border-[#3B494B]/15 flex items-center justify-between"
          initial={{ opacity: 0, y: 8 }}
          animate={isActive ? { opacity: 1, y: 0 } : undefined}
          transition={{ delay: 0.06, duration: 0.35, ease: "easeOut" }}
        >
          <span className="font-mono text-xs text-[#B9CACB]/60 uppercase tracking-widest">
            Aggregate Score
          </span>
          <div className="flex items-center gap-3">
            <div className="w-24 h-1.5 bg-[#0D0D0D] rounded-sm overflow-hidden">
              <motion.div
                className="h-full rounded-sm bg-[#00F0FF]"
                initial={{ width: "0%" }}
                animate={isActive ? { width: `${aggregate}%` } : undefined}
                transition={{ delay: 0.065, duration: 0.25, ease: "easeOut" }}
              />
            </div>
            <motion.span
              className="font-mono text-lg font-black text-[#00F0FF]"
              initial={{ opacity: 0 }}
              animate={isActive ? { opacity: 1 } : undefined}
              transition={{ delay: 0.1, duration: 0.3 }}
            >
              {aggregate}%
            </motion.span>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}

function StepSignal({ isActive }: { isActive: boolean }) {
  return (
    <div className="relative w-full">
      {/* Pulse rings behind card */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div
          className="absolute w-[90%] h-[90%] rounded-sm border border-[#40E56C]/15 pipeline-pulse"
          style={{ animationDelay: "0s" }}
        />
        <div
          className="absolute w-[100%] h-[100%] rounded-sm border border-[#40E56C]/8 pipeline-pulse"
          style={{ animationDelay: "0.6s" }}
        />
      </div>

      {/* Signal card */}
      <motion.div
        className="relative w-full bg-[#1C1B1B] border border-[#40E56C]/25 rounded-sm overflow-hidden"
        initial={{ opacity: 0, scale: 0.92 }}
        animate={isActive ? { opacity: 1, scale: 1 } : undefined}
        transition={{ duration: 0.4, ease: "easeOut" }}
        style={{ boxShadow: "0 0 40px rgba(64, 229, 108, 0.06)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#40E56C]/10 bg-[#131313]">
          <motion.span
            className="font-mono text-[10px] font-bold text-[#0D0D0D] bg-[#00F0FF] px-2 py-0.5 rounded-[2px] uppercase tracking-wider"
            initial={{ opacity: 0, x: -10 }}
            animate={isActive ? { opacity: 1, x: 0 } : undefined}
            transition={{ delay: 0.06, duration: 0.3 }}
          >
            New Signal
          </motion.span>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-[#B9CACB]/40">2026-03-28 14:32:18</span>
          </div>
        </div>

        {/* Two-column body */}
        <div className="grid grid-cols-2 gap-0 divide-x divide-[#3B494B]/10">
          {/* Left: Direction + pair + grade */}
          <div className="p-4 space-y-3">
            <div>
              <div className="font-mono text-[9px] text-[#B9CACB]/50 uppercase tracking-widest mb-1">Pair</div>
              <div className="font-mono text-lg font-black text-[#E5E2E1]">ETH/USDT</div>
            </div>
            <div className="flex items-center gap-2">
              <motion.span
                className="font-mono text-xs font-bold text-[#0D0D0D] bg-[#40E56C] px-2.5 py-1 rounded-[2px]"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={isActive ? { opacity: 1, scale: 1 } : undefined}
                transition={{ delay: 0.1, duration: 0.3, ease: "backOut" }}
              >
                LONG
              </motion.span>
              <motion.span
                className="font-mono text-xs font-bold text-[#00F0FF] bg-[#00F0FF]/10 px-2.5 py-1 rounded-[2px] border border-[#00F0FF]/20"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={isActive ? { opacity: 1, scale: 1 } : undefined}
                transition={{ delay: 0.12, duration: 0.3, ease: "backOut" }}
              >
                Grade A
              </motion.span>
            </div>
            <div>
              <div className="font-mono text-[9px] text-[#B9CACB]/50 uppercase tracking-widest mb-1">Leverage</div>
              <div className="font-mono text-sm font-bold text-[#E5E2E1]">10x</div>
            </div>
          </div>

          {/* Right: Prices */}
          <div className="p-4 space-y-2.5">
            <div>
              <div className="font-mono text-[9px] text-[#B9CACB]/50 uppercase tracking-widest mb-0.5">Entry</div>
              <div className="font-mono text-sm font-bold text-[#E5E2E1]">$2,185.55</div>
            </div>
            <div>
              <div className="font-mono text-[9px] text-[#B9CACB]/50 uppercase tracking-widest mb-0.5">Stop Loss</div>
              <div className="font-mono text-sm font-bold text-[#FFB4AB]">$2,163.86</div>
            </div>
            <div>
              <div className="font-mono text-[9px] text-[#B9CACB]/50 uppercase tracking-widest mb-0.5">Take Profit</div>
              <div className="font-mono text-sm font-bold text-[#40E56C]">$2,218.08</div>
            </div>
            <div>
              <div className="font-mono text-[9px] text-[#B9CACB]/50 uppercase tracking-widest mb-0.5">R:R</div>
              <div className="font-mono text-sm font-bold text-[#00F0FF]">1 : 1.50</div>
            </div>
          </div>
        </div>

        {/* Strength meter */}
        <div className="px-4 py-3 border-t border-[#3B494B]/10">
          <div className="flex items-center gap-3">
            <span className="font-mono text-[9px] text-[#B9CACB]/50 uppercase tracking-widest shrink-0">
              Strength
            </span>
            <div className="flex-1 h-2 bg-[#0D0D0D] rounded-sm overflow-hidden">
              <motion.div
                className="h-full rounded-sm"
                style={{
                  background: "linear-gradient(90deg, #00F0FF, #40E56C)",
                  boxShadow: "0 0 8px #00F0FF40",
                }}
                initial={{ width: "0%" }}
                animate={isActive ? { width: "90%" } : undefined}
                transition={{ delay: 0.12, duration: 0.3, ease: "easeOut" }}
              />
            </div>
            <motion.span
              className="font-mono text-sm font-black text-[#00F0FF]"
              initial={{ opacity: 0 }}
              animate={isActive ? { opacity: 1 } : undefined}
              transition={{ delay: 0.1, duration: 0.3 }}
            >
              90%
            </motion.span>
          </div>
        </div>

        {/* Strategy breakdown */}
        <motion.div
          className="px-4 py-2.5 border-t border-[#3B494B]/10 bg-[#131313] flex flex-wrap gap-x-4 gap-y-1"
          initial={{ opacity: 0 }}
          animate={isActive ? { opacity: 1 } : undefined}
          transition={{ delay: 0.04, duration: 0.3 }}
        >
          <span className="font-mono text-[10px] text-[#B9CACB]/40">momentum: <span className="text-[#00F0FF]">0.75</span></span>
          <span className="font-mono text-[10px] text-[#B9CACB]/40">smc: <span className="text-[#00F0FF]">0.88</span></span>
          <span className="font-mono text-[10px] text-[#B9CACB]/40">volume: <span className="text-[#40E56C]">0.62</span></span>
          <span className="font-mono text-[10px] text-[#B9CACB]/40">mean_rev: <span className="text-[#B9CACB]">0.45</span></span>
        </motion.div>
      </motion.div>
    </div>
  );
}

function StepExecution({ isActive }: { isActive: boolean }) {
  return (
    <motion.div
      className="w-full bg-[#1C1B1B] border border-[#3B494B]/20 rounded-sm overflow-hidden"
      initial={{ opacity: 0, y: 12 }}
      animate={isActive ? { opacity: 1, y: 0 } : undefined}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#3B494B]/15 bg-[#131313]">
        <div className="flex items-center gap-2">
          <motion.div
            className="flex items-center gap-1.5"
            initial={{ opacity: 0 }}
            animate={isActive ? { opacity: 1 } : undefined}
            transition={{ delay: 0.04, duration: 0.3 }}
          >
            {/* Animated checkmark circle */}
            <motion.div
              className="w-5 h-5 rounded-full bg-[#40E56C]/15 border border-[#40E56C]/30 flex items-center justify-center"
              initial={{ scale: 0 }}
              animate={isActive ? { scale: 1 } : undefined}
              transition={{ delay: 0.04, duration: 0.3, ease: "backOut" }}
            >
              <motion.svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                <motion.path
                  d="M5 13l4 4L19 7"
                  stroke="#40E56C"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  initial={{ pathLength: 0 }}
                  animate={isActive ? { pathLength: 1 } : undefined}
                  transition={{ delay: 0.065, duration: 0.4, ease: "easeOut" }}
                />
              </motion.svg>
            </motion.div>
            <span className="font-mono text-xs font-bold text-[#40E56C]">ORDER FILLED</span>
          </motion.div>
        </div>
        <motion.span
          className="font-mono text-[10px] text-[#B9CACB]/40"
          initial={{ opacity: 0 }}
          animate={isActive ? { opacity: 1 } : undefined}
          transition={{ delay: 0.1, duration: 0.3 }}
        >
          2026-03-28 14:32:19.847
        </motion.span>
      </div>

      {/* Order details */}
      <div className="p-4">
        {/* Exchange badge */}
        <div className="flex items-center gap-2 mb-4">
          <motion.span
            className="font-mono text-[10px] font-bold text-[#0D0D0D] bg-[#00F0FF] px-2 py-0.5 rounded-[2px] uppercase"
            initial={{ opacity: 0, x: -10 }}
            animate={isActive ? { opacity: 1, x: 0 } : undefined}
            transition={{ delay: 0.04, duration: 0.3 }}
          >
            Market Buy
          </motion.span>
          <span className="font-mono text-sm font-bold text-[#E5E2E1]">ETH/USDT</span>
          <span className="font-mono text-[10px] text-[#B9CACB]/40">Perpetual</span>
        </div>

        {/* Detail grid */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-3">
          {[
            { label: "Side", value: "BUY (Long)", color: "#40E56C" },
            { label: "Type", value: "MARKET", color: "#E5E2E1" },
            { label: "Quantity", value: "0.500 ETH", color: "#E5E2E1" },
            { label: "Avg. Price", value: "$2,185.55", color: "#E5E2E1" },
            { label: "Fee", value: "0.437 USDT", color: "#FFB4AB" },
            { label: "Total Cost", value: "$1,092.78", color: "#E5E2E1" },
          ].map((d, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={isActive ? { opacity: 1, y: 0 } : undefined}
              transition={{ delay: i * 0.06 + 0.2, duration: 0.25 }}
            >
              <div className="font-mono text-[9px] text-[#B9CACB]/50 uppercase tracking-widest">{d.label}</div>
              <div className="font-mono text-sm font-bold mt-0.5" style={{ color: d.color }}>{d.value}</div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <motion.div
        className="flex items-center justify-between px-4 py-2.5 border-t border-[#3B494B]/10 bg-[#131313]"
        initial={{ opacity: 0 }}
        animate={isActive ? { opacity: 1 } : undefined}
        transition={{ delay: 0.065, duration: 0.3 }}
      >
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-[#B9CACB]/40">Order ID:</span>
          <span className="font-mono text-[10px] text-[#B9CACB]/60">e7f3a2b1-9c4d</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-[#B9CACB]/40">Latency:</span>
          <span className="font-mono text-[10px] text-[#40E56C]">47ms</span>
        </div>
      </motion.div>
    </motion.div>
  );
}

function StepMonitoring({ isActive }: { isActive: boolean }) {
  const [pnl, setPnl] = useState(0);

  useEffect(() => {
    const target = 33.54;
    const duration = 800;
    const startTime = performance.now();

    function tick(now: number) {
      const elapsed = now - startTime;
      const t = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setPnl(target * eased);
      if (t < 1) requestAnimationFrame(tick);
    }

    const raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <motion.div
      className="w-full bg-[#1C1B1B] border border-[#3B494B]/20 rounded-sm overflow-hidden"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={isActive ? { opacity: 1, scale: 1 } : undefined}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      {/* P&L header */}
      <div className="px-4 pt-5 pb-4 text-center border-b border-[#3B494B]/10">
        <div className="font-mono text-[10px] text-[#B9CACB]/50 uppercase tracking-widest mb-2">
          Unrealized P&L
        </div>
        <div
          className="font-mono text-4xl md:text-5xl font-black text-[#40E56C]"
          style={{ textShadow: "0 0 30px rgba(64, 229, 108, 0.3), 0 0 60px rgba(64, 229, 108, 0.1)" }}
        >
          +${pnl.toFixed(2)}
        </div>
      </div>

      {/* Stat cards row */}
      <div className="grid grid-cols-3 divide-x divide-[#3B494B]/10">
        {[
          { label: "ROI", value: "+1.53%", color: "#40E56C" },
          { label: "Duration", value: "2h 14m", color: "#E5E2E1" },
          { label: "Status", value: "OPEN", color: "#00F0FF" },
        ].map((stat, i) => (
          <motion.div
            key={i}
            className="p-3 text-center"
            initial={{ opacity: 0, y: 10 }}
            animate={isActive ? { opacity: 1, y: 0 } : undefined}
            transition={{ delay: i * 0.1 + 0.4, duration: 0.3, ease: "easeOut" }}
          >
            <div className="font-mono text-[9px] text-[#B9CACB]/50 uppercase tracking-widest mb-1">
              {stat.label}
            </div>
            <div className="font-mono text-sm font-bold" style={{ color: stat.color }}>
              {stat.value}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Dashboard preview */}
      <motion.div
        className="border-t border-[#3B494B]/10"
        initial={{ opacity: 0, y: 12 }}
        animate={isActive ? { opacity: 1, y: 0 } : undefined}
        transition={{ delay: 0.06, duration: 0.4, ease: "easeOut" }}
      >
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0D0D0D] border-b border-[#3B494B]/10">
          <div className="w-1.5 h-1.5 rounded-full bg-[#FFB4AB]/40" />
          <div className="w-1.5 h-1.5 rounded-full bg-[#FFB3B6]/30" />
          <div className="w-1.5 h-1.5 rounded-full bg-[#40E56C]/40" />
          <div className="flex-1 flex justify-center">
            <div className="bg-[#1C1B1B] px-3 py-0.5 rounded-sm text-[8px] font-mono text-[#B9CACB]/30">
              localhost:3000/dashboard
            </div>
          </div>
        </div>
        <img
          src="/docs/images/02-dashboard.png"
          alt="Dashboard preview"
          className="w-full"
          width={1200}
          height={700}
          loading="lazy"
          decoding="async"
        />
      </motion.div>
    </motion.div>
  );
}

/* ── Step icon SVGs ── */

function CandlestickIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00F0FF" strokeWidth="2" strokeLinecap="round">
      <line x1="9" y1="2" x2="9" y2="22" />
      <rect x="5" y="6" width="8" height="10" rx="1" fill="#00F0FF" fillOpacity="0.2" stroke="#00F0FF" />
      <line x1="18" y1="4" x2="18" y2="20" />
      <rect x="14" y="8" width="8" height="8" rx="1" fill="#FFB4AB" fillOpacity="0.2" stroke="#FFB4AB" />
    </svg>
  );
}

function IndicatorIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00F0FF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 18 7 12 11 15 15 8 21 4" />
      <polyline points="3 22 3 2" />
      <polyline points="1 22 23 22" />
    </svg>
  );
}

function StrategyIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00F0FF" strokeWidth="2" strokeLinecap="round">
      <rect x="3" y="4" width="18" height="4" rx="1" fill="#00F0FF" fillOpacity="0.15" />
      <rect x="3" y="10" width="12" height="4" rx="1" fill="#40E56C" fillOpacity="0.15" stroke="#40E56C" />
      <rect x="3" y="16" width="15" height="4" rx="1" fill="#B9CACB" fillOpacity="0.15" stroke="#B9CACB" />
    </svg>
  );
}

function SignalIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#40E56C" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="3" fill="#40E56C" fillOpacity="0.2" />
      <path d="M8 8a6 6 0 0 1 8 0" />
      <path d="M5 5a10 10 0 0 1 14 0" />
    </svg>
  );
}

function ExecutionIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00F0FF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L2 7l10 5 10-5-10-5z" fill="#00F0FF" fillOpacity="0.1" />
      <path d="M2 17l10 5 10-5" />
      <path d="M2 12l10 5 10-5" />
    </svg>
  );
}

function MonitorIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#40E56C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="20" height="14" rx="2" fill="#40E56C" fillOpacity="0.1" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
      <polyline points="6 10 10 7 14 11 18 8" stroke="#40E56C" />
    </svg>
  );
}

const STEP_ICONS = [CandlestickIcon, IndicatorIcon, StrategyIcon, SignalIcon, ExecutionIcon, MonitorIcon];
const STEP_VISUALS = [StepMarketData, StepIndicators, StepStrategies, StepSignal, StepExecution, StepMonitoring];


/* ══════════════════════════════════════════════
   Main Component
   ══════════════════════════════════════════════ */

export default function Pipeline() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const [scrollProgress, setScrollProgress] = useState(0);

  /* ── Native scroll listener using getBoundingClientRect (rAF-throttled) ── */
  useEffect(() => {
    let ticking = false;

    function handleScroll() {
      if (!ticking) {
        requestAnimationFrame(() => {
          if (!sectionRef.current) { ticking = false; return; }
          const rect = sectionRef.current.getBoundingClientRect();
          const sectionH = sectionRef.current.offsetHeight;
          const viewH = window.innerHeight;
          const scrolled = -rect.top;
          const total = sectionH - viewH;
          if (total > 0) {
            const progress = Math.min(Math.max(scrolled / total, 0), 1);
            setScrollProgress(progress);
          }
          ticking = false;
        });
        ticking = true;
      }
    }

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    return () => {
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  /* ── Derive active step from scroll progress ── */
  const stepSize = 1 / STEPS.length;
  const rawStep = Math.floor(scrollProgress / stepSize);
  const currentStep = Math.min(rawStep, STEPS.length - 1);

  return (
    <>
      {/* Pulse + glow keyframe CSS */}
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes pipeline-pulse {
          0% { transform: scale(1); opacity: 0.5; }
          100% { transform: scale(1.3); opacity: 0; }
        }
        .pipeline-pulse {
          animation: pipeline-pulse 2s ease-out infinite;
        }
        @keyframes pipeline-dot-glow {
          0%, 100% { box-shadow: 0 0 8px #00F0FF60, 0 0 20px #00F0FF30; }
          50% { box-shadow: 0 0 14px #00F0FF80, 0 0 28px #00F0FF40; }
        }
        .pipeline-dot-active {
          animation: pipeline-dot-glow 2s ease-in-out infinite;
        }
      `}} />

      <section
        ref={sectionRef}
        className="relative bg-[#0D0D0D]"
        style={{ height: "400vh" }}
      >
        {/* ── Sticky viewport pinned while scrolling through 400vh ── */}
        <div className="sticky top-[40px] flex items-center overflow-hidden" style={{ height: "calc(100vh - 40px)" }}>
          <div className="w-full max-w-7xl mx-auto px-6 md:px-12 flex gap-6 md:gap-10">
            {/* ── Far left: Progress dots with connecting line ── */}
            <div className="hidden md:flex flex-col items-center justify-center shrink-0">
              {STEPS.map((_, i) => {
                const isActive = i === currentStep;
                const isPast = i < currentStep;

                const segStart = (i + 1) * stepSize;
                const segEnd = (i + 2) * stepSize;
                const segFill =
                  i < STEPS.length - 1
                    ? scrollProgress >= segEnd
                      ? 1
                      : scrollProgress <= segStart
                        ? 0
                        : (scrollProgress - segStart) / (segEnd - segStart)
                    : 0;

                return (
                  <div key={i} className="flex flex-col items-center">
                    {/* Dot */}
                    <div
                      className={`rounded-full transition-all duration-300 ${isActive ? "pipeline-dot-active" : ""}`}
                      style={{
                        width: isActive ? 12 : 8,
                        height: isActive ? 12 : 8,
                        backgroundColor: isActive || isPast ? "#00F0FF" : "#3B494B",
                        boxShadow: isActive
                          ? "0 0 12px #00F0FF60, 0 0 24px #00F0FF30"
                          : isPast
                            ? "0 0 4px #00F0FF30"
                            : "none",
                      }}
                    />
                    {/* Connecting line segment */}
                    {i < STEPS.length - 1 && (
                      <div
                        className="w-[2px] relative overflow-hidden"
                        style={{ height: 32, backgroundColor: "#3B494B30" }}
                      >
                        <div
                          className="absolute top-0 left-0 w-full transition-all duration-300"
                          style={{
                            height: isPast ? "100%" : isActive ? `${segFill * 100}%` : "0%",
                            backgroundColor: "#00F0FF",
                          }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* ── Content: Two-column layout ── */}
            <div className="flex-1 min-w-0">
              {/* Section label */}
              <div className="font-mono text-[10px] text-[#B9CACB]/40 uppercase tracking-widest mb-4">
                How It Works
              </div>

              {/* Render ALL steps simultaneously — show/hide via CSS opacity+transform (GPU only, zero DOM churn) */}
              <div className="relative" style={{ minHeight: 320 }}>
                {STEPS.map((step, i) => {
                  const Icon = STEP_ICONS[i];
                  const Visual = STEP_VISUALS[i];
                  const isActive = i === currentStep;
                  return (
                    <div
                      key={i}
                      className="absolute inset-0 flex flex-col md:flex-row gap-6 md:gap-10"
                      style={{
                        opacity: isActive ? 1 : 0,
                        transform: isActive ? "translateY(0)" : "translateY(8px)",
                        transition: "opacity 0.18s ease-out, transform 0.18s ease-out",
                        pointerEvents: isActive ? "auto" : "none",
                        willChange: isActive ? "opacity, transform" : "auto",
                      }}
                    >
                      {/* ── Left Column (40%): Title area ── */}
                      <div className="md:w-[38%] shrink-0">
                        <div className="flex items-center gap-3 mb-3">
                          <div className="w-10 h-10 rounded-sm bg-[#00F0FF]/10 flex items-center justify-center">
                            <Icon />
                          </div>
                          <span className="font-mono text-[10px] text-[#B9CACB]/40 uppercase tracking-widest">
                            Step {step.id} of 6
                          </span>
                        </div>
                        <h2 className="font-mono font-black text-2xl md:text-3xl lg:text-4xl text-[#E5E2E1] tracking-tight mb-3">
                          {step.title}
                        </h2>
                        <p className="text-sm text-[#B9CACB]/80 leading-relaxed">
                          {step.subtitle}
                        </p>
                        <div
                          className="mt-6 h-[1px] rounded-full"
                          style={{
                            background: "linear-gradient(90deg, #00F0FF40, transparent)",
                            width: isActive ? "80%" : "0%",
                            transition: "width 0.3s ease-out 0.1s",
                          }}
                        />
                      </div>
                      {/* ── Right Column (60%): Rich visual ── */}
                      <div className="md:w-[62%] flex items-start">
                        <Visual isActive={isActive} />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Mobile step dots */}
              <div className="flex md:hidden items-center justify-center gap-2 mt-8">
                {STEPS.map((_, i) => (
                  <div
                    key={i}
                    className={`rounded-full transition-all duration-300 ${i === currentStep ? "pipeline-dot-active" : ""}`}
                    style={{
                      width: i === currentStep ? 10 : 6,
                      height: i === currentStep ? 10 : 6,
                      backgroundColor: i <= currentStep ? "#00F0FF" : "#3B494B",
                    }}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
