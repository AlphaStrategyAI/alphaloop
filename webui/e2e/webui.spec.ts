// Playwright e2e smoke tests (require dev server + backend running)
// Run with: npx playwright test

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.WEBUI_URL ?? "http://localhost:5173";

test.describe("alphaloop webui", () => {
  test("top-5 view has 5 cards", async ({ page }) => {
    await page.goto(BASE_URL);
    await expect(page.getByTestId("top-five-card")).toHaveCount(5, { timeout: 10000 });
  });

  test("dark mode background", async ({ page }) => {
    await page.goto(BASE_URL);
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    // rgb(11, 14, 20) is #0B0E14
    expect(bg).toBe("rgb(11, 14, 20)");
  });

  test("strategy detail route loads", async ({ page }) => {
    await page.goto(`${BASE_URL}/strategy/task-0001?rid=test-rid`);
    await expect(page.getByText(/Back to top-5/)).toBeVisible({ timeout: 10000 });
  });

  test("replay route loads", async ({ page }) => {
    await page.goto(`${BASE_URL}/replay/test-rid`);
    await expect(page.getByTestId("play-btn")).toBeVisible({ timeout: 10000 });
  });
});
