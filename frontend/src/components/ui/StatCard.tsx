"use client";

import { type ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string;
  change?: number;
  icon?: ReactNode;
  prefix?: string;
  className?: string;
  /** Color for the left border accent */
  accentColor?: string;
}

function formatChange(change: number): string {
  const sign = change >= 0 ? "+" : "";
  return `${sign}${change.toFixed(2)}%`;
}

export function StatCard({
  label,
  value,
  change,
  icon,
  prefix,
  className = "",
  accentColor,
}: StatCardProps) {
  const changeColor =
    change === undefined
      ? ""
      : change >= 0
        ? "text-[#40E56C]"
        : "text-[#FFB4AB]";

  const changeBg =
    change === undefined
      ? ""
      : change >= 0
        ? "bg-[#40E56C]/10"
        : "bg-[#FFB4AB]/10";

  return (
    <div
      className={`
        bg-[#201F1F] border border-[#3B494B]/10 rounded-sm p-4
        transition-colors duration-150
        ${accentColor ? `border-l-2` : ""}
        ${className}
      `}
      style={accentColor ? { borderLeftColor: accentColor } : undefined}
    >
      {/* Header row: label + icon */}
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10px] font-mono font-medium uppercase tracking-widest text-[#B9CACB]">
          {label}
        </span>
        {icon && (
          <span className="text-[#00F0FF]/60">{icon}</span>
        )}
      </div>

      {/* Value */}
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-xl font-black tracking-tight text-[#E5E2E1] tabular-nums">
          {prefix && (
            <span className="mr-0.5 text-base text-[#B9CACB]">
              {prefix}
            </span>
          )}
          {value}
        </span>
      </div>

      {/* Change indicator */}
      {change !== undefined && (
        <div className="mt-2">
          <span
            className={`
              inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5
              font-mono text-[10px] font-medium tabular-nums
              ${changeColor} ${changeBg}
            `}
          >
            <span className="text-[0.65rem]">
              {change >= 0 ? "\u25B2" : "\u25BC"}
            </span>
            {formatChange(change)}
          </span>
        </div>
      )}
    </div>
  );
}
