/**
 * Smoke tests — verify every page loads without crashing.
 *
 * Run: npx playwright test e2e/smoke.spec.ts
 */

import { test, expect } from "@playwright/test";
import { injectAuth } from "./helpers";

// All tests use auth so pages load fully (not stuck on "Loading...")
test.beforeEach(async ({ page }) => {
  await injectAuth(page);
});

// ---------------------------------------------------------------------------
// Sidebar + Layout
// ---------------------------------------------------------------------------

test.describe("Layout & Navigation", () => {
  test("sidebar shows all 8 navigation links", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    const nav = page.locator("nav");
    await expect(nav.getByRole("link", { name: "Overview" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Signals" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Bot Manager" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Positions" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Analytics" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Chart" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Backtest" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Settings" })).toBeVisible();
  });

  test("header shows Binance Futures badge", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.getByText("Binance Futures")).toBeVisible();
  });

  test("branding shows CryptoQuant Engine v0.1", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "CryptoQuant" })).toBeVisible();
    await expect(page.getByText("Engine v0.1")).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Page loads
// ---------------------------------------------------------------------------

test.describe("Page Smoke Tests", () => {
  test("Overview (/) loads Dashboard heading", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Dashboard Overview" })).toBeVisible({ timeout: 15_000 });
  });

  test("Signals (/signals) loads Signal Terminal", async ({ page }) => {
    await page.goto("/signals", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Signal Terminal" })).toBeVisible({ timeout: 15_000 });
  });

  test("Bot Manager (/bot) loads Bot Manager", async ({ page }) => {
    await page.goto("/bot", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Bot Manager" })).toBeVisible({ timeout: 15_000 });
  });

  test("Positions (/positions) loads Position Manager", async ({ page }) => {
    await page.goto("/positions", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Position Manager" })).toBeVisible({ timeout: 15_000 });
  });

  test("Analytics (/analytics) loads Trading Analytics", async ({ page }) => {
    await page.goto("/analytics", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Trading Analytics" })).toBeVisible({ timeout: 15_000 });
  });

  test("Chart (/chart) loads TradingView chart", async ({ page }) => {
    await page.goto("/chart", { waitUntil: "networkidle" });
    await expect(page.getByRole("button", { name: "BTC/USDT" })).toBeVisible({ timeout: 15_000 });
  });

  test("Backtest (/backtest) loads Backtest Lab", async ({ page }) => {
    await page.goto("/backtest", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Backtest Lab" })).toBeVisible({ timeout: 15_000 });
  });

  test("Settings (/settings) loads Settings page", async ({ page }) => {
    await page.goto("/settings", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible({ timeout: 15_000 });
  });
});

// ---------------------------------------------------------------------------
// Navigation clicks
// ---------------------------------------------------------------------------

test.describe("Sidebar Navigation", () => {
  test("clicking each nav link navigates to correct URL", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Dashboard Overview" })).toBeVisible({ timeout: 15_000 });

    // Signals
    await page.getByRole("link", { name: "Signals" }).click();
    await expect(page).toHaveURL("/signals");
    await expect(page.getByRole("heading", { name: "Signal Terminal" })).toBeVisible({ timeout: 15_000 });

    // Bot Manager
    await page.getByRole("link", { name: "Bot Manager" }).click();
    await expect(page).toHaveURL("/bot");
    await expect(page.getByRole("heading", { name: "Bot Manager" })).toBeVisible({ timeout: 15_000 });

    // Positions
    await page.getByRole("link", { name: "Positions" }).click();
    await expect(page).toHaveURL("/positions");
    await expect(page.getByRole("heading", { name: "Position Manager" })).toBeVisible({ timeout: 15_000 });

    // Analytics
    await page.getByRole("link", { name: "Analytics" }).click();
    await expect(page).toHaveURL("/analytics");
    await expect(page.getByRole("heading", { name: "Trading Analytics" })).toBeVisible({ timeout: 15_000 });

    // Chart
    await page.getByRole("link", { name: "Chart" }).click();
    await expect(page).toHaveURL("/chart");
    await expect(page.getByRole("button", { name: "BTC/USDT" })).toBeVisible({ timeout: 15_000 });

    // Backtest
    await page.getByRole("link", { name: "Backtest" }).click();
    await expect(page).toHaveURL("/backtest");
    await expect(page.getByRole("heading", { name: "Backtest Lab" })).toBeVisible({ timeout: 15_000 });

    // Settings
    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page).toHaveURL("/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible({ timeout: 15_000 });

    // Back to Overview
    await page.getByRole("link", { name: "Overview" }).click();
    await expect(page).toHaveURL("/");
  });
});
