"use client";

import { type ReactNode } from "react";

export interface Column<T> {
  key: string;
  label: string;
  render?: (row: T) => ReactNode;
  align?: "left" | "center" | "right";
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T, index: number) => void;
  emptyMessage?: string;
  className?: string;
}

function looksNumeric(value: unknown): boolean {
  if (typeof value === "number") return true;
  if (typeof value !== "string") return false;
  return /^[\s$\-+%]?\d/.test(value);
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  onRowClick,
  emptyMessage = "No data available",
  className = "",
}: DataTableProps<T>) {
  return (
    <div className={`bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm overflow-hidden ${className}`}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[540px] border-collapse">
          {/* Header */}
          <thead>
            <tr className="border-b border-[#2A2A2A]/20">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`
                    px-4 py-3 text-[10px] font-mono font-semibold uppercase tracking-widest
                    text-[#B9CACB]/60 bg-[#201F1F]/50
                    ${col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"}
                  `}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>

          {/* Body */}
          <tbody className="divide-y divide-[#2A2A2A]/5">
            {data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-12 text-center text-sm text-[#B9CACB]/40"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((row, rowIndex) => (
                <tr
                  key={rowIndex}
                  onClick={() => onRowClick?.(row, rowIndex)}
                  className={`
                    transition-colors duration-150
                    ${onRowClick ? "cursor-pointer" : ""}
                    hover:bg-[#2A2A2A]/40
                  `}
                >
                  {columns.map((col) => {
                    const rawValue = row[col.key];
                    const rendered = col.render ? col.render(row) : String(rawValue ?? "");
                    const isNumeric = !col.render && looksNumeric(rawValue);

                    return (
                      <td
                        key={col.key}
                        className={`
                          px-4 py-3 text-[13px] text-[#E5E2E1]/85
                          ${isNumeric ? "font-mono tabular-nums" : ""}
                          ${col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"}
                        `}
                      >
                        {rendered}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
