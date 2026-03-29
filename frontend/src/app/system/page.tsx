"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Activity,
  Database,
  Server,
  Wifi,
  WifiOff,
  Bot,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Zap,
  RefreshCw,
  BarChart3,
  Shield,
  Network,
  Cpu,
  Terminal,
} from "lucide-react";
import { useApi } from "@/hooks/useApi";
import { useWebSocket } from "@/hooks/useApi";
import {
  fetchSystemStatus,
  fetchPing,
  type SystemStatusResponse,
  type ComponentStatusDetail,
} from "@/lib/api";
import { wsManager, type SystemStatusData } from "@/lib/websocket";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PING_COUNT = 3;
const PING_INTERVAL = 2_000;
const LATENCY_HISTORY_MAX = 60;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusColor(status: string): string {
  switch (status) {
    case "ok":
    case "ready":
      return "#40E56C";
    case "degraded":
      return "#FFB3B6";
    case "error":
    case "offline":
      return "#FFB4AB";
    default:
      return "#849495";
  }
}

function statusIcon(status: string) {
  switch (status) {
    case "ok":
    case "ready":
      return <CheckCircle2 size={16} color="#40E56C" />;
    case "degraded":
      return <AlertTriangle size={16} color="#FFB3B6" />;
    default:
      return <XCircle size={16} color="#FFB4AB" />;
  }
}

function componentIcon(name: string) {
  switch (name) {
    case "database":
      return <Database size={18} />;
    case "redis":
      return <Server size={18} />;
    case "exchange":
      return <Zap size={18} />;
    case "websocket":
      return <Wifi size={18} />;
    case "bot_service":
      return <Bot size={18} />;
    default:
      return <Activity size={18} />;
  }
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (d > 0) return `${d}d ${h}h ${m}m ${s}s`;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatAge(seconds: number | null): string {
  if (seconds === null) return "No data";
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h ago`;
  return `${(seconds / 86400).toFixed(1)}d ago`;
}

// ---------------------------------------------------------------------------
// SVG Sparkline
// ---------------------------------------------------------------------------

function Sparkline({
  data,
  color,
  height = 32,
  width = 140,
}: {
  data: number[];
  color: string;
  height?: number;
  width?: number;
}) {
  if (data.length < 2) return null;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;

  const points = data
    .map((val, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((val - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} className="mt-1 opacity-70">
      <polyline fill="none" stroke={color} strokeWidth={1.5} points={points} />
      {data.length > 0 && (
        <circle
          cx={width}
          cy={
            height -
            ((data[data.length - 1] - min) / range) * (height - 4) -
            2
          }
          r={2.5}
          fill={color}
        />
      )}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function SystemPage() {
  const { data: initialStatus, refetch: refetchStatus } = useApi(() => fetchSystemStatus(), []);
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);

  useWebSocket("system_status", (data: SystemStatusData) => {
    setStatus(data as unknown as SystemStatusResponse);
  });

  const current = status ?? initialStatus;

  const [rtt, setRtt] = useState<number | null>(null);
  const [jitter, setJitter] = useState<number | null>(null);
  const [rttHistory, setRttHistory] = useState<number[]>([]);
  const [latencyHistory, setLatencyHistory] = useState<Record<string, number[]>>({});
  const [wsConnected, setWsConnected] = useState(false);
  const prevWsConnected = useRef(false);
  const [liveTime, setLiveTime] = useState("");
  const [lastUpdate, setLastUpdate] = useState("");
  const [updateCount, setUpdateCount] = useState(0);
  const updateCountRef = useRef(0);

  useEffect(() => {
    if (!current) return;
    const now = new Date();
    setLastUpdate(
      now.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" }) +
        "." + String(now.getMilliseconds()).padStart(3, "0")
    );
    updateCountRef.current += 1;
    setUpdateCount(updateCountRef.current);
    setLatencyHistory((prev) => {
      const next = { ...prev };
      for (const comp of current.components) {
        if (comp.latency_ms !== null) {
          const arr = next[comp.name] || [];
          next[comp.name] = [...arr, comp.latency_ms].slice(-LATENCY_HISTORY_MAX);
        }
      }
      return next;
    });
  }, [current]);

  useEffect(() => {
    const check = () => {
      const isConnected = wsManager.connected;
      if (isConnected && !prevWsConnected.current) { refetchStatus(); }
      prevWsConnected.current = isConnected;
      setWsConnected(isConnected);
    };
    check();
    wsManager.connect();
    const interval = setInterval(check, 100);
    return () => clearInterval(interval);
  }, [refetchStatus]);

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setLiveTime(
        now.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" }) +
          "." + String(now.getMilliseconds()).padStart(3, "0")
      );
    };
    tick();
    const interval = setInterval(tick, 100);
    return () => clearInterval(interval);
  }, []);

  const measurePing = useCallback(async () => {
    const times: number[] = [];
    for (let i = 0; i < PING_COUNT; i++) {
      const t0 = performance.now();
      try { await fetchPing(); times.push(performance.now() - t0); } catch { /* skip */ }
    }
    if (times.length > 0) {
      const avg = times.reduce((a, b) => a + b, 0) / times.length;
      setRtt(Math.round(avg * 10) / 10);
      setRttHistory((prev) => [...prev, Math.round(avg * 10) / 10].slice(-LATENCY_HISTORY_MAX));
      if (times.length >= 2) {
        const deviations = times.map((t) => Math.abs(t - avg));
        setJitter(Math.round((deviations.reduce((a, b) => a + b, 0) / deviations.length) * 10) / 10);
      }
    }
  }, []);

  useEffect(() => {
    measurePing();
    const interval = setInterval(measurePing, PING_INTERVAL);
    return () => clearInterval(interval);
  }, [measurePing]);

  if (!current) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: "#00F0FF", borderTopColor: "transparent" }} />
          <span className="font-mono text-sm text-[#B9CACB]/50">Connecting to system...</span>
        </div>
      </div>
    );
  }

  const overallStatus = current.overall_status;
  const okCount = current.components.filter((c) => c.status === "ok").length;
  const totalCount = current.components.length;

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-[1600px] mx-auto pb-20 md:pb-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Network className="w-6 h-6 text-[#00F0FF]" />
          <div>
            <h2 className="font-mono text-xl font-black tracking-tighter text-[#E5E2E1] uppercase">Infrastructure Monitoring</h2>
            <p className="font-mono text-[10px] text-[#B9CACB] uppercase tracking-widest mt-1">Real-time infrastructure health and diagnostics</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <span className="text-xs font-mono block text-[#B9CACB]/50">{liveTime}</span>
            <span className="text-[10px] font-mono text-[#B9CACB]/30">Updates: {updateCount}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <RefreshCw size={12} className="text-[#00F0FF] animate-spin" />
            <span className="text-[10px] font-mono text-[#B9CACB]/50">LIVE 2s</span>
          </div>
        </div>
      </div>

      {/* Top Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-[#1C1B1B] p-4 border border-[#3B494B]/10 rounded-sm">
          <p className="text-[10px] font-bold text-[#B9CACB] uppercase tracking-tighter mb-1">System Uptime</p>
          <div className="font-mono text-xl font-black text-[#E5E2E1]">{formatUptime(current.system_info.uptime_seconds)}</div>
          <div className="text-[10px] font-mono text-[#40E56C] mt-1">v{current.system_info.version}</div>
        </div>
        <div className="bg-[#1C1B1B] p-4 border border-[#3B494B]/10 rounded-sm">
          <p className="text-[10px] font-bold text-[#B9CACB] uppercase tracking-tighter mb-1">Avg Latency</p>
          <div className="font-mono text-xl font-black text-[#00F0FF]">{rtt !== null ? `${rtt}ms` : "..."}</div>
          <div className="text-[10px] font-mono text-[#B9CACB] mt-1">Jitter: {jitter !== null ? `${jitter}ms` : "..."}</div>
        </div>
        <div className="bg-[#1C1B1B] p-4 border border-[#3B494B]/10 rounded-sm">
          <p className="text-[10px] font-bold text-[#B9CACB] uppercase tracking-tighter mb-1">Components</p>
          <div className="font-mono text-xl font-black text-[#E5E2E1]">{okCount}/{totalCount}</div>
          <div className="text-[10px] font-mono text-[#40E56C] mt-1">{okCount === totalCount ? "ALL HEALTHY" : "DEGRADED"}</div>
        </div>
        <div className="bg-[#1C1B1B] p-4 border border-[#3B494B]/10 rounded-sm">
          <p className="text-[10px] font-bold text-[#B9CACB] uppercase tracking-tighter mb-1">Data Freshness</p>
          <div className="font-mono text-xl font-black text-[#E5E2E1]">{(current.data_freshness.candle_count ?? 0).toLocaleString()}</div>
          <div className="text-[10px] font-mono text-[#B9CACB] mt-1">candles stored</div>
        </div>
      </div>

      {/* Overall Readiness */}
      <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-sm flex items-center justify-center" style={{ background: `${statusColor(overallStatus)}12`, border: `2px solid ${statusColor(overallStatus)}40` }}>
              {overallStatus === "ready" && <CheckCircle2 size={32} color="#40E56C" />}
              {overallStatus === "degraded" && <AlertTriangle size={32} color="#FFB3B6" />}
              {overallStatus === "offline" && <XCircle size={32} color="#FFB4AB" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-sm" style={{ background: statusColor(overallStatus), animation: "pulse 2s infinite" }} />
                <span className="font-mono text-xl font-black uppercase tracking-wide" style={{ color: statusColor(overallStatus) }}>
                  {overallStatus === "ready" ? "System Ready" : overallStatus === "degraded" ? "Partially Degraded" : "System Offline"}
                </span>
              </div>
              <p className="text-xs font-mono mt-1 text-[#B9CACB]/50">{okCount}/{totalCount} components healthy</p>
            </div>
          </div>
          <div className="text-right">
            <span className="text-[10px] font-mono block text-[#B9CACB]/30">Last update</span>
            <span className="text-sm font-mono font-semibold tabular-nums text-[#00F0FF]">{lastUpdate || "..."}</span>
          </div>
        </div>
      </div>

      {/* Core Modules + Kernel Log */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-[#1C1B1B] p-6 rounded-sm border border-[#3B494B]/10">
          <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase mb-6 flex items-center gap-2">
            <Server className="w-4 h-4 text-[#00F0FF]" />
            Core Modules
          </h3>
          <div className="space-y-3">
            {current.components.map((comp) => (
              <div key={comp.name} className="flex items-center justify-between p-3 bg-[#2A2A2A] rounded-sm border border-[#3B494B]/10">
                <div className="flex items-center gap-3">
                  <span style={{ color: statusColor(comp.status) }}>{componentIcon(comp.name)}</span>
                  <div>
                    <div className="font-mono text-xs font-bold text-[#E5E2E1] capitalize">{comp.name.replace("_", " ")}</div>
                    <div className="font-mono text-[9px] uppercase" style={{ color: statusColor(comp.status) }}>{comp.message}</div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    {comp.latency_ms !== null && (
                      <div className="font-mono text-[10px] font-semibold tabular-nums" style={{ color: comp.latency_ms < 50 ? "#40E56C" : comp.latency_ms < 200 ? "#FFB3B6" : "#FFB4AB" }}>
                        {comp.latency_ms}ms
                      </div>
                    )}
                    {Object.entries(comp.details).slice(0, 1).map(([key, val]) => (
                      <div key={key} className="font-mono text-[10px] text-[#B9CACB]/40">{key.replace(/_/g, " ")}: {String(val)}</div>
                    ))}
                  </div>
                  {latencyHistory[comp.name] && latencyHistory[comp.name].length > 1 && (
                    <Sparkline data={latencyHistory[comp.name]} color={statusColor(comp.status)} width={80} height={24} />
                  )}
                  {statusIcon(comp.status)}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-[#1C1B1B] p-6 rounded-sm border border-[#3B494B]/10 flex flex-col">
          <h3 className="font-mono text-xs font-black tracking-widest text-[#E5E2E1] uppercase mb-4 flex items-center gap-2">
            <Terminal className="w-4 h-4 text-[#00F0FF]" />
            Kernel Event Log
          </h3>
          <div className="flex-1 bg-[#0A0A0A] p-4 rounded-sm font-mono text-[10px] overflow-y-auto h-64 border border-[#3B494B]/10">
            <div className="text-[#849495] mb-2">CQ Engine v{current.system_info.version} initialized.</div>
            {current.components.map((comp) => (
              <div key={comp.name} className="mb-1" style={{ color: statusColor(comp.status) }}>
                [{comp.status === "ok" ? "SYS" : "WARN"}] {comp.name.replace("_", " ")} — {comp.message}
                {comp.latency_ms !== null && ` (${comp.latency_ms}ms)`}
              </div>
            ))}
            <div className="text-[#00F0FF] mb-1">[NET] WebSocket: {wsConnected ? "Connected" : "Disconnected"}</div>
            <div className="text-[#B9CACB]/50 mb-1">[NET] RTT: {rtt !== null ? `${rtt}ms` : "measuring..."} | Jitter: {jitter !== null ? `${jitter}ms` : "..."}</div>
            <div className="text-[#40E56C] mb-1">[SYS] Trading: {current.system_info.trading_enabled ? "ENABLED" : "DISABLED"}</div>
            <div className="text-[#B9CACB]/50 mb-1">[DATA] Candles: {(current.data_freshness.candle_count ?? 0).toLocaleString()} | Signals: {(current.data_freshness.signal_count ?? 0).toLocaleString()}</div>
            <div className="text-[#849495] mb-1">[SYS] Environment: {current.system_info.environment} | Python: {current.system_info.python_version}</div>
            <div className="text-[#40E56C] mb-1">[SYS] System ready. Awaiting signals.</div>
            <div className="text-[#B9CACB]/30 mb-1 animate-pulse">_</div>
          </div>
        </section>
      </div>

      {/* Network + WebSocket */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-4">
          <h4 className="text-[11px] font-mono font-semibold uppercase tracking-widest text-[#B9CACB]/50 mb-3">Network Performance</h4>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-widest block text-[#B9CACB]/40">Round-Trip Time (RTT)</span>
                <span className="text-2xl font-mono font-semibold tabular-nums" style={{ color: rtt !== null ? (rtt < 50 ? "#40E56C" : rtt < 200 ? "#FFB3B6" : "#FFB4AB") : "#B9CACB" }}>
                  {rtt !== null ? `${rtt}ms` : "measuring..."}
                </span>
              </div>
              <div className="text-right">
                <span className="text-[10px] font-mono uppercase tracking-widest block text-[#B9CACB]/40">Jitter</span>
                <span className="text-lg font-mono font-semibold tabular-nums" style={{ color: jitter !== null ? (jitter < 10 ? "#40E56C" : jitter < 50 ? "#FFB3B6" : "#FFB4AB") : "#B9CACB" }}>
                  {jitter !== null ? `${jitter}ms` : "..."}
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between text-[10px] font-mono text-[#B9CACB]/30">
              <span>Samples: {rttHistory.length}/{LATENCY_HISTORY_MAX}</span>
              <span>Interval: {PING_INTERVAL / 1000}s | {PING_COUNT} pings/sample</span>
            </div>
            {rttHistory.length > 1 && <Sparkline data={rttHistory} color="#00F0FF" height={40} width={500} />}
          </div>
        </div>

        <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-4">
          <h4 className="text-[11px] font-mono font-semibold uppercase tracking-widest text-[#B9CACB]/50 mb-3">WebSocket Connection</h4>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-sm flex items-center justify-center" style={{ background: wsConnected ? "rgba(64,229,108,0.12)" : "rgba(255,180,171,0.12)", border: `1px solid ${wsConnected ? "rgba(64,229,108,0.25)" : "rgba(255,180,171,0.25)"}` }}>
                {wsConnected ? <Wifi size={22} color="#40E56C" /> : <WifiOff size={22} color="#FFB4AB" />}
              </div>
              <div>
                <span className="text-lg font-semibold font-mono" style={{ color: wsConnected ? "#40E56C" : "#FFB4AB" }}>{wsConnected ? "Connected" : "Disconnected"}</span>
                <p className="text-[10px] font-mono text-[#B9CACB]/40">Heartbeat interval: 30s | Timeout: 10s</p>
              </div>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-[#B9CACB]/40">Server WS Connections</span>
                <span className="text-sm font-mono tabular-nums text-[#E5E2E1]/80">{String(current.components.find((c) => c.name === "websocket")?.details?.active_connections ?? 0)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-[#B9CACB]/40">Real-time Feed</span>
                <span className="text-[10px] font-mono" style={{ color: status ? "#40E56C" : "#FFB3B6" }}>{status ? "Receiving system_status events" : "Waiting for first push..."}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-[#B9CACB]/40">Protocol</span>
                <span className="text-[10px] font-mono text-[#B9CACB]/60">WS + JSON | Auto-reconnect with backoff</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Data Freshness */}
      <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-4">
        <h4 className="text-[11px] font-mono font-semibold uppercase tracking-widest text-[#B9CACB]/50 mb-3">Data Freshness</h4>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40">Total Candles</span>
            <p className="text-2xl font-mono font-semibold tabular-nums mt-1 text-[#E5E2E1]">{(current.data_freshness.candle_count ?? 0).toLocaleString()}</p>
          </div>
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40">Total Signals</span>
            <p className="text-2xl font-mono font-semibold tabular-nums mt-1 text-[#E5E2E1]">{(current.data_freshness.signal_count ?? 0).toLocaleString()}</p>
          </div>
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40">Last Candle</span>
            <p className="text-sm font-mono mt-1" style={{ color: current.data_freshness.candle_age_seconds !== null && current.data_freshness.candle_age_seconds < 7200 ? "#40E56C" : "#FFB3B6" }}>
              {formatAge(current.data_freshness.candle_age_seconds)}
            </p>
          </div>
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40">Last Signal</span>
            <p className="text-sm font-mono mt-1 text-[#B9CACB]/70">{formatAge(current.data_freshness.signal_age_seconds)}</p>
          </div>
        </div>
      </div>

      {/* System Information */}
      <div className="bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-4">
        <h4 className="text-[11px] font-mono font-semibold uppercase tracking-widest text-[#B9CACB]/50 mb-3">System Information</h4>
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-6">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40">Uptime</span>
            <p className="text-sm font-mono font-semibold mt-1 tabular-nums text-[#E5E2E1]">{formatUptime(current.system_info.uptime_seconds)}</p>
          </div>
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40">Version</span>
            <p className="text-sm font-mono font-semibold mt-1 text-[#E5E2E1]">v{current.system_info.version}</p>
          </div>
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40">Environment</span>
            <p className="mt-1">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] font-mono font-semibold uppercase" style={{
                background: current.system_info.environment === "live" ? "rgba(255,180,171,0.12)" : "rgba(0,240,255,0.12)",
                color: current.system_info.environment === "live" ? "#FFB4AB" : "#00F0FF",
                border: `1px solid ${current.system_info.environment === "live" ? "rgba(255,180,171,0.25)" : "rgba(0,240,255,0.25)"}`,
              }}>{current.system_info.environment}</span>
            </p>
          </div>
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40">Python</span>
            <p className="text-sm font-mono font-semibold mt-1 text-[#E5E2E1]">{current.system_info.python_version}</p>
          </div>
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#B9CACB]/40">Trading</span>
            <p className="mt-1 flex items-center gap-1.5">
              <Shield size={14} color={current.system_info.trading_enabled ? "#40E56C" : "#FFB4AB"} />
              <span className="text-xs font-mono font-semibold" style={{ color: current.system_info.trading_enabled ? "#40E56C" : "#FFB4AB" }}>
                {current.system_info.trading_enabled ? "ENABLED" : "DISABLED"}
              </span>
            </p>
          </div>
        </div>
        {current.system_info.started_at && (
          <div className="mt-3 pt-3 border-t border-[#3B494B]/10 flex items-center gap-2">
            <Clock size={12} className="text-[#B9CACB]/40" />
            <span className="text-[10px] font-mono text-[#B9CACB]/40">Started: {new Date(current.system_info.started_at).toLocaleString()}</span>
          </div>
        )}
      </div>

      {/* Live Update Bar */}
      <div className="flex items-center justify-between px-4 py-2 rounded-sm bg-[#1C1B1B] border border-[#3B494B]/10">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-sm" style={{ background: wsConnected ? "#40E56C" : "#FFB4AB", animation: wsConnected ? "pulse 2s infinite" : "none" }} />
          <span className="text-[10px] font-mono text-[#B9CACB]/40">{wsConnected ? "Receiving real-time updates via WebSocket" : "WebSocket disconnected — reconnecting..."}</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-[10px] font-mono tabular-nums text-[#B9CACB]/30">Last: {lastUpdate}</span>
          <span className="text-[10px] font-mono tabular-nums text-[#B9CACB]/30">RTT: {rtt !== null ? `${rtt}ms` : "..."}</span>
          <span className="text-[10px] font-mono tabular-nums text-[#B9CACB]/30">Jitter: {jitter !== null ? `${jitter}ms` : "..."}</span>
        </div>
      </div>
    </div>
  );
}
