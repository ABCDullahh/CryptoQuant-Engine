/**
 * Critical flow tests — verify key interactive features work.
 *
 * Run: npx playwright test e2e/critical-flows.spec.ts
 */

import { test, expect } from "@playwright/test";
import { injectAuth } from "./helpers";

test.beforeEach(async ({ page }) => {
  await injectAuth(page);
});

test.describe("Signal Terminal Features", () => {
  test("signal table shows columns", async ({ page }) => {
    await page.goto("/signals", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Signal Terminal" })).toBeVisible({ timeout: 15_000 });

    const table = page.locator("table");
    await expect(table.getByRole("columnheader", { name: "Symbol" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Direction" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Grade" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Entry" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Status" })).toBeVisible();
  });

  test("direction filter buttons work", async ({ page }) => {
    await page.goto("/signals", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Signal Terminal" })).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Long" }).click();
    await page.getByRole("button", { name: "All" }).first().click();
  });

  test("grade filter buttons render", async ({ page }) => {
    await page.goto("/signals", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Signal Terminal" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByRole("button", { name: "A", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "B", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "C", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "D", exact: true })).toBeVisible();
  });

  test("search box accepts input", async ({ page }) => {
    await page.goto("/signals", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Signal Terminal" })).toBeVisible({ timeout: 15_000 });

    const searchBox = page.getByPlaceholder("Search symbol...");
    await expect(searchBox).toBeVisible();
    await searchBox.fill("BTC");
    await expect(searchBox).toHaveValue("BTC");
  });

  test("stats cards display", async ({ page }) => {
    await page.goto("/signals", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Signal Terminal" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText("Total Signals")).toBeVisible();
    await expect(page.getByText("Avg. Strength")).toBeVisible();
  });
});

test.describe("Bot Manager Features", () => {
  test("bot status and controls render", async ({ page }) => {
    await page.goto("/bot", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Bot Manager" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText("Bot Status")).toBeVisible();
    await expect(page.getByRole("button", { name: "Start" })).toBeVisible();
  });

  test("strategy checkboxes render", async ({ page }) => {
    await page.goto("/bot", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Bot Manager" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText("Smart Money Concepts (SMC)")).toBeVisible();
    await expect(page.getByText("Volume Profile")).toBeVisible();
    await expect(page.getByText("Market Structure")).toBeVisible();
    await expect(page.getByText("Momentum", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Funding Rate")).toBeVisible();
  });

  test("symbol and timeframe buttons render", async ({ page }) => {
    await page.goto("/bot", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Bot Manager" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByRole("button", { name: "BTC/USDT" })).toBeVisible();
    await expect(page.getByRole("button", { name: "ETH/USDT" })).toBeVisible();
    await expect(page.getByRole("button", { name: "1h", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "4h", exact: true })).toBeVisible();
  });

  test("paper mode toggle and balance input exist", async ({ page }) => {
    await page.goto("/bot", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Bot Manager" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText("Paper Trading Mode")).toBeVisible();
    await expect(page.getByText("Starting Balance")).toBeVisible();
  });
});

test.describe("Position Manager Features", () => {
  test("position table columns render", async ({ page }) => {
    await page.goto("/positions", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Position Manager" })).toBeVisible({ timeout: 15_000 });

    const table = page.locator("table");
    await expect(table.getByRole("columnheader", { name: "Symbol" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Direction" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Entry" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Stop Loss" })).toBeVisible();
  });

  test("status filter buttons render", async ({ page }) => {
    await page.goto("/positions", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Position Manager" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByRole("button", { name: "All" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Closed" })).toBeVisible();
  });

  test("stats cards display", async ({ page }) => {
    await page.goto("/positions", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Position Manager" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText("Total Unrealized P&L")).toBeVisible();
    await expect(page.getByText("Open Positions", { exact: true })).toBeVisible();
    await expect(page.getByText("Total Fees")).toBeVisible();
  });
});

test.describe("Chart Features", () => {
  test("symbol selector and timeframe buttons render", async ({ page }) => {
    await page.goto("/chart", { waitUntil: "networkidle" });
    await expect(page.getByRole("button", { name: "BTC/USDT" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByRole("button", { name: "1m", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "5m", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "15m", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "1h", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "4h", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "1D", exact: true })).toBeVisible();
  });

  test("timeframe switch changes display", async ({ page }) => {
    await page.goto("/chart", { waitUntil: "networkidle" });
    await expect(page.getByRole("button", { name: "BTC/USDT" })).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "5m", exact: true }).click();
    await expect(page.getByText("5M", { exact: true })).toBeVisible();
  });

  test("bottom stats bar renders", async ({ page }) => {
    await page.goto("/chart", { waitUntil: "networkidle" });
    await expect(page.getByRole("button", { name: "BTC/USDT" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText("Data Source")).toBeVisible();
    await expect(page.getByText("Price")).toBeVisible();
  });
});

test.describe("Backtest Lab Features", () => {
  test("backtest form renders all inputs", async ({ page }) => {
    await page.goto("/backtest", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Backtest Lab" })).toBeVisible({ timeout: 15_000 });

    const strategySelect = page.locator("select").first();
    await expect(strategySelect).toBeVisible();
    await expect(page.getByRole("button", { name: "Run Backtest" })).toBeVisible();
    await expect(page.getByRole("spinbutton")).toBeVisible();
  });

  test("strategy dropdown has 5 options", async ({ page }) => {
    await page.goto("/backtest", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Backtest Lab" })).toBeVisible({ timeout: 15_000 });

    const options = page.locator("select").first().locator("option");
    await expect(options).toHaveCount(5);
  });

  test("backtest history table renders", async ({ page }) => {
    await page.goto("/backtest", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Backtest Lab" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByRole("heading", { name: "Backtest History" })).toBeVisible();
    const table = page.locator("table").last();
    await expect(table.getByRole("columnheader", { name: "Strategy" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Return" })).toBeVisible();
  });
});

test.describe("Analytics Features", () => {
  test("analytics stats cards render", async ({ page }) => {
    await page.goto("/analytics", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Trading Analytics" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText("Total Trades")).toBeVisible();
  });

  test("signal history table renders", async ({ page }) => {
    await page.goto("/analytics", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Trading Analytics" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByRole("heading", { name: "Signal History" })).toBeVisible();
  });

  test("win/loss distribution section renders", async ({ page }) => {
    await page.goto("/analytics", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Trading Analytics" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText("Win / Loss Distribution")).toBeVisible();
  });
});

test.describe("Settings Features", () => {
  test("exchange configuration section renders", async ({ page }) => {
    await page.goto("/settings", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByRole("heading", { name: "Exchange Configuration" })).toBeVisible();
    await expect(page.getByText("Exchange", { exact: true })).toBeVisible();
    await expect(page.getByPlaceholder("Enter API Key")).toBeVisible();
    await expect(page.getByPlaceholder("Enter API Secret")).toBeVisible();
    await expect(page.getByRole("button", { name: "Save Exchange Settings" })).toBeVisible();
  });

  test("risk management section renders with defaults", async ({ page }) => {
    await page.goto("/settings", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByRole("heading", { name: "Risk Management" })).toBeVisible();
    await expect(page.getByText("Risk Per Trade")).toBeVisible();
    await expect(page.getByText("Max Leverage")).toBeVisible();
    await expect(page.getByText("Max Positions")).toBeVisible();
    await expect(page.getByRole("button", { name: "Save Risk Parameters" })).toBeVisible();
  });

  test("notification section renders", async ({ page }) => {
    await page.goto("/settings", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
    await expect(page.getByText("Enable Telegram Notifications")).toBeVisible();
    await expect(page.getByText("Enable Discord Notifications")).toBeVisible();
    await expect(page.getByRole("button", { name: "Save Notification Settings" })).toBeVisible();
  });

  test("API key input accepts text", async ({ page }) => {
    await page.goto("/settings", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible({ timeout: 15_000 });

    const apiKeyInput = page.getByPlaceholder("Enter API Key");
    await apiKeyInput.fill("test-api-key-123");
    await expect(apiKeyInput).toHaveValue("test-api-key-123");
  });
});
