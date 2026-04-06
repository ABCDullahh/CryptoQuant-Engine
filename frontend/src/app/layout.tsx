import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import AppShell from "@/components/layout/AppShell";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "CQ Engine — Open-Source Crypto Trading Automation & Backtesting",
  description:
    "CryptoQuant Engine: open-source crypto trading automation and backtesting platform for Binance USDM Futures. 6 strategies, 545+ pairs, real-time signals, ML-powered signal grading.",
  keywords: [
    "crypto trading bot",
    "binance futures",
    "algorithmic trading",
    "backtesting",
    "trading automation",
    "open source",
    "quantitative trading",
  ],
  openGraph: {
    title: "CQ Engine — Crypto Trading Automation",
    description:
      "Open-source crypto trading platform with 6 strategies, real-time signals, backtesting engine, and TradingView charts.",
    type: "website",
    siteName: "CryptoQuant Engine",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className={inter.className}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
