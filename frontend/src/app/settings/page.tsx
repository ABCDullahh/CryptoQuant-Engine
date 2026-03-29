"use client";

import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useApi } from "@/hooks/useApi";
import {
  fetchSettings,
  updateExchangeKeys,
  updateRiskParams,
  updateNotifications,
  fetchSignalPolicy,
  updateSignalPolicy,
  applySignalPolicyPreset,
  fetchDCAConfig,
  updateDCAConfig,
  type Settings,
  type RiskSettings,
  type NotificationSettings,
  type SignalPolicy,
  type DCAConfig,
} from "@/lib/api";
import {
  Settings as SettingsIcon,
  Shield,
  Zap,
  Bell,
  Database,
  Key,
  CheckCircle2,
  Layers,
} from "lucide-react";

/* ═══════════════════════════════════════════════════════
   Constants
   ═══════════════════════════════════════════════════════ */

const INPUT_CLASS =
  "w-full bg-[#2A2A2A] border border-[#3B494B]/10 rounded-sm px-3 py-2 text-sm font-mono text-[#E5E2E1] focus:outline-none focus:border-[#00F0FF] focus:ring-1 focus:ring-[#00F0FF]/30 placeholder:text-[#B9CACB]/30";

const STRATEGY_KEYS = [
  "momentum",
  "mean_reversion",
  "smart_money",
  "volume_analysis",
  "funding_arb",
  "ob_zones",
] as const;

const STRATEGY_LABELS: Record<string, string> = {
  momentum: "Momentum",
  mean_reversion: "Mean Reversion",
  smart_money: "Smart Money",
  volume_analysis: "Volume Analysis",
  funding_arb: "Funding Arb",
  ob_zones: "Order Block Zones",
};

const GRADES = ["A", "B", "C", "D"] as const;

const ACTIONS = ["auto", "alert", "queue", "skip"] as const;
type PolicyAction = (typeof ACTIONS)[number];

const ACTION_STYLES: Record<PolicyAction, { bg: string; border: string; text: string; label: string }> = {
  auto:  { bg: "bg-[#40E56C]/12", border: "border-[#40E56C]/30", text: "text-[#40E56C]", label: "Auto" },
  alert: { bg: "bg-[#FFB3B6]/12", border: "border-[#FFB3B6]/30", text: "text-[#FFB3B6]", label: "Alert" },
  queue: { bg: "bg-[#3498DB]/12", border: "border-[#3498DB]/30", text: "text-[#3498DB]", label: "Queue" },
  skip:  { bg: "bg-[#6B6B6B]/12", border: "border-[#6B6B6B]/30", text: "text-[#6B6B6B]", label: "Skip" },
};

function getDefaultMatrix(): Record<string, Record<string, string>> {
  const m: Record<string, Record<string, string>> = {};
  for (const s of STRATEGY_KEYS) {
    m[s] = { A: "auto", B: "alert", C: "queue", D: "skip" };
  }
  return m;
}

function cycleAction(current: string): string {
  const idx = ACTIONS.indexOf(current as PolicyAction);
  return ACTIONS[(idx + 1) % ACTIONS.length];
}

/* ═══════════════════════════════════════════════════════
   Toggle Switch Component
   ═══════════════════════════════════════════════════════ */

function Toggle({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (val: boolean) => void;
  label: string;
  description?: string;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div>
        <p className="text-sm text-[#E5E2E1]/85">{label}</p>
        {description && (
          <p className="text-xs text-[#B9CACB]/50 mt-0.5">
            {description}
          </p>
        )}
      </div>
      <label className="relative inline-flex items-center cursor-pointer">
        <input
          type="checkbox"
          className="sr-only peer"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        <div className="w-9 h-5 bg-[#353534] rounded-sm peer peer-checked:bg-[#00F0FF] transition-colors after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-[#E5E2E1] after:rounded-sm after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4" />
      </label>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Labeled Input Component
   ═══════════════════════════════════════════════════════ */

function LabeledInput({
  label,
  description,
  value,
  onChange,
  type = "number",
  min,
  max,
  step,
  placeholder,
  inputType,
}: {
  label: string;
  description?: string;
  value: string | number;
  onChange: (val: string) => void;
  type?: string;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  inputType?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-mono uppercase tracking-widest text-[#B9CACB]/50 mb-1">
        {label}
      </label>
      {description && (
        <p className="text-xs text-[#B9CACB]/30 mb-2">
          {description}
        </p>
      )}
      <input
        type={inputType || type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        min={min}
        max={max}
        step={step}
        placeholder={placeholder}
        className={INPUT_CLASS}
      />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Toast Component
   ═══════════════════════════════════════════════════════ */

type ToastType = "success" | "error";

interface ToastState {
  message: string;
  type: ToastType;
  visible: boolean;
}

function Toast({ toast }: { toast: ToastState }) {
  if (!toast.visible) return null;

  const bgColor =
    toast.type === "success"
      ? "bg-[#40E56C]/15 border-[#40E56C]/30 text-[#40E56C]"
      : "bg-[#FFB4AB]/15 border-[#FFB4AB]/30 text-[#FFB4AB]";

  return (
    <div
      className={`
        fixed top-4 right-4 z-50 px-4 py-3 rounded-sm border font-mono text-sm
        animate-fade-in-up ${bgColor}
      `}
    >
      {toast.message}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Nav items
   ═══════════════════════════════════════════════════════ */

const NAV_ITEMS = [
  { id: "exchange", label: "Exchange API", icon: Database },
  { id: "risk", label: "Risk Management", icon: Shield },
  { id: "dca", label: "DCA / Average Down", icon: Layers },
  { id: "execution", label: "Execution Policy", icon: Zap },
  { id: "alerts", label: "Alerts & Webhooks", icon: Bell },
  { id: "security", label: "Security", icon: Key },
] as const;

/* ═══════════════════════════════════════════════════════
   Settings Page
   ═══════════════════════════════════════════════════════ */

export default function SettingsPage() {
  // -- Active nav tab --
  const [activeTab, setActiveTab] = useState("exchange");

  // -- Global settings load --
  const { data: settings, loading: settingsLoading } = useApi(
    () => fetchSettings(),
    []
  );

  // -- Toast state --
  const [toast, setToast] = useState<ToastState>({
    message: "",
    type: "success",
    visible: false,
  });

  const showToast = useCallback((message: string, type: ToastType) => {
    setToast({ message, type, visible: true });
    setTimeout(() => {
      setToast((prev) => ({ ...prev, visible: false }));
    }, 3000);
  }, []);

  // -- Exchange form state --
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [testnet, setTestnet] = useState(false);
  const [exchangeSaving, setExchangeSaving] = useState(false);

  // -- Risk form state (matches backend RiskSettings) --
  const [riskPerTrade, setRiskPerTrade] = useState(1);
  const [maxLeverage, setMaxLeverage] = useState(20);
  const [defaultLeverage, setDefaultLeverage] = useState(5);
  const [maxPositions, setMaxPositions] = useState(5);
  const [maxPortfolioHeat, setMaxPortfolioHeat] = useState(50);
  const [maxDailyLoss, setMaxDailyLoss] = useState(5);
  const [maxDrawdown, setMaxDrawdown] = useState(15);
  const [autoKillSwitch, setAutoKillSwitch] = useState(true);
  const [strictSizing, setStrictSizing] = useState(false);
  const [riskSaving, setRiskSaving] = useState(false);

  // -- Password form state --
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);

  // -- Notifications form state (matches backend NotificationSettings) --
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [telegramBotToken, setTelegramBotToken] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [discordEnabled, setDiscordEnabled] = useState(false);
  const [discordWebhookUrl, setDiscordWebhookUrl] = useState("");
  const [notifSaving, setNotifSaving] = useState(false);

  // -- DCA form state --
  const [dcaEnabled, setDcaEnabled] = useState(false);
  const [dcaMaxOrders, setDcaMaxOrders] = useState(3);
  const [dcaTriggers, setDcaTriggers] = useState("2.0, 4.0, 6.0");
  const [dcaMultipliers, setDcaMultipliers] = useState("1.0, 1.5, 2.0");
  const [dcaMaxRisk, setDcaMaxRisk] = useState(5.0);
  const [dcaSlMode, setDcaSlMode] = useState<"fixed" | "follow">("follow");
  const [dcaTpMode, setDcaTpMode] = useState<"fixed" | "recalculate">("recalculate");
  const [dcaSaving, setDcaSaving] = useState(false);
  const [dcaLoaded, setDcaLoaded] = useState(false);

  // -- Signal Execution Policy state --
  const [policyPreset, setPolicyPreset] = useState("balanced");
  const [policyMatrix, setPolicyMatrix] = useState<Record<string, Record<string, string>>>(getDefaultMatrix);
  const [maxAutoPerHour, setMaxAutoPerHour] = useState(5);
  const [policySaving, setPolicySaving] = useState(false);
  const [presetApplying, setPresetApplying] = useState<string | null>(null);
  const [policyLoaded, setPolicyLoaded] = useState(false);

  // -- Populate forms when settings load --
  useEffect(() => {
    if (!settings) return;

    // Risk
    if (settings.risk_params) {
      setRiskPerTrade(settings.risk_params.default_risk_pct ?? 1);
      setMaxLeverage(settings.risk_params.max_leverage ?? 20);
      setDefaultLeverage(settings.risk_params.default_leverage ?? 5);
      setMaxPositions(settings.risk_params.max_positions ?? 5);
      setMaxPortfolioHeat(settings.risk_params.max_portfolio_heat ?? 50);
      setMaxDailyLoss(settings.risk_params.max_daily_loss ?? 5);
      setMaxDrawdown(settings.risk_params.max_drawdown ?? 15);
      setAutoKillSwitch(settings.risk_params.auto_kill_switch ?? true);
      setStrictSizing(settings.risk_params.strict_sizing ?? false);
    }

    // Notifications
    if (settings.notification_config) {
      setTelegramEnabled(settings.notification_config.telegram_enabled ?? false);
      setTelegramBotToken(settings.notification_config.telegram_bot_token ?? "");
      setTelegramChatId(settings.notification_config.telegram_chat_id ?? "");
      setDiscordEnabled(settings.notification_config.discord_enabled ?? false);
      setDiscordWebhookUrl(settings.notification_config.discord_webhook_url ?? "");
    }
  }, [settings]);

  // -- Load DCA config --
  useEffect(() => {
    let cancelled = false;
    async function loadDCA() {
      try {
        const resp = await fetchDCAConfig();
        if (cancelled) return;
        const c = resp.dca_config;
        setDcaEnabled(c.enabled ?? false);
        setDcaMaxOrders(c.max_dca_orders ?? 3);
        setDcaTriggers((c.trigger_drop_pct ?? [2, 4, 6]).join(", "));
        setDcaMultipliers((c.qty_multiplier ?? [1, 1.5, 2]).join(", "));
        setDcaMaxRisk(c.max_total_risk_pct ?? 5);
        setDcaSlMode(c.sl_recalc_mode ?? "follow");
        setDcaTpMode(c.tp_recalc_mode ?? "recalculate");
        setDcaLoaded(true);
      } catch {
        setDcaLoaded(true);
      }
    }
    loadDCA();
    return () => { cancelled = true; };
  }, []);

  // -- Load signal policy separately --
  useEffect(() => {
    let cancelled = false;
    async function loadPolicy() {
      try {
        const resp = await fetchSignalPolicy();
        if (cancelled) return;
        const p = resp.signal_policy;
        setPolicyPreset(p.preset ?? "balanced");
        setPolicyMatrix(p.matrix ?? getDefaultMatrix());
        setMaxAutoPerHour(p.max_auto_per_hour ?? 5);
        setPolicyLoaded(true);
      } catch {
        // API may not exist yet — keep defaults
        setPolicyLoaded(true);
      }
    }
    loadPolicy();
    return () => { cancelled = true; };
  }, []);

  // -- Save handlers --
  const handleSaveExchange = useCallback(async () => {
    setExchangeSaving(true);
    try {
      await updateExchangeKeys({
        api_key: apiKey,
        api_secret: apiSecret,
        testnet,
      });
      showToast("Exchange settings saved successfully", "success");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to save exchange settings";
      showToast(message, "error");
    } finally {
      setExchangeSaving(false);
    }
  }, [apiKey, apiSecret, testnet, showToast]);

  const handleSaveRisk = useCallback(async () => {
    setRiskSaving(true);
    try {
      const data: RiskSettings = {
        default_risk_pct: riskPerTrade,
        max_leverage: maxLeverage,
        default_leverage: defaultLeverage,
        max_positions: maxPositions,
        max_portfolio_heat: maxPortfolioHeat,
        max_daily_loss: maxDailyLoss,
        max_drawdown: maxDrawdown,
        auto_kill_switch: autoKillSwitch,
        strict_sizing: strictSizing,
      } as RiskSettings;
      await updateRiskParams(data);
      showToast("Risk parameters saved successfully", "success");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to save risk settings";
      showToast(message, "error");
    } finally {
      setRiskSaving(false);
    }
  }, [
    riskPerTrade,
    maxLeverage,
    defaultLeverage,
    maxPositions,
    maxPortfolioHeat,
    maxDailyLoss,
    maxDrawdown,
    autoKillSwitch,
    strictSizing,
    showToast,
  ]);

  const handleSavePassword = useCallback(async () => {
    if (!currentPassword || !newPassword) {
      showToast("Please fill in both password fields", "error");
      return;
    }
    if (newPassword.length < 6) {
      showToast("New password must be at least 6 characters", "error");
      return;
    }
    setPasswordSaving(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/auth/change-password", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed to change password" }));
        throw new Error(err.detail || "Failed to change password");
      }
      showToast("Password updated successfully", "success");
      setCurrentPassword("");
      setNewPassword("");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to change password";
      showToast(message, "error");
    } finally {
      setPasswordSaving(false);
    }
  }, [currentPassword, newPassword, showToast]);

  const handleSaveDCA = useCallback(async () => {
    setDcaSaving(true);
    try {
      const triggers = dcaTriggers.split(",").map((s) => parseFloat(s.trim())).filter((n) => !isNaN(n));
      const multipliers = dcaMultipliers.split(",").map((s) => parseFloat(s.trim())).filter((n) => !isNaN(n));

      await updateDCAConfig({
        enabled: dcaEnabled,
        max_dca_orders: dcaMaxOrders,
        trigger_drop_pct: triggers,
        qty_multiplier: multipliers,
        max_total_risk_pct: dcaMaxRisk,
        sl_recalc_mode: dcaSlMode,
        tp_recalc_mode: dcaTpMode,
      });
      showToast("DCA settings saved successfully", "success");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to save DCA settings";
      showToast(message, "error");
    } finally {
      setDcaSaving(false);
    }
  }, [dcaEnabled, dcaMaxOrders, dcaTriggers, dcaMultipliers, dcaMaxRisk, dcaSlMode, dcaTpMode, showToast]);

  const handleSaveNotifications = useCallback(async () => {
    setNotifSaving(true);
    try {
      const data: NotificationSettings = {
        telegram_enabled: telegramEnabled,
        telegram_bot_token: telegramBotToken || undefined,
        telegram_chat_id: telegramChatId || undefined,
        discord_enabled: discordEnabled,
        discord_webhook_url: discordWebhookUrl || undefined,
      };
      await updateNotifications(data);
      showToast("Notification settings saved successfully", "success");
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Failed to save notification settings";
      showToast(message, "error");
    } finally {
      setNotifSaving(false);
    }
  }, [
    telegramEnabled,
    telegramBotToken,
    telegramChatId,
    discordEnabled,
    discordWebhookUrl,
    showToast,
  ]);

  const handleApplyPreset = useCallback(
    async (preset: string) => {
      setPresetApplying(preset);
      try {
        const resp = await applySignalPolicyPreset(preset);
        const p = resp.signal_policy;
        setPolicyPreset(p.preset);
        setPolicyMatrix(p.matrix);
        setMaxAutoPerHour(p.max_auto_per_hour);
        showToast(`Applied "${preset}" preset`, "success");
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to apply preset";
        showToast(message, "error");
      } finally {
        setPresetApplying(null);
      }
    },
    [showToast]
  );

  const handleCycleAction = useCallback(
    (strategy: string, grade: string) => {
      setPolicyMatrix((prev) => {
        const next = { ...prev };
        next[strategy] = { ...next[strategy] };
        next[strategy][grade] = cycleAction(next[strategy][grade] ?? "skip");
        return next;
      });
      setPolicyPreset("custom");
    },
    []
  );

  const handleSavePolicy = useCallback(async () => {
    setPolicySaving(true);
    try {
      const data: SignalPolicy = {
        preset: policyPreset,
        matrix: policyMatrix,
        max_auto_per_hour: maxAutoPerHour,
        quiet_hours_start: null,
        quiet_hours_end: null,
      };
      const resp = await updateSignalPolicy(data);
      const p = resp.signal_policy;
      setPolicyPreset(p.preset);
      setPolicyMatrix(p.matrix);
      setMaxAutoPerHour(p.max_auto_per_hour);
      showToast("Signal execution policy saved successfully", "success");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to save signal policy";
      showToast(message, "error");
    } finally {
      setPolicySaving(false);
    }
  }, [policyPreset, policyMatrix, maxAutoPerHour, showToast]);

  // -- Loading state --
  if (settingsLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex items-center gap-3">
          <div
            className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin"
            style={{
              borderColor: "#00F0FF",
              borderTopColor: "transparent",
            }}
          />
          <span
            className="font-mono text-sm text-[#B9CACB]/50"
          >
            Loading settings...
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-[1600px] mx-auto pb-20 md:pb-6">
      {/* Toast */}
      <Toast toast={toast} />

      {/* -- Header -- */}
      <div className="flex items-center gap-3 mb-6">
        <SettingsIcon className="w-6 h-6 text-[#00F0FF]" />
        <div>
          <h2 className="font-mono text-xl font-black tracking-tighter text-[#E5E2E1] uppercase">System Configuration</h2>
          <p className="font-mono text-[10px] text-[#B9CACB] uppercase tracking-widest mt-1">
            Exchange, risk management, and notification configuration
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Nav */}
        <div className="lg:col-span-3 space-y-1">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 font-mono text-[11px] uppercase tracking-widest rounded-sm transition-colors ${
                activeTab === item.id
                  ? "bg-[#00F0FF]/10 text-[#00F0FF] border-l-2 border-[#00F0FF]"
                  : "text-[#B9CACB] hover:bg-[#201F1F] hover:text-[#E5E2E1]"
              }`}
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </button>
          ))}
        </div>

        {/* Main Settings Area */}
        <div className="lg:col-span-9 space-y-6">
          {/* ═══════════════════════════════════════════════════
             Section A: Exchange Configuration
             ═══════════════════════════════════════════════════ */}
          {activeTab === "exchange" && (
          <section className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-6">
            <h3 className="font-mono text-sm font-black tracking-widest text-[#E5E2E1] uppercase mb-6 border-b border-[#3B494B]/10 pb-4">Exchange API Configuration</h3>

            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  {/* Exchange name + API status */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-[#E5E2E1]/85">
                        Exchange
                      </span>
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-[#00F0FF]/12 text-[#00F0FF] border border-[#00F0FF]/25 text-xs font-mono font-semibold uppercase tracking-wider">
                        Binance
                      </span>
                    </div>
                  </div>

                  {/* Exchange Provider */}
                  <div>
                    <label className="block font-mono text-[10px] text-[#B9CACB]/50 uppercase mb-2 tracking-widest">Exchange Provider</label>
                    <select className="w-full bg-[#2A2A2A] text-[#E5E2E1] font-mono text-xs px-4 py-3 rounded-sm outline-none border border-[#3B494B]/10 focus:ring-1 focus:ring-[#00F0FF] appearance-none">
                      <option>Binance Futures</option>
                      <option>Bybit USDT-M</option>
                      <option>OKX</option>
                    </select>
                  </div>

                  {/* Testnet toggle */}
                  <Toggle
                    checked={testnet}
                    onChange={setTestnet}
                    label="Testnet Mode"
                    description="Use Binance testnet for paper trading"
                  />

                  {/* API Key */}
                  <div>
                    <label className="block font-mono text-[10px] text-[#B9CACB]/50 uppercase mb-2 tracking-widest">API Key</label>
                    <input
                      className={INPUT_CLASS}
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="Enter API Key"
                    />
                  </div>

                  {/* API Secret */}
                  <div>
                    <label className="block font-mono text-[10px] text-[#B9CACB]/50 uppercase mb-2 tracking-widest">API Secret</label>
                    <input
                      className={INPUT_CLASS}
                      type="password"
                      value={apiSecret}
                      onChange={(e) => setApiSecret(e.target.value)}
                      placeholder="Enter API Secret"
                    />
                  </div>

                  {/* Masked key + source display */}
                  {settings?.exchange.api_key_masked && (
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-mono text-[#B9CACB]/50">
                        Current Key:
                      </span>
                      <span className="text-xs font-mono text-[#E5E2E1]/70">
                        {settings.exchange.api_key_masked}
                      </span>
                      {settings.exchange.source === "env" && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-[#3498DB]/12 text-[#3498DB] border border-[#3498DB]/25 text-xs font-mono">
                          via .env
                        </span>
                      )}
                      {settings.exchange.testnet && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-[#FFB3B6]/12 text-[#FFB3B6] border border-[#FFB3B6]/25 text-xs font-mono">
                          Testnet
                        </span>
                      )}
                    </div>
                  )}

                  {/* Info: keys from .env */}
                  {settings?.exchange.source === "env" && (
                    <div className="flex items-start gap-2 px-3 py-2.5 rounded-sm bg-[#3498DB]/5 border border-[#3498DB]/15">
                      <svg
                        className="w-4 h-4 text-[#3498DB] mt-0.5 flex-shrink-0"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M11.25 11.25l.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z"
                        />
                      </svg>
                      <p className="text-xs font-mono text-[#3498DB]/80">
                        API key loaded from server .env file. You can override it by saving new keys below.
                      </p>
                    </div>
                  )}

                  {/* Warning */}
                  <div className="flex items-start gap-2 px-3 py-2.5 rounded-sm bg-[#00F0FF]/5 border border-[#00F0FF]/15">
                    <svg
                      className="w-4 h-4 text-[#00F0FF] mt-0.5 flex-shrink-0"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
                      />
                    </svg>
                    <p className="text-xs font-mono text-[#00F0FF]/80">
                      API keys are encrypted and stored securely
                    </p>
                  </div>

                  <Button
                    variant="primary"
                    loading={exchangeSaving}
                    onClick={handleSaveExchange}
                    className="w-full"
                  >
                    Save Exchange Settings
                  </Button>
                </div>

                {/* Connection Status Panel */}
                <div className="bg-[#2A2A2A] p-4 rounded-sm border border-[#3B494B]/10">
                  <h4 className="font-mono text-[10px] font-bold text-[#B9CACB]/50 uppercase mb-4">Connection Status</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="font-mono text-[10px] text-[#E5E2E1]">Status</span>
                      {settings?.exchange.configured ? (
                        <span className="flex items-center gap-1 text-[10px] font-mono text-[#40E56C]">
                          <CheckCircle2 className="w-3 h-3" /> CONNECTED
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-[10px] font-mono text-[#FFB4AB]">
                          NOT SET
                        </span>
                      )}
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="font-mono text-[10px] text-[#E5E2E1]">Latency</span>
                      <span className="font-mono text-[10px] text-[#B9CACB]">12ms</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="font-mono text-[10px] text-[#E5E2E1]">Rate Limit Usage</span>
                      <span className="font-mono text-[10px] text-[#00F0FF]">14%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="font-mono text-[10px] text-[#E5E2E1]">Last Sync</span>
                      <span className="font-mono text-[10px] text-[#B9CACB]">2s ago</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
          )}

          {/* ═══════════════════════════════════════════════════
             Section B: Risk Management
             ═══════════════════════════════════════════════════ */}
          {activeTab === "risk" && (
          <section className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-6">
            <h3 className="font-mono text-sm font-black tracking-widest text-[#E5E2E1] uppercase mb-6 border-b border-[#3B494B]/10 pb-4">Global Risk Parameters</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <LabeledInput
                    label="Risk Per Trade"
                    description="% of portfolio risked per trade"
                    value={riskPerTrade}
                    onChange={(val) => setRiskPerTrade(Number(val) || 0)}
                    min={0.1}
                    max={10}
                    step={0.1}
                    placeholder="1"
                  />
                  <LabeledInput
                    label="Max Leverage"
                    description="Maximum allowed leverage"
                    value={maxLeverage}
                    onChange={(val) => setMaxLeverage(Number(val) || 1)}
                    min={1}
                    max={125}
                    step={1}
                    placeholder="20"
                  />
                  <LabeledInput
                    label="Default Leverage"
                    description="Default leverage for new positions"
                    value={defaultLeverage}
                    onChange={(val) => setDefaultLeverage(Number(val) || 1)}
                    min={1}
                    max={125}
                    step={1}
                    placeholder="5"
                  />
                  <LabeledInput
                    label="Max Positions"
                    description="Maximum number of concurrent positions"
                    value={maxPositions}
                    onChange={(val) => setMaxPositions(Number(val) || 1)}
                    min={1}
                    max={50}
                    step={1}
                    placeholder="5"
                  />
                  <LabeledInput
                    label="Max Portfolio Heat"
                    description="% maximum total portfolio exposure"
                    value={maxPortfolioHeat}
                    onChange={(val) => setMaxPortfolioHeat(Number(val) || 0)}
                    min={1}
                    max={100}
                    step={1}
                    placeholder="50"
                  />
                  <LabeledInput
                    label="Max Daily Loss"
                    description="% max loss allowed per day"
                    value={maxDailyLoss}
                    onChange={(val) => setMaxDailyLoss(Number(val) || 0)}
                    min={1}
                    max={100}
                    step={0.5}
                    placeholder="5"
                  />
                </div>

                <LabeledInput
                  label="Max Drawdown"
                  description="% max drawdown before bot stops"
                  value={maxDrawdown}
                  onChange={(val) => setMaxDrawdown(Number(val) || 0)}
                  min={1}
                  max={100}
                  step={1}
                  placeholder="15"
                />
              </div>

              <div className="space-y-4">
                <Toggle
                  checked={autoKillSwitch}
                  onChange={setAutoKillSwitch}
                  label="Auto-Kill Switch"
                  description="Close all positions on critical error"
                />
                <Toggle
                  checked={strictSizing}
                  onChange={setStrictSizing}
                  label="Strict Position Sizing"
                  description="Enforce Kelly Criterion limits"
                />
              </div>
            </div>

            <div className="mt-8 flex justify-end">
              <Button
                variant="primary"
                loading={riskSaving}
                onClick={handleSaveRisk}
              >
                Save Risk Parameters
              </Button>
            </div>
          </section>
          )}

          {/* ═══════════════════════════════════════════════════
             Section B2: DCA / Average Down
             ═══════════════════════════════════════════════════ */}
          {activeTab === "dca" && (
          <section className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-6">
            <h3 className="font-mono text-sm font-black tracking-widest text-[#E5E2E1] uppercase mb-6 border-b border-[#3B494B]/10 pb-4 flex items-center gap-2">
              <Layers size={16} className="text-[#00F0FF]" />
              DCA / Average Down
            </h3>

            <div className="space-y-6">
              {/* Master toggle */}
              <Toggle
                checked={dcaEnabled}
                onChange={setDcaEnabled}
                label="Enable DCA System"
                description="Automatically add to losing positions at predefined price levels to lower average entry"
              />

              {dcaEnabled && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                  <div className="space-y-5">
                    <LabeledInput
                      label="Max DCA Orders"
                      description="Maximum additional orders per position (1-5)"
                      value={dcaMaxOrders}
                      onChange={(val) => setDcaMaxOrders(Math.min(5, Math.max(1, Number(val) || 1)))}
                      min={1}
                      max={5}
                      step={1}
                      placeholder="3"
                    />

                    <div>
                      <label className="block text-xs font-mono font-bold text-[#B9CACB] mb-1 uppercase tracking-wider">
                        Trigger Drop % (per level)
                      </label>
                      <p className="text-[10px] font-mono text-[#B9CACB]/40 mb-2">
                        Comma-separated % drop from entry price to trigger each DCA order
                      </p>
                      <input
                        type="text"
                        className={INPUT_CLASS}
                        value={dcaTriggers}
                        onChange={(e) => setDcaTriggers(e.target.value)}
                        placeholder="2.0, 4.0, 6.0"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-mono font-bold text-[#B9CACB] mb-1 uppercase tracking-wider">
                        Qty Multiplier (per level)
                      </label>
                      <p className="text-[10px] font-mono text-[#B9CACB]/40 mb-2">
                        Multiplier for each DCA order size vs initial position (1.0 = same size)
                      </p>
                      <input
                        type="text"
                        className={INPUT_CLASS}
                        value={dcaMultipliers}
                        onChange={(e) => setDcaMultipliers(e.target.value)}
                        placeholder="1.0, 1.5, 2.0"
                      />
                    </div>

                    <LabeledInput
                      label="Max Total Risk %"
                      description="Maximum total portfolio % at risk across all DCA orders for one position"
                      value={dcaMaxRisk}
                      onChange={(val) => setDcaMaxRisk(Number(val) || 1)}
                      min={0.5}
                      max={20}
                      step={0.5}
                      placeholder="5"
                    />
                  </div>

                  <div className="space-y-5">
                    {/* SL recalc mode */}
                    <div>
                      <label className="block text-xs font-mono font-bold text-[#B9CACB] mb-1 uppercase tracking-wider">
                        Stop Loss Mode
                      </label>
                      <p className="text-[10px] font-mono text-[#B9CACB]/40 mb-2">
                        How to handle SL after DCA orders fill
                      </p>
                      <div className="flex gap-2">
                        {(["fixed", "follow"] as const).map((mode) => (
                          <button
                            key={mode}
                            onClick={() => setDcaSlMode(mode)}
                            className={`flex-1 px-3 py-2 rounded-sm text-[11px] font-mono font-bold transition-colors cursor-pointer ${
                              dcaSlMode === mode
                                ? "bg-[#00F0FF]/15 text-[#00F0FF] border border-[#00F0FF]/30"
                                : "bg-[#2A2A2A] text-[#B9CACB]/60 border border-[#3B494B]/10 hover:text-[#E5E2E1]"
                            }`}
                          >
                            {mode === "fixed" ? "FIXED (Keep Original)" : "FOLLOW (Move to New Avg)"}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* TP recalc mode */}
                    <div>
                      <label className="block text-xs font-mono font-bold text-[#B9CACB] mb-1 uppercase tracking-wider">
                        Take Profit Mode
                      </label>
                      <p className="text-[10px] font-mono text-[#B9CACB]/40 mb-2">
                        How to handle TPs after DCA orders fill
                      </p>
                      <div className="flex gap-2">
                        {(["fixed", "recalculate"] as const).map((mode) => (
                          <button
                            key={mode}
                            onClick={() => setDcaTpMode(mode)}
                            className={`flex-1 px-3 py-2 rounded-sm text-[11px] font-mono font-bold transition-colors cursor-pointer ${
                              dcaTpMode === mode
                                ? "bg-[#00F0FF]/15 text-[#00F0FF] border border-[#00F0FF]/30"
                                : "bg-[#2A2A2A] text-[#B9CACB]/60 border border-[#3B494B]/10 hover:text-[#E5E2E1]"
                            }`}
                          >
                            {mode === "fixed" ? "FIXED (Keep TPs)" : "RECALCULATE (New Avg)"}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* DCA visual preview */}
                    <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4 mt-4">
                      <h4 className="text-[9px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/50 mb-3">DCA LEVELS PREVIEW</h4>
                      <div className="space-y-2">
                        <div className="flex justify-between items-center text-[10px] font-mono">
                          <span className="text-[#00F0FF]">Initial Entry</span>
                          <span className="text-[#E5E2E1]">1.0x size</span>
                        </div>
                        {dcaTriggers.split(",").map((t, i) => {
                          const trigger = parseFloat(t.trim());
                          const mult = dcaMultipliers.split(",").map((m) => parseFloat(m.trim()))[i];
                          if (isNaN(trigger)) return null;
                          return (
                            <div key={i} className="flex justify-between items-center text-[10px] font-mono">
                              <span className="text-[#FFB4AB]">DCA {i + 1}: -{trigger}% drop</span>
                              <span className="text-[#E5E2E1]">{isNaN(mult) ? "?" : mult}x size</span>
                            </div>
                          );
                        })}
                        <div className="border-t border-[#3B494B]/10 pt-2 mt-2 flex justify-between items-center text-[10px] font-mono">
                          <span className="text-[#B9CACB]">Max Risk</span>
                          <span className="text-[#FFB4AB] font-bold">{dcaMaxRisk}% of portfolio</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex justify-end pt-2">
                <Button
                  variant="primary"
                  loading={dcaSaving}
                  onClick={handleSaveDCA}
                >
                  Save DCA Settings
                </Button>
              </div>
            </div>
          </section>
          )}

          {/* ═══════════════════════════════════════════════════
             Section C: Notifications
             ═══════════════════════════════════════════════════ */}
          {activeTab === "alerts" && (
          <section className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-6">
            <h3 className="font-mono text-sm font-black tracking-widest text-[#E5E2E1] uppercase mb-6 border-b border-[#3B494B]/10 pb-4">Alerts & Webhooks</h3>

            <div className="space-y-5">
              {/* Telegram Section */}
              <Toggle
                checked={telegramEnabled}
                onChange={setTelegramEnabled}
                label="Enable Telegram Notifications"
                description="Receive trading alerts via Telegram bot"
              />

              <div className="border-t border-[#3B494B]/10" />

              <div>
                <label className="block text-xs font-mono uppercase tracking-widest text-[#B9CACB]/50 mb-2">
                  Telegram Bot Token
                </label>
                <input
                  type="password"
                  value={telegramBotToken}
                  onChange={(e) => setTelegramBotToken(e.target.value)}
                  placeholder="Enter your Telegram Bot Token"
                  className={INPUT_CLASS}
                  disabled={!telegramEnabled}
                />
              </div>

              <div>
                <label className="block text-xs font-mono uppercase tracking-widest text-[#B9CACB]/50 mb-2">
                  Telegram Chat ID
                </label>
                <input
                  type="text"
                  value={telegramChatId}
                  onChange={(e) => setTelegramChatId(e.target.value)}
                  placeholder="Enter your Telegram Chat ID"
                  className={INPUT_CLASS}
                  disabled={!telegramEnabled}
                />
              </div>

              {/* Discord Section */}
              <div className="border-t border-[#3B494B]/10" />

              <Toggle
                checked={discordEnabled}
                onChange={setDiscordEnabled}
                label="Enable Discord Notifications"
                description="Receive trading alerts via Discord webhook"
              />

              <div>
                <label className="block text-xs font-mono uppercase tracking-widest text-[#B9CACB]/50 mb-2">
                  Discord Webhook URL
                </label>
                <input
                  type="text"
                  value={discordWebhookUrl}
                  onChange={(e) => setDiscordWebhookUrl(e.target.value)}
                  placeholder="Enter Discord Webhook URL"
                  className={INPUT_CLASS}
                  disabled={!discordEnabled}
                />
              </div>

              <Button
                variant="primary"
                loading={notifSaving}
                onClick={handleSaveNotifications}
                className="w-full"
              >
                Save Notification Settings
              </Button>
            </div>
          </section>
          )}

          {/* ═══════════════════════════════════════════════════
             Section D: Signal Execution Policy
             ═══════════════════════════════════════════════════ */}
          {activeTab === "execution" && (
          <section className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-6">
            <div className="space-y-5">
              {/* Section header */}
              <div className="flex items-center gap-3 border-b border-[#3B494B]/10 pb-4">
                <Zap className="w-5 h-5 text-[#00F0FF]" />
                <div>
                  <h3 className="font-mono text-sm font-black tracking-widest text-[#E5E2E1] uppercase">
                    Signal Execution Policy
                  </h3>
                  <p className="text-xs text-[#B9CACB]/40 mt-0.5">
                    Configure how each strategy/grade combination is handled
                  </p>
                </div>
              </div>

              {/* Preset buttons */}
              <div>
                <label className="block text-xs font-mono uppercase tracking-widest text-[#B9CACB]/50 mb-2">
                  Preset
                </label>
                <div className="flex gap-2">
                  {(["conservative", "balanced", "aggressive"] as const).map(
                    (preset) => {
                      const isActive = policyPreset === preset;
                      return (
                        <button
                          key={preset}
                          disabled={presetApplying !== null}
                          onClick={() => handleApplyPreset(preset)}
                          className={`
                            flex-1 px-3 py-2 rounded-sm text-xs font-mono font-semibold uppercase tracking-wider
                            border transition-all duration-200 cursor-pointer
                            ${
                              isActive
                                ? "bg-[#00F0FF]/15 border-[#00F0FF]/40 text-[#00F0FF]"
                                : "bg-[#2A2A2A] border-[#3B494B]/10 text-[#B9CACB]/60 hover:border-[#00F0FF]/25 hover:text-[#E5E2E1]/70"
                            }
                            ${presetApplying === preset ? "opacity-60" : ""}
                          `}
                        >
                          {presetApplying === preset ? (
                            <span className="flex items-center justify-center gap-1.5">
                              <svg
                                className="w-3 h-3 animate-spin"
                                fill="none"
                                viewBox="0 0 24 24"
                              >
                                <circle
                                  className="opacity-25"
                                  cx="12"
                                  cy="12"
                                  r="10"
                                  stroke="currentColor"
                                  strokeWidth="4"
                                />
                                <path
                                  className="opacity-75"
                                  fill="currentColor"
                                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                                />
                              </svg>
                              Applying...
                            </span>
                          ) : (
                            preset
                          )}
                        </button>
                      );
                    }
                  )}
                </div>
              </div>

              <div className="border-t border-[#3B494B]/10" />

              {/* Policy Matrix Grid */}
              <div>
                <label className="block text-xs font-mono uppercase tracking-widest text-[#B9CACB]/50 mb-3">
                  Policy Matrix
                </label>
                <div className="rounded-sm border border-[#3B494B]/10 overflow-hidden">
                  {/* Header row */}
                  <div className="grid grid-cols-[1fr_repeat(4,minmax(0,1fr))] bg-[#0D0D0D]">
                    <div className="px-3 py-2.5 text-xs font-mono uppercase tracking-widest text-[#B9CACB]/30 border-b border-[#3B494B]/10">
                      Strategy
                    </div>
                    {GRADES.map((g) => (
                      <div
                        key={g}
                        className="px-3 py-2.5 text-center text-xs font-mono font-semibold tracking-widest text-[#B9CACB]/50 border-b border-l border-[#3B494B]/10"
                      >
                        Grade {g}
                      </div>
                    ))}
                  </div>

                  {/* Strategy rows */}
                  {STRATEGY_KEYS.map((strategy, rowIdx) => (
                    <div
                      key={strategy}
                      className={`grid grid-cols-[1fr_repeat(4,minmax(0,1fr))] ${
                        rowIdx % 2 === 0 ? "bg-[#0D0D0D]" : "bg-[#1C1B1B]"
                      }`}
                    >
                      <div className="px-3 py-3 text-xs font-mono text-[#E5E2E1]/70 flex items-center border-b border-[#3B494B]/5">
                        {STRATEGY_LABELS[strategy]}
                      </div>
                      {GRADES.map((grade) => {
                        const action = (policyMatrix[strategy]?.[grade] ??
                          "skip") as PolicyAction;
                        const style = ACTION_STYLES[action];
                        return (
                          <div
                            key={grade}
                            className="px-2 py-2.5 border-b border-l border-[#3B494B]/5 flex items-center justify-center"
                          >
                            <button
                              onClick={() => handleCycleAction(strategy, grade)}
                              title={`Click to cycle: ${ACTIONS.join(" → ")}`}
                              className={`
                                px-3 py-1.5 rounded-sm text-xs font-mono font-semibold uppercase tracking-wider
                                border transition-all duration-150 cursor-pointer
                                hover:scale-105 active:scale-95
                                ${style.bg} ${style.border} ${style.text}
                              `}
                            >
                              {style.label}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>

                {/* Legend */}
                <div className="flex items-center gap-4 mt-3 flex-wrap">
                  {ACTIONS.map((action) => {
                    const s = ACTION_STYLES[action];
                    return (
                      <div key={action} className="flex items-center gap-1.5">
                        <span
                          className={`w-2 h-2 rounded-sm ${s.bg} ${s.border} border`}
                        />
                        <span className="text-[10px] font-mono text-[#B9CACB]/40 uppercase tracking-wider">
                          {s.label}
                        </span>
                      </div>
                    );
                  })}
                  <span className="text-[10px] font-mono text-[#B9CACB]/25 ml-auto">
                    Click cells to cycle actions
                  </span>
                </div>
              </div>

              <div className="border-t border-[#3B494B]/10" />

              {/* Max auto-executions per hour */}
              <LabeledInput
                label="Max Auto-Executions / Hour"
                description="Limit automatic trade executions per hour (safety cap)"
                value={maxAutoPerHour}
                onChange={(val) => setMaxAutoPerHour(Math.max(0, Number(val) || 0))}
                min={0}
                max={100}
                step={1}
                placeholder="5"
              />

              {/* Save button */}
              <Button
                variant="primary"
                loading={policySaving}
                onClick={handleSavePolicy}
                disabled={!policyLoaded}
                className="w-full"
              >
                Save Signal Execution Policy
              </Button>
            </div>
          </section>
          )}

          {/* ═══════════════════════════════════════════════════
             Section E: Security
             ═══════════════════════════════════════════════════ */}
          {activeTab === "security" && (
          <section className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-6">
            <h3 className="font-mono text-sm font-black tracking-widest text-[#E5E2E1] uppercase mb-6 border-b border-[#3B494B]/10 pb-4 flex items-center gap-2">
              <Key size={16} className="text-[#00F0FF]" />
              Security Settings
            </h3>

            <div className="space-y-6">
              {/* Session */}
              <div className="space-y-4">
                <h4 className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/60">Session</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4">
                    <div className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/60 mb-1">Session Expiry</div>
                    <div className="font-mono text-sm text-[#E5E2E1]">24 hours</div>
                    <p className="text-[9px] font-mono text-[#B9CACB]/40 mt-1">JWT tokens expire after 24h, requiring re-login</p>
                  </div>
                  <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4">
                    <div className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/60 mb-1">Auth Method</div>
                    <div className="font-mono text-sm text-[#E5E2E1]">JWT + bcrypt</div>
                    <p className="text-[9px] font-mono text-[#B9CACB]/40 mt-1">Password hashed with bcrypt, token-based auth</p>
                  </div>
                </div>
              </div>

              {/* API Security */}
              <div className="space-y-4">
                <h4 className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/60">API Security</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle2 size={14} className="text-[#40E56C]" />
                      <span className="text-xs font-mono font-bold text-[#E5E2E1]">Rate Limiting</span>
                    </div>
                    <p className="text-[9px] font-mono text-[#B9CACB]/40">300 req/min general, 10 req/min auth endpoints</p>
                  </div>
                  <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle2 size={14} className="text-[#40E56C]" />
                      <span className="text-xs font-mono font-bold text-[#E5E2E1]">CORS Protection</span>
                    </div>
                    <p className="text-[9px] font-mono text-[#B9CACB]/40">Restricted origins, methods, and headers</p>
                  </div>
                  <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle2 size={14} className="text-[#40E56C]" />
                      <span className="text-xs font-mono font-bold text-[#E5E2E1]">Encrypted Keys</span>
                    </div>
                    <p className="text-[9px] font-mono text-[#B9CACB]/40">Exchange API keys encrypted at rest with Fernet</p>
                  </div>
                </div>
              </div>

              {/* Infrastructure */}
              <div className="space-y-4">
                <h4 className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/60">Infrastructure</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle2 size={14} className="text-[#40E56C]" />
                      <span className="text-xs font-mono font-bold text-[#E5E2E1]">Database</span>
                    </div>
                    <p className="text-[9px] font-mono text-[#B9CACB]/40">TimescaleDB with parameterized queries (SQL injection safe)</p>
                  </div>
                  <div className="bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle2 size={14} className="text-[#40E56C]" />
                      <span className="text-xs font-mono font-bold text-[#E5E2E1]">WebSocket</span>
                    </div>
                    <p className="text-[9px] font-mono text-[#B9CACB]/40">JWT-authenticated WS connections with heartbeat</p>
                  </div>
                </div>
              </div>

              {/* Change Password */}
              <div className="space-y-4 pt-4 border-t border-[#3B494B]/10">
                <h4 className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#B9CACB]/60">Change Password</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-mono font-bold text-[#B9CACB] mb-1 uppercase tracking-wider">Current Password</label>
                    <input type="password" className={INPUT_CLASS} placeholder="Enter current password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
                  </div>
                  <div>
                    <label className="block text-xs font-mono font-bold text-[#B9CACB] mb-1 uppercase tracking-wider">New Password</label>
                    <input type="password" className={INPUT_CLASS} placeholder="Enter new password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
                  </div>
                </div>
                <div className="flex justify-end">
                  <Button variant="primary" loading={passwordSaving} onClick={handleSavePassword}>Update Password</Button>
                </div>
              </div>
            </div>
          </section>
          )}

        </div>
      </div>
    </div>
  );
}
