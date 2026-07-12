import { expect, test } from "@playwright/test";

import { mockResearchApi, TEST_JOB_ID, TEST_QUERY } from "./helpers/mock-api";

test.describe("Error handling", () => {
  test("shows a toast when research submission fails", async ({ page }) => {
    await mockResearchApi(page, {
      submitError: { status: 503, message: "Backend unavailable." },
    });
    await page.goto("/");

    await page.getByLabel("Research query").fill(TEST_QUERY);
    await page.getByRole("button", { name: "Research", exact: true }).click();

    await expect(page.getByText("Could not start research")).toBeVisible();
    await expect(page.getByText("Backend unavailable.")).toBeVisible();
    await expect(page).toHaveURL("/");
  });

  test("shows retry UI when history fails to load", async ({ page }) => {
    await mockResearchApi(page, {
      historyError: { status: 500, message: "History service unavailable." },
    });
    await page.goto("/history");

    await expect(page.getByText("History service unavailable.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
  });

  test("displays a failed job with error details", async ({ page }) => {
    await mockResearchApi(page, {
      initialStatus: "failed",
      error: "Agent timeout after 30s.",
      streamProgress: false,
    });
    await page.goto(`/research/${TEST_JOB_ID}`);

    await expect(
      page.locator('[data-slot="card-title"]').filter({ hasText: "Research failed" }),
    ).toBeVisible();
    await expect(page.getByText("Agent timeout after 30s.")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Try a new query" }),
    ).toBeVisible();
  });

  test("shows failure when the live stream reports an error", async ({
    page,
  }) => {
    await mockResearchApi(page, {
      initialStatus: "running",
      failOnStream: true,
      error: "Worker crashed unexpectedly.",
    });
    await page.goto(`/research/${TEST_JOB_ID}`);

    await expect(
      page.getByText("Worker crashed unexpectedly.").last(),
    ).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.locator('[data-slot="card-title"]').filter({ hasText: "Research failed" }),
    ).toBeVisible();
  });

  test("shows load error when job is not found", async ({ page }) => {
    await mockResearchApi(page, { jobNotFound: true });
    await page.goto(`/research/${TEST_JOB_ID}`);

    await expect(page.getByText(/Job not found/i)).toBeVisible();
    await expect(page.getByText(/Retrying live updates/i)).toBeVisible();
  });
});
