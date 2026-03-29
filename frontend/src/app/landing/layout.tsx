import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "CQ Engine — Open-Source Crypto Trading Automation & Backtesting",
  description:
    "CryptoQuant Engine: open-source crypto trading automation and backtesting platform for Binance USDM Futures. 6 strategies, 545+ pairs, real-time signals, ML-powered signal grading. Built with Python, FastAPI, Next.js.",
  keywords: [
    "crypto trading bot",
    "binance futures",
    "algorithmic trading",
    "backtesting",
    "trading automation",
    "open source",
    "quantitative trading",
    "CCXT",
    "TradingView",
    "Python trading",
  ],
  openGraph: {
    title: "CQ Engine — Crypto Trading Automation",
    description:
      "Open-source crypto trading platform with 6 strategies, real-time signals, backtesting engine, and TradingView charts. Binance USDM Futures.",
    type: "website",
    siteName: "CryptoQuant Engine",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "CQ Engine — Crypto Trading Automation",
    description:
      "Open-source trading platform: 6 strategies, 545+ pairs, real-time ML signals. Binance Futures.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function LandingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
