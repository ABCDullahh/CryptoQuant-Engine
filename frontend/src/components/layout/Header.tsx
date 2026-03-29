"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bell,
  Wifi,
  WifiOff,
  TrendingUp,
  TrendingDown,
  Zap,
  AlertTriangle,
  Play,
  Square,
  Pause,
  X,
} from "lucide-react";
import { wsManager } from "@/lib/websocket";
import { useWebSocket } from "@/hooks/useApi";
import type { Signal, Position, BotStatus as BotStatusType } from "@/lib/api";

// =============================================================================
// Notification Types
// =============================================================================
interface Notification {
  id: string;
  type: "signal" | "position" | "bot" | "error";
  title: string;
  message: string;
  color: string;
  icon: "signal" | "position_open" | "position_close" | "bot_start" | "bot_stop" | "bot_pause" | "error";
  timestamp: number;
  read: boolean;
}

function getNotificationIcon(icon: Notification["icon"]) {
  switch (icon) {
    case "signal":
      return <Zap size={14} />;
    case "position_open":
      return <TrendingUp size={14} />;
    case "position_close":
      return <TrendingDown size={14} />;
    case "bot_start":
      return <Play size={14} />;
    case "bot_stop":
      return <Square size={14} />;
    case "bot_pause":
      return <Pause size={14} />;
    case "error":
      return <AlertTriangle size={14} />;
  }
}

function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

const MAX_NOTIFICATIONS = 50;
const AUTO_DISMISS_MS = 24 * 60 * 60 * 1000; // 24h

// =============================================================================
// Header
// =============================================================================
interface HeaderBotStatus {
  status: string;
  paper_mode: boolean;
  active_strategies: string[];
  total_pnl: number;
}

export default function Header() {
  const [botStatus, setBotStatus] = useState<HeaderBotStatus | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [currentTime, setCurrentTime] = useState("");
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [showPanel, setShowPanel] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const bellRef = useRef<HTMLButtonElement>(null);

  // --- Notification helpers ---
  const addNotification = useCallback((notif: Omit<Notification, "id" | "timestamp" | "read">) => {
    setNotifications((prev) => {
      const now = Date.now();
      // Remove old (>24h) and trim to max
      const filtered = prev
        .filter((n) => now - n.timestamp < AUTO_DISMISS_MS)
        .slice(0, MAX_NOTIFICATIONS - 1);
      return [
        { ...notif, id: `${now}-${Math.random().toString(36).slice(2, 6)}`, timestamp: now, read: false },
        ...filtered,
      ];
    });
  }, []);

  const markAllRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  // --- WebSocket event handlers ---
  useWebSocket(
    "signal_new",
    useCallback(
      (data: Signal) => {
        const dir = data.direction === "LONG" ? "LONG" : "SHORT";
        addNotification({
          type: "signal",
          title: `New Signal: ${data.symbol}`,
          message: `${dir} ${data.signal_grade}-grade @ $${data.entry_price?.toFixed(2) ?? "—"}`,
          color: data.direction === "LONG" ? "#40E56C" : "#FFB4AB",
          icon: "signal",
        });
      },
      [addNotification]
    )
  );

  useWebSocket(
    "position_update",
    useCallback(
      (data: Position) => {
        if (data.status === "CLOSED") {
          const pnl = data.realized_pnl ?? 0;
          const pnlStr = pnl >= 0 ? `+$${pnl.toFixed(2)}` : `-$${Math.abs(pnl).toFixed(2)}`;
          addNotification({
            type: "position",
            title: `Position Closed: ${data.symbol}`,
            message: `${data.direction} closed — P&L: ${pnlStr}${data.close_reason ? ` (${data.close_reason})` : ""}`,
            color: pnl >= 0 ? "#40E56C" : "#FFB4AB",
            icon: "position_close",
          });
        } else if (data.status === "OPEN") {
          addNotification({
            type: "position",
            title: `Position Opened: ${data.symbol}`,
            message: `${data.direction} @ $${data.entry_price?.toFixed(2) ?? "—"} | ${data.leverage}x`,
            color: "#00F0FF",
            icon: "position_open",
          });
        }
      },
      [addNotification]
    )
  );

  useWebSocket(
    "bot_status",
    useCallback(
      (data: BotStatusType) => {
        const status = data.status;
        if (status === "RUNNING") {
          addNotification({
            type: "bot",
            title: "Bot Started",
            message: `Trading engine is now running${data.paper_mode ? " (paper mode)" : ""}`,
            color: "#40E56C",
            icon: "bot_start",
          });
        } else if (status === "STOPPED") {
          addNotification({
            type: "bot",
            title: "Bot Stopped",
            message: "Trading engine has stopped",
            color: "#B9CACB",
            icon: "bot_stop",
          });
        } else if (status === "PAUSED") {
          addNotification({
            type: "bot",
            title: "Bot Paused",
            message: "Trading engine is paused",
            color: "#FFB3B6",
            icon: "bot_pause",
          });
        }
      },
      [addNotification]
    )
  );

  useWebSocket(
    "error",
    useCallback(
      (data: { message: string }) => {
        addNotification({
          type: "error",
          title: "Error",
          message: data.message,
          color: "#FFB4AB",
          icon: "error",
        });
      },
      [addNotification]
    )
  );

  // --- Click outside to close ---
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (
        showPanel &&
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        bellRef.current &&
        !bellRef.current.contains(e.target as Node)
      ) {
        setShowPanel(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showPanel]);

  // --- Bot status polling ---
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const token = localStorage.getItem("token");
        const res = await fetch("/api/bot/status", {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) setBotStatus(await res.json());
      } catch {
        // Bot status fetch failed
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  // --- WS connection check ---
  useEffect(() => {
    const checkWs = () => setWsConnected(wsManager.connected);
    checkWs();
    const interval = setInterval(checkWs, 2000);
    wsManager.connect();
    return () => clearInterval(interval);
  }, []);

  // --- Clock ---
  useEffect(() => {
    const tick = () => {
      setCurrentTime(
        new Date().toLocaleTimeString("en-US", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  const statusColor =
    botStatus?.status === "RUNNING"
      ? "#40E56C"
      : botStatus?.status === "PAUSED"
        ? "#FFB3B6"
        : "#849495";

  return (
    <header className="flex justify-between items-center w-full px-6 h-14 bg-[#131313] border-b border-[#2A2A2A]/10 shrink-0">
      {/* Left — Status */}
      <div className="flex items-center gap-8">
        <span className="font-mono font-bold text-lg text-[#00F0FF] tracking-tighter md:hidden">
          CQ
        </span>

        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full animate-pulse"
            style={{
              background: statusColor,
              boxShadow:
                botStatus?.status === "RUNNING"
                  ? "0 0 8px rgba(64, 229, 108, 0.6)"
                  : undefined,
            }}
          />
          <span
            className="font-body font-bold text-xs tracking-tight"
            style={{ color: statusColor }}
          >
            {botStatus?.status || "OFFLINE"}
          </span>
          {botStatus?.paper_mode && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-sm bg-[#FFB3B6]/10 text-[#FFB3B6] border border-[#FFB3B6]/20">
              PAPER
            </span>
          )}
        </div>

        <div className="hidden sm:flex items-center gap-4 text-[#E5E2E1]/50 font-body font-medium text-xs tracking-tight">
          <div className="flex items-center gap-1.5">
            {wsConnected ? (
              <Wifi size={12} className="text-[#40E56C]" />
            ) : (
              <WifiOff size={12} className="text-[#FFB4AB]" />
            )}
            <span>{wsConnected ? "Connected" : "Offline"}</span>
          </div>
          <span className="font-mono text-[11px]">{currentTime}</span>
        </div>
      </div>

      {/* Right — Actions */}
      <div className="flex items-center gap-4">
        {/* Notification Bell */}
        <div className="relative">
          <button
            ref={bellRef}
            onClick={() => {
              setShowPanel((prev) => !prev);
              if (!showPanel) markAllRead();
            }}
            className="w-8 h-8 flex items-center justify-center rounded-sm hover:bg-[#201F1F] transition-colors duration-150 text-[#B9CACB] hover:text-[#E5E2E1] relative"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 flex items-center justify-center rounded-full bg-[#00F0FF] text-[#0D0D0D] text-[9px] font-mono font-black px-1">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </button>

          {/* Notification Panel */}
          {showPanel && (
            <div
              ref={panelRef}
              className="absolute right-0 top-10 w-80 max-h-96 bg-[#1C1B1B] border border-[#3B494B]/30 rounded-sm shadow-2xl z-50 flex flex-col overflow-hidden"
            >
              {/* Panel Header */}
              <div className="flex items-center justify-between px-3 py-2 border-b border-[#2A2A2A]/30">
                <span className="font-mono text-[10px] font-black tracking-widest text-[#B9CACB] uppercase">
                  Notifications
                </span>
                <div className="flex items-center gap-2">
                  {notifications.length > 0 && (
                    <button
                      onClick={clearAll}
                      className="text-[9px] font-mono text-[#B9CACB]/50 hover:text-[#FFB4AB] transition-colors"
                    >
                      Clear all
                    </button>
                  )}
                  <button
                    onClick={() => setShowPanel(false)}
                    className="text-[#B9CACB]/50 hover:text-[#E5E2E1] transition-colors"
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>

              {/* Notification List */}
              <div className="overflow-y-auto flex-1">
                {notifications.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-10 text-[#B9CACB]/30">
                    <Bell size={24} className="mb-2" />
                    <span className="font-mono text-xs">No notifications</span>
                  </div>
                ) : (
                  notifications.map((notif) => (
                    <div
                      key={notif.id}
                      className="flex gap-2.5 px-3 py-2.5 border-b border-[#2A2A2A]/15 hover:bg-[#201F1F] transition-colors"
                    >
                      {/* Icon */}
                      <div
                        className="w-7 h-7 rounded-sm flex items-center justify-center shrink-0 mt-0.5"
                        style={{
                          backgroundColor: `${notif.color}15`,
                          color: notif.color,
                        }}
                      >
                        {getNotificationIcon(notif.icon)}
                      </div>
                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-[11px] font-bold text-[#E5E2E1] truncate">
                            {notif.title}
                          </span>
                          {!notif.read && (
                            <span className="w-1.5 h-1.5 rounded-full bg-[#00F0FF] shrink-0" />
                          )}
                        </div>
                        <p className="font-mono text-[10px] text-[#B9CACB]/70 truncate mt-0.5">
                          {notif.message}
                        </p>
                        <span className="font-mono text-[9px] text-[#B9CACB]/40 mt-0.5 block">
                          {timeAgo(notif.timestamp)}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 pl-4 border-l border-[#2A2A2A]/10">
          <div className="w-8 h-8 bg-[#353534] rounded-sm flex items-center justify-center text-[10px] font-bold text-[#00F0FF] border border-[#3B494B]/20">
            TQ
          </div>
        </div>
      </div>
    </header>
  );
}
