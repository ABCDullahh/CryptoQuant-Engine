"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Activity,
  Bot,
  Wallet,
  Landmark,
  LineChart,
  TrendingUp,
  History,
  Settings,
  Network,
} from "lucide-react";

const MAIN_NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/signals", label: "Signals", icon: Activity },
  { href: "/bot", label: "Bot Manager", icon: Bot },
  { href: "/positions", label: "Positions", icon: Wallet },
  { href: "/wallet", label: "Wallet", icon: Landmark },
  { href: "/analytics", label: "Analytics", icon: LineChart },
  { href: "/chart", label: "Chart", icon: TrendingUp },
  { href: "/backtest", label: "Backtest", icon: History },
];

const BOTTOM_NAV = [
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/system", label: "System Status", icon: Network },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [systemStatus, setSystemStatus] = useState<"online" | "offline">("offline");

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch("/health");
        setSystemStatus(res.ok ? "online" : "offline");
      } catch {
        setSystemStatus("offline");
      }
    };
    check();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, []);

  const renderNavItem = (item: typeof MAIN_NAV[0]) => {
    const Icon = item.icon;
    const isActive = pathname === item.href;
    return (
      <Link
        key={item.href}
        href={item.href}
        className={`flex items-center gap-3 px-3 py-2 font-body text-[13px] font-medium transition-all duration-150 rounded-sm w-full text-left
          ${isActive
            ? "text-[#00F0FF] bg-[#201F1F] border-r-2 border-[#00F0FF] translate-x-1"
            : "text-[#E5E2E1]/60 hover:text-[#E5E2E1] hover:bg-[#161616]"
          }`}
      >
        <Icon className="w-5 h-5" />
        <span>{item.label}</span>
      </Link>
    );
  };

  return (
    <aside className="hidden md:flex flex-col h-screen w-64 border-r border-[#2A2A2A]/10 bg-[#0D0D0D] py-4 gap-1 shrink-0">
      {/* Logo */}
      <div className="px-6 mb-8">
        <h1 className="font-mono font-black text-[#00F0FF] text-xl">CQ Engine</h1>
        <span className="text-[10px] font-mono text-[#B9CACB]/50 tracking-widest uppercase">
          v2.0 Terminal
        </span>
      </div>

      {/* Main Navigation */}
      <nav className="flex flex-col gap-1 px-3 flex-1 overflow-y-auto no-scrollbar">
        {MAIN_NAV.map(renderNavItem)}

        {/* Bottom Navigation */}
        <div className="mt-auto pt-4 flex flex-col gap-1 border-t border-[#2A2A2A]/10">
          {BOTTOM_NAV.map(renderNavItem)}

          {/* System Status Indicator */}
          <div className="px-3 pt-3 flex items-center gap-2">
            <div
              className="w-2 h-2 rounded-full animate-pulse-dot"
              style={{
                background: systemStatus === "online" ? "#40E56C" : "#FFB4AB",
                boxShadow: systemStatus === "online"
                  ? "0 0 8px rgba(64, 229, 108, 0.6)"
                  : "0 0 8px rgba(255, 180, 171, 0.6)",
              }}
            />
            <span className="text-[10px] font-mono text-[#B9CACB]/50 tracking-widest uppercase">
              {systemStatus === "online" ? "System Online" : "Offline"}
            </span>
          </div>
        </div>
      </nav>
    </aside>
  );
}
