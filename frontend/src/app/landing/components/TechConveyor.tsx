"use client";

/* ══════════════════════════════════════════════
   TechConveyor — Infinite horizontal conveyor belt
   Two rows, opposite directions, inline SVG icons
   Seamless loop with edge fade overlays
   ══════════════════════════════════════════════ */

interface TechItem {
  name: string;
  icon: React.ReactNode;
}

const C = "#B9CACB";

const ROW_1: TechItem[] = [
  {
    name: "Python",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={C} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2c-1.7 0-3 .5-3.8 1.2C7.5 3.8 7.2 4.8 7.2 6v2.2H12v.8H5.2c-1.2 0-2.3.7-2.8 1.8-.6 1.3-.6 2.7 0 4 .4 1 1.4 1.7 2.6 1.7H6.8V14c0-1.4 1.2-2.6 2.6-2.6h4.8c1.1 0 2-.9 2-2V6c0-1.1-.8-2-1.8-2.6C13.8 2.2 12.8 2 12 2zM9.4 4.2a.9.9 0 110 1.8.9.9 0 010-1.8z" />
        <path d="M12 22c1.7 0 3-.5 3.8-1.2.7-.6 1-1.6 1-3V15.6H12v-.8h6.8c1.2 0 2.3-.7 2.8-1.8.6-1.3.6-2.7 0-4-.4-1-1.4-1.7-2.6-1.7H17.2V10c0 1.4-1.2 2.6-2.6 2.6H9.8c-1.1 0-2 .9-2 2V18c0 1.1.8 2 1.8 2.6.6 1.2 1.6 1.4 2.4 1.4zM14.6 19.8a.9.9 0 110-1.8.9.9 0 010 1.8z" />
      </svg>
    ),
  },
  {
    name: "FastAPI",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill={C}>
        <path d="M13 2L3 14h9l-1 10 10-12h-9l1-10z" />
      </svg>
    ),
  },
  {
    name: "SQLAlchemy",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <rect x="2" y="2" width="20" height="20" rx="4" stroke={C} strokeWidth="1.5"/>
        <text x="12" y="16" textAnchor="middle" fill={C} fontSize="10" fontWeight="bold" fontFamily="monospace">SA</text>
      </svg>
    ),
  },
  {
    name: "TimescaleDB",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={C} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <polyline points="12 6 12 12 16 14" />
        <rect x="10" y="16" width="2" height="3" fill={C} stroke="none" rx="0.5" />
        <rect x="13" y="15" width="2" height="4" fill={C} stroke="none" rx="0.5" />
        <rect x="7" y="17" width="2" height="2" fill={C} stroke="none" rx="0.5" />
      </svg>
    ),
  },
  {
    name: "Redis",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={C} strokeWidth="1.5" strokeLinejoin="round">
        <path d="M12 2L3 8l9 6 9-6-9-6z" />
        <path d="M3 8v8l9 6 9-6V8" />
        <path d="M3 12l9 6 9-6" />
      </svg>
    ),
  },
  {
    name: "CCXT",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <rect x="1" y="4" width="22" height="16" rx="4" stroke={C} strokeWidth="1.5"/>
        <text x="12" y="15.5" textAnchor="middle" fill={C} fontSize="8" fontWeight="bold" fontFamily="monospace">ccxt</text>
      </svg>
    ),
  },
  {
    name: "XGBoost",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <rect x="2" y="2" width="20" height="20" rx="4" stroke={C} strokeWidth="1.5"/>
        <text x="12" y="16" textAnchor="middle" fill={C} fontSize="10" fontWeight="bold" fontFamily="monospace">XG</text>
      </svg>
    ),
  },
  {
    name: "ONNX",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <rect x="2" y="2" width="20" height="20" rx="4" stroke={C} strokeWidth="1.5"/>
        <text x="12" y="16" textAnchor="middle" fill={C} fontSize="10" fontWeight="bold" fontFamily="monospace">OX</text>
      </svg>
    ),
  },
];

const ROW_2: TechItem[] = [
  {
    name: "Next.js 15",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke={C} strokeWidth="1.5" />
        <text x="12" y="16" textAnchor="middle" fill={C} fontSize="12" fontWeight="bold" fontFamily="monospace">N</text>
      </svg>
    ),
  },
  {
    name: "React 19",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={C} strokeWidth="1">
        <circle cx="12" cy="12" r="2.5" fill={C} stroke="none" />
        <ellipse cx="12" cy="12" rx="10" ry="4" />
        <ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)" />
        <ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)" />
      </svg>
    ),
  },
  {
    name: "Tailwind 4",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill={C}>
        <path d="M12 6c-2.67 0-4.33 1.33-5 4 1-1.33 2.17-1.83 3.5-1.5.76.19 1.3.74 1.9 1.35C13.37 10.84 14.53 12 17 12c2.67 0 4.33-1.33 5-4-1 1.33-2.17 1.83-3.5 1.5-.76-.19-1.3-.74-1.9-1.35C15.63 7.16 14.47 6 12 6zM7 12c-2.67 0-4.33 1.33-5 4 1-1.33 2.17-1.83 3.5-1.5.76.19 1.3.74 1.9 1.35C8.37 16.84 9.53 18 12 18c2.67 0 4.33-1.33 5-4-1 1.33-2.17 1.83-3.5 1.5-.76-.19-1.3-.74-1.9-1.35C10.63 13.16 9.47 12 7 12z" />
      </svg>
    ),
  },
  {
    name: "TradingView",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={C} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="3 17 8 11 13 15 21 5" />
        <circle cx="21" cy="5" r="1.5" fill={C} stroke="none" />
      </svg>
    ),
  },
  {
    name: "TypeScript",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <rect x="2" y="2" width="20" height="20" rx="3" stroke={C} strokeWidth="1.5" />
        <text x="12" y="16.5" textAnchor="middle" fill={C} fontSize="11" fontWeight="bold" fontFamily="monospace">TS</text>
      </svg>
    ),
  },
  {
    name: "Framer Motion",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={C} strokeWidth="1.5" strokeLinecap="round">
        <line x1="4" y1="8" x2="20" y2="8" />
        <line x1="4" y1="12" x2="16" y2="12" />
        <line x1="4" y1="16" x2="12" y2="16" />
      </svg>
    ),
  },
  {
    name: "Playwright",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={C} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="9" cy="10" r="5" />
        <circle cx="15" cy="10" r="5" />
        <path d="M7.5 8.5a1 1 0 100 1 1 1 0 000-1" fill={C} stroke="none" />
        <path d="M10 8.5a1 1 0 100 1 1 1 0 000-1" fill={C} stroke="none" />
        <path d="M14 8.5a1 1 0 100 1 1 1 0 000-1" fill={C} stroke="none" />
        <path d="M16.5 8.5a1 1 0 100 1 1 1 0 000-1" fill={C} stroke="none" />
        <path d="M7 12.5c1 1.5 3 1.5 4 0" />
        <path d="M13 12.5c1 1.5 3 1.5 4 0" />
        <path d="M5 16v4" />
        <path d="M19 16v4" />
      </svg>
    ),
  },
  {
    name: "Docker",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={C} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 14c0 0 .5 3 4 4 4.5 1.2 9 .5 12-2 1.5-1.3 2.5-3 3-5h-2c0 0-.5-2-3-2v-1h-2v1h-2V8h-2v1h-2V7h-2v2H7v2H4c-1 0-1.5.5-1.5 1.5" />
        <rect x="9" y="9" width="1.8" height="1.8" rx="0.3" fill={C} stroke="none" />
        <rect x="11.5" y="9" width="1.8" height="1.8" rx="0.3" fill={C} stroke="none" />
        <rect x="14" y="9" width="1.8" height="1.8" rx="0.3" fill={C} stroke="none" />
        <rect x="9" y="6.5" width="1.8" height="1.8" rx="0.3" fill={C} stroke="none" />
        <rect x="11.5" y="6.5" width="1.8" height="1.8" rx="0.3" fill={C} stroke="none" />
        <rect x="14" y="6.5" width="1.8" height="1.8" rx="0.3" fill={C} stroke="none" />
        <rect x="11.5" y="4" width="1.8" height="1.8" rx="0.3" fill={C} stroke="none" />
      </svg>
    ),
  },
];

function Badge({ name, icon }: { name: string; icon: React.ReactNode }) {
  return (
    <div className="group/badge bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm px-5 py-3 flex items-center gap-3 shrink-0 hover:border-[#00F0FF]/40 hover:bg-[#201F1F] transition-all duration-200 cursor-default select-none">
      <span className="text-[#B9CACB] group-hover/badge:text-[#00F0FF] transition-colors duration-200 flex items-center">
        {icon}
      </span>
      <span className="font-mono text-sm text-[#B9CACB] group-hover/badge:text-white whitespace-nowrap transition-colors duration-200">
        {name}
      </span>
    </div>
  );
}

function ConveyorRow({
  items,
  duration,
  reverse,
}: {
  items: TechItem[];
  duration: number;
  reverse?: boolean;
}) {
  // 4x duplication for perfectly seamless loop
  const sets = [0, 1, 2, 3];

  return (
    <div className="relative overflow-hidden group">
      {/* Left fade overlay */}
      <div
        className="absolute left-0 top-0 bottom-0 z-10 pointer-events-none"
        style={{
          width: 60,
          background: "linear-gradient(to right, #0D0D0D, transparent)",
        }}
      />
      {/* Right fade overlay */}
      <div
        className="absolute right-0 top-0 bottom-0 z-10 pointer-events-none"
        style={{
          width: 60,
          background: "linear-gradient(to left, #0D0D0D, transparent)",
        }}
      />

      <div
        className="flex group-hover:[animation-play-state:paused]"
        style={{
          width: "max-content",
          willChange: "transform",
          animation: `${reverse ? "conveyorRight" : "conveyorLeft"} ${duration}s linear infinite`,
        }}
      >
        {sets.map((setIndex) =>
          items.map((item, i) => (
            <div key={`${setIndex}-${item.name}-${i}`} className="px-2">
              <Badge name={item.name} icon={item.icon} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function TechConveyor() {
  return (
    <>
      <style
        dangerouslySetInnerHTML={{
          __html: `
            @keyframes conveyorLeft {
              0% { transform: translateX(0); }
              100% { transform: translateX(-25%); }
            }
            @keyframes conveyorRight {
              0% { transform: translateX(-25%); }
              100% { transform: translateX(0); }
            }
          `,
        }}
      />

      <section
        id="tech"
        className="py-20 border-y border-[#3B494B]/10 overflow-hidden"
      >
        <div className="text-center mb-10">
          <p className="font-mono text-[10px] text-[#B9CACB]/40 uppercase tracking-[0.3em] mb-2">
            Powered By
          </p>
          <h2 className="font-mono font-black text-2xl text-[#E5E2E1] tracking-tight">
            Battle-Tested Stack
          </h2>
        </div>

        <div className="flex flex-col gap-4">
          <ConveyorRow items={ROW_1} duration={40} />
          <ConveyorRow items={ROW_2} duration={45} reverse />
        </div>
      </section>
    </>
  );
}
