"use client";

import { type ReactNode } from "react";

type CardPadding = "none" | "sm" | "md" | "lg";

interface CardProps {
  title?: string;
  children: ReactNode;
  className?: string;
  padding?: CardPadding;
  headerRight?: ReactNode;
}

const paddingClasses: Record<CardPadding, string> = {
  none: "p-0",
  sm: "p-3",
  md: "p-5",
  lg: "p-7",
};

export function Card({
  title,
  children,
  className = "",
  padding = "md",
  headerRight,
}: CardProps) {
  return (
    <div
      className={`
        bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm
        transition-colors duration-150
        hover:border-[#00F0FF]/8
        ${paddingClasses[padding]}
        ${className}
      `}
    >
      {title && (
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-[11px] font-semibold uppercase tracking-widest text-[#B9CACB]">
            {title}
          </h3>
          {headerRight && <div>{headerRight}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
