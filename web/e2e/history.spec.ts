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
      page.getByRole("link", { name: "Start your first research" }).or(
        page.getByRole("button", { name: "Start your first research" }),
      ),
    ).toBeVisible();
  });

  test("empty state link navigates to home", async ({ page }) => {
    await mockResearchApi(page, { historyItems: [] });
    await page.goto("/history");

    const startLink = page
      .getByRole("link", { name: "Start your first research" })
      .or(page.getByRole("button", { name: "Start your first research" }));
    await startLink.click();
    await expect(page).toHaveURL("/");
    await expect(page.getByLabel("Research query")).toBeVisible();
  });

  test("refresh reloads the history list", async ({ page }) => {
    let requestCount = 0;
    await mockResearchApi(page);
    await page.route(/\/research$/, async (route) => {
      if (route.request().method() === "GET") {
        requestCount += 1;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              jobId: TEST_JOB_ID,
              query: TEST_QUERY,
              status: "done",
              createdAt: "2026-07-05T12:00:00.000Z",
            },
          ]),
        });
        return;
      }
      await route.continue();
    });
    await page.goto("/history");
    await expect(page.getByText(TEST_QUERY)).toBeVisible();

    await page.getByRole("button", { name: "Refresh history" }).click();
    await expect.poll(() => requestCount).toBeGreaterThan(1);
  });

  test("shows status badges for different job states", async ({ page }) => {
    await mockResearchApi(page, {
      historyItems: [
        {
          jobId: "job-running",
          query: "Running query",
          status: "running",
          createdAt: "2026-07-05T12:00:00.000Z",
        },
        {
          jobId: "job-failed",
          query: "Failed query",
          status: "failed",
          createdAt: "2026-07-05T11:00:00.000Z",
        },
      ],
    });
    await page.goto("/history");

    await expect(
      page.getByRole("link", { name: /Running query/ }).getByText("Running", {
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /Failed query/ }).getByText("Failed", {
        exact: true,
      }),
    ).toBeVisible();
  });
});
