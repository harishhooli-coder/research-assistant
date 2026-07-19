import { defineConfig, devices } from "@playwright/test";

process.loadEnvFile(".env.local");

const PORT = process.env.PLAYWRIGHT_PORT ?? "3000";
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${PORT}`;
const isRemote = /^https?:\/\//i.test(baseURL) && !/localhost|127\.0\.0\.1/i.test(baseURL);
const captureEvidence =
  process.env.PLAYWRIGHT_EVIDENCE === "1" ||
  process.env.PLAYWRIGHT_EVIDENCE === "true" ||
  isRemote;

export default defineConfig({
  testDir: "./e2e",
  outputDir: "test-results",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : captureEvidence ? 1 : 0,
  workers: process.env.CI || isRemote ? 1 : undefined,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
    ["json", { outputFile: "test-results/results.json" }],
  ],
  timeout: isRemote ? 90_000 : 60_000,
  expect: { timeout: isRemote ? 20_000 : 10_000 },
  use: {
    baseURL,
    trace: captureEvidence ? "on" : "on-first-retry",
    screenshot: captureEvidence ? "on" : "only-on-failure",
    video: captureEvidence ? "on" : "off",
    actionTimeout: isRemote ? 20_000 : undefined,
  },
  projects: [
    {
      name: "global setup",
      testMatch: /global\.setup\.ts/,
    },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "playwright/.clerk/user.json",
      },
      dependencies: ["global setup"],
      testIgnore: /auth\.spec\.ts/,
    },
    {
      name: "chromium-unauth",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["global setup"],
      testMatch: /auth\.spec\.ts/,
    },
  ],
  // Against a deployed server we never start a local Next.js process.
  ...(isRemote
    ? {}
    : {
        webServer: {
          command: "npm run dev",
          url: baseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          env: {
            ...process.env,
            NEXT_PUBLIC_API_URL:
              process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000",
          },
        },
      }),
});
