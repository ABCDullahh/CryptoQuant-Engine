"use client";

import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { ChevronDown, AlertTriangle, Search, X, BarChart3, Settings, Eye, EyeOff } from "lucide-react";
import {
  fetchCandles,
  fetchMarkets,
  fetchIndicators,
  fetchOrderBook,
  fetchPositions,
  fetchExchangePositions,
  fetchOrders,
  closePosition,
  fetchLeverageTiers,
  placeManualOrder,
  type CandleData,
  type MarketInfo,
  type IndicatorDataPoint,
  type OrderBookResponse,
  type Position,
  type ExchangePosition,
  type Order,
  type ManualOrderRequest,
} from "@/lib/api";
import { useWebSocket } from "@/hooks/useApi";
import type { PriceUpdate, OrderBookUpdate } from "@/lib/websocket";

/* =========================================================================
   Types & Config
   ========================================================================= */

const TIMEFRAMES = [
  { value: "1m", label: "1m", seconds: 60 },
  { value: "3m", label: "3m", seconds: 180 },
  { value: "5m", label: "5m", seconds: 300 },
  { value: "15m", label: "15m", seconds: 900 },
  { value: "30m", label: "30m", seconds: 1800 },
  { value: "1h", label: "1H", seconds: 3600 },
  { value: "2h", label: "2H", seconds: 7200 },
  { value: "4h", label: "4H", seconds: 14400 },
  { value: "6h", label: "6H", seconds: 21600 },
  { value: "8h", label: "8H", seconds: 28800 },
  { value: "12h", label: "12H", seconds: 43200 },
  { value: "1d", label: "1D", seconds: 86400 },
  { value: "1w", label: "1W", seconds: 604800 },
  { value: "1M", label: "1M", seconds: 2592000 },
];

interface IndicatorDef {
  id: string;
  label: string;
  category: "trend" | "momentum" | "volatility" | "volume";
  placement: "overlay" | "panel";
  color: string;
  apiParam: string;
  keys: string[];
  defaultPeriod?: number;
}

const INDICATOR_DEFS: IndicatorDef[] = [
  { id: "ema_9", label: "EMA 9", category: "trend", placement: "overlay", color: "#FFDD57", apiParam: "ema_9", keys: ["ema_9"], defaultPeriod: 9 },
  { id: "ema_21", label: "EMA 21", category: "trend", placement: "overlay", color: "#FF9F43", apiParam: "ema_21", keys: ["ema_21"], defaultPeriod: 21 },
  { id: "ema_55", label: "EMA 55", category: "trend", placement: "overlay", color: "#A855F7", apiParam: "ema_55", keys: ["ema_55"], defaultPeriod: 55 },
  { id: "ema_200", label: "EMA 200", category: "trend", placement: "overlay", color: "#EF4444", apiParam: "ema_200", keys: ["ema_200"], defaultPeriod: 200 },
  { id: "sma_20", label: "SMA 20", category: "trend", placement: "overlay", color: "#38BDF8", apiParam: "sma_20", keys: ["sma_20"], defaultPeriod: 20 },
  { id: "sma_50", label: "SMA 50", category: "trend", placement: "overlay", color: "#34D399", apiParam: "sma_50", keys: ["sma_50"], defaultPeriod: 50 },
  { id: "sma_200", label: "SMA 200", category: "trend", placement: "overlay", color: "#F472B6", apiParam: "sma_200", keys: ["sma_200"], defaultPeriod: 200 },
  { id: "bb", label: "Bollinger Bands", category: "volatility", placement: "overlay", color: "#818CF8", apiParam: "bb", keys: ["bb_upper", "bb_middle", "bb_lower"] },
  { id: "atr", label: "ATR (14)", category: "volatility", placement: "panel", color: "#A78BFA", apiParam: "atr", keys: ["atr"], defaultPeriod: 14 },
  { id: "rsi_14", label: "RSI (14)", category: "momentum", placement: "panel", color: "#FBBF24", apiParam: "rsi_14", keys: ["rsi_14"], defaultPeriod: 14 },
  { id: "macd", label: "MACD", category: "momentum", placement: "panel", color: "#38BDF8", apiParam: "macd", keys: ["macd", "macd_signal", "macd_histogram"] },
  { id: "stoch", label: "Stochastic", category: "momentum", placement: "panel", color: "#34D399", apiParam: "stoch", keys: ["stoch_k", "stoch_d"], defaultPeriod: 14 },
  { id: "adx", label: "ADX (14)", category: "trend", placement: "panel", color: "#FB923C", apiParam: "adx", keys: ["adx"], defaultPeriod: 14 },
  { id: "vwap", label: "VWAP Bands", category: "volume", placement: "overlay", color: "#22D3EE", apiParam: "vwap", keys: ["vwap", "vwap_upper", "vwap_lower"] },
  { id: "obv", label: "OBV", category: "volume", placement: "panel", color: "#4ADE80", apiParam: "obv", keys: ["obv"] },
  { id: "mfi", label: "MFI (14)", category: "volume", placement: "panel", color: "#F59E0B", apiParam: "mfi", keys: ["mfi"], defaultPeriod: 14 },
  { id: "vol_sma", label: "Volume SMA", category: "volume", placement: "panel", color: "#94A3B8", apiParam: "vol_sma", keys: ["vol_sma"] },
];

/* ---- Indicator settings types & persistence ---- */

interface IndicatorSettings { period?: number; color: string; lineWidth: number; }

const STORAGE_KEY = "cq_selected_indicators";
const SETTINGS_STORAGE_KEY = "cq_indicator_settings";
const COLOR_PALETTE = ["#FFDD57","#FF9F43","#A855F7","#EF4444","#38BDF8","#34D399","#818CF8","#FBBF24","#F472B6","#22D3EE","#4ADE80","#FB923C","#F59E0B","#A78BFA","#94A3B8","#FFB4AB"];
const DEFAULT_INDICATORS = ["ema_9", "rsi_14", "macd"];

function loadSavedIndicators(): Set<string> {
  if (typeof window === "undefined") return new Set(DEFAULT_INDICATORS);
  try { const s = localStorage.getItem(STORAGE_KEY); if (s) { const p = JSON.parse(s); if (Array.isArray(p) && p.length > 0) return new Set(p); } } catch { /* */ }
  return new Set(DEFAULT_INDICATORS);
}
function saveIndicators(ids: Set<string>) { try { localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids])); } catch { /* */ } }

function loadSavedSettings(): Map<string, IndicatorSettings> {
  if (typeof window === "undefined") return new Map();
  try { const s = localStorage.getItem(SETTINGS_STORAGE_KEY); if (s) { return new Map(JSON.parse(s) as [string, IndicatorSettings][]); } } catch { /* */ }
  return new Map();
}
function saveSettings(settings: Map<string, IndicatorSettings>) { try { localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify([...settings.entries()])); } catch { /* */ } }

function getEffectiveApiParam(def: IndicatorDef, settings: Map<string, IndicatorSettings>): string {
  const s = settings.get(def.id);
  if (!s?.period || !def.defaultPeriod || s.period === def.defaultPeriod) return def.apiParam;
  return `${def.apiParam.replace(/_\d+$/, "")}_${s.period}`;
}

function getEffectiveKeys(def: IndicatorDef, settings: Map<string, IndicatorSettings>): string[] {
  const s = settings.get(def.id);
  if (!s?.period || !def.defaultPeriod || s.period === def.defaultPeriod) return def.keys;
  return def.keys.map((k) => /_\d+$/.test(k) ? `${k.replace(/_\d+$/, "")}_${s.period}` : k);
}

function resolveIndicatorValue(dp: Record<string, unknown>, ek: string, ok: string): number | null {
  const v = dp[ek]; if (v != null) return v as number;
  if (ek !== ok) { const f = dp[ok]; if (f != null) return f as number; }
  return null;
}

function getEffectiveColor(def: IndicatorDef, settings: Map<string, IndicatorSettings>): string { return settings.get(def.id)?.color ?? def.color; }
function getEffectiveLineWidth(def: IndicatorDef, settings: Map<string, IndicatorSettings>): 1|2|3|4 { const w = settings.get(def.id)?.lineWidth ?? 1; return (w >= 1 && w <= 4 ? w : 1) as 1|2|3|4; }

/* =========================================================================
   Symbol Selector
   ========================================================================= */

function SymbolSelector({ value, onChange, markets, loading }: { value: string; onChange: (s: string) => void; markets: MarketInfo[]; loading: boolean }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => { const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) { setOpen(false); setSearch(""); } }; document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h); }, []);
  useEffect(() => { if (open && searchRef.current) searchRef.current.focus(); }, [open]);

  const filtered = useMemo(() => { if (!search) return markets.slice(0, 50); const q = search.toUpperCase(); return markets.filter((m) => m.base.includes(q) || m.symbol.includes(q)).slice(0, 50); }, [markets, search]);

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 px-3 py-2 rounded-sm transition-all duration-200 cursor-pointer" style={{ background: open ? "rgba(0,240,255,0.12)" : "rgba(229,226,225,0.05)", border: `1px solid ${open ? "rgba(0,240,255,0.3)" : "rgba(229,226,225,0.08)"}` }}>
        <span className="font-mono text-sm font-semibold" style={{ color: "#E5E2E1" }}>{value}</span>
        <ChevronDown size={14} style={{ color: "rgba(185,202,203,0.6)", transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }} />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-[#1C1B1B] border border-[#3B494B]/30 rounded-sm py-1" style={{ width: 240, maxHeight: 400, display: "flex", flexDirection: "column" }}>
          <div className="px-2 py-1.5 flex-shrink-0" style={{ borderBottom: "1px solid rgba(229,226,225,0.06)" }}>
            <div className="flex items-center gap-2 px-2 py-1.5 rounded-sm" style={{ background: "rgba(229,226,225,0.04)", border: "1px solid rgba(229,226,225,0.08)" }}>
              <Search size={12} style={{ color: "rgba(185,202,203,0.4)" }} />
              <input ref={searchRef} type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search symbol..." className="flex-1 bg-transparent outline-none text-xs font-mono" style={{ color: "#E5E2E1" }} />
              {search && <button onClick={() => setSearch("")} className="cursor-pointer"><X size={12} style={{ color: "rgba(185,202,203,0.4)" }} /></button>}
            </div>
          </div>
          <div className="overflow-y-auto flex-1" style={{ maxHeight: 340 }}>
            {loading ? <div className="px-3 py-4 text-center"><span className="text-xs font-mono" style={{ color: "rgba(185,202,203,0.4)" }}>Loading markets...</span></div>
            : filtered.length === 0 ? <div className="px-3 py-4 text-center"><span className="text-xs font-mono" style={{ color: "rgba(185,202,203,0.4)" }}>No markets found</span></div>
            : filtered.map((m) => (
              <button key={m.symbol} onClick={() => { onChange(m.symbol); setOpen(false); setSearch(""); }} className="w-full text-left px-3 py-2 text-sm font-mono transition-colors duration-150 cursor-pointer flex items-center justify-between" style={{ color: m.symbol === value ? "#00F0FF" : "rgba(229,226,225,0.7)", background: m.symbol === value ? "rgba(0,240,255,0.08)" : "transparent" }} onMouseEnter={(e) => { if (m.symbol !== value) (e.currentTarget as HTMLElement).style.background = "rgba(229,226,225,0.04)"; }} onMouseLeave={(e) => { if (m.symbol !== value) (e.currentTarget as HTMLElement).style.background = "transparent"; }}>
                <span>{m.symbol}</span>
                {m.symbol === value && <div className="w-1.5 h-1.5 rounded-full" style={{ background: "#00F0FF" }} />}
              </button>
            ))}
          </div>
          <div className="px-3 py-1.5 flex-shrink-0" style={{ borderTop: "1px solid rgba(229,226,225,0.06)" }}>
            <span className="text-[10px] font-mono" style={{ color: "rgba(185,202,203,0.3)" }}>{markets.length} pairs available</span>
          </div>
        </div>
      )}
    </div>
  );
}

/* =========================================================================
   Timeframe Selector
   ========================================================================= */

function TimeframeSelector({ value, onChange }: { value: string; onChange: (tf: string) => void }) {
  const [showAll, setShowAll] = useState(false);
  const [customTf, setCustomTf] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setShowAll(false); }; document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h); }, []);

  const popular = ["1m", "5m", "15m", "1h", "4h", "1d"];
  const isCustom = !TIMEFRAMES.some((t) => t.value === value);

  return (
    <div ref={ref} className="relative flex items-center gap-1">
      <div className="flex items-center rounded-sm overflow-hidden bg-[#2A2A2A]" style={{ border: "1px solid rgba(229,226,225,0.06)" }}>
        {popular.map((tfVal) => { const tf = TIMEFRAMES.find((t) => t.value === tfVal); if (!tf) return null; const isActive = tf.value === value; return (
          <button key={tf.value} onClick={() => onChange(tf.value)} className="px-2.5 py-1.5 text-xs font-mono font-medium transition-all duration-200 cursor-pointer" style={{ color: isActive ? "#002022" : "rgba(185,202,203,0.6)", background: isActive ? "#00F0FF" : "transparent", borderRight: "1px solid rgba(229,226,225,0.04)" }} onMouseEnter={(e) => { if (!isActive) { (e.target as HTMLElement).style.color = "#E5E2E1"; (e.target as HTMLElement).style.background = "rgba(229,226,225,0.06)"; } }} onMouseLeave={(e) => { if (!isActive) { (e.target as HTMLElement).style.color = "rgba(185,202,203,0.6)"; (e.target as HTMLElement).style.background = "transparent"; } }}>{tf.label}</button>
        ); })}
        <button onClick={() => setShowAll(!showAll)} className="px-2.5 py-1.5 text-xs font-mono font-medium transition-all duration-200 cursor-pointer" style={{ color: (showAll || (!popular.includes(value) && !isCustom)) ? "#00F0FF" : "rgba(185,202,203,0.6)", background: showAll ? "rgba(0,240,255,0.12)" : "transparent" }} onMouseEnter={(e) => { (e.target as HTMLElement).style.color = "#00F0FF"; }} onMouseLeave={(e) => { if (!showAll) (e.target as HTMLElement).style.color = (!popular.includes(value) && !isCustom) ? "#00F0FF" : "rgba(185,202,203,0.6)"; }}>
          {!popular.includes(value) && !isCustom ? TIMEFRAMES.find(t => t.value === value)?.label ?? "..." : "..."}
        </button>
      </div>
      {showAll && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-[#1C1B1B] border border-[#3B494B]/30 rounded-sm py-2" style={{ width: 200 }}>
          <div className="grid grid-cols-4 gap-1 px-2 py-1">
            {TIMEFRAMES.map((tf) => { const isActive = tf.value === value; return (
              <button key={tf.value} onClick={() => { onChange(tf.value); setShowAll(false); }} className="py-1.5 rounded-sm text-xs font-mono font-medium cursor-pointer transition-all" style={{ color: isActive ? "#002022" : "rgba(229,226,225,0.6)", background: isActive ? "#00F0FF" : "rgba(229,226,225,0.03)", border: `1px solid ${isActive ? "rgba(0,240,255,0.5)" : "rgba(229,226,225,0.06)"}` }} onMouseEnter={(e) => { if (!isActive) (e.currentTarget as HTMLElement).style.background = "rgba(229,226,225,0.06)"; }} onMouseLeave={(e) => { if (!isActive) (e.currentTarget as HTMLElement).style.background = "rgba(229,226,225,0.03)"; }}>{tf.label}</button>
            ); })}
          </div>
          <div className="px-2 pt-2 mt-1" style={{ borderTop: "1px solid rgba(229,226,225,0.06)" }}>
            <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: "rgba(185,202,203,0.4)" }}>Custom</div>
            <div className="flex gap-1">
              <input type="text" placeholder="e.g. 2h, 45m" value={customTf} onChange={(e) => setCustomTf(e.target.value)} className="flex-1 px-2 py-1 rounded-sm text-xs font-mono outline-none" style={{ background: "rgba(229,226,225,0.04)", border: "1px solid rgba(229,226,225,0.08)", color: "#E5E2E1" }} onKeyDown={(e) => { if (e.key === "Enter" && customTf.trim()) { onChange(customTf.trim().toLowerCase()); setShowAll(false); setCustomTf(""); } }} />
              <button onClick={() => { if (customTf.trim()) { onChange(customTf.trim().toLowerCase()); setShowAll(false); setCustomTf(""); } }} className="px-2 py-1 rounded-sm text-xs font-mono cursor-pointer" style={{ background: "rgba(0,240,255,0.15)", border: "1px solid rgba(0,240,255,0.3)", color: "#00F0FF" }}>Go</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* =========================================================================
   Indicator Settings Popup
   ========================================================================= */

function IndicatorSettingsPopup({ def, settings, onApply, onClose }: { def: IndicatorDef; settings: IndicatorSettings | undefined; onApply: (id: string, s: IndicatorSettings) => void; onClose: () => void }) {
  const [period, setPeriod] = useState<number | undefined>(settings?.period ?? def.defaultPeriod);
  const [color, setColor] = useState(settings?.color ?? def.color);
  const [lineWidth, setLineWidth] = useState(settings?.lineWidth ?? 1);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onClose(); }; document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h); }, [onClose]);

  return (
    <div ref={ref} className="rounded-sm py-3 px-4" style={{ background: "#2A2A2A", border: "1px solid rgba(0,240,255,0.2)", width: 220 }}>
      <div className="text-xs font-mono font-semibold mb-3" style={{ color: "#E5E2E1" }}>{def.label}</div>
      {def.defaultPeriod != null && (
        <div className="mb-3">
          <div className="text-[10px] font-mono uppercase tracking-wider mb-1.5" style={{ color: "rgba(185,202,203,0.5)" }}>Period</div>
          <input type="number" min={1} max={500} value={period ?? ""} onChange={(e) => setPeriod(e.target.value ? parseInt(e.target.value, 10) : undefined)} className="w-full px-2 py-1.5 rounded-sm text-xs font-mono outline-none" style={{ background: "rgba(229,226,225,0.06)", border: "1px solid rgba(229,226,225,0.1)", color: "#E5E2E1" }} />
        </div>
      )}
      <div className="mb-3">
        <div className="text-[10px] font-mono uppercase tracking-wider mb-1.5" style={{ color: "rgba(185,202,203,0.5)" }}>Color</div>
        <div className="flex flex-wrap gap-1.5">
          {COLOR_PALETTE.map((c) => <button key={c} onClick={() => setColor(c)} className="w-5 h-5 rounded-full cursor-pointer transition-transform" style={{ background: c, border: color === c ? "2px solid #E5E2E1" : "2px solid transparent", transform: color === c ? "scale(1.2)" : "scale(1)" }} />)}
        </div>
      </div>
      <div className="mb-3">
        <div className="text-[10px] font-mono uppercase tracking-wider mb-1.5" style={{ color: "rgba(185,202,203,0.5)" }}>Line Width</div>
        <div className="flex gap-2">
          {([1,2,3] as const).map((w) => <button key={w} onClick={() => setLineWidth(w)} className="flex-1 py-1.5 rounded-sm text-[10px] font-mono cursor-pointer transition-all" style={{ background: lineWidth === w ? "rgba(0,240,255,0.2)" : "rgba(229,226,225,0.04)", border: `1px solid ${lineWidth === w ? "rgba(0,240,255,0.4)" : "rgba(229,226,225,0.08)"}`, color: lineWidth === w ? "#00F0FF" : "rgba(185,202,203,0.6)" }}>{w === 1 ? "Thin" : w === 2 ? "Med" : "Thick"}</button>)}
        </div>
      </div>
      <button onClick={() => { onApply(def.id, { period, color, lineWidth }); onClose(); }} className="w-full py-1.5 rounded-sm text-xs font-mono font-semibold cursor-pointer transition-all" style={{ background: "rgba(0,240,255,0.2)", border: "1px solid rgba(0,240,255,0.4)", color: "#00F0FF" }}>Apply</button>
    </div>
  );
}

/* =========================================================================
   Indicator Selector Dropdown
   ========================================================================= */

function IndicatorSelector({ selected, onToggle, indicatorSettings, onApplySettings }: { selected: Set<string>; onToggle: (id: string) => void; indicatorSettings: Map<string, IndicatorSettings>; onApplySettings: (id: string, s: IndicatorSettings) => void }) {
  const [open, setOpen] = useState(false);
  const [settingsTarget, setSettingsTarget] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) { setOpen(false); setSettingsTarget(null); } }; document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h); }, []);

  const categories = [
    { key: "trend_overlay" as const, label: "Trend (overlay)", filter: (d: IndicatorDef) => d.category === "trend" && d.placement === "overlay" },
    { key: "volatility" as const, label: "Volatility", filter: (d: IndicatorDef) => d.category === "volatility" },
    { key: "momentum" as const, label: "Momentum (panel)", filter: (d: IndicatorDef) => d.category === "momentum" },
    { key: "volume" as const, label: "Volume", filter: (d: IndicatorDef) => d.category === "volume" },
    { key: "trend_panel" as const, label: "Trend (panel)", filter: (d: IndicatorDef) => d.category === "trend" && d.placement === "panel" },
  ];

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1.5 px-3 py-2 rounded-sm transition-all duration-200 cursor-pointer" style={{ background: open ? "rgba(0,240,255,0.12)" : "rgba(229,226,225,0.05)", border: `1px solid ${open ? "rgba(0,240,255,0.3)" : "rgba(229,226,225,0.08)"}` }}>
        <BarChart3 size={14} style={{ color: selected.size > 0 ? "#00F0FF" : "rgba(185,202,203,0.5)" }} />
        <span className="text-xs font-mono" style={{ color: selected.size > 0 ? "#00F0FF" : "rgba(185,202,203,0.5)" }}>Indicators{selected.size > 0 ? ` (${selected.size})` : ""}</span>
        <ChevronDown size={12} style={{ color: "rgba(185,202,203,0.5)", transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }} />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-[#1C1B1B] border border-[#3B494B]/30 rounded-sm py-2" style={{ width: 280 }}>
          <div style={{ maxHeight: 420, overflowY: "auto" }}>
            {categories.map((cat) => { const items = INDICATOR_DEFS.filter(cat.filter); if (items.length === 0) return null; return (
              <div key={cat.key}>
                <div className="px-3 py-1"><span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "rgba(185,202,203,0.4)" }}>{cat.label}</span></div>
                {items.map((ind) => { const isOn = selected.has(ind.id); const effColor = getEffectiveColor(ind, indicatorSettings); return (
                  <div key={ind.id} className="relative flex items-center">
                    <button onClick={() => onToggle(ind.id)} className="flex-1 text-left px-3 py-1.5 flex items-center gap-2 cursor-pointer transition-colors duration-150" style={{ background: isOn ? "rgba(0,240,255,0.06)" : "transparent" }} onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(229,226,225,0.04)"; }} onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = isOn ? "rgba(0,240,255,0.06)" : "transparent"; }}>
                      <div className="w-3 h-3 rounded-sm border flex items-center justify-center" style={{ borderColor: isOn ? effColor : "rgba(229,226,225,0.2)", background: isOn ? effColor : "transparent" }}>{isOn && <span className="text-[8px] text-black font-bold">&#10003;</span>}</div>
                      <div className="w-4 h-0.5 rounded-full" style={{ background: effColor }} />
                      <span className="text-xs font-mono" style={{ color: isOn ? "#E5E2E1" : "rgba(229,226,225,0.6)" }}>{ind.label}</span>
                      <span className="ml-auto text-[9px] font-mono" style={{ color: "rgba(185,202,203,0.3)" }}>{ind.placement === "overlay" ? "chart" : "panel"}</span>
                    </button>
                    {isOn && <button onClick={(e) => { e.stopPropagation(); setSettingsTarget(settingsTarget === ind.id ? null : ind.id); }} className="px-2 py-1.5 cursor-pointer transition-colors" style={{ color: settingsTarget === ind.id ? "#00F0FF" : "rgba(185,202,203,0.3)" }} onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "#00F0FF"; }} onMouseLeave={(e) => { if (settingsTarget !== ind.id) (e.currentTarget as HTMLElement).style.color = "rgba(185,202,203,0.3)"; }}><Settings size={12} /></button>}
                  </div>
                ); })}
              </div>
            ); })}
          </div>
          {selected.size > 0 && <div className="px-3 pt-2 mt-1" style={{ borderTop: "1px solid rgba(229,226,225,0.06)" }}><button onClick={() => { for (const id of selected) onToggle(id); }} className="text-[10px] font-mono cursor-pointer" style={{ color: "rgba(185,202,203,0.4)" }}>Clear all</button></div>}
          {settingsTarget && (() => { const td = INDICATOR_DEFS.find((d) => d.id === settingsTarget); if (!td) return null; return <div className="absolute left-full top-0 ml-2" style={{ zIndex: 60 }}><IndicatorSettingsPopup def={td} settings={indicatorSettings.get(td.id)} onApply={onApplySettings} onClose={() => setSettingsTarget(null)} /></div>; })()}
        </div>
      )}
    </div>
  );
}

/* =========================================================================
   Order Book Panel
   ========================================================================= */

function OrderBookPanel({ data, symbol }: { data: OrderBookResponse | null; symbol: string }) {
  void symbol;
  if (!data || (data.bids.length === 0 && data.asks.length === 0)) return <div className="flex items-center justify-center h-full"><span className="text-xs font-mono" style={{ color: "rgba(185,202,203,0.3)" }}>Loading order book...</span></div>;

  const bids = data.bids.slice(0, 20);
  const rawAsks = data.asks.slice(0, 20);
  const asksCum: number[] = []; let cumA = 0; for (const a of rawAsks) { cumA += a[1]; asksCum.push(cumA); }
  const bidsCum: number[] = []; let cumB = 0; for (const b of bids) { cumB += b[1]; bidsCum.push(cumB); }
  const maxCum = Math.max(asksCum[asksCum.length - 1] || 1, bidsCum[bidsCum.length - 1] || 1);
  const asksDisplay = rawAsks.map((a, i) => ({ price: a[0], qty: a[1], cum: asksCum[i] })).reverse();
  const bestBid = bids.length > 0 ? bids[0][0] : 0;
  const bestAsk = rawAsks.length > 0 ? rawAsks[0][0] : 0;
  const spread = bestAsk > 0 && bestBid > 0 ? bestAsk - bestBid : 0;
  const spreadPct = bestBid > 0 ? (spread / bestBid) * 100 : 0;

  return (
    <div className="flex flex-col h-full text-[10px] font-mono">
      <div className="flex items-center px-3 py-1.5 flex-shrink-0" style={{ borderBottom: "1px solid rgba(229,226,225,0.06)" }}>
        <span className="flex-1 text-[9px] uppercase tracking-wider" style={{ color: "rgba(185,202,203,0.4)" }}>Price</span>
        <span className="flex-1 text-right text-[9px] uppercase tracking-wider" style={{ color: "rgba(185,202,203,0.4)" }}>Size</span>
      </div>
      <div className="flex-1 overflow-y-auto flex flex-col justify-end min-h-0">
        {asksDisplay.map((row, i) => (
          <div key={`a-${i}`} className="flex items-center px-3 py-[2px] relative cursor-pointer hover:bg-[#201F1F]">
            <div className="absolute right-0 top-0 bottom-0" style={{ width: `${(row.cum / maxCum) * 100}%`, background: "rgba(255,180,171,0.06)" }} />
            <span className="flex-1 relative z-10 tabular-nums" style={{ color: "#FFB4AB" }}>{fmtOBP(row.price)}</span>
            <span className="flex-1 text-right relative z-10 tabular-nums" style={{ color: "rgba(229,226,225,0.5)" }}>{fmtOBQ(row.qty)}</span>
          </div>
        ))}
      </div>
      <div className="px-3 py-2 flex-shrink-0 flex items-center justify-between" style={{ background: "rgba(229,226,225,0.02)", borderTop: "1px solid rgba(229,226,225,0.06)", borderBottom: "1px solid rgba(229,226,225,0.06)" }}>
        <span className="text-xs font-semibold tabular-nums" style={{ color: "#00F0FF" }}>{fmtOBP(bestBid)}</span>
        <span className="tabular-nums" style={{ color: "rgba(185,202,203,0.5)" }}>{fmtOBP(spread)} ({spreadPct.toFixed(3)}%)</span>
      </div>
      <div className="flex-1 overflow-y-auto min-h-0">
        {bids.map((bid, i) => (
          <div key={`b-${i}`} className="flex items-center px-3 py-[2px] relative cursor-pointer hover:bg-[#201F1F]">
            <div className="absolute right-0 top-0 bottom-0" style={{ width: `${(bidsCum[i] / maxCum) * 100}%`, background: "rgba(64,229,108,0.06)" }} />
            <span className="flex-1 relative z-10 tabular-nums" style={{ color: "#40E56C" }}>{fmtOBP(bid[0])}</span>
            <span className="flex-1 text-right relative z-10 tabular-nums" style={{ color: "rgba(229,226,225,0.5)" }}>{fmtOBQ(bid[1])}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function fmtOBP(p: number): string { if (p >= 1000) return p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); if (p >= 1) return p.toFixed(4); return p.toFixed(6); }
function fmtOBQ(q: number): string { if (q >= 1000) return `${(q / 1000).toFixed(1)}K`; if (q >= 1) return q.toFixed(3); return q.toFixed(4); }

/* =========================================================================
   Chart Page (main)
   ========================================================================= */

export default function ChartPage() {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [livePrice, setLivePrice] = useState<number | null>(null);
  const [priceChange, setPriceChange] = useState<number | null>(null);
  const [priceChangePercent, setPriceChangePercent] = useState<number | null>(null);
  const [dataSource, setDataSource] = useState<"binance"|"binance_cached"|"database"|"empty">("empty");
  const [markets, setMarkets] = useState<MarketInfo[]>([]);
  const [marketsLoading, setMarketsLoading] = useState(true);
  const [selectedIndicators, setSelectedIndicators] = useState<Set<string>>(loadSavedIndicators);
  const [orderBook, setOrderBook] = useState<OrderBookResponse | null>(null);
  const [indicatorSettings, setIndicatorSettings] = useState<Map<string, IndicatorSettings>>(loadSavedSettings);
  const [chartReady, setChartReady] = useState(false);
  const [panelValues, setPanelValues] = useState<Map<string, number>>(new Map());
  const [tradeTab, setTradeTab] = useState<"orderbook"|"trade">("orderbook");
  const [tradeDirection, setTradeDirection] = useState<"LONG"|"SHORT">("LONG");
  const [tradeOrderType, setTradeOrderType] = useState<"MARKET"|"LIMIT"|"STOP_MARKET"|"STOP_LIMIT">("MARKET");
  const [tradePrice, setTradePrice] = useState("");
  const [tradeStopPrice, setTradeStopPrice] = useState("");
  const [tradeQty, setTradeQty] = useState("");
  const [tradeLeverage, setTradeLeverage] = useState(1);
  const [customLeverage, setCustomLeverage] = useState(false);
  const [tradeSLEnabled, setTradeSLEnabled] = useState(false);
  const [tradeSL, setTradeSL] = useState("");
  const [tradeTPEnabled, setTradeTPEnabled] = useState(false);
  const [tradeTP, setTradeTP] = useState("");
  const [tradeSubmitting, setTradeSubmitting] = useState(false);
  const [tradeResult, setTradeResult] = useState<{msg:string;ok:boolean}|null>(null);
  const [maxLeverage, setMaxLeverage] = useState(20);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const oldestTimestampRef = useRef<number | null>(null);
  const hasMoreDataRef = useRef(true);
  const isLoadingHistoryRef = useRef(false);
  const allCandlesRef = useRef<CandleData[]>([]);
  const lastCandleTimeRef = useRef<number>(0);
  const currentCandleRef = useRef<{time:number;open:number;high:number;low:number;close:number;volume:number}|null>(null);
  const lastUpdateRef = useRef<number>(0);
  const [countdown, setCountdown] = useState<string>("");
  const [showPositions, setShowPositions] = useState(false);
  const [openPositions, setOpenPositions] = useState<Position[]>([]);
  const [bottomTab, setBottomTab] = useState<"positions"|"orders"|"history"|"trade">("positions");
  const [panelPositions, setPanelPositions] = useState<ExchangePosition[]>([]);
  const [panelOrders, setPanelOrders] = useState<Order[]>([]);
  const [panelHistory, setPanelHistory] = useState<Position[]>([]);
  const [closingPositionId, setClosingPositionId] = useState<string|null>(null);
  const priceLinesRef = useRef<Map<string,unknown>>(new Map());
  const bidLineRef = useRef<unknown>(null);
  const askLineRef = useRef<unknown>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const rsiContainerRef = useRef<HTMLDivElement>(null);
  const macdContainerRef = useRef<HTMLDivElement>(null);
  const stochContainerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<ReturnType<typeof import("lightweight-charts").createChart>|null>(null);
  const candleSeriesRef = useRef<unknown>(null);
  const volumeSeriesRef = useRef<unknown>(null);
  const rsiChartRef = useRef<ReturnType<typeof import("lightweight-charts").createChart>|null>(null);
  const macdChartRef = useRef<ReturnType<typeof import("lightweight-charts").createChart>|null>(null);
  const stochChartRef = useRef<ReturnType<typeof import("lightweight-charts").createChart>|null>(null);
  const overlaySeriesRef = useRef<Map<string,unknown>>(new Map());
  const rsiSeriesRef = useRef<unknown>(null);
  const macdLineRef = useRef<unknown>(null);
  const macdSignalRef = useRef<unknown>(null);
  const macdHistRef = useRef<unknown>(null);
  const stochKSeriesRef = useRef<unknown>(null);
  const stochDSeriesRef = useRef<unknown>(null);
  const symbolRef = useRef(symbol); symbolRef.current = symbol;
  const timeframeRef = useRef(timeframe); timeframeRef.current = timeframe;
  const refreshIntervalRef = useRef<ReturnType<typeof setInterval>|null>(null);
  const lcRef = useRef<typeof import("lightweight-charts")|null>(null);

  const handleToggleIndicator = useCallback((id: string) => { setSelectedIndicators((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); saveIndicators(next); return next; }); }, []);
  const handleApplySettings = useCallback((id: string, s: IndicatorSettings) => { setIndicatorSettings((prev) => { const next = new Map(prev); next.set(id, s); saveSettings(next); return next; }); }, []);

  const tradeCalcs = useMemo(() => {
    const price = tradeOrderType === "MARKET" ? (livePrice ?? 0) : parseFloat(tradePrice) || 0;
    const qty = parseFloat(tradeQty) || 0; const lev = tradeLeverage || 1;
    const notional = qty * price; const margin = notional / lev;
    const liqPrice = qty > 0 ? (tradeDirection === "LONG" ? price - (margin / qty) : price + (margin / qty)) : 0;
    const sl = tradeSLEnabled ? parseFloat(tradeSL) || 0 : 0; const tp = tradeTPEnabled ? parseFloat(tradeTP) || 0 : 0;
    const risk = sl > 0 ? Math.abs(price - sl) * qty : 0; const reward = tp > 0 ? Math.abs(tp - price) * qty : 0;
    const rr = risk > 0 && reward > 0 ? reward / risk : 0;
    return { price, notional, margin, liqPrice, risk, reward, rr };
  }, [tradeOrderType, tradePrice, tradeQty, tradeLeverage, tradeDirection, tradeSL, tradeTP, tradeSLEnabled, tradeTPEnabled, livePrice]);

  const handlePlaceTrade = useCallback(async () => {
    setTradeSubmitting(true); setTradeResult(null);
    try {
      const d: ManualOrderRequest = { symbol, direction: tradeDirection, order_type: tradeOrderType, quantity: parseFloat(tradeQty), price: tradeOrderType !== "MARKET" ? parseFloat(tradePrice) || undefined : undefined, stop_price: ["STOP_MARKET","STOP_LIMIT"].includes(tradeOrderType) ? parseFloat(tradeStopPrice) || undefined : undefined, leverage: tradeLeverage, stop_loss: tradeSLEnabled ? parseFloat(tradeSL) || undefined : undefined, take_profit: tradeTPEnabled ? parseFloat(tradeTP) || undefined : undefined };
      const r = await placeManualOrder(d);
      setTradeResult({ msg: `Order ${r.status}: ${r.order_type} ${r.side} ${r.executed_qty} @ $${r.executed_price.toFixed(2)}`, ok: true }); setTradeQty("");
    } catch (e: unknown) { setTradeResult({ msg: `Error: ${e instanceof Error ? e.message : String(e)}`, ok: false }); } finally { setTradeSubmitting(false); }
  }, [symbol, tradeDirection, tradeOrderType, tradeQty, tradePrice, tradeStopPrice, tradeLeverage, tradeSLEnabled, tradeSL, tradeTPEnabled, tradeTP]);

  useEffect(() => { let c = false; (async () => { try { const r = await fetchMarkets(); if (!c) setMarkets(r.markets); } catch (e) { console.error(e); } finally { if (!c) setMarketsLoading(false); } })(); return () => { c = true; }; }, []);

  useEffect(() => { let c = false; fetchLeverageTiers(symbol).then((d) => { if (!c) { setMaxLeverage(d.max_leverage); setTradeLeverage((p) => Math.min(p, d.max_leverage)); } }).catch(() => { if (!c) setMaxLeverage(20); }); return () => { c = true; }; }, [symbol]);

  const leverageOptions = useMemo(() => { const o = [1]; if (maxLeverage >= 3) o.push(3); if (maxLeverage >= 5) o.push(5); if (maxLeverage >= 10) o.push(10); if (maxLeverage >= 20) o.push(20); if (maxLeverage >= 50) o.push(50); if (maxLeverage >= 75) o.push(75); if (maxLeverage >= 100) o.push(100); if (maxLeverage >= 125) o.push(125); return o; }, [maxLeverage]);

  useEffect(() => { let c = false; (async () => { try { const d = await fetchOrderBook(symbol, 20); if (!c) setOrderBook(d); } catch (e) { console.error(e); } })(); return () => { c = true; }; }, [symbol]);

  const handleOBUpdate = useCallback((d: OrderBookUpdate) => { if (d.symbol !== symbolRef.current) return; setOrderBook(d); }, []);
  useWebSocket("orderbook_update", handleOBUpdate);

  /* ---- Chart init ---- */
  useEffect(() => {
    let mainChart: ReturnType<typeof import("lightweight-charts").createChart>|null = null;
    let rsiChart: ReturnType<typeof import("lightweight-charts").createChart>|null = null;
    let macdChart: ReturnType<typeof import("lightweight-charts").createChart>|null = null;
    let stochChart: ReturnType<typeof import("lightweight-charts").createChart>|null = null;
    const resizeObs: ResizeObserver[] = [];
    let cancelled = false;

    async function init() {
      const mainEl = chartContainerRef.current; if (!mainEl) return;
      const lc = await import("lightweight-charts"); if (cancelled) return; lcRef.current = lc;

      const pOpts = { layout: { background: { type: lc.ColorType.Solid, color: "#131313" }, textColor: "rgba(185,202,203,0.5)", fontFamily: '"JetBrains Mono", monospace', fontSize: 10 }, grid: { vertLines: { visible: false }, horzLines: { visible: false } }, rightPriceScale: { borderColor: "rgba(229,226,225,0.04)", scaleMargins: { top: 0.1, bottom: 0.1 } }, timeScale: { visible: false }, crosshair: { mode: lc.CrosshairMode.Normal, vertLine: { visible: false }, horzLine: { color: "rgba(0,240,255,0.3)", width: 1, style: lc.LineStyle.Dashed, labelBackgroundColor: "#00F0FF" } } } as const;

      mainEl.innerHTML = "";
      mainChart = lc.createChart(mainEl, { layout: { background: { type: lc.ColorType.Solid, color: "#131313" }, textColor: "rgba(185,202,203,0.6)", fontFamily: '"JetBrains Mono", monospace', fontSize: 11 }, grid: { vertLines: { color: "rgba(229,226,225,0.04)" }, horzLines: { color: "rgba(229,226,225,0.04)" } }, crosshair: { mode: lc.CrosshairMode.Normal, vertLine: { color: "rgba(0,240,255,0.4)", width: 1, style: lc.LineStyle.Dashed, labelBackgroundColor: "#00F0FF" }, horzLine: { color: "rgba(0,240,255,0.4)", width: 1, style: lc.LineStyle.Dashed, labelBackgroundColor: "#00F0FF" } }, rightPriceScale: { borderColor: "rgba(229,226,225,0.06)", scaleMargins: { top: 0.05, bottom: 0.25 } }, timeScale: { borderColor: "rgba(229,226,225,0.06)", timeVisible: true, secondsVisible: false, rightOffset: 5, barSpacing: 8 }, handleScroll: { vertTouchDrag: false } });

      const cs = mainChart.addSeries(lc.CandlestickSeries, { upColor: "#40E56C", downColor: "#FFB4AB", borderVisible: false, wickUpColor: "#40E56C", wickDownColor: "#FFB4AB", borderUpColor: "#40E56C", borderDownColor: "#FFB4AB" });
      const vs = mainChart.addSeries(lc.HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "" }); vs.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      chartInstanceRef.current = mainChart; candleSeriesRef.current = cs; volumeSeriesRef.current = vs;
      const mObs = new ResizeObserver((e) => { if (mainChart && e[0]) { const { width, height } = e[0].contentRect; mainChart.applyOptions({ width, height }); } }); mObs.observe(mainEl); resizeObs.push(mObs);

      const rsiEl = rsiContainerRef.current;
      if (rsiEl) { rsiEl.innerHTML = ""; rsiChart = lc.createChart(rsiEl, pOpts); const rs = rsiChart.addSeries(lc.LineSeries, { color: "#FBBF24", lineWidth: 1, priceFormat: { type: "custom", formatter: (v: number) => v.toFixed(1) } }); rsiSeriesRef.current = rs; rsiChartRef.current = rsiChart; const o = new ResizeObserver((e) => { if (rsiChart && e[0]) { const { width, height } = e[0].contentRect; rsiChart.applyOptions({ width, height }); } }); o.observe(rsiEl); resizeObs.push(o); }

      const macdEl = macdContainerRef.current;
      if (macdEl) { macdEl.innerHTML = ""; macdChart = lc.createChart(macdEl, pOpts); const ml = macdChart.addSeries(lc.LineSeries, { color: "#38BDF8", lineWidth: 1 }); const ms = macdChart.addSeries(lc.LineSeries, { color: "#FB923C", lineWidth: 1 }); const mh = macdChart.addSeries(lc.HistogramSeries, { priceFormat: { type: "price" } }); macdLineRef.current = ml; macdSignalRef.current = ms; macdHistRef.current = mh; macdChartRef.current = macdChart; const o = new ResizeObserver((e) => { if (macdChart && e[0]) { const { width, height } = e[0].contentRect; macdChart.applyOptions({ width, height }); } }); o.observe(macdEl); resizeObs.push(o); }

      const stochEl = stochContainerRef.current;
      if (stochEl) { stochEl.innerHTML = ""; stochChart = lc.createChart(stochEl, pOpts); const sk = stochChart.addSeries(lc.LineSeries, { color: "#34D399", lineWidth: 1, priceFormat: { type: "custom", formatter: (v: number) => v.toFixed(1) } }); const sd = stochChart.addSeries(lc.LineSeries, { color: "#FB923C", lineWidth: 1, priceFormat: { type: "custom", formatter: (v: number) => v.toFixed(1) } }); stochKSeriesRef.current = sk; stochDSeriesRef.current = sd; stochChartRef.current = stochChart; const o = new ResizeObserver((e) => { if (stochChart && e[0]) { const { width, height } = e[0].contentRect; stochChart.applyOptions({ width, height }); } }); o.observe(stochEl); resizeObs.push(o); }

      loadData(symbol, timeframe, cs, vs, mainChart, true);
      if (!cancelled) setChartReady(true);
    }
    init();
    return () => { cancelled = true; setChartReady(false); for (const o of resizeObs) o.disconnect(); if (mainChart) { mainChart.remove(); chartInstanceRef.current = null; } if (rsiChart) { rsiChart.remove(); rsiChartRef.current = null; } if (macdChart) { macdChart.remove(); macdChartRef.current = null; } if (stochChart) { stochChart.remove(); stochChartRef.current = null; } overlaySeriesRef.current.clear(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---- Load candle data ---- */
  const loadData = useCallback(async (sym: string, tf: string, candleSeries?: unknown, volumeSeries?: unknown, chartObj?: unknown, isInitial?: boolean) => {
    const cs = candleSeries ?? candleSeriesRef.current; const vs = volumeSeries ?? volumeSeriesRef.current; const chart = chartObj ?? chartInstanceRef.current;
    if (!cs || !vs || !chart) return;
    let freshCandles: CandleData[] = []; let source: "binance"|"binance_cached"|"database"|"empty" = "empty";
    try { const tfc = TIMEFRAMES.find((t) => t.value === tf); const limit = (tfc?.seconds ?? 3600) <= 300 ? 1000 : 500; const r = await fetchCandles(sym, tf, limit); if (r.candles && r.candles.length > 0) { freshCandles = r.candles; source = (r as {source?:string}).source as typeof source || "binance"; setLivePrice(freshCandles[freshCandles.length-1].close); } } catch (e) { console.error(e); }
    setDataSource(source);

    // If we have loaded extra history via infinite scroll, merge fresh candles with historical data
    type TS = import("lightweight-charts").UTCTimestamp;
    let displayCandles: CandleData[];
    const existingOldest = oldestTimestampRef.current;
    const freshOldest = freshCandles.length > 0 ? freshCandles[0].time : null;

    if (!isInitial && existingOldest != null && freshOldest != null && existingOldest < freshOldest && allCandlesRef.current.length > 0) {
      // We have historical candles older than the fresh load — preserve them
      const historicalPart = allCandlesRef.current.filter((c) => c.time < freshOldest);
      displayCandles = [...historicalPart, ...freshCandles];
    } else {
      displayCandles = freshCandles;
    }

    allCandlesRef.current = displayCandles;

    (cs as {setData:(d:unknown[])=>void}).setData(displayCandles.map((c) => ({ time: c.time as TS, open: c.open, high: c.high, low: c.low, close: c.close })));
    (vs as {setData:(d:unknown[])=>void}).setData(displayCandles.map((c) => ({ time: c.time as TS, value: c.volume, color: c.close >= c.open ? "rgba(64,229,108,0.25)" : "rgba(255,180,171,0.25)" })));
    if (isInitial) {
      (chart as {timeScale:()=>{fitContent:()=>void}}).timeScale().fitContent();
    }
    if (freshCandles.length > 0) {
      lastCandleTimeRef.current = freshCandles[freshCandles.length-1].time;
      const l = freshCandles[freshCandles.length-1];
      currentCandleRef.current = { time: l.time, open: l.open, high: l.high, low: l.low, close: l.close, volume: l.volume };
    }
    if (displayCandles.length > 0 && (isInitial || oldestTimestampRef.current == null)) {
      // Track for infinite scroll — only set oldest on initial load or if not yet tracked
      oldestTimestampRef.current = displayCandles[0].time;
      hasMoreDataRef.current = true;
      isLoadingHistoryRef.current = false;
      setIsLoadingHistory(false);
    }
  }, []);

  /* ---- Infinite scroll: load older candles when panning left ---- */
  const loadMoreCandles = useCallback(async () => {
    if (isLoadingHistoryRef.current || !hasMoreDataRef.current || !oldestTimestampRef.current) return;
    isLoadingHistoryRef.current = true;
    setIsLoadingHistory(true);

    try {
      const tfc = TIMEFRAMES.find((t) => t.value === timeframeRef.current);
      const limit = (tfc?.seconds ?? 3600) <= 300 ? 1000 : 500;
      const result = await fetchCandles(symbolRef.current, timeframeRef.current, limit, oldestTimestampRef.current);

      if (!result.candles || result.candles.length === 0) {
        hasMoreDataRef.current = false;
        return;
      }

      // Filter to only candles strictly older than what we have
      const olderCandles = result.candles.filter((c) => c.time < (oldestTimestampRef.current ?? 0));

      if (olderCandles.length === 0) {
        hasMoreDataRef.current = false;
        return;
      }

      // If we got fewer candles than limit, there is no more data beyond this
      if (olderCandles.length < limit * 0.5) {
        hasMoreDataRef.current = false;
      }

      // Merge with existing data
      const existing = allCandlesRef.current;
      const merged = [...olderCandles, ...existing];
      allCandlesRef.current = merged;
      oldestTimestampRef.current = olderCandles[0].time;

      // Update chart series
      const cs = candleSeriesRef.current;
      const vs = volumeSeriesRef.current;
      if (cs && vs) {
        type TS = import("lightweight-charts").UTCTimestamp;
        (cs as {setData:(d:unknown[])=>void}).setData(
          merged.map((c) => ({ time: c.time as TS, open: c.open, high: c.high, low: c.low, close: c.close }))
        );
        (vs as {setData:(d:unknown[])=>void}).setData(
          merged.map((c) => ({ time: c.time as TS, value: c.volume, color: c.close >= c.open ? "rgba(64,229,108,0.25)" : "rgba(255,180,171,0.25)" }))
        );
      }
    } catch (err) {
      console.error("Failed to load more candles:", err);
    } finally {
      isLoadingHistoryRef.current = false;
      setIsLoadingHistory(false);
    }
  }, []);

  /* ---- Subscribe to visible range for infinite scroll ---- */
  useEffect(() => {
    const chart = chartInstanceRef.current;
    if (!chart || !chartReady) return;

    const handler = (logicalRange: {from: number; to: number} | null) => {
      if (!logicalRange) return;
      // When the user scrolls near the left edge (first 20 bars visible), load more
      if (logicalRange.from < 20 && !isLoadingHistoryRef.current && hasMoreDataRef.current) {
        loadMoreCandles();
      }
    };

    chart.timeScale().subscribeVisibleLogicalRangeChange(handler as Parameters<ReturnType<typeof chart.timeScale>["subscribeVisibleLogicalRangeChange"]>[0]);

    return () => {
      try {
        chart.timeScale().unsubscribeVisibleLogicalRangeChange(handler as Parameters<ReturnType<typeof chart.timeScale>["unsubscribeVisibleLogicalRangeChange"]>[0]);
      } catch { /* chart may have been removed */ }
    };
  }, [chartReady, loadMoreCandles]);

  /* ---- Load indicators ---- */
  useEffect(() => {
    let cancelled = false;
    async function go() {
      const lc = lcRef.current; const chart = chartInstanceRef.current; if (!lc || !chart) return;
      for (const [,s] of overlaySeriesRef.current) { try { chart.removeSeries(s as Parameters<typeof chart.removeSeries>[0]); } catch(e){console.error(e);} } overlaySeriesRef.current.clear();
      if (rsiSeriesRef.current) (rsiSeriesRef.current as {setData:(d:unknown[])=>void}).setData([]);
      if (macdLineRef.current) (macdLineRef.current as {setData:(d:unknown[])=>void}).setData([]);
      if (macdSignalRef.current) (macdSignalRef.current as {setData:(d:unknown[])=>void}).setData([]);
      if (macdHistRef.current) (macdHistRef.current as {setData:(d:unknown[])=>void}).setData([]);
      if (stochKSeriesRef.current) (stochKSeriesRef.current as {setData:(d:unknown[])=>void}).setData([]);
      if (stochDSeriesRef.current) (stochDSeriesRef.current as {setData:(d:unknown[])=>void}).setData([]);
      setPanelValues(new Map());
      if (selectedIndicators.size === 0) return;
      const ap = new Set<string>(); for (const id of selectedIndicators) { const d = INDICATOR_DEFS.find((x) => x.id === id); if (d) ap.add(getEffectiveApiParam(d, indicatorSettings)); }
      let data: IndicatorDataPoint[] = [];
      try { const r = await fetchIndicators(symbol, timeframe, 500, [...ap].join(",")); if (!cancelled && r.data) data = r.data; } catch(e){console.error(e);return;}
      if (cancelled || data.length === 0) return;
      type TS = import("lightweight-charts").UTCTimestamp;
      const npv = new Map<string, number>();
      for (const id of selectedIndicators) { const def = INDICATOR_DEFS.find((x) => x.id === id); if (!def || def.placement !== "overlay") continue; const ec = getEffectiveColor(def, indicatorSettings); const ew = getEffectiveLineWidth(def, indicatorSettings);
        if (def.id === "bb") { const u = data.filter((d) => d.bb_upper != null).map((d) => ({time:d.time as TS,value:d.bb_upper as number})); const m = data.filter((d) => d.bb_middle != null).map((d) => ({time:d.time as TS,value:d.bb_middle as number})); const l = data.filter((d) => d.bb_lower != null).map((d) => ({time:d.time as TS,value:d.bb_lower as number})); const us = chart.addSeries(lc.LineSeries,{color:`${ec}80`,lineWidth:ew,priceScaleId:"right",lastValueVisible:false,priceLineVisible:false}); const ms = chart.addSeries(lc.LineSeries,{color:`${ec}CC`,lineWidth:ew,lineStyle:lc.LineStyle.Dashed,priceScaleId:"right",lastValueVisible:false,priceLineVisible:false}); const ls = chart.addSeries(lc.LineSeries,{color:`${ec}80`,lineWidth:ew,priceScaleId:"right",lastValueVisible:false,priceLineVisible:false}); us.setData(u); ms.setData(m); ls.setData(l); overlaySeriesRef.current.set("bb_upper",us); overlaySeriesRef.current.set("bb_middle",ms); overlaySeriesRef.current.set("bb_lower",ls);
        } else if (def.id === "vwap") { const vd = data.filter((d) => d.vwap != null).map((d) => ({time:d.time as TS,value:d.vwap as number})); const ud = data.filter((d) => d.vwap_upper != null).map((d) => ({time:d.time as TS,value:d.vwap_upper as number})); const ld = data.filter((d) => d.vwap_lower != null).map((d) => ({time:d.time as TS,value:d.vwap_lower as number})); const vs = chart.addSeries(lc.LineSeries,{color:ec,lineWidth:ew,priceScaleId:"right",lastValueVisible:false,priceLineVisible:false}); const us = chart.addSeries(lc.LineSeries,{color:`${ec}60`,lineWidth:ew,lineStyle:lc.LineStyle.Dashed,priceScaleId:"right",lastValueVisible:false,priceLineVisible:false}); const ls = chart.addSeries(lc.LineSeries,{color:`${ec}60`,lineWidth:ew,lineStyle:lc.LineStyle.Dashed,priceScaleId:"right",lastValueVisible:false,priceLineVisible:false}); vs.setData(vd); us.setData(ud); ls.setData(ld); overlaySeriesRef.current.set("vwap",vs); overlaySeriesRef.current.set("vwap_upper",us); overlaySeriesRef.current.set("vwap_lower",ls);
        } else { const ek = getEffectiveKeys(def, indicatorSettings); const ok = def.keys; const ld = data.map((d) => { const v = resolveIndicatorValue(d as Record<string,unknown>,ek[0],ok[0]); return v != null ? {time:d.time as TS,value:v} : null; }).filter((d): d is {time:TS;value:number} => d != null); const s = chart.addSeries(lc.LineSeries,{color:ec,lineWidth:ew,priceScaleId:"right",lastValueVisible:false,priceLineVisible:false}); s.setData(ld); overlaySeriesRef.current.set(def.id,s); }
      }
      if (selectedIndicators.has("rsi_14") && rsiSeriesRef.current) { const rd = INDICATOR_DEFS.find((d) => d.id === "rsi_14")!; const ek = getEffectiveKeys(rd, indicatorSettings); const ok = rd.keys; const d2 = data.map((d) => { const v = resolveIndicatorValue(d as Record<string,unknown>,ek[0],ok[0]); return v != null ? {time:d.time as TS,value:v} : null; }).filter((d): d is {time:TS;value:number} => d != null); (rsiSeriesRef.current as {setData:(d:unknown[])=>void}).setData(d2); }
      if (selectedIndicators.has("macd")) { const md = data.filter((d) => d.macd != null).map((d) => ({time:d.time as TS,value:d.macd as number})); const sd = data.filter((d) => d.macd_signal != null).map((d) => ({time:d.time as TS,value:d.macd_signal as number})); const hd = data.filter((d) => d.macd_histogram != null).map((d) => ({time:d.time as TS,value:d.macd_histogram as number,color:(d.macd_histogram as number)>=0?"rgba(64,229,108,0.5)":"rgba(255,180,171,0.5)"})); if (macdLineRef.current) (macdLineRef.current as {setData:(d:unknown[])=>void}).setData(md); if (macdSignalRef.current) (macdSignalRef.current as {setData:(d:unknown[])=>void}).setData(sd); if (macdHistRef.current) (macdHistRef.current as {setData:(d:unknown[])=>void}).setData(hd); }
      if (selectedIndicators.has("stoch")) { const kd = data.filter((d) => d.stoch_k != null).map((d) => ({time:d.time as TS,value:d.stoch_k as number})); const dd = data.filter((d) => d.stoch_d != null).map((d) => ({time:d.time as TS,value:d.stoch_d as number})); if (stochKSeriesRef.current) (stochKSeriesRef.current as {setData:(d:unknown[])=>void}).setData(kd); if (stochDSeriesRef.current) (stochDSeriesRef.current as {setData:(d:unknown[])=>void}).setData(dd); }
      for (const indId of ["adx","atr","obv","mfi","vol_sma"]) { if (!selectedIndicators.has(indId)) continue; const def = INDICATOR_DEFS.find((d) => d.id === indId); if (!def) continue; const ek = getEffectiveKeys(def, indicatorSettings); const ok = def.keys; for (let i = data.length-1; i >= 0; i--) { const v = resolveIndicatorValue(data[i] as Record<string,unknown>,ek[0],ok[0]); if (v != null) { npv.set(indId, v); break; } } }
      setPanelValues(npv);
    }
    go(); return () => { cancelled = true; };
  }, [selectedIndicators, symbol, timeframe, indicatorSettings, chartReady]);

  useEffect(() => { /* Reset infinite scroll state on symbol/timeframe change */ oldestTimestampRef.current = null; hasMoreDataRef.current = true; isLoadingHistoryRef.current = false; setIsLoadingHistory(false); allCandlesRef.current = []; loadData(symbol, timeframe, undefined, undefined, undefined, true); if (refreshIntervalRef.current) clearInterval(refreshIntervalRef.current); const tfc = TIMEFRAMES.find((t) => t.value === timeframe); const ms = Math.min((tfc?.seconds ?? 60) * 1000, 30000); refreshIntervalRef.current = setInterval(() => loadData(symbol, timeframe), ms); return () => { if (refreshIntervalRef.current) { clearInterval(refreshIntervalRef.current); refreshIntervalRef.current = null; } }; }, [symbol, timeframe, loadData]);

  const handlePriceUpdate = useCallback((data: PriceUpdate) => {
    if (data.symbol !== symbolRef.current) return;
    setLivePrice(data.price); if (data.change_24h != null) setPriceChange(data.change_24h); if (data.change_24h_percent != null) setPriceChangePercent(data.change_24h_percent);
    const cs = candleSeriesRef.current; const vs = volumeSeriesRef.current; if (!cs || !vs || !data.time || !data.open || !data.close) return;
    const rawTime = typeof data.time === "string" ? Math.floor(new Date(data.time).getTime()/1000) : Number(data.time); if (!rawTime || isNaN(rawTime)) return;
    const tfMap: Record<string,number> = {"1m":60,"3m":180,"5m":300,"15m":900,"30m":1800,"1h":3600,"1H":3600,"2h":7200,"4h":14400,"4H":14400,"6h":21600,"8h":28800,"12h":43200,"1d":86400,"1D":86400,"1w":604800,"1M":2592000};
    const tfSec = tfMap[timeframeRef.current] || 3600; const candleTime = Math.floor(rawTime/tfSec)*tfSec;
    if (candleTime < lastCandleTimeRef.current) return;
    const cur = currentCandleRef.current;
    if (cur && cur.time === candleTime) { cur.high = Math.max(cur.high, data.high ?? data.close); cur.low = Math.min(cur.low, data.low ?? data.close); cur.close = data.close; cur.volume = (cur.volume||0)+(data.volume??0); } else { currentCandleRef.current = { time: candleTime, open: data.open, high: data.high ?? data.close, low: data.low ?? data.close, close: data.close, volume: data.volume ?? 0 }; }
    lastCandleTimeRef.current = candleTime;
    const now = Date.now(); if (now - lastUpdateRef.current < 100) return; lastUpdateRef.current = now;
    const candle = currentCandleRef.current!;
    try { (cs as {update:(d:unknown)=>void}).update({time:candle.time as import("lightweight-charts").UTCTimestamp,open:candle.open,high:candle.high,low:candle.low,close:candle.close}); (vs as {update:(d:unknown)=>void}).update({time:candle.time as import("lightweight-charts").UTCTimestamp,value:candle.volume,color:candle.close>=candle.open?"rgba(64,229,108,0.25)":"rgba(255,180,171,0.25)"}); } catch(e){console.warn("Chart update skipped:",e);}
  }, []);
  useWebSocket("price_update", handlePriceUpdate);

  useEffect(() => { const tfc = TIMEFRAMES.find((t) => t.value === timeframe); const tfSec = tfc?.seconds ?? 3600; const timer = setInterval(() => { const n = Math.floor(Date.now()/1000); const cs = Math.floor(n/tfSec)*tfSec; const ns = cs+tfSec; const rem = ns-n; if (rem <= 0) { setCountdown("00:00"); } else { const h = Math.floor(rem/3600); const m = Math.floor((rem%3600)/60); const s = rem%60; setCountdown(h > 0 ? `${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}` : `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`); } }, 1000); return () => clearInterval(timer); }, [timeframe]);

  useEffect(() => { if (!showPositions) return; let c = false; async function lp() { try { const p = await fetchPositions({status:"OPEN"}); if (!c) setOpenPositions(p); } catch(e){console.warn("Failed to load positions:",e);} } lp(); const i = setInterval(lp, 30000); return () => { c = true; clearInterval(i); }; }, [showPositions, symbol]);

  useEffect(() => {
    const cs = candleSeriesRef.current; const lc = lcRef.current; if (!cs || !lc) return;
    const s = cs as {createPriceLine:(o:unknown)=>unknown;removePriceLine:(l:unknown)=>void};
    for (const [,l] of priceLinesRef.current) { try{s.removePriceLine(l);}catch{/**/} } priceLinesRef.current.clear();
    if (!showPositions) return;
    for (const pos of openPositions.filter((p) => p.symbol === symbol)) { const pid = pos.id.slice(0,8);
      if (pos.entry_price) { priceLinesRef.current.set(`entry_${pid}`, s.createPriceLine({price:pos.entry_price,color:"#3B82F6",lineStyle:0,lineWidth:1,title:`Entry $${fmtPS(pos.entry_price)} (${pos.direction})`,axisLabelVisible:true})); }
      if (pos.stop_loss) { priceLinesRef.current.set(`sl_${pid}`, s.createPriceLine({price:pos.stop_loss,color:"#EF4444",lineStyle:2,lineWidth:1,title:`SL $${fmtPS(pos.stop_loss)}`,axisLabelVisible:true})); }
      for (const tp of [{l:"TP1",p:pos.tp1_price},{l:"TP2",p:pos.tp2_price},{l:"TP3",p:pos.tp3_price}]) { if (tp.p) { priceLinesRef.current.set(`${tp.l.toLowerCase()}_${pid}`, s.createPriceLine({price:tp.p,color:"#22C55E",lineStyle:2,lineWidth:1,title:`${tp.l} $${fmtPS(tp.p)}`,axisLabelVisible:true})); } }
    }
  }, [showPositions, openPositions, symbol]);

  useEffect(() => {
    const cs = candleSeriesRef.current; if (!cs || !orderBook) return;
    const s = cs as {createPriceLine:(o:unknown)=>unknown;removePriceLine:(l:unknown)=>void};
    if (bidLineRef.current) { try{s.removePriceLine(bidLineRef.current);}catch{/**/} bidLineRef.current = null; }
    if (askLineRef.current) { try{s.removePriceLine(askLineRef.current);}catch{/**/} askLineRef.current = null; }
    const bid = orderBook.bids.length > 0 ? orderBook.bids[0][0] : null;
    const ask = orderBook.asks.length > 0 ? orderBook.asks[0][0] : null;
    if (bid) bidLineRef.current = s.createPriceLine({price:bid,color:"rgba(64,229,108,0.35)",lineStyle:1,lineWidth:1,title:"",axisLabelVisible:false});
    if (ask) askLineRef.current = s.createPriceLine({price:ask,color:"rgba(255,180,171,0.35)",lineStyle:1,lineWidth:1,title:"",axisLabelVisible:false});
  }, [orderBook]);

  /* ---- Bottom panel: exchange positions (poll every 15s) ---- */
  useEffect(() => {
    if (bottomTab !== "positions") return;
    let c = false;
    async function load() { try { const r = await fetchExchangePositions(); if (!c) setPanelPositions(r.positions); } catch { if (!c) setPanelPositions([]); } }
    load();
    const iv = setInterval(load, 15000);
    return () => { c = true; clearInterval(iv); };
  }, [bottomTab]);

  /* ---- Bottom panel: open orders ---- */
  useEffect(() => {
    if (bottomTab !== "orders") return;
    let c = false;
    async function load() { try { const r = await fetchOrders(); if (!c) setPanelOrders(r.filter((o) => ["PENDING","SUBMITTED","NEW","PARTIALLY_FILLED"].includes(o.status))); } catch { if (!c) setPanelOrders([]); } }
    load();
    const iv = setInterval(load, 15000);
    return () => { c = true; clearInterval(iv); };
  }, [bottomTab]);

  /* ---- Bottom panel: trade history ---- */
  useEffect(() => {
    if (bottomTab !== "history") return;
    let c = false;
    async function load() { try { const r = await fetchPositions({ status: "CLOSED" }); if (!c) setPanelHistory(r.slice(0, 20)); } catch { if (!c) setPanelHistory([]); } }
    load();
    return () => { c = true; };
  }, [bottomTab]);

  /* ---- Bottom panel: close position handler ---- */
  const handleClosePosition = useCallback(async (posId: string) => {
    setClosingPositionId(posId);
    try { await closePosition(posId); setPanelPositions((prev) => prev.filter((p) => `${p.symbol}-${p.direction}` !== posId)); } catch (e) { console.error("Failed to close position:", e); } finally { setClosingPositionId(null); }
  }, []);

  const showRsi = selectedIndicators.has("rsi_14");
  const showMacd = selectedIndicators.has("macd");
  const showStoch = selectedIndicators.has("stoch");
  const isPositive = priceChangePercent != null ? priceChangePercent >= 0 : null;
  const bestBid = orderBook && orderBook.bids.length > 0 ? orderBook.bids[0][0] : null;
  const bestAsk = orderBook && orderBook.asks.length > 0 ? orderBook.asks[0][0] : null;
  const badgeIndicators = useMemo(() => { const r: {id:string;label:string;color:string;value:number}[] = []; for (const [id,value] of panelValues) { const d = INDICATOR_DEFS.find((x)=>x.id===id); if (d) r.push({id,label:d.label,color:getEffectiveColor(d,indicatorSettings),value}); } return r; }, [panelValues, indicatorSettings]);

  return (
    <div className="flex flex-col bg-[#0D0D0D]" style={{ height: "calc(100vh - 48px - 48px)" }}>
      <style jsx global>{`.tv-lightweight-charts .chart-controls-bar, a[href*="tradingview"] { display: none !important; }`}</style>

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 flex-shrink-0 bg-[#131313]" style={{ borderBottom: "1px solid rgba(229,226,225,0.06)" }}>
        <div className="flex items-center gap-3">
          <SymbolSelector value={symbol} onChange={setSymbol} markets={markets} loading={marketsLoading} />
          <TimeframeSelector value={timeframe} onChange={setTimeframe} />
          <IndicatorSelector selected={selectedIndicators} onToggle={handleToggleIndicator} indicatorSettings={indicatorSettings} onApplySettings={handleApplySettings} />
          <div className="flex items-center gap-3 ml-2">
            <span className="font-mono text-lg font-semibold tabular-nums" style={{ color: "#E5E2E1" }}>{livePrice ? fmtP(livePrice) : "--"}</span>
            {priceChangePercent != null && <span className="font-mono text-xs font-medium tabular-nums" style={{ color: isPositive ? "#40E56C" : "#FFB4AB" }}>{isPositive ? "+" : ""}{priceChangePercent.toFixed(2)}%</span>}
            {priceChange != null && <span className="font-mono text-xs tabular-nums" style={{ color: "rgba(185,202,203,0.5)" }}>{isPositive ? "+" : ""}{fmtP(priceChange)}</span>}
          </div>
          {bestBid != null && bestAsk != null && (
            <div className="flex items-center gap-2 ml-2 pl-3 text-[10px] font-mono" style={{ borderLeft: "1px solid rgba(229,226,225,0.08)" }}>
              <span style={{ color: "rgba(185,202,203,0.4)" }}>Bid</span><span style={{ color: "#40E56C" }}>{fmtP(bestBid)}</span>
              <span style={{ color: "rgba(229,226,225,0.1)" }}>|</span>
              <span style={{ color: "rgba(185,202,203,0.4)" }}>Ask</span><span style={{ color: "#FFB4AB" }}>{fmtP(bestAsk)}</span>
              <span style={{ color: "rgba(229,226,225,0.1)" }}>|</span>
              <span style={{ color: "rgba(185,202,203,0.4)" }}>Spread</span><span style={{ color: "rgba(185,202,203,0.5)" }}>{fmtP(bestAsk - bestBid)}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => setShowPositions((p) => !p)} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm transition-all duration-200 cursor-pointer" style={{ background: showPositions ? "rgba(59,130,246,0.15)" : "rgba(229,226,225,0.05)", border: `1px solid ${showPositions ? "rgba(59,130,246,0.3)" : "rgba(229,226,225,0.08)"}` }} title={showPositions ? "Hide position lines" : "Show position lines"}>
            {showPositions ? <EyeOff size={12} style={{ color: "#3B82F6" }} /> : <Eye size={12} style={{ color: "rgba(185,202,203,0.5)" }} />}
            <span className="text-[10px] font-mono" style={{ color: showPositions ? "#3B82F6" : "rgba(185,202,203,0.5)" }}>Positions</span>
          </button>
          {countdown && <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm" style={{ background: "rgba(0,240,255,0.08)", border: "1px solid rgba(0,240,255,0.2)" }}><span className="text-[10px] font-mono" style={{ color: "rgba(185,202,203,0.5)" }}>Next</span><span className="text-[11px] font-mono tabular-nums font-semibold" style={{ color: "#00F0FF" }}>{countdown}</span></div>}
          <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "rgba(185,202,203,0.3)" }}>Binance Futures</span>
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full animate-pulse-dot" style={{ background: dataSource === "binance" || dataSource === "binance_cached" ? "#40E56C" : dataSource === "database" ? "#F59E0B" : "#FFB4AB" }} />
            <span className="text-[10px] font-mono uppercase" style={{ color: "rgba(185,202,203,0.3)" }}>{dataSource === "binance" || dataSource === "binance_cached" ? "Live" : dataSource === "database" ? "Cached" : "No Data"}</span>
          </div>
        </div>
      </div>

      {dataSource === "empty" && <div className="flex items-center gap-3 px-4 py-3 flex-shrink-0 bg-[#201F1F]" style={{ borderBottom: "1px solid rgba(0,240,255,0.2)" }}><AlertTriangle size={20} style={{ color: "#00F0FF", flexShrink: 0 }} /><div><p className="font-mono text-sm font-semibold" style={{ color: "#00F0FF" }}>Loading market data...</p><p className="font-mono text-xs mt-0.5" style={{ color: "rgba(0,240,255,0.5)" }}>Fetching candles from Binance Futures</p></div></div>}

      {/* Main: chart + sidebar */}
      <div className="flex flex-1 min-h-0">
        <div className="flex flex-col flex-1 min-w-0">
          <div className="flex-1 relative" style={{ minHeight: 300, background: "#131313" }}>
            <div ref={chartContainerRef} className="absolute inset-0" />
            {isLoadingHistory && (
              <div className="absolute top-2 left-2 z-20 flex items-center gap-2 px-2.5 py-1.5 rounded-sm" style={{ background: "rgba(0,32,34,0.85)", border: "1px solid rgba(0,240,255,0.25)" }}>
                <div className="w-3 h-3 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: "rgba(0,240,255,0.6)", borderTopColor: "transparent" }} />
                <span className="text-[10px] font-mono" style={{ color: "rgba(0,240,255,0.7)" }}>Loading history...</span>
              </div>
            )}
          </div>
          <div style={{ borderTop: "1px solid rgba(229,226,225,0.06)", position: "relative", display: showRsi ? "block" : "none" }}><div className="absolute left-2 top-1 z-10 text-[9px] font-mono" style={{ color: "#FBBF24" }}>RSI (14)</div><div ref={rsiContainerRef} style={{ height: 100, background: "#131313" }} /></div>
          <div style={{ borderTop: "1px solid rgba(229,226,225,0.06)", position: "relative", display: showMacd ? "block" : "none" }}><div className="absolute left-2 top-1 z-10 text-[9px] font-mono" style={{ color: "#38BDF8" }}>MACD</div><div ref={macdContainerRef} style={{ height: 100, background: "#131313" }} /></div>
          <div style={{ borderTop: "1px solid rgba(229,226,225,0.06)", position: "relative", display: showStoch ? "block" : "none" }}><div className="absolute left-2 top-1 z-10 text-[9px] font-mono" style={{ color: "#34D399" }}>Stoch <span style={{ color: "#34D399" }}>%K</span> <span style={{ color: "#FB923C" }}>%D</span></div><div ref={stochContainerRef} style={{ height: 100, background: "#131313" }} /></div>
        </div>

        {/* Right sidebar */}
        <div className="flex-shrink-0 flex flex-col bg-[#131313]" style={{ width: 272, borderLeft: "1px solid rgba(229,226,225,0.06)" }}>
          <div className="flex flex-shrink-0" style={{ borderBottom: "1px solid rgba(229,226,225,0.06)" }}>
            <button onClick={() => setTradeTab("orderbook")} className="flex-1 py-2 text-xs font-mono text-center cursor-pointer transition-colors" style={{ color: tradeTab === "orderbook" ? "#00F0FF" : "rgba(185,202,203,0.4)", borderBottom: tradeTab === "orderbook" ? "2px solid #00F0FF" : "2px solid transparent" }}>Order Book</button>
            <button onClick={() => setTradeTab("trade")} className="flex-1 py-2 text-xs font-mono text-center cursor-pointer transition-colors" style={{ color: tradeTab === "trade" ? "#00F0FF" : "rgba(185,202,203,0.4)", borderBottom: tradeTab === "trade" ? "2px solid #00F0FF" : "2px solid transparent" }}>Trade</button>
          </div>
          <div className="flex-1 overflow-y-auto min-h-0">
            {tradeTab === "orderbook" ? <OrderBookPanel data={orderBook} symbol={symbol} /> : (
              <div className="flex flex-col gap-3 p-3">
                <div className="flex gap-2">
                  <button onClick={() => setTradeDirection("LONG")} className="flex-1 py-2 rounded-sm text-xs font-mono font-semibold cursor-pointer transition-all" style={{ background: tradeDirection === "LONG" ? "#02C953" : "rgba(64,229,108,0.08)", color: tradeDirection === "LONG" ? "#fff" : "#40E56C", border: `1px solid ${tradeDirection === "LONG" ? "#02C953" : "rgba(64,229,108,0.2)"}` }}>LONG</button>
                  <button onClick={() => setTradeDirection("SHORT")} className="flex-1 py-2 rounded-sm text-xs font-mono font-semibold cursor-pointer transition-all" style={{ background: tradeDirection === "SHORT" ? "#93000A" : "rgba(255,180,171,0.08)", color: tradeDirection === "SHORT" ? "#fff" : "#FFB4AB", border: `1px solid ${tradeDirection === "SHORT" ? "#93000A" : "rgba(255,180,171,0.2)"}` }}>SHORT</button>
                </div>
                <div>
                  <label className="text-[10px] font-mono uppercase tracking-widest block mb-1" style={{ color: "rgba(185,202,203,0.4)" }}>Type</label>
                  <select value={tradeOrderType} onChange={(e) => setTradeOrderType(e.target.value as typeof tradeOrderType)} className="w-full px-3 py-2 rounded-sm text-xs font-mono cursor-pointer appearance-none" style={{ background: "#2A2A2A", border: "1px solid rgba(229,226,225,0.1)", color: "#E5E2E1", backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2300F0FF' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E")`, backgroundRepeat: "no-repeat", backgroundPosition: "right 12px center", paddingRight: 32, outline: "none" }}>
                    <option value="MARKET" style={{ background: "#1C1B1B", color: "#E5E2E1" }}>Market</option>
                    <option value="LIMIT" style={{ background: "#1C1B1B", color: "#E5E2E1" }}>Limit</option>
                    <option value="STOP_MARKET" style={{ background: "#1C1B1B", color: "#E5E2E1" }}>Stop Market</option>
                    <option value="STOP_LIMIT" style={{ background: "#1C1B1B", color: "#E5E2E1" }}>Stop Limit</option>
                  </select>
                </div>
                {tradeOrderType !== "MARKET" && <div><label className="text-[10px] font-mono uppercase tracking-widest block mb-1" style={{ color: "rgba(185,202,203,0.4)" }}>Price</label><input type="number" step="any" value={tradePrice} onChange={(e) => setTradePrice(e.target.value)} placeholder={livePrice ? livePrice.toFixed(2) : "0.00"} className="w-full px-3 py-2 rounded-sm text-xs font-mono outline-none tabular-nums transition-colors" style={{ background: "#2A2A2A", border: "1px solid rgba(229,226,225,0.1)", color: "#E5E2E1" }} /></div>}
                {["STOP_MARKET","STOP_LIMIT"].includes(tradeOrderType) && <div><label className="text-[10px] font-mono uppercase tracking-widest block mb-1" style={{ color: "rgba(185,202,203,0.4)" }}>Stop Price</label><input type="number" step="any" value={tradeStopPrice} onChange={(e) => setTradeStopPrice(e.target.value)} placeholder="0.00" className="w-full px-3 py-2 rounded-sm text-xs font-mono outline-none tabular-nums transition-colors" style={{ background: "#2A2A2A", border: "1px solid rgba(229,226,225,0.1)", color: "#E5E2E1" }} /></div>}
                <div>
                  <label className="text-[10px] font-mono uppercase tracking-widest block mb-1" style={{ color: "rgba(185,202,203,0.4)" }}>Quantity</label>
                  <input type="number" step="any" value={tradeQty} onChange={(e) => setTradeQty(e.target.value)} placeholder="0.000" className="w-full px-3 py-2 rounded-sm text-xs font-mono outline-none tabular-nums transition-colors" style={{ background: "#2A2A2A", border: "1px solid rgba(229,226,225,0.1)", color: "#E5E2E1" }} />
                  {tradeCalcs.notional > 0 && <div className="mt-1 text-[10px] font-mono tabular-nums" style={{ color: "rgba(185,202,203,0.5)" }}>&asymp; ${tradeCalcs.notional.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})} USDT</div>}
                </div>
                <div>
                  <label className="text-[10px] font-mono uppercase tracking-widest block mb-1" style={{ color: "rgba(185,202,203,0.4)" }}>Leverage <span style={{ color: "rgba(0,240,255,0.6)" }}>(max {maxLeverage}x)</span></label>
                  <div className="flex gap-1.5 flex-wrap">
                    {leverageOptions.map((lev) => <button key={lev} onClick={() => { setTradeLeverage(lev); setCustomLeverage(false); }} className="px-2 py-1 rounded-sm text-[10px] font-mono cursor-pointer transition-all" style={{ background: !customLeverage && tradeLeverage === lev ? "rgba(0,240,255,0.2)" : "#2A2A2A", border: `1px solid ${!customLeverage && tradeLeverage === lev ? "rgba(0,240,255,0.4)" : "rgba(229,226,225,0.08)"}`, color: !customLeverage && tradeLeverage === lev ? "#00F0FF" : "rgba(185,202,203,0.6)" }}>{lev}x</button>)}
                    <button onClick={() => setCustomLeverage(!customLeverage)} className="px-2 py-1 rounded-sm text-[10px] font-mono cursor-pointer transition-all" style={{ background: customLeverage ? "rgba(0,240,255,0.2)" : "#2A2A2A", border: `1px solid ${customLeverage ? "rgba(0,240,255,0.4)" : "rgba(229,226,225,0.08)"}`, color: customLeverage ? "#00F0FF" : "rgba(185,202,203,0.6)" }}>+</button>
                  </div>
                  {customLeverage && <input type="number" min={1} max={maxLeverage} value={tradeLeverage} onChange={(e) => setTradeLeverage(Math.max(1,Math.min(maxLeverage,parseInt(e.target.value)||1)))} className="w-full mt-1.5 px-2 py-1.5 rounded-sm text-xs font-mono outline-none tabular-nums" style={{ background: "#2A2A2A", border: "1px solid rgba(229,226,225,0.1)", color: "#E5E2E1" }} />}
                </div>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <input type="checkbox" checked={tradeSLEnabled} onChange={(e) => setTradeSLEnabled(e.target.checked)} className="cursor-pointer accent-cyan-400" style={{ width: 12, height: 12 }} />
                    <label className="text-[10px] font-mono uppercase tracking-widest flex-shrink-0" style={{ color: "rgba(185,202,203,0.4)" }}>Stop Loss</label>
                    {tradeSLEnabled && <input type="number" step="any" value={tradeSL} onChange={(e) => setTradeSL(e.target.value)} placeholder="0.00" className="flex-1 px-2.5 py-1.5 rounded-sm text-xs font-mono outline-none tabular-nums transition-colors" style={{ background: "#2A2A2A", border: "1px solid rgba(229,226,225,0.1)", color: "#E5E2E1" }} />}
                  </div>
                  <div className="flex items-center gap-2">
                    <input type="checkbox" checked={tradeTPEnabled} onChange={(e) => setTradeTPEnabled(e.target.checked)} className="cursor-pointer accent-cyan-400" style={{ width: 12, height: 12 }} />
                    <label className="text-[10px] font-mono uppercase tracking-widest flex-shrink-0" style={{ color: "rgba(185,202,203,0.4)" }}>Take Profit</label>
                    {tradeTPEnabled && <input type="number" step="any" value={tradeTP} onChange={(e) => setTradeTP(e.target.value)} placeholder="0.00" className="flex-1 px-2.5 py-1.5 rounded-sm text-xs font-mono outline-none tabular-nums transition-colors" style={{ background: "#2A2A2A", border: "1px solid rgba(229,226,225,0.1)", color: "#E5E2E1" }} />}
                  </div>
                </div>
                {tradeCalcs.price > 0 && parseFloat(tradeQty) > 0 && (
                  <div className="pt-2" style={{ borderTop: "1px solid rgba(229,226,225,0.06)" }}>
                    <div className="text-[10px] font-mono uppercase tracking-widest mb-2" style={{ color: "rgba(185,202,203,0.4)" }}>Estimated</div>
                    <div className="flex flex-col gap-1">
                      <div className="flex justify-between"><span className="text-[10px] font-mono" style={{ color: "rgba(185,202,203,0.5)" }}>Margin</span><span className="text-xs font-mono tabular-nums" style={{ color: "rgba(229,226,225,0.7)" }}>${tradeCalcs.margin.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}</span></div>
                      <div className="flex justify-between"><span className="text-[10px] font-mono" style={{ color: "rgba(185,202,203,0.5)" }}>Liq. Price</span><span className="text-xs font-mono tabular-nums" style={{ color: "rgba(229,226,225,0.7)" }}>${tradeCalcs.liqPrice > 0 ? tradeCalcs.liqPrice.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2}) : "\u2014"}</span></div>
                      {tradeCalcs.risk > 0 && <div className="flex justify-between"><span className="text-[10px] font-mono" style={{ color: "rgba(185,202,203,0.5)" }}>Risk</span><span className="text-xs font-mono tabular-nums" style={{ color: "#FFB4AB" }}>${tradeCalcs.risk.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}</span></div>}
                      {tradeCalcs.rr > 0 && <div className="flex justify-between"><span className="text-[10px] font-mono" style={{ color: "rgba(185,202,203,0.5)" }}>R:R</span><span className="text-xs font-mono tabular-nums" style={{ color: "#40E56C" }}>1:{tradeCalcs.rr.toFixed(2)}</span></div>}
                    </div>
                  </div>
                )}
                <button onClick={handlePlaceTrade} disabled={tradeSubmitting || !parseFloat(tradeQty)} className="w-full py-2.5 rounded-sm text-xs font-mono font-semibold cursor-pointer transition-all disabled:opacity-40 disabled:cursor-not-allowed" style={{ background: tradeDirection === "LONG" ? "#02C953" : "#93000A", color: "#fff", border: "none" }}>{tradeSubmitting ? "Placing..." : `Place ${tradeDirection} ${tradeOrderType.replace("_"," ")}`}</button>
                {tradeResult && <div className="px-2 py-1.5 rounded-sm text-[10px] font-mono" style={{ background: tradeResult.ok ? "rgba(64,229,108,0.08)" : "rgba(255,180,171,0.08)", border: `1px solid ${tradeResult.ok ? "rgba(64,229,108,0.2)" : "rgba(255,180,171,0.2)"}`, color: tradeResult.ok ? "#40E56C" : "#FFB4AB" }}>{tradeResult.msg}</div>}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom trading panel */}
      <div className="flex-shrink-0 flex flex-col bg-[#131313]" style={{ height: 200, borderTop: "1px solid rgba(59,73,75,0.1)" }}>
        {/* Tab bar */}
        <div className="flex items-center bg-[#131313] px-4 flex-shrink-0" style={{ borderBottom: "1px solid rgba(59,73,75,0.1)" }}>
          {(["positions", "orders", "history", "trade"] as const).map((tab) => (
            <button key={tab} onClick={() => setBottomTab(tab)}
              className={`px-4 py-2 text-[10px] font-mono uppercase tracking-widest transition-colors cursor-pointer ${bottomTab === tab ? "text-[#00F0FF] border-b-2 border-[#00F0FF]" : "text-[#B9CACB]/50 hover:text-[#B9CACB] border-b-2 border-transparent"}`}>
              {tab === "positions" ? "Positions" : tab === "orders" ? "Open Orders" : tab === "history" ? "Trade History" : "Place Order"}
            </button>
          ))}
        </div>
        {/* Tab content */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {/* Positions tab */}
          {bottomTab === "positions" && (
            panelPositions.length === 0 ? (
              <div className="flex items-center justify-center h-full"><span className="text-xs font-mono" style={{ color: "rgba(185,202,203,0.3)" }}>No open positions</span></div>
            ) : (
              <table className="w-full text-[10px] font-mono">
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(229,226,225,0.06)" }}>
                    {["Symbol","Dir","Entry","Mark","Qty","Lev","P&L","ROI","Margin","Liq","Notional",""].map((h) => (
                      <th key={h} className="px-3 py-1.5 text-left text-[9px] uppercase tracking-wider font-normal" style={{ color: "rgba(185,202,203,0.4)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {panelPositions.map((p) => {
                    const key = `${p.symbol}-${p.direction}`;
                    const pnlColor = p.unrealized_pnl >= 0 ? "#40E56C" : "#FFB4AB";
                    const roi = p.margin > 0 ? (p.unrealized_pnl / p.margin) * 100 : 0;
                    return (
                      <tr key={key} className="hover:bg-[#1C1B1B] transition-colors" style={{ borderBottom: "1px solid rgba(229,226,225,0.03)" }}>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "#E5E2E1" }}>{p.symbol}</td>
                        <td className="px-3 py-1.5"><span style={{ color: p.direction === "LONG" ? "#40E56C" : "#FFB4AB" }}>{p.direction}</span></td>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(229,226,225,0.7)" }}>{fmtP(p.entry_price)}</td>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(229,226,225,0.7)" }}>{fmtP(p.current_price)}</td>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(229,226,225,0.7)" }}>{p.quantity}</td>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(0,240,255,0.7)" }}>{p.leverage}x</td>
                        <td className="px-3 py-1.5 tabular-nums font-semibold" style={{ color: pnlColor }}>{p.unrealized_pnl >= 0 ? "+" : ""}{p.unrealized_pnl.toFixed(2)}</td>
                        <td className="px-3 py-1.5 tabular-nums font-semibold" style={{ color: pnlColor }}>{roi >= 0 ? "+" : ""}{roi.toFixed(2)}%</td>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(229,226,225,0.5)" }}>${p.margin.toFixed(2)}</td>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: p.liquidation_price > 0 ? "rgba(255,180,171,0.6)" : "rgba(185,202,203,0.2)" }}>{p.liquidation_price > 0 ? fmtP(p.liquidation_price) : "\u2014"}</td>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(229,226,225,0.4)" }}>${p.notional.toFixed(2)}</td>
                        <td className="px-3 py-1.5">
                          <button onClick={() => handleClosePosition(key)} disabled={closingPositionId === key}
                            className="px-2 py-0.5 rounded-sm text-[9px] font-mono font-semibold cursor-pointer transition-all disabled:opacity-40"
                            style={{ background: "rgba(255,180,171,0.1)", border: "1px solid rgba(255,180,171,0.2)", color: "#FFB4AB" }}>
                            {closingPositionId === key ? "..." : "Close"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )
          )}

          {/* Open Orders tab */}
          {bottomTab === "orders" && (
            panelOrders.length === 0 ? (
              <div className="flex items-center justify-center h-full"><span className="text-xs font-mono" style={{ color: "rgba(185,202,203,0.3)" }}>No pending orders</span></div>
            ) : (
              <table className="w-full text-[10px] font-mono">
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(229,226,225,0.06)" }}>
                    {["Symbol","Side","Type","Price","Qty","Filled","Avg Fill","Fees","Status","Time",""].map((h) => (
                      <th key={h} className="px-3 py-1.5 text-left text-[9px] uppercase tracking-wider font-normal" style={{ color: "rgba(185,202,203,0.4)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {panelOrders.map((o) => (
                    <tr key={o.id} className="hover:bg-[#1C1B1B] transition-colors" style={{ borderBottom: "1px solid rgba(229,226,225,0.03)" }}>
                      <td className="px-3 py-1.5 tabular-nums" style={{ color: "#E5E2E1" }}>{o.symbol}</td>
                      <td className="px-3 py-1.5"><span style={{ color: o.side === "BUY" ? "#40E56C" : "#FFB4AB" }}>{o.side}</span></td>
                      <td className="px-3 py-1.5" style={{ color: "rgba(229,226,225,0.7)" }}>{o.order_type.replace("_"," ")}</td>
                      <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(229,226,225,0.7)" }}>{o.price ? fmtP(o.price) : "Market"}</td>
                      <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(229,226,225,0.7)" }}>{o.quantity ?? "-"}</td>
                      <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(229,226,225,0.5)" }}>{o.filled_qty}</td>
                      <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(229,226,225,0.5)" }}>{o.avg_fill_price ? fmtP(o.avg_fill_price) : "\u2014"}</td>
                      <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(255,180,171,0.5)" }}>{o.fees ? `$${o.fees.toFixed(4)}` : "\u2014"}</td>
                      <td className="px-3 py-1.5"><span className="px-1.5 py-0.5 rounded-sm text-[9px]" style={{ background: "rgba(0,240,255,0.08)", color: "rgba(0,240,255,0.7)" }}>{o.status}</span></td>
                      <td className="px-3 py-1.5" style={{ color: "rgba(185,202,203,0.4)" }}>{o.created_at ? new Date(o.created_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }) : "\u2014"}</td>
                      <td className="px-3 py-1.5">
                        <button className="px-2 py-0.5 rounded-sm text-[9px] font-mono font-semibold cursor-pointer transition-all"
                          style={{ background: "rgba(255,180,171,0.1)", border: "1px solid rgba(255,180,171,0.2)", color: "#FFB4AB" }}>
                          Cancel
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          )}

          {/* Trade History tab */}
          {bottomTab === "history" && (
            panelHistory.length === 0 ? (
              <div className="flex items-center justify-center h-full"><span className="text-xs font-mono" style={{ color: "rgba(185,202,203,0.3)" }}>No trade history</span></div>
            ) : (
              <table className="w-full text-[10px] font-mono">
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(229,226,225,0.06)" }}>
                    {["Symbol","Dir","Strategy","Entry","Exit","Qty","P&L","Fees","Reason","Duration","Opened","Closed"].map((h) => (
                      <th key={h} className="px-3 py-1.5 text-left text-[9px] uppercase tracking-wider font-normal" style={{ color: "rgba(185,202,203,0.4)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {panelHistory.map((p) => {
                    const pnl = p.realized_pnl;
                    const pnlColor = pnl >= 0 ? "#40E56C" : "#FFB4AB";
                    const holdMs = p.opened_at && p.closed_at ? new Date(p.closed_at).getTime() - new Date(p.opened_at).getTime() : 0;
                    const holdHrs = holdMs / 3_600_000;
                    const holdStr = holdHrs < 1 ? `${Math.round(holdHrs * 60)}m` : holdHrs < 24 ? `${holdHrs.toFixed(1)}h` : `${(holdHrs / 24).toFixed(1)}d`;
                    return (
                      <tr key={p.id} className="hover:bg-[#1C1B1B] transition-colors" style={{ borderBottom: "1px solid rgba(229,226,225,0.03)" }}>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "#E5E2E1" }}>{p.symbol}</td>
                        <td className="px-3 py-1.5"><span style={{ color: p.direction === "LONG" ? "#40E56C" : "#FFB4AB" }}>{p.direction}</span></td>
                        <td className="px-3 py-1.5" style={{ color: "rgba(0,240,255,0.7)" }}>{p.strategy_name ?? "\u2014"}</td>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(229,226,225,0.7)" }}>{p.entry_price ? fmtP(p.entry_price) : "-"}</td>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(229,226,225,0.7)" }}>{p.current_price ? fmtP(p.current_price) : "-"}</td>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(229,226,225,0.5)" }}>{p.quantity}</td>
                        <td className="px-3 py-1.5 tabular-nums font-semibold" style={{ color: pnlColor }}>{pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}</td>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(255,180,171,0.5)" }}>${p.total_fees.toFixed(4)}</td>
                        <td className="px-3 py-1.5"><span className="px-1 py-0.5 rounded-sm text-[8px]" style={{
                          background: p.close_reason?.includes("TP") ? "rgba(64,229,108,0.1)" : p.close_reason?.includes("SL") ? "rgba(255,180,171,0.1)" : "rgba(185,202,203,0.08)",
                          color: p.close_reason?.includes("TP") ? "#40E56C" : p.close_reason?.includes("SL") ? "#FFB4AB" : "rgba(185,202,203,0.5)",
                        }}>{p.close_reason ?? "\u2014"}</span></td>
                        <td className="px-3 py-1.5 tabular-nums" style={{ color: "rgba(185,202,203,0.5)" }}>{holdMs > 0 ? holdStr : "\u2014"}</td>
                        <td className="px-3 py-1.5" style={{ color: "rgba(185,202,203,0.4)" }}>{p.opened_at ? new Date(p.opened_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "-"}</td>
                        <td className="px-3 py-1.5" style={{ color: "rgba(185,202,203,0.5)" }}>{p.closed_at ? new Date(p.closed_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "-"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )
          )}

          {/* Place Order tab */}
          {bottomTab === "trade" && (
            <div className="flex items-center justify-center h-full gap-3">
              <span className="text-xs font-mono" style={{ color: "rgba(185,202,203,0.4)" }}>Use the sidebar Trade tab to place orders</span>
              <button onClick={() => setTradeTab("trade")} className="px-3 py-1.5 rounded-sm text-[10px] font-mono font-semibold cursor-pointer transition-all" style={{ background: "rgba(0,240,255,0.15)", border: "1px solid rgba(0,240,255,0.3)", color: "#00F0FF" }}>Open Trade Panel &rarr;</button>
            </div>
          )}
        </div>
      </div>

      {/* Bottom bar */}
      <div className="flex items-center gap-6 px-4 py-1.5 flex-shrink-0 bg-[#131313]" style={{ borderTop: "1px solid rgba(229,226,225,0.06)" }}>
        <MS l="Source" v={dataSource === "binance" ? "Binance REST" : dataSource === "binance_cached" ? "Binance (cached)" : dataSource === "database" ? "Local DB" : "Loading..."} />
        <MS l="Symbol" v={symbol} />
        <MS l="Timeframe" v={timeframe.toUpperCase()} />
        {livePrice && <MS l="Price" v={fmtP(livePrice)} />}
        <MS l="Markets" v={marketsLoading ? "Loading..." : `${markets.length} pairs`} />
        {selectedIndicators.size > 0 && <MS l="Indicators" v={`${selectedIndicators.size} active`} />}
        {badgeIndicators.map((bi) => <div key={bi.id} className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full" style={{ background: bi.color }} /><span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "rgba(185,202,203,0.4)" }}>{bi.label}</span><span className="text-xs font-mono font-medium tabular-nums" style={{ color: bi.color }}>{fmtBV(bi.id, bi.value)}</span></div>)}
      </div>
    </div>
  );
}

/* =========================================================================
   Helpers
   ========================================================================= */

function MS({ l, v, p }: { l: string; v: string; p?: boolean }) {
  return <div className="flex items-center gap-2"><span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "rgba(185,202,203,0.3)" }}>{l}</span><span className="text-xs font-mono font-medium tabular-nums" style={{ color: p === true ? "#40E56C" : p === false ? "#FFB4AB" : "rgba(229,226,225,0.7)" }}>{v}</span></div>;
}

function fmtP(price: number): string { if (price === 0) return "--"; if (Math.abs(price) < 0.01) return `$${price.toFixed(6)}`; if (Math.abs(price) < 1) return `$${price.toFixed(4)}`; if (Math.abs(price) < 100) return `$${price.toFixed(2)}`; return `$${price.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}`; }
function fmtPS(price: number): string { if (price === 0) return "--"; if (Math.abs(price) < 0.01) return price.toFixed(6); if (Math.abs(price) < 1) return price.toFixed(4); if (Math.abs(price) < 100) return price.toFixed(2); return price.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2}); }
function fmtBV(id: string, v: number): string { if (id === "obv") { if (Math.abs(v)>=1e9) return `${(v/1e9).toFixed(2)}B`; if (Math.abs(v)>=1e6) return `${(v/1e6).toFixed(2)}M`; if (Math.abs(v)>=1e3) return `${(v/1e3).toFixed(1)}K`; return v.toFixed(0); } if (id === "vol_sma") { if (v>=1e6) return `${(v/1e6).toFixed(2)}M`; if (v>=1e3) return `${(v/1e3).toFixed(1)}K`; return v.toFixed(0); } if (id === "atr") return v.toFixed(4); return v.toFixed(1); }
