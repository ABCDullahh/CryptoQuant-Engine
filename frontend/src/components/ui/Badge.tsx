"use client";

import { type ReactNode } from "react";

type Grade = "A" | "B" | "C" | "D";
type BadgeSize = "sm" | "md" | "lg";

interface GradeBadgeProps {
  grade: Grade;
  size?: BadgeSize;
  className?: string;
}

const gradeStyles: Record<Grade, string> = {
  A: "bg-[#00F0FF]/10 text-[#00F0FF] border-[#00F0FF]/20",
  B: "bg-[#40E56C]/10 text-[#40E56C] border-[#40E56C]/20",
  C: "bg-[#FFB3B6]/10 text-[#FFB3B6] border-[#FFB3B6]/20",
  D: "bg-[#849495]/10 text-[#849495] border-[#849495]/20",
};

const sizeClasses: Record<BadgeSize, string> = {
  sm: "px-1.5 py-0.5 text-[10px]",
  md: "px-2 py-0.5 text-[10px]",
  lg: "px-3 py-1 text-xs",
};

export function GradeBadge({ grade, size = "md", className = "" }: GradeBadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center gap-1 rounded-sm border font-mono font-semibold
        uppercase tracking-wider
        ${gradeStyles[grade]}
        ${sizeClasses[size]}
        ${className}
      `}
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "currentColor" }} />
      {grade}
    </span>
  );
}

type Direction = "LONG" | "SHORT";

interface DirectionBadgeProps {
  direction: Direction;
  size?: BadgeSize;
  className?: string;
  children?: ReactNode;
}

const directionStyles: Record<Direction, string> = {
  LONG: "bg-[#40E56C]/10 text-[#40E56C] border-[#40E56C]/20",
  SHORT: "bg-[#FFB4AB]/10 text-[#FFB4AB] border-[#FFB4AB]/20",
};

const directionIcons: Record<Direction, string> = {
  LONG: "\u25B2",
  SHORT: "\u25BC",
};

export function DirectionBadge({
  direction,
  size = "md",
  className = "",
  children,
}: DirectionBadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center gap-1 rounded-sm border font-mono font-semibold
        uppercase tracking-wider
        ${directionStyles[direction]}
        ${sizeClasses[size]}
        ${className}
      `}
    >
      <span className="text-[0.7em]">{directionIcons[direction]}</span>
      {children ?? direction}
    </span>
  );
}
