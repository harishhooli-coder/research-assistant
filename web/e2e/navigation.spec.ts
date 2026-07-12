import { expect, test } from "@playwright/test";

import { mockResearchApi } from "./helpers/mock-api";

test.describe("Site navigation", () => {
  test.beforeEach(async ({ page }) => {
    await mockResearchApi(page);
  });

  test("header links switch between Research and History", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("navigation").getByRole("link", { name: "Research", exact: true }),
    ).toBeVisible();

    await page.getByRole("navigation").getByRole("link", { name: "History" }).click();
    await expect(page).toHaveURL("/history");

    await page.getByRole("navigation").getByRole("link", { name: "Research", exact: true }).click();
    await expect(page).toHaveURL("/");
  });

  test("logo returns to home", async ({ page }) => {
    await page.goto("/history");
    await page.getByRole("link", { name: /Research Assistant|Research/ }).first().click();
    await expect(page).toHaveURL("/");
  });

  test("highlights the active navigation item", async ({ page }) => {
    await page.goto("/");
    const researchLink = page
      .getByRole("navigation")
      .getByRole("link", { name: "Research", exact: true });
    await expect(researchLink).toHaveClass(/text-primary/);

    await page.getByRole("navigation").getByRole("link", { name: "History" }).click();
    const historyLink = page
      .getByRole("navigation")
      .getByRole("link", { name: "History" });
    await expect(historyLink).toHaveClass(/text-primary/);
  });

  test("shows authenticated user controls in the header", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("button", { name: "Toggle theme" })).toBeVisible();
    await expect(page.locator(".cl-userButton-root, [data-clerk-component='user-button']")).toBeVisible();
  });
});
