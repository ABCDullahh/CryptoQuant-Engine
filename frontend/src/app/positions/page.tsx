"use client";

import React, { useState, useCallback, useMemo, useRef, useEffect } from "react";
import {
  Wallet,
  Search,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Shield,
  AlertTriangle,
  X,
  Check,
  Circle,
  Save,
  History,
  ChevronDown,
} from "lucide-react";
import { DirectionBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { usePolling, useWebSocket } from "@/hooks/useApi";
import {
  fetchPositions,
  closePosition,
  updateStopLoss,
  updateTakeProfit,
  fetchExchangePositions,
  fetchBotStatus,
  type Position,
  type PositionStatus,
  type ExchangePosition,
  type TradingMode,
  type BotStatus,
} from "@/lib/api";
import type { PriceUpdate } from "@/lib/websocket";
import { formatPrice, formatPnl, formatPercent, cn } from "@/lib/utils";

/* PnL pulse animation is now in globals.css */

/* ── Status Filter Options ── */
const STATUS_OPTIONS: Array<{ label: string; value: PositionStatus | "ALL" }> = [
  { label: "All", value: "ALL" },
  { label: "Open", value: "OPEN" },
  { label: "Reducing", value: "REDUCING" },
  { label: "Closed", value: "CLOSED" },
];

/* ── Filter Button ── */
function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-3 py-1.5 rounded-sm text-xs font-medium font-mono transition-all duration-150",
        active
          ? "bg-[#00F0FF]/10 text-[#00F0FF] border border-[#00F0FF]/20"
          : "bg-[#201F1F] text-[#B9CACB]/50 border border-[#3B494B]/10 hover:text-[#E5E2E1] hover:border-[#3B494B]/20"
      )}
    >
      {children}
    </button>
  );
}

/* ── Take Profit Display ── */
function TakeProfitDisplay({ position }: { position: Position }) {
  const tps = [
    { label: "TP1", price: position.tp1_price },
    { label: "TP2", price: position.tp2_price },
    { label: "TP3", price: position.tp3_price },
  ].filter((tp) => tp.price != null);

  if (tps.length === 0) {
    return <span className="text-xs text-[#B9CACB]/30">\u2014</span>;
  }

  return (
    <div className="flex items-center gap-1.5">
      {tps.map((tp, i) => (
        <div key={i} className="flex items-center gap-0.5" title={`${tp.label}: ${formatPrice(tp.price!)}`}>
          <Circle size={8} className="text-[#3B494B]" />
          <span className="font-mono text-[10px] tabular-nums text-[#B9CACB]/40">
            {tp.label}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ── Position Detail Panel ── */
function PositionDetailPanel({
  position,
  onClose,
  onUpdated,
}: {
  position: Position;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const [closing, setClosing] = useState(false);
  const [savingSl, setSavingSl] = useState(false);
  const [savingTp, setSavingTp] = useState(false);
  const [slValue, setSlValue] = useState(String(position.stop_loss ?? ""));
  const [tpValues, setTpValues] = useState<string[]>(
    [position.tp1_price, position.tp2_price, position.tp3_price]
      .filter((v): v is number => v != null)
      .map(String)
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    setSlValue(String(position.stop_loss ?? ""));
    setTpValues(
      [position.tp1_price, position.tp2_price, position.tp3_price]
        .filter((v): v is number => v != null)
        .map(String)
    );
    setActionError(null);
    setActionSuccess(null);
  }, [position.id, position.stop_loss, position.tp1_price, position.tp2_price, position.tp3_price]);

  useEffect(() => {
    if (actionSuccess) {
      const timer = setTimeout(() => setActionSuccess(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [actionSuccess]);

  const handleClosePosition = async () => {
    try {
      setClosing(true);
      setActionError(null);
      await closePosition(position.id);
      setActionSuccess("Position close order sent");
      onUpdated();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to close position");
    } finally {
      setClosing(false);
    }
  };

  const handleUpdateSl = async () => {
    const newSl = parseFloat(slValue);
    if (isNaN(newSl) || newSl <= 0) {
      setActionError("Invalid stop loss value");
      return;
    }
    try {
      setSavingSl(true);
      setActionError(null);
      await updateStopLoss(position.id, newSl);
      setActionSuccess("Stop loss updated");
      onUpdated();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to update stop loss");
    } finally {
      setSavingSl(false);
    }
  };

  const handleUpdateTp = async () => {
    const tpPayload: Array<{ level: string; price: number }> = [];
    for (let i = 0; i < tpValues.length; i++) {
      const price = parseFloat(tpValues[i]);
      if (isNaN(price) || price <= 0) {
        setActionError(`Invalid price for TP${i + 1}`);
        return;
      }
      tpPayload.push({ level: `TP${i + 1}`, price });
    }
    try {
      setSavingTp(true);
      setActionError(null);
      await updateTakeProfit(position.id, tpPayload);
      setActionSuccess("Take profits updated");
      onUpdated();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to update take profits");
    } finally {
      setSavingTp(false);
    }
  };

  const handleTpChange = (index: number, value: string) => {
    setTpValues((prev) => {
      const updated = [...prev];
      updated[index] = value;
      return updated;
    });
  };

  const addTpLevel = () => setTpValues((prev) => [...prev, ""]);
  const removeTpLevel = (index: number) => setTpValues((prev) => prev.filter((_, i) => i !== index));

  const inputClass = "w-full px-3 py-2 rounded-sm text-sm font-mono bg-[#2A2A2A] text-[#E5E2E1] border-0 focus:outline-none focus:ring-1 focus:ring-[#00F0FF] placeholder:text-[#B9CACB]/30";
  const inputSmClass = "flex-1 px-2 py-1.5 rounded-sm text-xs font-mono bg-[#2A2A2A] text-[#E5E2E1] border-0 focus:outline-none focus:ring-1 focus:ring-[#00F0FF] placeholder:text-[#B9CACB]/30";

  return (
    <div className="animate-fade-in-up">
      <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-5 mt-3">
        {/* Action feedback */}
        {actionError && (
          <div className="mb-4 flex items-center gap-2 px-3 py-2 rounded-sm text-xs font-mono bg-[#FFB4AB]/10 border border-[#FFB4AB]/20 text-[#FFB4AB]">
            <AlertTriangle size={14} />
            {actionError}
            <button onClick={() => setActionError(null)} className="ml-auto">
              <X size={12} />
            </button>
          </div>
        )}

        {actionSuccess && (
          <div className="mb-4 flex items-center gap-2 px-3 py-2 rounded-sm text-xs font-mono bg-[#40E56C]/10 border border-[#40E56C]/20 text-[#40E56C]">
            <Check size={14} />
            {actionSuccess}
          </div>
        )}

        <div className="grid grid-cols-4 gap-6">
          {/* Position info */}
          <div className="space-y-3">
            <h4 className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]">
              Position Info
            </h4>
            <div className="space-y-2">
              {[
                { label: "Symbol", value: <span className="font-mono text-sm font-semibold text-[#E5E2E1]">{position.symbol}</span> },
                { label: "Direction", value: <DirectionBadge direction={position.direction} size="sm">{position.direction} {position.leverage}x</DirectionBadge> },
                { label: "Entry", value: <span className="font-mono text-sm tabular-nums text-[#E5E2E1]">{formatPrice(position.entry_price ?? 0)}</span> },
                { label: "Current", value: <span className="font-mono text-sm tabular-nums text-[#E5E2E1]">{formatPrice(position.current_price ?? 0)}</span> },
                { label: "Qty", value: <span className="font-mono text-sm tabular-nums text-[#B9CACB]">{position.quantity}</span> },
                { label: "Unrealized P&L", value: <span className={`font-mono text-sm tabular-nums font-semibold ${position.unrealized_pnl >= 0 ? "text-[#40E56C]" : "text-[#FFB4AB]"}`}>{formatPnl(position.unrealized_pnl)}</span> },
                { label: "Total Fees", value: <span className="font-mono text-sm tabular-nums text-[#B9CACB]">${position.total_fees.toFixed(2)}</span> },
              ].map((item, i) => (
                <div key={i} className="flex justify-between items-center">
                  <span className="text-xs text-[#B9CACB]/50">{item.label}</span>
                  {item.value}
                </div>
              ))}
            </div>
          </div>

          {/* Update Stop Loss */}
          <div className="space-y-3">
            <h4 className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]">
              Stop Loss
            </h4>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-mono uppercase text-[#B9CACB]/50 block mb-1">
                  Stop Loss Price
                </label>
                <input
                  type="number"
                  step="any"
                  value={slValue}
                  onChange={(e) => setSlValue(e.target.value)}
                  className={inputClass}
                  placeholder="0.00"
                />
              </div>
              <Button variant="secondary" size="sm" loading={savingSl} onClick={handleUpdateSl}>
                <Save size={12} />
                Update SL
              </Button>
            </div>
          </div>

          {/* Update Take Profits */}
          <div className="space-y-3">
            <h4 className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]">
              Take Profits
            </h4>
            <div className="space-y-2">
              {tpValues.map((tp, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-[#B9CACB]/30 w-6">TP{i + 1}</span>
                  <input
                    type="number"
                    step="any"
                    value={tp}
                    onChange={(e) => handleTpChange(i, e.target.value)}
                    className={inputSmClass}
                    placeholder="0.00"
                  />
                  {tpValues.length > 1 && (
                    <button
                      onClick={() => removeTpLevel(i)}
                      className="text-[#B9CACB]/20 hover:text-[#FFB4AB] transition-colors"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              ))}
              <div className="flex items-center gap-2">
                <button
                  onClick={addTpLevel}
                  className="text-[10px] font-mono text-[#00F0FF]/60 hover:text-[#00F0FF] transition-colors"
                >
                  + Add TP level
                </button>
              </div>
              <Button variant="secondary" size="sm" loading={savingTp} onClick={handleUpdateTp}>
                <Save size={12} />
                Update TP
              </Button>
            </div>
          </div>

          {/* Close Position */}
          <div className="space-y-3">
            <h4 className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]">
              Actions
            </h4>
            <div className="space-y-3">
              <div className="p-3 rounded-sm space-y-2 bg-[#FFB4AB]/5 border border-[#FFB4AB]/10">
                <p className="text-[10px] font-mono text-[#B9CACB]/40">
                  Close this position at market price. This action cannot be undone.
                </p>
                <Button
                  variant="danger"
                  size="sm"
                  loading={closing}
                  onClick={handleClosePosition}
                  disabled={position.status !== "OPEN"}
                >
                  <X size={12} />
                  Close Position
                </Button>
              </div>
              <button
                onClick={onClose}
                className="text-xs font-mono text-[#B9CACB]/30 hover:text-[#B9CACB]/60 transition-colors"
              >
                Collapse panel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════
   Closed Positions Section (Trade History)
   ══════════════════════════════════════════════ */
function ClosedPositionsSection() {
  const [closedPositions, setClosedPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    fetchPositions({ status: "CLOSED" })
      .then((data) => { setClosedPositions(data); setLoading(false); })
      .catch(() => { setClosedPositions([]); setLoading(false); });
  }, []);

  if (loading) {
    return (
      <div>
        <div className="flex items-center gap-2 mb-3">
          <History size={14} className="text-[#B9CACB]/50" />
          <h2 className="text-sm font-semibold text-[#E5E2E1]">Trade History</h2>
        </div>
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-6 text-center">
          <div className="w-4 h-4 border-2 border-[#00F0FF] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <span className="font-mono text-xs text-[#B9CACB]/40">Loading history...</span>
        </div>
      </div>
    );
  }

  const totalPnl = closedPositions.reduce((sum, p) => sum + (p.realized_pnl ?? 0), 0);
  const totalFees = closedPositions.reduce((sum, p) => sum + (p.total_fees ?? 0), 0);
  const wins = closedPositions.filter((p) => (p.realized_pnl ?? 0) > 0).length;
  const losses = closedPositions.filter((p) => (p.realized_pnl ?? 0) <= 0).length;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <History size={14} className="text-[#B9CACB]/50" />
        <h2 className="text-sm font-semibold text-[#E5E2E1]">Trade History</h2>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-[#B9CACB]/10 text-[#B9CACB]/60">
          {closedPositions.length} trades
        </span>
        {closedPositions.length > 0 && (
          <>
            <span className={`text-[10px] font-mono font-bold tabular-nums ${totalPnl >= 0 ? "text-[#40E56C]" : "text-[#FFB4AB]"}`}>
              {formatPnl(totalPnl)}
            </span>
            <span className="text-[9px] font-mono text-[#B9CACB]/30">
              {wins}W / {losses}L | Fees: ${totalFees.toFixed(2)}
            </span>
          </>
        )}
      </div>

      {closedPositions.length === 0 ? (
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-6">
          <p className="text-sm text-center text-[#B9CACB]/30">No closed positions yet</p>
        </div>
      ) : (
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-[#2A2A2A]/20">
                  {["Symbol","Dir","Strategy","Entry","Exit","Qty","Lev","Realized P&L","Fees","Close Reason","Holding Time","Closed",""].map((h) => (
                    <th key={h} className="px-3 py-2.5 text-left text-[9px] font-mono uppercase tracking-widest text-[#B9CACB]/60 bg-[#201F1F]/50">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2A2A2A]/5">
                {closedPositions.map((pos) => {
                  const isExpanded = expandedId === pos.id;
                  const pnl = pos.realized_pnl ?? 0;
                  const holdMs = pos.opened_at && pos.closed_at
                    ? new Date(pos.closed_at).getTime() - new Date(pos.opened_at).getTime()
                    : 0;
                  const holdHrs = holdMs / 3_600_000;
                  const holdStr = holdHrs < 1 ? `${Math.round(holdHrs * 60)}m` : holdHrs < 24 ? `${holdHrs.toFixed(1)}h` : `${(holdHrs / 24).toFixed(1)}d`;

                  return (
                    <React.Fragment key={pos.id}>
                      <tr className="hover:bg-[#2A2A2A]/40 transition-colors cursor-pointer" onClick={() => setExpandedId(isExpanded ? null : pos.id)}>
                        <td className="px-3 py-2.5 font-mono font-medium text-[#E5E2E1]">{pos.symbol}</td>
                        <td className="px-3 py-2.5">
                          <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-sm ${pos.direction === "LONG" ? "text-[#40E56C] bg-[#40E56C]/10" : "text-[#FFB4AB] bg-[#FFB4AB]/10"}`}>
                            {pos.direction}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          {pos.strategy_name ? (
                            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-[#00F0FF]/8 text-[#00F0FF] border border-[#00F0FF]/15">{pos.strategy_name}</span>
                          ) : <span className="text-[#B9CACB]/20">&mdash;</span>}
                        </td>
                        <td className="px-3 py-2.5 font-mono tabular-nums text-[#E5E2E1]">{pos.entry_price != null ? formatPrice(pos.entry_price) : "--"}</td>
                        <td className="px-3 py-2.5 font-mono tabular-nums text-[#E5E2E1]">{pos.current_price != null ? formatPrice(pos.current_price) : "--"}</td>
                        <td className="px-3 py-2.5 font-mono tabular-nums text-[#B9CACB]">{pos.quantity}</td>
                        <td className="px-3 py-2.5 font-mono tabular-nums text-[#B9CACB]">{pos.leverage}x</td>
                        <td className={`px-3 py-2.5 font-mono tabular-nums font-semibold ${pnl >= 0 ? "text-[#40E56C]" : "text-[#FFB4AB]"}`}>
                          {formatPnl(pnl)}
                        </td>
                        <td className="px-3 py-2.5 font-mono tabular-nums text-[#B9CACB]/60">${(pos.total_fees ?? 0).toFixed(2)}</td>
                        <td className="px-3 py-2.5">
                          {pos.close_reason ? (
                            <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-sm ${
                              pos.close_reason.includes("TP") || pos.close_reason === "TAKE_PROFIT" ? "bg-[#40E56C]/10 text-[#40E56C]" :
                              pos.close_reason.includes("SL") || pos.close_reason === "STOP_LOSS" ? "bg-[#FFB4AB]/10 text-[#FFB4AB]" :
                              "bg-[#B9CACB]/10 text-[#B9CACB]/60"
                            }`}>{pos.close_reason}</span>
                          ) : <span className="text-[#B9CACB]/20">&mdash;</span>}
                        </td>
                        <td className="px-3 py-2.5 font-mono tabular-nums text-[#B9CACB]/60">{holdMs > 0 ? holdStr : "--"}</td>
                        <td className="px-3 py-2.5 font-mono text-xs text-[#B9CACB]/45">
                          {pos.closed_at ? new Date(pos.closed_at).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "--"}
                        </td>
                        <td className="px-3 py-2.5">
                          <ChevronDown size={12} className={`text-[#B9CACB]/30 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr>
                          <td colSpan={13} className="px-4 py-3 bg-[#181818]">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-[11px] font-mono">
                              <div className="space-y-1.5">
                                <div className="text-[9px] font-bold uppercase tracking-widest text-[#B9CACB]/50 mb-2">Position Info</div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Symbol</span><span className="text-[#E5E2E1]">{pos.symbol}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Direction</span><span className={pos.direction === "LONG" ? "text-[#40E56C]" : "text-[#FFB4AB]"}>{pos.direction}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Leverage</span><span className="text-[#00F0FF]">{pos.leverage}x</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Mode</span><span className="text-[#E5E2E1]">{pos.trading_mode}</span></div>
                                {pos.strategy_name && <div className="flex justify-between"><span className="text-[#B9CACB]">Strategy</span><span className="text-[#00F0FF]">{pos.strategy_name}</span></div>}
                              </div>
                              <div className="space-y-1.5">
                                <div className="text-[9px] font-bold uppercase tracking-widest text-[#B9CACB]/50 mb-2">Prices</div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Entry</span><span className="text-[#E5E2E1] tabular-nums">{pos.entry_price != null ? formatPrice(pos.entry_price) : "--"}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Exit</span><span className="text-[#E5E2E1] tabular-nums">{pos.current_price != null ? formatPrice(pos.current_price) : "--"}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Stop Loss</span><span className="text-[#FFB4AB] tabular-nums">{pos.stop_loss != null ? formatPrice(pos.stop_loss) : "--"}</span></div>
                                {pos.tp1_price && <div className="flex justify-between"><span className="text-[#B9CACB]">TP1</span><span className="text-[#40E56C] tabular-nums">{formatPrice(pos.tp1_price)}</span></div>}
                                {pos.tp2_price && <div className="flex justify-between"><span className="text-[#B9CACB]">TP2</span><span className="text-[#40E56C] tabular-nums">{formatPrice(pos.tp2_price)}</span></div>}
                                {pos.tp3_price && <div className="flex justify-between"><span className="text-[#B9CACB]">TP3</span><span className="text-[#40E56C] tabular-nums">{formatPrice(pos.tp3_price)}</span></div>}
                              </div>
                              <div className="space-y-1.5">
                                <div className="text-[9px] font-bold uppercase tracking-widest text-[#B9CACB]/50 mb-2">P&L Details</div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Realized P&L</span><span className={`tabular-nums font-bold ${pnl >= 0 ? "text-[#40E56C]" : "text-[#FFB4AB]"}`}>{formatPnl(pnl)}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Total Fees</span><span className="text-[#FFB4AB]/70 tabular-nums">${(pos.total_fees ?? 0).toFixed(4)}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Quantity</span><span className="text-[#E5E2E1] tabular-nums">{pos.quantity}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Remaining</span><span className="text-[#E5E2E1] tabular-nums">{pos.remaining_qty ?? 0}</span></div>
                              </div>
                              <div className="space-y-1.5">
                                <div className="text-[9px] font-bold uppercase tracking-widest text-[#B9CACB]/50 mb-2">Timeline</div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Opened</span><span className="text-[#E5E2E1]">{pos.opened_at ? new Date(pos.opened_at).toLocaleString() : "--"}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Closed</span><span className="text-[#E5E2E1]">{pos.closed_at ? new Date(pos.closed_at).toLocaleString() : "--"}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Duration</span><span className="text-[#E5E2E1]">{holdMs > 0 ? holdStr : "--"}</span></div>
                                <div className="flex justify-between"><span className="text-[#B9CACB]">Close Reason</span><span className="text-[#E5E2E1]">{pos.close_reason ?? "--"}</span></div>
                                {pos.exchange_order_id && <div className="flex justify-between"><span className="text-[#B9CACB]">Order ID</span><span className="text-[#B9CACB]/60 truncate max-w-[100px]">{pos.exchange_order_id}</span></div>}
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
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════
   Positions Page — Main
   ══════════════════════════════════════════════ */

export default function PositionsPage() {
  const [statusFilter, setStatusFilter] = useState<PositionStatus | "ALL">("ALL");
  const [modeFilter, setModeFilter] = useState<TradingMode | "ALL">("ALL");
  const [symbolSearch, setSymbolSearch] = useState("");
  const [selectedPositionId, setSelectedPositionId] = useState<string | null>(null);

  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);

  useEffect(() => {
    fetchBotStatus()
      .then(data => setBotStatus(data))
      .catch((e) => { console.error("Failed to fetch bot status:", e); setBotStatus(null); });
  }, []);

  const [exchangePositions, setExchangePositions] = useState<ExchangePosition[]>([]);
  const [exchangeLoading, setExchangeLoading] = useState(true);

  const fetchExchangeData = useCallback(() => {
    return fetchExchangePositions()
      .then(data => { setExchangePositions(data.positions); setExchangeLoading(false); return data; })
      .catch((e) => { console.error("Failed to fetch exchange positions:", e); setExchangePositions([]); setExchangeLoading(false); });
  }, []);

  useEffect(() => {
    fetchExchangeData();
    const interval = setInterval(fetchExchangeData, 15_000);
    return () => clearInterval(interval);
  }, [fetchExchangeData]);

  const [pulsedIds, setPulsedIds] = useState<Set<string>>(new Set());
  const prevPositionsRef = useRef<Position[] | null>(null);
  const [livePrices, setLivePrices] = useState<Record<string, number>>({});

  const {
    data: positions,
    loading,
    error,
    refetch,
  } = usePolling(() => fetchPositions(), 30_000, []);

  useEffect(() => {
    if (!positions || !prevPositionsRef.current) {
      prevPositionsRef.current = positions;
      return;
    }
    const changedIds = new Set<string>();
    const prevMap = new Map(prevPositionsRef.current.map((p) => [p.id, p]));
    for (const pos of positions) {
      const prev = prevMap.get(pos.id);
      if (prev && prev.unrealized_pnl !== pos.unrealized_pnl) changedIds.add(pos.id);
    }
    if (changedIds.size > 0) {
      setPulsedIds(changedIds);
      const timer = setTimeout(() => setPulsedIds(new Set()), 700);
      prevPositionsRef.current = positions;
      return () => clearTimeout(timer);
    }
    prevPositionsRef.current = positions;
  }, [positions]);

  useWebSocket("price_update", useCallback((data: PriceUpdate) => {
    setLivePrices((prev) => ({ ...prev, [data.symbol]: data.price }));
  }, []));

  useWebSocket("position_update", useCallback(() => {
    refetch();
  }, [refetch]));

  const positionsWithLivePrices = useMemo(() => {
    if (!positions) return null;
    if (Object.keys(livePrices).length === 0) return positions;
    return positions.map((p) => {
      const livePrice = livePrices[p.symbol];
      if (!livePrice || p.status !== "OPEN") return p;
      const entryPrice = p.entry_price;
      const quantity = p.quantity;
      if (entryPrice == null || quantity == null) return p;
      const dirMultiplier = p.direction === "LONG" ? 1 : -1;
      const unrealizedPnl = (livePrice - entryPrice) * quantity * dirMultiplier;
      return { ...p, current_price: livePrice, unrealized_pnl: unrealizedPnl };
    });
  }, [positions, livePrices]);

  const filteredPositions = useMemo(() => {
    if (!positionsWithLivePrices) return [];
    return positionsWithLivePrices.filter((p) => {
      if (statusFilter !== "ALL" && p.status !== statusFilter) return false;
      if (modeFilter !== "ALL" && p.trading_mode !== modeFilter) return false;
      if (symbolSearch && !p.symbol.toLowerCase().includes(symbolSearch.toLowerCase())) return false;
      return true;
    });
  }, [positionsWithLivePrices, statusFilter, modeFilter, symbolSearch]);

  const stats = useMemo(() => {
    const ep = exchangePositions;
    const totalUnrealizedPnl = ep.reduce((sum, p) => sum + p.unrealized_pnl, 0);
    const totalMargin = ep.reduce((sum, p) => sum + p.margin, 0);
    const openCount = ep.length;
    let bestPnl = 0;
    let worstPnl = 0;
    if (ep.length > 0) {
      bestPnl = Math.max(...ep.map((p) => p.unrealized_pnl));
      worstPnl = Math.min(...ep.map((p) => p.unrealized_pnl));
    }
    const pnlPercent = totalMargin > 0 ? (totalUnrealizedPnl / totalMargin) * 100 : 0;
    return { totalUnrealizedPnl, pnlPercent, openCount, totalMargin, bestPnl, worstPnl };
  }, [exchangePositions]);

  const mergedPositions = useMemo(() => {
    const botOpen = (positionsWithLivePrices ?? []).filter((p) => p.status === "OPEN");
    return exchangePositions.map((ep) => {
      const normalizedSymbol = ep.symbol.replace(":USDT", "").replace("/", "/");
      const botMatch = botOpen.find((bp) => {
        const bpSymbol = bp.symbol.replace("/", "/");
        return (normalizedSymbol.includes(bpSymbol) || bpSymbol.includes(normalizedSymbol.split(":")[0]))
          && bp.direction === ep.direction;
      });
      return { ...ep, bot: botMatch ?? null };
    });
  }, [exchangePositions, positionsWithLivePrices]);

  const filteredMerged = useMemo(() => {
    if (!symbolSearch) return mergedPositions;
    const q = symbolSearch.toLowerCase();
    return mergedPositions.filter((p) => p.symbol.toLowerCase().includes(q));
  }, [mergedPositions, symbolSearch]);

  const selectedPosition = useMemo(() => {
    if (!selectedPositionId) return null;
    const merged = filteredMerged.find((m) => m.bot?.id === selectedPositionId);
    return merged?.bot ?? null;
  }, [filteredMerged, selectedPositionId]);

  const handleRowClick = useCallback((symbol: string, botId: string | null) => {
    if (botId) setSelectedPositionId((prev) => (prev === botId ? null : botId));
  }, []);

  if (loading && !positions) {
    return (
      <div className="flex items-center justify-center h-96">
  
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-[#00F0FF] border-t-transparent rounded-full animate-spin" />
          <span className="font-mono text-sm text-[#B9CACB]/40">Loading positions...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
  
        <div className="text-center space-y-3">
          <div className="w-12 h-12 rounded-sm flex items-center justify-center mx-auto bg-[#FFB4AB]/10">
            <Shield size={24} className="text-[#FFB4AB]" />
          </div>
          <p className="font-mono text-sm text-[#FFB4AB]">Failed to load positions</p>
          <p className="text-xs text-[#B9CACB]/30">{error}</p>
          <button
            onClick={refetch}
            className="mt-2 px-4 py-2 rounded-sm text-xs font-mono bg-[#00F0FF]/10 text-[#00F0FF] border border-[#00F0FF]/20 hover:bg-[#00F0FF]/20 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const bestWorstLabel =
    stats.openCount > 0
      ? `${formatPnl(stats.bestPnl)} / ${formatPnl(stats.worstPnl)}`
      : "\u2014";

  return (
    <div className="space-y-6">


      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-sm flex items-center justify-center bg-[#00F0FF]/10">
            <Wallet size={18} className="text-[#00F0FF]" />
          </div>
          <div>
            <h1 className="text-xl font-black text-[#E5E2E1]">Position Manager</h1>
            <p className="text-xs text-[#B9CACB]/50 mt-0.5">
              Manage open positions, stop losses, and take profits
            </p>
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 stagger-children">
        {[
          {
            label: "Total Unrealized P&L",
            value: formatPnl(stats.totalUnrealizedPnl),
            accent: stats.totalUnrealizedPnl >= 0 ? "#40E56C" : "#FFB4AB",
            icon: stats.totalUnrealizedPnl >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />,
            change: stats.openCount > 0 ? stats.pnlPercent : undefined,
          },
          { label: "Open Positions", value: String(stats.openCount), accent: "#00F0FF", icon: <Wallet size={16} /> },
          { label: "Total Margin", value: `$${stats.totalMargin.toFixed(2)}`, accent: "#B9CACB", icon: <DollarSign size={16} /> },
          { label: "Best / Worst", value: bestWorstLabel, accent: "#849495", icon: <AlertTriangle size={16} /> },
        ].map((s, i) => (
          <div
            key={i}
            className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4 border-l-2"
            style={{ borderLeftColor: s.accent }}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]">{s.label}</span>
              <span style={{ color: s.accent, opacity: 0.6 }}>{s.icon}</span>
            </div>
            <span className="font-mono text-xl font-black text-[#E5E2E1] tabular-nums">{s.value}</span>
            {s.change !== undefined && (
              <div className="mt-1">
                <span className={`inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 font-mono text-[10px] tabular-nums ${s.change >= 0 ? "text-[#40E56C] bg-[#40E56C]/10" : "text-[#FFB4AB] bg-[#FFB4AB]/10"}`}>
                  {s.change >= 0 ? "\u25B2" : "\u25BC"} {s.change >= 0 ? "+" : ""}{s.change.toFixed(2)}%
                </span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Live Positions Table */}
      <div>
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <h2 className="text-sm font-semibold text-[#E5E2E1]">Live Positions</h2>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-[#40E56C]/10 text-[#40E56C] border border-[#40E56C]/20">
            BINANCE LIVE
          </span>
          <span className="text-[9px] font-mono text-[#B9CACB]/25">auto-refresh 15s</span>
          <div className="flex-1" />
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#B9CACB]/30" />
            <input
              type="text"
              value={symbolSearch}
              onChange={(e) => setSymbolSearch(e.target.value)}
              placeholder="Search symbol..."
              className="pl-8 pr-3 py-1.5 rounded-sm text-xs font-mono bg-[#2A2A2A] text-[#E5E2E1] border-0 focus:outline-none focus:ring-1 focus:ring-[#00F0FF] placeholder:text-[#B9CACB]/20"
            />
          </div>
        </div>

        {exchangeLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-4 h-4 border-2 border-[#00F0FF] border-t-transparent rounded-full animate-spin mr-2" />
            <span className="font-mono text-xs text-[#B9CACB]/40">Loading positions from Binance...</span>
          </div>
        ) : filteredMerged.length === 0 ? (
          <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-6">
            <p className="text-sm text-center text-[#B9CACB]/30">No open positions on Binance</p>
          </div>
        ) : (
          <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-[#2A2A2A]/20">
                    {["Symbol", "Direction", "Strategy", "Entry", "Mark Price", "Qty", "Leverage", "Unrealized P&L", "Margin", "Liq. Price", "Stop Loss", "Take Profits"].map((h) => (
                      <th key={h} className="px-3 py-3 text-left text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/60 bg-[#201F1F]/50">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#2A2A2A]/5">
                  {filteredMerged.map((mp, idx) => (
                    <tr
                      key={`${mp.symbol}-${mp.direction}-${idx}`}
                      className="hover:bg-[#2A2A2A]/40 transition-colors duration-150 cursor-pointer"
                      onClick={() => handleRowClick(mp.symbol, mp.bot?.id ?? null)}
                    >
                      <td className="px-3 py-3 font-semibold text-[#E5E2E1]">
                        <div className="flex items-center gap-1.5">
                          {mp.symbol.replace(":USDT", "")}
                          {mp.bot && (
                            <span className="text-[8px] font-mono px-1 py-0.5 rounded-sm bg-[#00F0FF]/10 text-[#00F0FF]">BOT</span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-sm ${mp.direction === "LONG" ? "text-[#40E56C] bg-[#40E56C]/10" : "text-[#FFB4AB] bg-[#FFB4AB]/10"}`}>
                          {mp.direction}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        {mp.bot?.strategy_name ? (
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-[#00F0FF]/8 text-[#00F0FF] border border-[#00F0FF]/15">
                            {mp.bot.strategy_name}
                          </span>
                        ) : (
                          <span className="text-[#B9CACB]/15">&mdash;</span>
                        )}
                      </td>
                      <td className="px-3 py-3 font-mono tabular-nums text-[#E5E2E1]">{formatPrice(mp.entry_price)}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-[#E5E2E1]">{formatPrice(mp.current_price)}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-[#B9CACB]">{mp.quantity}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-[#B9CACB]">{mp.leverage}x</td>
                      <td className={`px-3 py-3 font-mono tabular-nums font-semibold ${mp.unrealized_pnl >= 0 ? "text-[#40E56C]" : "text-[#FFB4AB]"}`}>
                        {formatPnl(mp.unrealized_pnl)}
                      </td>
                      <td className="px-3 py-3 font-mono tabular-nums text-[#B9CACB]">${mp.margin.toFixed(2)}</td>
                      <td className={`px-3 py-3 font-mono tabular-nums ${mp.liquidation_price > 0 ? "text-[#FFB4AB]/70" : "text-[#B9CACB]/20"}`}>
                        {mp.liquidation_price > 0 ? formatPrice(mp.liquidation_price) : "\u2014"}
                      </td>
                      <td className={`px-3 py-3 font-mono tabular-nums ${mp.bot?.stop_loss ? "text-[#FFB4AB]" : "text-[#B9CACB]/15"}`}>
                        {mp.bot?.stop_loss ? formatPrice(mp.bot.stop_loss) : "\u2014"}
                      </td>
                      <td className="px-3 py-3">
                        {mp.bot ? (
                          <div className="flex gap-1">
                            {[mp.bot.tp1_price, mp.bot.tp2_price, mp.bot.tp3_price].map((tp, i) =>
                              tp ? (
                                <span key={i} className="text-[9px] font-mono px-1 py-0.5 rounded-sm bg-[#40E56C]/8 text-[#40E56C] border border-[#40E56C]/15">
                                  TP{i + 1}
                                </span>
                              ) : null
                            )}
                          </div>
                        ) : (
                          <span className="text-[#B9CACB]/15">\u2014</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* ===== Trade History (Closed Positions) ===== */}
      <ClosedPositionsSection />

      {/* Detail Panel */}
      {selectedPosition && (
        <div className="relative">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/30">
              Position Detail
            </span>
            <span className="font-mono text-xs text-[#00F0FF]">
              {selectedPosition.symbol}
            </span>
            <DirectionBadge direction={selectedPosition.direction} size="sm">
              {selectedPosition.direction} {selectedPosition.leverage}x
            </DirectionBadge>
            <span className={`font-mono text-xs tabular-nums font-semibold ${selectedPosition.unrealized_pnl >= 0 ? "text-[#40E56C]" : "text-[#FFB4AB]"}`}>
              {formatPnl(selectedPosition.unrealized_pnl)}
            </span>
          </div>
          <PositionDetailPanel
            position={selectedPosition}
            onClose={() => setSelectedPositionId(null)}
            onUpdated={refetch}
          />
        </div>
      )}
    </div>
  );
}
