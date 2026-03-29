// =============================================================================
// CryptoQuant Engine - Utility Functions
// =============================================================================

// ---------------------------------------------------------------------------
// Number formatting
// ---------------------------------------------------------------------------

/**
 * Format a price with dollar sign and smart decimal places.
 * Automatically adjusts decimals based on price magnitude so sub-dollar
 * altcoins don't display as "$0.00".
 *
 * @example formatPrice(43250.5)      => "$43,250.50"
 * @example formatPrice(0.00012345)   => "$0.000123"
 * @example formatPrice(0.85)         => "$0.8500"
 */
export function formatPrice(price: number, decimals?: number): string {
  const d = decimals ?? (
    price === 0 ? 2 :
    Math.abs(price) >= 1 ? 2 :
    Math.abs(price) >= 0.01 ? 4 :
    6
  );
  return "$" + price.toLocaleString("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

/**
 * Format a PnL value with sign and dollar symbol.
 * @example formatPnl(150)   => "+$150.00"
 * @example formatPnl(-50)   => "-$50.00"
 * @example formatPnl(0)     => "$0.00"
 */
export function formatPnl(pnl: number): string {
  const abs = Math.abs(pnl);
  const formatted = abs.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  if (pnl > 0) return "+$" + formatted;
  if (pnl < 0) return "-$" + formatted;
  return "$" + formatted;
}

/**
 * Format a percentage value with sign.
 * @example formatPercent(2.5)   => "+2.50%"
 * @example formatPercent(-1.2)  => "-1.20%"
 * @example formatPercent(0)     => "0.00%"
 */
export function formatPercent(pct: number): string {
  const abs = Math.abs(pct);
  const formatted = abs.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  if (pct > 0) return "+" + formatted + "%";
  if (pct < 0) return "-" + formatted + "%";
  return formatted + "%";
}

/**
 * Format a number with thousand separators.
 * @example formatNumber(1250)    => "1,250"
 * @example formatNumber(1000000) => "1,000,000"
 */
export function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

// ---------------------------------------------------------------------------
// Class name merger
// ---------------------------------------------------------------------------

/**
 * Merge CSS class names, filtering out falsy values.
 * @example cn("base", isActive && "active", undefined, "end") => "base active end"
 */
export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

// ---------------------------------------------------------------------------
// Time formatting
// ---------------------------------------------------------------------------

/**
 * Return a human-readable relative time string.
 * @example timeAgo("2024-01-01T12:00:00Z") => "5m ago"
 */
export function timeAgo(date: string): string {
  const now = Date.now();
  const then = new Date(date).getTime();
  const diffMs = now - then;

  if (diffMs < 0) return "just now";

  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  const weeks = Math.floor(days / 7);
  const months = Math.floor(days / 30);

  if (seconds < 60) return `${seconds}s ago`;
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  if (weeks < 5) return `${weeks}w ago`;
  return `${months}mo ago`;
}

// ---------------------------------------------------------------------------
// Signal grade colors
// ---------------------------------------------------------------------------

/**
 * Returns a CSS color variable name (or Tailwind-friendly class hint) for
 * signal grades A through D.
 *
 * Intended usage with CSS custom properties:
 *   style={{ color: `var(${gradeColor("A")})` }}
 *
 * Or map to Tailwind classes in the component layer.
 */
export function gradeColor(grade: string): string {
  switch (grade.toUpperCase()) {
    case "A":
      return "--color-grade-a";
    case "B":
      return "--color-grade-b";
    case "C":
      return "--color-grade-c";
    case "D":
      return "--color-grade-d";
    default:
      return "--color-grade-default";
  }
}
