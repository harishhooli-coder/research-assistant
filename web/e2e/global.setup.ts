import { clerk, clerkSetup, setupClerkTestingToken } from "@clerk/testing/playwright";
import { createClerkClient } from "@clerk/backend";
import { test as setup } from "@playwright/test";
import fs from "fs";
import path from "path";

setup.describe.configure({ mode: "serial" });

const authDir = path.join(__dirname, "../playwright/.clerk");
const authFile = path.join(authDir, "user.json");

const E2E_EMAIL =
  process.env.E2E_CLERK_USER_EMAIL ?? "e2e+clerk_test@example.com";
const E2E_PASSWORD =
  process.env.E2E_CLERK_USER_PASSWORD ?? "E2eTestPass123!";

setup("global setup", async () => {
  await clerkSetup({ dotenv: false });

  if (!process.env.CLERK_SECRET_KEY) {
    throw new Error(
      "CLERK_SECRET_KEY is required for e2e tests. Copy web/.env.local.example to .env.local.",
    );
  }

  fs.mkdirSync(authDir, { recursive: true });

  const client = createClerkClient({
    secretKey: process.env.CLERK_SECRET_KEY,
  });

  const { data: users } = await client.users.getUserList({
    emailAddress: [E2E_EMAIL],
  });

  if (users.length === 0) {
    await client.users.createUser({
      emailAddress: [E2E_EMAIL],
      password: E2E_PASSWORD,
      firstName: "E2E",
      lastName: "Tester",
    });
  } else {
    await client.users.updateUser(users[0].id, {
      password: E2E_PASSWORD,
    });
  }
});

setup("authenticate", async ({ page }) => {
  // Public page that loads Clerk — required before clerk.signIn().
  await page.goto("/sign-in");
  await setupClerkTestingToken({ page });
  await clerk.signIn({
    page,
    emailAddress: E2E_EMAIL,
  });

  await page.goto("/");
  await page
    .getByRole("heading", { name: "Ask anything. Get a sourced answer." })
    .waitFor({ timeout: 30_000 });

  await page.context().storageState({ path: authFile });
});
