"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Wallet,
  ArrowRightLeft,
  ArrowRight,
  Coins,
  DollarSign,
  Lock,
  Package,
  ChevronDown,
  Check,
  AlertTriangle,
  Clock,
  Info,
  Landmark,
  History,
} from "lucide-react";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Button } from "@/components/ui/Button";
import { usePolling, useApi } from "@/hooks/useApi";
import {
  fetchWalletBalances,
  transferFunds,
  fetchTransferHistory,
  type WalletAsset,
  type WalletBalancesResponse,
  type TransferResponse,
  type TransferHistoryEntry,
  type TransferHistoryResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

/* ═══════════════════════════════════════════════════════
   Constants
   ═══════════════════════════════════════════════════════ */

const WALLET_OPTIONS = ["spot", "future", "margin", "funding"] as const;
type WalletType = (typeof WALLET_OPTIONS)[number];

const WALLET_LABELS: Record<WalletType, string> = {
  spot: "Spot Wallet",
  future: "Futures (USDM)",
  margin: "Margin",
  funding: "Funding",
};

const STABLECOINS = new Set(["USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD"]);

const INPUT_CLASS =
  "w-full bg-[#2A2A2A] border-0 rounded-sm px-3 py-2 text-sm font-mono text-[#E5E2E1] focus:outline-none focus:ring-1 focus:ring-[#00F0FF] placeholder:text-[#B9CACB]/30";

const SELECT_CLASS =
  "w-full bg-[#2A2A2A] border-0 rounded-sm px-3 py-2 text-sm font-mono text-[#E5E2E1] focus:outline-none focus:ring-1 focus:ring-[#00F0FF] appearance-none cursor-pointer";

/* ═══════════════════════════════════════════════════════
   Number formatting helpers
   ═══════════════════════════════════════════════════════ */

function fmtUsd(value: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtCrypto(value: number, currency?: string): string {
  if (value === 0) return "0.00";
  const isStable = currency ? STABLECOINS.has(currency.toUpperCase()) : false;
  if (isStable) {
    return value.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  // Crypto: 8 decimal places
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 8,
    maximumFractionDigits: 8,
  });
}

function fmtWalletBalance(
  asset: WalletAsset,
  walletKey: string,
): string {
  const wallet = asset.wallets[walletKey];
  if (!wallet || wallet.total === 0) return "\u2014";
  const formatted = fmtCrypto(wallet.total, asset.currency);
  return STABLECOINS.has(asset.currency.toUpperCase()) ? `$${formatted}` : formatted;
}

/* ═══════════════════════════════════════════════════════
   Select Wrapper with chevron icon
   ═══════════════════════════════════════════════════════ */

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div>
      <label className="mb-1 block font-mono text-[9px] font-bold uppercase tracking-widest text-[#B9CACB]/60">
        {label}
      </label>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={SELECT_CLASS}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown
          size={14}
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#B9CACB]/30"
        />
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Transfer Status Badge
   ═══════════════════════════════════════════════════════ */

function StatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  const color =
    s === "success" || s === "completed"
      ? "text-[#40E56C] bg-[#40E56C]/10 border-[#40E56C]/25"
      : s === "pending" || s === "processing"
        ? "text-[#FFB3B6] bg-[#FFB3B6]/10 border-[#FFB3B6]/25"
        : s === "failed" || s === "error"
          ? "text-[#FFB4AB] bg-[#FFB4AB]/10 border-[#FFB4AB]/25"
          : "text-[#E5E2E1]/60 bg-[#E5E2E1]/5 border-[#E5E2E1]/10";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
        color
      )}
    >
      {status}
    </span>
  );
}

/* ═══════════════════════════════════════════════════════
   Main Wallet Page
   ═══════════════════════════════════════════════════════ */

export default function WalletPage() {
  // ── Wallet Balances (polled every 15s) ──
  const {
    data: walletData,
    loading: walletLoading,
    error: walletError,
    refetch: refetchWallet,
  } = usePolling<WalletBalancesResponse>(fetchWalletBalances, 15_000, []);

  // ── Transfer History (fetched on mount) ──
  const {
    data: historyData,
    loading: historyLoading,
    error: historyError,
    refetch: refetchHistory,
  } = useApi<TransferHistoryResponse>(() => fetchTransferHistory(50), []);

  // ── Transfer Form State ──
  const [fromWallet, setFromWallet] = useState<WalletType>("spot");
  const [toWallet, setToWallet] = useState<WalletType>("future");
  const [currency, setCurrency] = useState<string>("");
  const [amount, setAmount] = useState<string>("");
  const [transferring, setTransferring] = useState(false);
  const [transferResult, setTransferResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  // ── Derived data ──
  const assets = walletData?.assets ?? [];
  const totalUsd = walletData?.total_usd_value ?? 0;

  const freeBalance = useMemo(() => {
    return assets
      .filter((a) => STABLECOINS.has(a.currency.toUpperCase()))
      .reduce((sum, a) => sum + a.free, 0);
  }, [assets]);

  const usedBalance = useMemo(() => {
    return assets.reduce((sum, a) => sum + a.used, 0);
  }, [assets]);

  const nonZeroAssetCount = useMemo(() => {
    return assets.filter((a) => a.total > 0).length;
  }, [assets]);

  // ── Currency options from assets ──
  const currencyOptions = useMemo(() => {
    const opts = assets
      .filter((a) => a.total > 0)
      .map((a) => ({ value: a.currency, label: a.currency }));
    return opts.length > 0 ? opts : [{ value: "", label: "No assets" }];
  }, [assets]);

  // Auto-select first currency when assets load
  useEffect(() => {
    if (currency === "" && currencyOptions.length > 0 && currencyOptions[0].value !== "") {
      setCurrency(currencyOptions[0].value);
    }
  }, [currencyOptions, currency]);

  // ── Max amount for selected currency in selected from_wallet ──
  const maxAmount = useMemo(() => {
    if (!currency) return 0;
    const asset = assets.find((a) => a.currency === currency);
    if (!asset) return 0;
    const wallet = asset.wallets[fromWallet];
    return wallet?.free ?? 0;
  }, [assets, currency, fromWallet]);

  // ── Transfer handler ──
  const handleTransfer = useCallback(async () => {
    if (!currency || !amount || parseFloat(amount) <= 0) {
      setTransferResult({ success: false, message: "Please enter a valid amount" });
      return;
    }

    if (fromWallet === toWallet) {
      setTransferResult({ success: false, message: "From and To wallets must be different" });
      return;
    }

    const numAmount = parseFloat(amount);
    if (numAmount > maxAmount) {
      setTransferResult({
        success: false,
        message: `Insufficient balance. Max: ${fmtCrypto(maxAmount)} ${currency}`,
      });
      return;
    }

    setTransferring(true);
    setTransferResult(null);

    try {
      const result = await transferFunds({
        from_wallet: fromWallet,
        to_wallet: toWallet,
        currency,
        amount: numAmount,
      });
      setTransferResult({
        success: true,
        message: `Transferred ${fmtCrypto(numAmount)} ${currency} from ${WALLET_LABELS[fromWallet]} to ${WALLET_LABELS[toWallet as WalletType]}`,
      });
      setAmount("");
      // Refresh both balances and history
      refetchWallet();
      refetchHistory();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Transfer failed";
      setTransferResult({ success: false, message });
    } finally {
      setTransferring(false);
    }
  }, [currency, amount, fromWallet, toWallet, maxAmount, refetchWallet, refetchHistory]);

  // ── Asset Table Columns ──
  const assetColumns: Column<WalletAsset & Record<string, unknown>>[] = useMemo(
    () => [
      {
        key: "currency",
        label: "Asset",
        render: (row) => (
          <span className="font-mono text-xs font-bold text-[#E5E2E1]">
            {row.currency}
          </span>
        ),
      },
      {
        key: "total",
        label: "Total",
        align: "right" as const,
        render: (row) => {
          const isStable = STABLECOINS.has(row.currency.toUpperCase());
          return (
            <span className="font-mono text-xs tabular-nums text-[#E5E2E1]">
              {isStable ? "$" : ""}{fmtCrypto(row.total, row.currency)}
            </span>
          );
        },
      },
      {
        key: "free",
        label: "Available",
        align: "right" as const,
        render: (row) => {
          const isStable = STABLECOINS.has(row.currency.toUpperCase());
          return (
            <span className="font-mono text-xs tabular-nums text-[#B9CACB]">
              {isStable ? "$" : ""}{fmtCrypto(row.free, row.currency)}
            </span>
          );
        },
      },
      {
        key: "used",
        label: "In Order",
        align: "right" as const,
        render: (row) => {
          const isStable = STABLECOINS.has(row.currency.toUpperCase());
          return (
            <span className="font-mono text-xs tabular-nums text-[#B9CACB]">
              {row.used > 0 ? `${isStable ? "$" : ""}${fmtCrypto(row.used, row.currency)}` : "\u2014"}
            </span>
          );
        },
      },
      {
        key: "futures",
        label: "Futures",
        align: "right" as const,
        render: (row) => (
          <span className="font-mono text-xs tabular-nums text-[#B9CACB]/60">
            {fmtWalletBalance(row, "future")}
          </span>
        ),
      },
      {
        key: "spot",
        label: "Spot",
        align: "right" as const,
        render: (row) => (
          <span className="font-mono text-xs tabular-nums text-[#B9CACB]/60">
            {fmtWalletBalance(row, "spot")}
          </span>
        ),
      },
      {
        key: "funding",
        label: "Funding",
        align: "right" as const,
        render: (row) => (
          <span className="font-mono text-xs tabular-nums text-[#B9CACB]/60">
            {fmtWalletBalance(row, "funding")}
          </span>
        ),
      },
    ],
    []
  );

  // ── Transfer History: rendered as compact cards in the sidebar ──
  const historyEntries = historyData?.transfers ?? [];

  // ── Loading skeleton ──
  if (walletLoading && !walletData) {
    return (
      <div className="space-y-6 p-4 md:p-6 max-w-[1600px] mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm h-[140px] animate-pulse" />
          <div className="md:col-span-2 grid grid-cols-2 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm h-[80px] animate-pulse"
              />
            ))}
          </div>
        </div>
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm h-[300px] animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 md:p-6 max-w-[1600px] mx-auto pb-20 md:pb-6">
      {/* ── Error Banner ── */}
      {walletError && (
        <div className="flex items-center gap-2 rounded-sm border border-[#FFB4AB]/25 bg-[#FFB4AB]/10 px-4 py-3">
          <AlertTriangle size={16} className="text-[#FFB4AB]" />
          <span className="text-sm text-[#FFB4AB]">{walletError}</span>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════
         Header Stats — Reference style: big value left + 4 metric cards right
         ═══════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Total Portfolio Value — Hero card */}
        <div className="bg-[#1C1B1B] p-6 border-l-2 border-[#00F0FF] rounded-sm flex flex-col justify-center">
          <p className="text-[10px] font-bold text-[#B9CACB] uppercase tracking-tighter mb-2">
            Total Estimated Value
          </p>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-4xl font-black text-[#E5E2E1] tabular-nums">
              {fmtUsd(totalUsd)}
            </span>
            <span className="text-xs font-mono text-[#B9CACB]">USDT</span>
          </div>
        </div>

        {/* 4 Metric sub-cards */}
        <div className="md:col-span-2 grid grid-cols-2 gap-4">
          <div className="bg-[#1C1B1B] p-4 border border-[#3B494B]/10 rounded-sm">
            <div className="flex items-center justify-between mb-1">
              <p className="text-[10px] font-bold text-[#B9CACB] uppercase tracking-tighter">Available Margin</p>
              <Coins size={14} className="text-[#00F0FF]/60" />
            </div>
            <div className="font-mono text-xl font-black text-[#E5E2E1] tabular-nums">
              {fmtUsd(freeBalance)}{" "}
              <span className="text-[10px] text-[#B9CACB] font-normal">USDT</span>
            </div>
          </div>
          <div className="bg-[#1C1B1B] p-4 border border-[#3B494B]/10 rounded-sm">
            <div className="flex items-center justify-between mb-1">
              <p className="text-[10px] font-bold text-[#B9CACB] uppercase tracking-tighter">Locked in Orders</p>
              <Lock size={14} className="text-[#00F0FF]/60" />
            </div>
            <div className="font-mono text-xl font-black text-[#E5E2E1] tabular-nums">
              {fmtUsd(usedBalance)}{" "}
              <span className="text-[10px] text-[#B9CACB] font-normal">USDT</span>
            </div>
          </div>
          <div className="bg-[#1C1B1B] p-4 border border-[#3B494B]/10 rounded-sm">
            <div className="flex items-center justify-between mb-1">
              <p className="text-[10px] font-bold text-[#B9CACB] uppercase tracking-tighter">Assets Held</p>
              <Package size={14} className="text-[#00F0FF]/60" />
            </div>
            <div className="font-mono text-xl font-black text-[#E5E2E1] tabular-nums">
              {nonZeroAssetCount}{" "}
              <span className="text-[10px] text-[#B9CACB] font-normal">tokens</span>
            </div>
          </div>
          <div className="bg-[#1C1B1B] p-4 border border-[#3B494B]/10 rounded-sm">
            <div className="flex items-center justify-between mb-1">
              <p className="text-[10px] font-bold text-[#B9CACB] uppercase tracking-tighter">Portfolio</p>
              <DollarSign size={14} className="text-[#00F0FF]/60" />
            </div>
            <div className="font-mono text-xl font-black text-[#E5E2E1] tabular-nums">
              ${fmtUsd(totalUsd)}
            </div>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════
         Main Content: lg:grid-cols-12 (Asset Table + Sidebar)
         ═══════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* ── Left: Asset Table (col-span-8) ── */}
        <div className="lg:col-span-8 space-y-6">
          <section className="bg-[#1C1B1B] rounded-sm border border-[#3B494B]/10">
            <div className="p-4 border-b border-[#2A2A2A]/20 flex justify-between items-center">
              <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase flex items-center gap-2">
                <Landmark size={16} />
                Asset Balances
              </h3>
              <span className="text-[10px] font-mono uppercase tracking-wider text-[#B9CACB]/40">
                {assets.filter((a) => a.total > 0).length} asset{assets.filter((a) => a.total > 0).length !== 1 ? "s" : ""}
              </span>
            </div>
            <DataTable<WalletAsset & Record<string, unknown>>
              columns={assetColumns as Column<WalletAsset & Record<string, unknown>>[]}
              data={assets.filter((a) => a.total > 0) as (WalletAsset & Record<string, unknown>)[]}
              emptyMessage="No assets found"
              className="border-0 rounded-none"
            />
          </section>
        </div>

        {/* ── Right: Transfer Form + History (col-span-4) ── */}
        <div className="lg:col-span-4 space-y-6">
          {/* Internal Transfer Section */}
          <section className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10">
            <h3 className="font-mono text-xs font-black tracking-widest text-[#00F0FF] uppercase mb-4 flex items-center gap-2">
              <ArrowRight size={16} />
              Internal Transfer
            </h3>

            {/* Demo account warning banner */}
            <div className="flex items-center gap-2 px-3 py-2 rounded-sm mb-4 bg-[#FFB3B6]/8 border border-[#FFB3B6]/20">
              <Info size={14} className="text-[#FFB3B6] shrink-0" />
              <span className="text-[10px] font-mono text-[#FFB3B6]">
                Demo account — wallet transfers require a live Binance account with real funds
              </span>
            </div>

            <div className="space-y-4">
              {/* From / To wallets in a row */}
              <div className="flex items-center gap-2">
                <div className="flex-1">
                  <SelectField
                    label="From"
                    value={fromWallet}
                    onChange={(v) => setFromWallet(v as WalletType)}
                    options={WALLET_OPTIONS.map((w) => ({
                      value: w,
                      label: WALLET_LABELS[w],
                    }))}
                  />
                </div>
                <div className="pt-4 text-[#B9CACB]">
                  <ArrowRight size={16} />
                </div>
                <div className="flex-1">
                  <SelectField
                    label="To"
                    value={toWallet}
                    onChange={(v) => setToWallet(v as WalletType)}
                    options={WALLET_OPTIONS.map((w) => ({
                      value: w,
                      label: WALLET_LABELS[w],
                    }))}
                  />
                </div>
              </div>

              {/* Currency select */}
              <SelectField
                label="Coin"
                value={currency}
                onChange={setCurrency}
                options={currencyOptions}
              />

              {/* Amount input */}
              <div>
                <label className="mb-1 flex items-center justify-between font-mono text-[9px] font-bold uppercase tracking-widest text-[#B9CACB]/60">
                  <span>Amount</span>
                  <button
                    type="button"
                    onClick={() => setAmount(String(maxAmount))}
                    className="text-[#00F0FF] cursor-pointer hover:underline"
                  >
                    Max: {fmtCrypto(maxAmount, currency)}
                  </button>
                </label>
                <div className="flex items-center bg-[#2A2A2A] px-3 py-2 rounded-sm focus-within:ring-1 focus-within:ring-[#00F0FF]">
                  <input
                    type="number"
                    step="any"
                    min="0"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="0.00"
                    className="bg-transparent border-none focus:ring-0 text-[#E5E2E1] font-mono text-sm w-full outline-none placeholder:text-[#B9CACB]/30"
                  />
                  <span className="text-[10px] font-mono text-[#B9CACB] ml-2 shrink-0">
                    {currency || "---"}
                  </span>
                </div>
              </div>

              {/* Same wallet warning */}
              {fromWallet === toWallet && (
                <p className="text-center text-[10px] font-mono text-[#FFB3B6]">
                  Source and destination must be different
                </p>
              )}

              {/* Transfer button */}
              <Button
                variant="primary"
                size="md"
                loading={transferring}
                disabled={!currency || !amount || fromWallet === toWallet}
                onClick={handleTransfer}
                className="w-full font-mono text-[10px] font-bold tracking-widest uppercase"
              >
                {transferring ? "Transferring..." : "Confirm Transfer"}
              </Button>

              {/* Transfer result feedback */}
              {transferResult && (
                <div
                  className={cn(
                    "flex items-start gap-2 rounded-sm border px-3 py-2.5 text-xs w-full",
                    transferResult.success
                      ? "border-[#40E56C]/25 bg-[#40E56C]/10 text-[#40E56C]"
                      : "border-[#FFB4AB]/25 bg-[#FFB4AB]/10 text-[#FFB4AB]"
                  )}
                >
                  {transferResult.success ? (
                    <Check size={14} className="mt-0.5 shrink-0" />
                  ) : (
                    <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                  )}
                  <span className="text-[11px] leading-relaxed font-mono">{transferResult.message}</span>
                </div>
              )}
            </div>
          </section>

          {/* Recent Transfers Section */}
          <section className="bg-[#1C1B1B] p-4 rounded-sm border border-[#3B494B]/10">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-mono text-[10px] font-black tracking-widest text-[#B9CACB] uppercase flex items-center gap-2">
                <History size={12} />
                Recent Transfers
              </h3>
              <div className="flex items-center gap-2">
                {historyLoading && (
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[#B9CACB]/30">
                    Loading...
                  </span>
                )}
                <Clock size={12} className="text-[#B9CACB]/30" />
              </div>
            </div>

            {historyError && (
              <div className="mb-3 flex items-center gap-2 rounded-sm border border-[#FFB3B6]/25 bg-[#FFB3B6]/10 px-3 py-2">
                <AlertTriangle size={12} className="text-[#FFB3B6]" />
                <span className="text-[10px] font-mono text-[#FFB3B6]">{historyError}</span>
              </div>
            )}

            {historyEntries.length === 0 ? (
              <p className="text-center text-[10px] font-mono text-[#B9CACB]/40 py-6">
                No transfers yet
              </p>
            ) : (
              <div className="space-y-2">
                {historyEntries.slice(0, 10).map((tx, i) => {
                  const fromLabel = WALLET_LABELS[tx.from as WalletType] ?? tx.from;
                  const toLabel = WALLET_LABELS[tx.to as WalletType] ?? tx.to;
                  const isStable = STABLECOINS.has(tx.currency.toUpperCase());
                  const timeStr = tx.timestamp
                    ? (() => {
                        const d = new Date(tx.timestamp);
                        return `${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })} ${d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })}`;
                      })()
                    : "\u2014";

                  return (
                    <div
                      key={tx.id ?? i}
                      className="flex justify-between items-center bg-[#2A2A2A] p-2.5 rounded-sm"
                    >
                      <div>
                        <div className="font-mono text-[10px] font-bold text-[#E5E2E1]">
                          {fromLabel} &rarr; {toLabel}
                        </div>
                        <div className="font-mono text-[9px] text-[#B9CACB]/60">
                          {timeStr}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-[10px] font-bold text-[#00F0FF]">
                          {isStable ? "$" : ""}{fmtCrypto(tx.amount, tx.currency)} {tx.currency}
                        </div>
                        <div className="font-mono text-[9px]">
                          <StatusBadge status={tx.status} />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
