import { expect, test } from "@playwright/test";

import { mockResearchApi, TEST_QUERY } from "./helpers/mock-api";

test.describe("Home page", () => {
  test("renders research form and feature cards", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: "Ask anything. Get a sourced answer." }),
    ).toBeVisible();
    await expect(page.getByLabel("Research query")).toBeVisible();
    await expect(page.getByRole("button", { name: "Research", exact: true })).toBeVisible();
    await expect(page.getByText("Web search")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Live progress" })).toBeVisible();
  });

  test("example chips fill the query input", async ({ page }) => {
    await page.goto("/");

    await page
      .getByRole("button", {
        name: "Compare the leading open-source vector databases.",
      })
      .click();

    await expect(page.getByLabel("Research query")).toHaveValue(
      "Compare the leading open-source vector databases.",
    );
  });

  test("submits a query and navigates to the research page", async ({
    page,
  }) => {
    const { jobId } = await mockResearchApi(page);
    await page.goto("/");

    await page.getByLabel("Research query").fill(TEST_QUERY);
    await page.getByRole("button", { name: "Research", exact: true }).click();

    await expect(page).toHaveURL(new RegExp(`/research/${jobId}$`));
    await expect(page.getByText(TEST_QUERY)).toBeVisible();
  });
});
