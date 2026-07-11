import { expect, test } from "@playwright/test";

import { mockResearchApi, TEST_JOB_ID, TEST_QUERY } from "./helpers/mock-api";

test.describe("History page", () => {
  test("lists past research runs", async ({ page }) => {
    await mockResearchApi(page);
    await page.goto("/history");

    await expect(page.getByRole("heading", { name: "History" })).toBeVisible();
    await expect(page.getByText(TEST_QUERY)).toBeVisible();
    await expect(page.getByText("Done")).toBeVisible();
  });

  test("opens a job from history", async ({ page }) => {
    await mockResearchApi(page, { initialStatus: "done" });
    await page.goto("/history");

    await page.getByRole("link", { name: new RegExp(TEST_QUERY) }).click();
    await expect(page).toHaveURL(new RegExp(`/research/${TEST_JOB_ID}$`));
    await expect(page.getByText("Event timeline")).toBeVisible();
  });

  test("shows empty state when no runs exist", async ({ page }) => {
    await mockResearchApi(page, { historyItems: [] });
    await page.goto("/history");

    await expect(page.getByText("No research runs yet")).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Start your first research" }),
    ).toBeVisible();
  });
});
