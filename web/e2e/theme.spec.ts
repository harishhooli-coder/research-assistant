import { expect, test } from "@playwright/test";

import { mockResearchApi } from "./helpers/mock-api";

test.describe("Theme toggle", () => {
  test.beforeEach(async ({ page }) => {
    await mockResearchApi(page);
  });

  test("switches between light and dark themes", async ({ page }) => {
    await page.goto("/");

    const html = page.locator("html");
    const toggle = page.getByRole("button", { name: "Toggle theme" });

    await expect(toggle).toBeVisible();

    const initialDark = await html.evaluate((el) => el.classList.contains("dark"));

    await toggle.click();
    await expect(html).toHaveClass(initialDark ? /^(?!.*\bdark\b)/ : /dark/);

    await toggle.click();
    if (initialDark) {
      await expect(html).toHaveClass(/dark/);
    } else {
      await expect(html).not.toHaveClass(/dark/);
    }
  });

  test("persists theme choice across navigation", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("button", { name: "Toggle theme" }).click();
    const isDark = await page
      .locator("html")
      .evaluate((el) => el.classList.contains("dark"));

    await page.getByRole("navigation").getByRole("link", { name: "History" }).click();
    await expect(page).toHaveURL("/history");

    const stillDark = await page
      .locator("html")
      .evaluate((el) => el.classList.contains("dark"));
    expect(stillDark).toBe(isDark);
  });
});
