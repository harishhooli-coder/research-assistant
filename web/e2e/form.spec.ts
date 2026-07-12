import { expect, test } from "@playwright/test";

import { mockResearchApi, TEST_QUERY } from "./helpers/mock-api";

test.describe("Research form", () => {
  test.beforeEach(async ({ page }) => {
    await mockResearchApi(page);
  });

  test("disables submit when the query is empty or whitespace", async ({
    page,
  }) => {
    await page.goto("/");

    const submit = page.getByRole("button", { name: "Research", exact: true });
    await expect(submit).toBeDisabled();

    await page.getByLabel("Research query").fill("   ");
    await expect(submit).toBeDisabled();
  });

  test("shows a success toast after enqueueing research", async ({ page }) => {
    await page.goto("/");

    await page.getByLabel("Research query").fill(TEST_QUERY);
    await page.getByRole("button", { name: "Research", exact: true }).click();

    await expect(page.getByText("Research enqueued")).toBeVisible();
    await expect(page.getByText("Streaming live progress…")).toBeVisible();
  });

  test("shows loading state while submitting", async ({ page }) => {
    await mockResearchApi(page, { submitDelayMs: 800 });
    await page.goto("/");

    await page.getByLabel("Research query").fill(TEST_QUERY);
    const submit = page.getByRole("button", { name: "Research", exact: true });
    await submit.click();

    await expect(page.getByRole("button", { name: "Submitting…" })).toBeDisabled();
    await expect(page.getByLabel("Research query")).toBeDisabled();
  });
});
