"use client";

import { motion } from "framer-motion";
import {
  Activity,
  Bot,
  TrendingUp,
  History,
  LineChart,
  Shield,
} from "lucide-react";

/* ══════════════════════════════════════════════
   Features — 3x2 grid with staggered scroll reveal
   ══════════════════════════════════════════════ */

const FEATURES = [
  {
    icon: Activity,
    title: "Signal Terminal",
    desc: "Real-time algorithmic trade signals with multi-strategy scoring and grade filtering.",
    accent: "#00F0FF",
  },
  {
    icon: Bot,
    title: "Trading Bot",
    desc: "Autonomous paper + live trading with 6 strategies. Automatic SL/TP management.",
    accent: "#40E56C",
  },
  {
    icon: TrendingUp,
    title: "TradingView Chart",
    desc: "Professional candlestick charts with 16 indicators, live order book, manual trade panel.",
    accent: "#00F0FF",
  },
  {
    icon: History,
    title: "Backtesting Engine",
    desc: "Historical strategy simulation with walk-forward analysis and Monte Carlo validation.",
    accent: "#FFB3B6",
  },
  {
    icon: LineChart,
    title: "Analytics",
    desc: "Equity curves, win/loss distribution, P&L histograms, Sharpe & Sortino ratios.",
    accent: "#40E56C",
  },
  {
    icon: Shield,
    title: "Risk Management",
    desc: "Position sizing with Kelly Criterion, drawdown kill switch, leverage caps.",
    accent: "#FFB4AB",
  },
];

const containerVariants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2,
    },
  },
} as const;

const cardVariants = {
  hidden: { opacity: 0, y: 40 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      type: "spring" as const,
      stiffness: 100,
      damping: 15,
    },
  },
};

const headerVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      type: "spring" as const,
      stiffness: 100,
      damping: 15,
    },
  },
};

export default function Features() {
  return (
    <section id="features" className="py-24 px-6 md:px-12 max-w-6xl mx-auto">
      {/* Section header */}
      <motion.div
        className="text-center mb-16"
        variants={headerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.2 }}
      >
        <h2 className="font-mono font-black text-3xl md:text-4xl text-[#E5E2E1] tracking-tight mb-4">
          Everything you need
        </h2>
        <p className="text-[#B9CACB] text-lg max-w-xl mx-auto">
          A complete toolkit for crypto trading research, automation, and
          monitoring.
        </p>
      </motion.div>

      {/* Feature cards grid */}
      <motion.div
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        variants={containerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.2 }}
      >
        {FEATURES.map((f, i) => {
          const Icon = f.icon;
          return (
            <motion.div
              key={i}
              variants={cardVariants}
              className="group bg-[#1C1B1B] border border-[#3B494B]/10 rounded-sm p-6
                         transition-all duration-300 ease-out
                         hover:-translate-y-2 hover:border-[#00F0FF]/20"
            >
              {/* Icon container */}
              <div
                className="w-12 h-12 rounded-sm flex items-center justify-center mb-4
                           transition-transform duration-300 ease-out group-hover:scale-[1.2]"
                style={{ background: `${f.accent}1A` }}
              >
                <Icon className="w-5 h-5" style={{ color: f.accent }} />
              </div>

              {/* Title */}
              <h3 className="font-mono font-bold text-sm text-[#E5E2E1] mb-2 tracking-tight">
                {f.title}
              </h3>

              {/* Description */}
              <p className="text-[13px] text-[#B9CACB] leading-relaxed">
                {f.desc}
              </p>
            </motion.div>
          );
        })}
      </motion.div>
    </section>
  );
}
