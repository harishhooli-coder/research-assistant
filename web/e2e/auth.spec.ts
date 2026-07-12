import { expect, test } from "@playwright/test";

test.describe("Authentication", () => {
  test("redirects unauthenticated users to sign-in", async ({ page }) => {
    await page.goto("/");

    await expect(page).toHaveURL(/\/sign-in/);
  });

  test("sign-in page renders the Clerk sign-in form", async ({ page }) => {
    await page.goto("/sign-in");

    await expect(page.locator("[data-clerk-component]")).toBeVisible();
    await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();
  });

  test("sign-up page renders the Clerk sign-up form", async ({ page }) => {
    await page.goto("/sign-up");

    await expect(page.locator("[data-clerk-component]")).toBeVisible();
  });

  test("sign-in page links to sign-up", async ({ page }) => {
    await page.goto("/sign-in");

    await page.getByRole("link", { name: /sign up/i }).click();
    await expect(page).toHaveURL(/\/sign-up/);
  });
});
