"use client";

export function ObsidianTooltip({
  active,
  payload,
  label,
  formatter,
}: {
  active?: boolean;
  payload?: Array<{
    value: number;
    name: string;
    color: string;
    dataKey: string;
  }>;
  label?: string;
  formatter?: (value: number, name: string) => [string, string];
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="bg-[#1C1B1B] border border-[#3B494B]/40 rounded-sm px-3 py-2 shadow-lg">
      {label && (
        <p className="font-mono text-[10px] text-[#B9CACB] mb-1">{label}</p>
      )}
      {payload.map((entry, i) => {
        const [val, name] = formatter
          ? formatter(entry.value, entry.name)
          : [String(entry.value), entry.name];
        return (
          <p
            key={i}
            className="font-mono text-xs font-bold tabular-nums"
            style={{ color: entry.color || "#00F0FF" }}
          >
            {name}: {val}
          </p>
        );
      })}
    </div>
  );
}
