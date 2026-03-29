/**
 * Shared helpers for Playwright E2E tests.
 *
 * Provides JWT route interception so the frontend can talk to the
 * authenticated backend API during tests.
 */

import { type Page } from "@playwright/test";

// Generate a fresh token before running tests:
//   cd backend && .venv/Scripts/python.exe -c \
//     "from app.api.auth import create_access_token; print(create_access_token('e2e-test'))"
// Then set E2E_JWT_TOKEN env var, or use the fallback below.
const JWT_TOKEN =
  process.env.E2E_JWT_TOKEN ??
  // fallback: 24h token for local dev (regenerate if expired)
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlMmUtdGVzdC11c2VyIiwiZXhwIjoxNzcxMDU1NzMxLCJpYXQiOjE3NzA5NjkzMzF9.GWDcPciZLPcT7yjadw1KNCsEKGBz0xa8RdXmuX4_DHk";

/**
 * Intercept all /api/* requests and inject the JWT Authorization header.
 * Call this once per test (or in beforeEach) before navigating.
 */
export async function injectAuth(page: Page): Promise<void> {
  if (!JWT_TOKEN) return; // no token → skip injection (tests still run, API returns 401)

  await page.route("**/api/**", async (route) => {
    const headers = {
      ...route.request().headers(),
      authorization: `Bearer ${JWT_TOKEN}`,
    };
    await route.continue({ headers });
  });
}

/**
 * Navigate to a page and wait for the health check to resolve.
 */
export async function gotoAndWait(page: Page, path: string): Promise<void> {
  await page.goto(path, { waitUntil: "networkidle" });
}
