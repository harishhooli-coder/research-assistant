import { expect, test } from "@playwright/test";

import { mockResearchApi, TEST_JOB_ID, TEST_QUERY } from "./helpers/mock-api";

test.describe("Research job page", () => {
  test("shows event timeline with timestamps during a live run", async ({
    page,
  }) => {
    await mockResearchApi(page, { initialStatus: "running" });
    await page.goto(`/research/${TEST_JOB_ID}`);

    await expect(page.getByText("Event timeline")).toBeVisible();
    await expect(page.getByText("Query submitted", { exact: true })).toBeVisible();
    await expect(page.getByText("Supervisor")).toBeVisible();
    await expect(page.getByText("T+", { exact: false }).first()).toBeVisible();
  });

  test("streams to completion and renders markdown result", async ({ page }) => {
    await mockResearchApi(page, { initialStatus: "running" });
    await page.goto(`/research/${TEST_JOB_ID}`);

    await expect(
      page.getByText("Research complete — report ready below"),
    ).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("Playwright E2E Result")).toBeVisible();
    await expect(page.getByRole("link", { name: /Playwright docs/i })).toBeVisible();
  });

  test("displays persisted timeline for a completed job from history", async ({
    page,
  }) => {
    await mockResearchApi(page, { initialStatus: "done" });
    await page.goto(`/research/${TEST_JOB_ID}`);

    await expect(page.getByText("Event timeline")).toBeVisible();
    await expect(page.getByText("Researcher")).toBeVisible();
    await expect(page.getByText("Editor")).toBeVisible();
    await expect(page.getByText("Total duration")).toBeVisible();
    await expect(page.getByText(TEST_QUERY)).toBeVisible();
  });

  test("navigates back to new research", async ({ page }) => {
    await mockResearchApi(page, { initialStatus: "done" });
    await page.goto(`/research/${TEST_JOB_ID}`);

    await page.getByRole("button", { name: "New research" }).click();
    await expect(page).toHaveURL("/");
    await expect(page.getByLabel("Research query")).toBeVisible();
  });

  test("renders sources with external links on completion", async ({ page }) => {
    await mockResearchApi(page, { initialStatus: "done" });
    await page.goto(`/research/${TEST_JOB_ID}`);

    await expect(
      page.getByText("Research complete — report ready below"),
    ).toBeVisible();
    await expect(
      page.locator('[data-slot="card-title"]').filter({ hasText: "Sources" }),
    ).toBeVisible();
    const sourceLink = page.getByRole("link", { name: /Playwright docs/i });
    await expect(sourceLink).toHaveAttribute("href", "https://playwright.dev/docs/intro");
    await expect(sourceLink).toHaveAttribute("target", "_blank");
  });

  test("shows progress bar while job is running", async ({ page }) => {
    await mockResearchApi(page, {
      initialStatus: "running",
      freezeStream: true,
    });
    await page.goto(`/research/${TEST_JOB_ID}`);

    // freezeStream emits a 30% progress event, so the UI shows pct text
    // rather than the zero-progress "Starting agents…" placeholder.
    await expect(page.getByText("30% complete")).toBeVisible();
    await expect(page.getByText("Running", { exact: true })).toBeVisible();
    await expect(page.getByText("Planning research steps.")).toBeVisible();
  });
});
