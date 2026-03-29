"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  fadeInUp,
  staggerContainer,
  useInView,
  useCountUp,
  useGlitchText,
} from "./animations";

/* ══════════════════════════════════════════════
   Hero Section — CryptoQuant Engine Landing
   ══════════════════════════════════════════════ */

const FLOATING_CODE = [
  { text: 'signal = strategy.evaluate(candles)', top: "12%", left: "5%", delay: "0s" },
  { text: 'if grade >= "A": execute(signal)', top: "25%", right: "3%", delay: "4s" },
  { text: "risk = sizer.calculate(atr, balance)", top: "55%", left: "2%", delay: "8s" },
  { text: "await exchange.create_order(symbol, side)", top: "70%", right: "6%", delay: "12s" },
  { text: "pnl = position.unrealized_pnl()", top: "40%", left: "8%", delay: "6s" },
  { text: "candles = await provider.fetch_ohlcv()", top: "82%", right: "10%", delay: "16s" },
];

const TAGLINE = "Open-source crypto trading automation & backtesting";

const FLOATING_COINS = [
  {
    // BTC — Bitcoin B in a circle
    svg: (
      <svg width="44" height="44" viewBox="0 0 44 44" fill="none" stroke="#00F0FF" strokeWidth="1.2">
        <circle cx="22" cy="22" r="20" />
        <path d="M18 12v20M22 12v20" strokeWidth="1" />
        <path d="M16 16h8c2.5 0 4 1.5 4 3.5s-1.5 3.5-4 3.5H16" />
        <path d="M16 23h9c2.5 0 4 1.5 4 3.5S27.5 30 25 30H16" />
      </svg>
    ),
    style: { top: "8%", left: "6%", opacity: 0.04, animationDuration: "18s" },
  },
  {
    // ETH — Ethereum diamond
    svg: (
      <svg width="36" height="36" viewBox="0 0 36 36" fill="none" stroke="#B9CACB" strokeWidth="1.2" strokeLinejoin="round">
        <path d="M18 3L6 18l12 7 12-7L18 3z" />
        <path d="M6 18l12 15 12-15" />
        <path d="M18 3v22" />
      </svg>
    ),
    style: { top: "15%", right: "8%", opacity: 0.05, animationDuration: "22s" },
  },
  {
    // BNB — Diamond shape
    svg: (
      <svg width="38" height="38" viewBox="0 0 38 38" fill="none" stroke="#00F0FF" strokeWidth="1.2" strokeLinejoin="round">
        <path d="M19 4l6 6-6 6-6-6 6-6z" />
        <path d="M9 14l-5 5 5 5 5-5-5-5z" />
        <path d="M29 14l-5 5 5 5 5-5-5-5z" />
        <path d="M19 22l6 6-6 6-6-6 6-6z" />
      </svg>
    ),
    style: { bottom: "22%", left: "4%", opacity: 0.035, animationDuration: "20s" },
  },
  {
    // SOL — Stylized S with horizontal lines
    svg: (
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none" stroke="#B9CACB" strokeWidth="1.2" strokeLinecap="round">
        <path d="M8 10h24l-24 0" />
        <path d="M8 10l4-4h24l-4 4" />
        <path d="M8 20h24" />
        <path d="M32 20l-4 4H4l4-4" />
        <path d="M8 30h24" />
        <path d="M8 30l4-4h24l-4 4" />
      </svg>
    ),
    style: { top: "50%", right: "5%", opacity: 0.04, animationDuration: "25s" },
  },
  {
    // Chart icon — line chart going up
    svg: (
      <svg width="42" height="42" viewBox="0 0 42 42" fill="none" stroke="#00F0FF" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="5 35 5 7" />
        <polyline points="5 35 37 35" />
        <polyline points="9 28 16 20 22 24 33 10" />
        <polyline points="27 10 33 10 33 16" />
      </svg>
    ),
    style: { bottom: "12%", right: "12%", opacity: 0.03, animationDuration: "17s" },
  },
  {
    // Candlestick icon
    svg: (
      <svg width="34" height="34" viewBox="0 0 34 34" fill="none" stroke="#B9CACB" strokeWidth="1.2" strokeLinecap="round">
        <line x1="10" y1="4" x2="10" y2="30" />
        <rect x="7" y="10" width="6" height="12" rx="1" />
        <line x1="22" y1="6" x2="22" y2="28" />
        <rect x="19" y="14" width="6" height="8" rx="1" />
      </svg>
    ),
    style: { top: "35%", left: "3%", opacity: 0.035, animationDuration: "21s" },
  },
  {
    // USDT — Dollar in circle
    svg: (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="#00F0FF" strokeWidth="1.2">
        <circle cx="16" cy="16" r="14" />
        <line x1="16" y1="6" x2="16" y2="26" />
        <path d="M10 11h12" />
        <path d="M11 15c0 0 0.5 8 5 8s5-8 5-8" />
      </svg>
    ),
    style: { bottom: "30%", right: "3%", opacity: 0.04, animationDuration: "19s" },
  },
];

export default function Hero() {
  const [scrollY, setScrollY] = useState(0);
  const [typedText, setTypedText] = useState("");
  const [showCursor, setShowCursor] = useState(true);
  const typingDone = useRef(false);
  const heroRef = useRef<HTMLElement>(null);
  const [isVisible, setIsVisible] = useState(true);

  const { ref: statsRef, isInView: statsInView } = useInView({ once: true });
  const glitchCQ = useGlitchText("CQ", 1500);

  const strategyCount = useCountUp(6, 1800, statsInView);
  const pairCount = useCountUp(545, 2200, statsInView);
  const volumeCount = useCountUp(29, 2000, statsInView);

  // IntersectionObserver — pause intervals when Hero is off screen
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => setIsVisible(entry.isIntersecting),
      { threshold: 0 }
    );
    if (heroRef.current) observer.observe(heroRef.current);
    return () => observer.disconnect();
  }, []);

  // Scroll tracking (throttled with requestAnimationFrame)
  useEffect(() => {
    let ticking = false;
    function onScroll() {
      if (!ticking) {
        requestAnimationFrame(() => {
          setScrollY(window.scrollY);
          ticking = false;
        });
        ticking = true;
      }
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Typing effect — pauses when not visible
  useEffect(() => {
    if (typingDone.current) return;
    if (!isVisible) return;
    let i = typedText.length;
    const id = setInterval(() => {
      i++;
      setTypedText(TAGLINE.slice(0, i));
      if (i >= TAGLINE.length) {
        clearInterval(id);
        typingDone.current = true;
      }
    }, 50);
    return () => clearInterval(id);
  }, [isVisible, typedText.length]);

  // Blinking cursor — pauses when not visible
  useEffect(() => {
    if (!isVisible) return;
    const id = setInterval(() => setShowCursor((c) => !c), 530);
    return () => clearInterval(id);
  }, [isVisible]);

  return (
    <section ref={heroRef} className="relative min-h-screen flex flex-col items-center justify-center px-6 text-center overflow-hidden">
      {/* ── Background layer ── */}

      {/* Animated grid */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(0,240,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,240,255,0.03) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      {/* Radial glow with pulsing opacity */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[700px] rounded-full hero-glow" />

      {/* Floating code snippets */}
      {FLOATING_CODE.map((snippet, i) => (
        <div
          key={i}
          className="absolute font-mono text-[11px] text-[#00F0FF] opacity-[0.04] whitespace-nowrap pointer-events-none select-none hero-float-code"
          style={{
            top: snippet.top,
            left: snippet.left,
            right: snippet.right,
            animationDelay: snippet.delay,
          }}
        >
          {snippet.text}
        </div>
      ))}

      {/* Floating crypto coins background */}
      {FLOATING_COINS.map((coin, i) => (
        <div
          key={`coin-${i}`}
          className="absolute pointer-events-none select-none hero-float-coin"
          style={{
            ...coin.style,
            zIndex: 0,
          }}
        >
          {coin.svg}
        </div>
      ))}

      {/* ── Content ── */}
      <motion.div
        className="relative z-10 max-w-4xl mx-auto"
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
      >
        {/* WIP Badge */}
        <motion.div variants={fadeInUp} className="flex justify-center mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-sm bg-[#00F0FF]/10 border border-[#00F0FF]/20 text-[#00F0FF] text-[10px] font-mono uppercase tracking-widest">
            <span className="w-1.5 h-1.5 rounded-full bg-[#40E56C] animate-pulse" />
            Open Source &middot; MIT License &middot; WIP
          </div>
        </motion.div>

        {/* CQ — Glitch text */}
        <motion.div variants={fadeInUp}>
          <h1
            className="font-mono font-black text-[120px] md:text-[200px] text-[#00F0FF] leading-none select-none"
            aria-label="CQ"
          >
            {glitchCQ}
          </h1>
        </motion.div>

        {/* Engine — slide in from right */}
        <motion.div
          initial={{ x: 100, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ type: "spring", stiffness: 80, damping: 18, delay: 0.3 }}
        >
          <span className="font-mono font-black text-[60px] md:text-[100px] text-[#E5E2E1] leading-none block -mt-4 md:-mt-8">
            Engine
          </span>
        </motion.div>

        {/* Tagline with typing effect */}
        <motion.div variants={fadeInUp} className="mt-8 mb-4">
          <p className="text-xl md:text-2xl font-light text-[#B9CACB] max-w-2xl mx-auto leading-relaxed h-[2em]">
            {typedText}
            <span
              className="inline-block w-[2px] h-[1.1em] bg-[#00F0FF] ml-0.5 align-text-bottom"
              style={{ opacity: showCursor ? 1 : 0 }}
            />
          </p>
        </motion.div>

        {/* Stats with count-up */}
        <motion.div variants={fadeInUp} ref={statsRef}>
          <p className="font-mono text-sm text-[#B9CACB]/60 mb-10">
            <span className="text-[#00F0FF]">{strategyCount}</span> strategies
            {" "}&middot;{" "}
            <span className="text-[#00F0FF]">{pairCount}+</span> pairs
            {" "}&middot;{" "}
            <span className="text-[#40E56C]">${volumeCount}K+</span> volume
          </p>
        </motion.div>

        {/* CTA Buttons */}
        <motion.div
          variants={fadeInUp}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            <Link
              href="/login"
              className="group relative flex items-center gap-2 bg-[#00F0FF] text-[#002022] font-mono font-bold text-sm px-8 py-4 rounded-sm overflow-hidden"
            >
              {/* Shimmer overlay */}
              <span className="absolute inset-0 hero-shimmer pointer-events-none" />
              <span className="relative z-10 flex items-center gap-2">
                Get Started
                <svg
                  className="w-4 h-4 group-hover:translate-x-1 transition-transform"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2.5}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </span>
            </Link>
          </motion.div>

          <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            <a
              href="https://github.com/ABCDullahh/CryptoQuant-Engine"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 bg-transparent text-[#E5E2E1] font-mono text-sm px-8 py-4 rounded-sm border border-[#3B494B]/30 hover:border-[#00F0FF]/30 hover:text-[#00F0FF] transition-all"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              View on GitHub
            </a>
          </motion.div>
        </motion.div>

        {/* Engine status line */}
        <motion.div variants={fadeInUp}>
          <div className="mt-16 font-mono text-[10px] text-[#B9CACB]/40 tracking-widest uppercase flex items-center justify-center gap-4">
            <span>Engine v2.0</span>
            <span className="w-1 h-1 rounded-full bg-[#3B494B]" />
            <span>Python + Next.js</span>
            <span className="w-1 h-1 rounded-full bg-[#3B494B]" />
            <span>MIT License</span>
          </div>
        </motion.div>
      </motion.div>

      {/* ── Floating Terminal Preview ── */}
      <motion.div
        className="relative z-10 mt-20 w-full max-w-5xl mx-auto"
        initial={{ rotateX: 15, opacity: 0, y: 40 }}
        whileInView={{ rotateX: 0, opacity: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 60, damping: 20, delay: 0.2 }}
        viewport={{ once: true, margin: "-100px" }}
        style={{ perspective: 1200 }}
      >
        <div className="relative" style={{ transformStyle: "preserve-3d" }}>
          {/* Browser frame */}
          <div className="bg-[#131313] border border-[#3B494B]/10 rounded-sm overflow-hidden shadow-2xl shadow-[#00F0FF]/5">
            {/* Chrome bar */}
            <div className="flex items-center gap-2 px-4 py-3 bg-[#0D0D0D] border-b border-[#3B494B]/10">
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-[#FFB4AB]/40" />
                <div className="w-2.5 h-2.5 rounded-full bg-[#FFB3B6]/30" />
                <div className="w-2.5 h-2.5 rounded-full bg-[#40E56C]/40" />
              </div>
              <div className="flex-1 flex justify-center">
                <div className="bg-[#1C1B1B] px-4 py-1 rounded-sm text-[10px] font-mono text-[#B9CACB]/40">
                  localhost:3000/dashboard
                </div>
              </div>
            </div>
            {/* Screenshot */}
            <img
              src="/docs/images/02-dashboard.png"
              alt="CryptoQuant Engine Dashboard"
              className="w-full"
              width={1200}
              height={700}
              decoding="async"
              loading="lazy"
            />
          </div>

          {/* Floating breakout: signal card (left) */}
          <motion.div
            className="absolute -left-4 md:-left-12 top-1/4 bg-[#1C1B1B] border border-[#00F0FF]/20 rounded-sm px-3 py-2 shadow-lg shadow-black/40 hero-float-element"
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.8, duration: 0.6 }}
            viewport={{ once: true }}
          >
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[#40E56C]" />
              <span className="font-mono text-xs text-[#E5E2E1] font-bold">ETH/USDT</span>
              <span className="font-mono text-[10px] text-[#40E56C] font-bold">LONG</span>
              <span className="font-mono text-[10px] text-[#00F0FF] font-bold px-1 bg-[#00F0FF]/10 rounded-sm">A</span>
            </div>
          </motion.div>

          {/* Floating breakout: P&L (right) */}
          <motion.div
            className="absolute -right-4 md:-right-10 top-1/3 bg-[#1C1B1B] border border-[#40E56C]/20 rounded-sm px-3 py-2 shadow-lg shadow-black/40 hero-float-element"
            style={{ animationDelay: "1.5s" }}
            initial={{ opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ delay: 1.0, duration: 0.6 }}
            viewport={{ once: true }}
          >
            <span className="font-mono text-lg text-[#40E56C] font-black">+$33.54</span>
          </motion.div>
        </div>
      </motion.div>

      {/* ── Scroll indicator ── */}
      <div
        className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 transition-opacity duration-300"
        style={{ opacity: Math.max(0, 1 - scrollY / 300) }}
      >
        <span className="font-mono text-[10px] text-[#B9CACB]/30 uppercase tracking-widest">
          scroll to explore
        </span>
        <svg
          className="w-5 h-5 text-[#B9CACB]/30 animate-bounce"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {/* ── CSS Animations ── */}
      <style jsx>{`
        .hero-glow {
          background: radial-gradient(circle, #00F0FF 0%, transparent 70%);
          animation: glowPulse 4s ease-in-out infinite;
        }
        @keyframes glowPulse {
          0%, 100% { opacity: 0.05; }
          50% { opacity: 0.12; }
        }

        .hero-float-code {
          animation: floatCodeUp 20s linear infinite;
        }
        @keyframes floatCodeUp {
          0% { transform: translateY(0); }
          100% { transform: translateY(-120px); }
        }

        .hero-shimmer {
          background: linear-gradient(
            110deg,
            transparent 25%,
            rgba(255, 255, 255, 0.25) 50%,
            transparent 75%
          );
          background-size: 200% 100%;
          animation: shimmerSweep 3s ease-in-out infinite;
        }
        @keyframes shimmerSweep {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }

        .hero-float-element {
          animation: floatY 3s ease-in-out infinite;
        }
        @keyframes floatY {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }

        .hero-float-coin {
          animation-name: floatCoin;
          animation-timing-function: ease-in-out;
          animation-iteration-count: infinite;
        }
        @keyframes floatCoin {
          0%, 100% { transform: translateY(0) rotate(0deg); }
          33% { transform: translateY(-15px) rotate(3deg); }
          66% { transform: translateY(10px) rotate(-2deg); }
        }
      `}</style>
    </section>
  );
}
