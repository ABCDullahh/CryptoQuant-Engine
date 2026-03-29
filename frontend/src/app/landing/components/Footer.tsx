"use client";

import { Zap, Github } from "lucide-react";
import Link from "next/link";

/* ══════════════════════════════════════════════
   Footer — Minimal branded footer
   ══════════════════════════════════════════════ */

export default function Footer() {
  return (
    <footer className="relative">
      {/* Top gradient line */}
      <div
        className="h-px w-full"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(0,240,255,0.3) 50%, transparent 100%)",
        }}
      />

      <div className="py-12 px-6 md:px-12">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          {/* Left: Logo + copyright */}
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#00F0FF]" />
            <span className="font-mono text-xs text-[#B9CACB]/40">
              CryptoQuant Engine &copy; 2026 &middot; MIT License
            </span>
          </div>

          {/* Center: tagline */}
          <span className="font-mono text-xs text-[#B9CACB]/20 hidden md:block">
            Made with code &amp; caffeine
          </span>

          {/* Right: links */}
          <div className="flex items-center gap-6">
            <a
              href="https://github.com/ABCDullahh/CryptoQuant-Engine"
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-xs text-[#B9CACB]/40 hover:text-[#00F0FF] transition-colors flex items-center gap-1"
            >
              <Github className="w-3 h-3" /> GitHub
            </a>
            <Link
              href="/login"
              className="font-mono text-xs text-[#B9CACB]/40 hover:text-[#00F0FF] transition-colors"
            >
              Launch App
            </Link>
          </div>
        </div>

        {/* Mobile center tagline */}
        <div className="md:hidden text-center mt-4">
          <span className="font-mono text-xs text-[#B9CACB]/20">
            Made with code &amp; caffeine
          </span>
        </div>
      </div>
    </footer>
  );
}
