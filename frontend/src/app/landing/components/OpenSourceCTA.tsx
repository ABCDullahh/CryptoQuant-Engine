"use client";

import { motion } from "framer-motion";
import { Star, GitFork, ExternalLink } from "lucide-react";
import Link from "next/link";

/* ══════════════════════════════════════════════
   OpenSourceCTA — Split text reveal on scroll
   ══════════════════════════════════════════════ */

const wordVariantLeft = {
  hidden: { opacity: 0, x: -40 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: {
      type: "spring" as const,
      stiffness: 80,
      damping: 18,
      delay: i * 0.1,
    },
  }),
};

const wordVariantRight = {
  hidden: { opacity: 0, x: 40 },
  visible: {
    opacity: 1,
    x: 0,
    transition: {
      type: "spring" as const,
      stiffness: 80,
      damping: 18,
      delay: 0.4,
    },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (delay: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      type: "spring" as const,
      stiffness: 80,
      damping: 18,
      delay,
    },
  }),
};

const LINE_1_WORDS = ["Built", "in", "the", "open."];

export default function OpenSourceCTA() {
  return (
    <section className="py-32 px-6 md:px-12 text-center relative overflow-hidden">
      {/* Subtle radial glow */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[350px] rounded-full pointer-events-none"
        style={{
          background: "radial-gradient(circle, #00F0FF 0%, transparent 70%)",
          opacity: 0.04,
        }}
      />

      <div className="relative z-10 max-w-2xl mx-auto">
        {/* ── Heading with split text reveal ── */}
        <h2 className="font-mono font-black text-4xl md:text-5xl tracking-tight mb-6 leading-tight">
          {/* Line 1: "Built in the open." — each word from left */}
          <span className="block">
            {LINE_1_WORDS.map((word, i) => (
              <motion.span
                key={i}
                className="inline-block text-[#E5E2E1] mr-3 md:mr-4"
                variants={wordVariantLeft}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, amount: 0.5 }}
                custom={i}
              >
                {word}
              </motion.span>
            ))}
          </span>

          {/* Line 2: "Join us." — from right */}
          <motion.span
            className="block text-[#00F0FF]"
            variants={wordVariantRight}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.5 }}
          >
            Join us.
          </motion.span>
        </h2>

        {/* ── Description ── */}
        <motion.p
          className="text-[#B9CACB] text-lg mb-4 leading-relaxed"
          variants={fadeUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.5 }}
          custom={0.5}
        >
          Whether it&apos;s a new strategy idea, a bug fix, or something we
          haven&apos;t thought of yet &mdash; contributions are welcome.
        </motion.p>

        <motion.p
          className="text-[#B9CACB]/60 text-sm mb-10"
          variants={fadeUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.5 }}
          custom={0.65}
        >
          Who knows, maybe with enough brains collaborating we can actually beat
          the market. Let&apos;s find out.
        </motion.p>

        {/* ── Buttons ── */}
        <motion.div
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
          variants={fadeUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.5 }}
          custom={0.8}
        >
          {/* Star on GitHub */}
          <motion.a
            href="https://github.com/ABCDullahh/CryptoQuant-Engine"
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center gap-2 bg-[#E5E2E1] text-[#0D0D0D] font-mono font-bold text-sm px-6 py-3 rounded-sm transition-all"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.98 }}
          >
            <Star className="w-4 h-4" />
            Star on GitHub
            <ExternalLink className="w-3 h-3 opacity-50" />
          </motion.a>

          {/* Fork & Contribute */}
          <motion.a
            href="https://github.com/ABCDullahh/CryptoQuant-Engine/fork"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-[#B9CACB] font-mono text-sm px-6 py-3 rounded-sm border border-[#3B494B]/30 hover:border-[#00F0FF]/30 hover:text-[#00F0FF] transition-all"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.98 }}
          >
            <GitFork className="w-4 h-4" />
            Fork &amp; Contribute
          </motion.a>
        </motion.div>

        {/* ── MIT License badge ── */}
        <motion.div
          className="mt-8 inline-flex items-center gap-2 px-3 py-1.5 rounded-sm bg-[#40E56C]/10 border border-[#40E56C]/20"
          variants={fadeUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.5 }}
          custom={1.0}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#40E56C]" />
          <span className="font-mono text-[10px] text-[#40E56C] uppercase tracking-widest">
            MIT License
          </span>
        </motion.div>
      </div>
    </section>
  );
}
