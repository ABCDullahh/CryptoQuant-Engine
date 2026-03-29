"use client";

import dynamic from "next/dynamic";

/* ══════════════════════════════════════════════
   Landing Page — "Kinetic Monolith"
   CryptoQuant Engine

   All sections lazy-loaded for performance.
   GSAP + Framer Motion for animations.
   ══════════════════════════════════════════════ */

const Hero = dynamic(() => import("./components/Hero"), { ssr: false });
const TickerBar = dynamic(() => import("./components/TickerBar"), { ssr: false });
const Features = dynamic(() => import("./components/Features"), { ssr: false });
const Pipeline = dynamic(() => import("./components/Pipeline"), { ssr: false });
const Strategies = dynamic(() => import("./components/Strategies"), { ssr: false });
const TechConveyor = dynamic(() => import("./components/TechConveyor"), { ssr: false });
const OpenSourceCTA = dynamic(() => import("./components/OpenSourceCTA"), { ssr: false });
const Footer = dynamic(() => import("./components/Footer"), { ssr: false });

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0D0D0D] text-[#E5E2E1]" style={{ overflowX: "clip" }}>
      {/* Accessibility: disable animations for users who prefer reduced motion */}
      <style dangerouslySetInnerHTML={{ __html: `
        @media (prefers-reduced-motion: reduce) {
          *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
          }
        }
      `}} />
      {/* Ticker always fixed at top */}
      <TickerBar />
      <Hero />
      <Features />
      <Pipeline />
      <Strategies />
      <TechConveyor />
      <OpenSourceCTA />
      <Footer />
    </div>
  );
}
