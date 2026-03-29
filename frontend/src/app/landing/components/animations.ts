"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useInView as framerUseInView } from "framer-motion";
import type { Variants } from "framer-motion";

/* ══════════════════════════════════════════════
   Shared Framer Motion Variants
   ══════════════════════════════════════════════ */

export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 30 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { type: "spring", stiffness: 100, damping: 20 },
  },
};

export const fadeInLeft: Variants = {
  hidden: { opacity: 0, x: -40 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { type: "spring", stiffness: 100, damping: 20 },
  },
};

export const fadeInRight: Variants = {
  hidden: { opacity: 0, x: 40 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { type: "spring", stiffness: 100, damping: 20 },
  },
};

export const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.8 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: { type: "spring", stiffness: 100, damping: 18 },
  },
};

/* ══════════════════════════════════════════════
   Hooks
   ══════════════════════════════════════════════ */

/**
 * Wrapper around framer-motion's useInView.
 * Returns { ref, isInView }.
 */
export function useInView(options?: { once?: boolean; margin?: `${number}px` }) {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = framerUseInView(ref, {
    once: options?.once ?? true,
    margin: options?.margin ?? "-80px" as `${number}px`,
  });
  return { ref, isInView };
}

/**
 * Animates a number from 0 to `target` over `duration` ms.
 * Uses requestAnimationFrame for smooth interpolation.
 */
export function useCountUp(
  target: number,
  duration: number = 2000,
  startWhen: boolean = true
): number {
  const [value, setValue] = useState(0);
  const startedRef = useRef(false);

  useEffect(() => {
    if (!startWhen || startedRef.current) return;
    startedRef.current = true;

    const startTime = performance.now();
    let rafId: number;

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));

      if (progress < 1) {
        rafId = requestAnimationFrame(tick);
      }
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [target, duration, startWhen]);

  return value;
}

/* ══════════════════════════════════════════════
   GlitchText Component
   ══════════════════════════════════════════════ */

const GLITCH_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?/~`0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";

/**
 * Renders text with a glitch effect: random character substitution
 * for 1.5s that progressively resolves to the real text.
 */
export function useGlitchText(text: string, durationMs: number = 1500): string {
  const [display, setDisplay] = useState(text);
  const resolvedRef = useRef(false);

  const scramble = useCallback(
    (progress: number): string => {
      return text
        .split("")
        .map((char, i) => {
          if (char === " ") return " ";
          // Characters resolve left-to-right as progress increases
          const threshold = i / text.length;
          if (progress > threshold) return char;
          return GLITCH_CHARS[Math.floor(Math.random() * GLITCH_CHARS.length)];
        })
        .join("");
    },
    [text]
  );

  useEffect(() => {
    if (resolvedRef.current) return;
    resolvedRef.current = true;

    const startTime = performance.now();
    let intervalId: ReturnType<typeof setInterval>;

    intervalId = setInterval(() => {
      const elapsed = performance.now() - startTime;
      const progress = Math.min(elapsed / durationMs, 1);

      if (progress >= 1) {
        setDisplay(text);
        clearInterval(intervalId);
        return;
      }

      setDisplay(scramble(progress));
    }, 50);

    return () => clearInterval(intervalId);
  }, [text, durationMs, scramble]);

  return display;
}
