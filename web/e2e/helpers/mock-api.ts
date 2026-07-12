import type { Page, Route } from "@playwright/test";

export const API_BASE =
  process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

export const TEST_JOB_ID = "e2e-test-job-001";
export const TEST_QUERY = "What is Playwright used for?";

const NOW = "2026-07-05T12:00:00.000Z";
const LATER = "2026-07-05T12:00:05.000Z";
const DONE_AT = "2026-07-05T12:00:30.000Z";

export interface MockJobState {
  status: "queued" | "running" | "done" | "failed";
  result?: { markdown: string; sources: { title: string; url: string }[] };
  error?: string;
}

export const defaultEvents = [
  {
    event: "submitted",
    timestamp: NOW,
    data: {
      phase: "queued",
      pct: 0,
      message: "Research query submitted and queued.",
    },
  },
  {
    event: "progress",
    timestamp: LATER,
    data: {
      phase: "supervisor",
      pct: 30,
      message: "Planning research steps.",
    },
  },
  {
    event: "progress",
    timestamp: "2026-07-05T12:00:10.000Z",
    data: {
      phase: "researcher",
      pct: 60,
      message: "Searching the web for sources.",
    },
  },
  {
    event: "progress",
    timestamp: "2026-07-05T12:00:20.000Z",
    data: {
      phase: "editor",
      pct: 90,
      message: "Writing the final answer.",
    },
  },
  {
    event: "completed",
    timestamp: DONE_AT,
    data: {
      phase: "done",
      pct: 100,
      message: "Research finished successfully.",
    },
  },
];

export function jobDetail(
  jobId: string,
  query: string,
  state: MockJobState,
) {
  return {
    jobId,
    query,
    status: state.status,
    result: state.result ?? null,
    error: state.error ?? null,
    createdAt: NOW,
    updatedAt: state.status === "queued" ? NOW : DONE_AT,
  };
}

function apiPattern(path: string): RegExp {
  const escaped = API_BASE.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`${escaped}${path}`);
}

/** Mock FastAPI routes so E2E tests run without a live backend. */
export async function mockResearchApi(
  page: Page,
  options: {
    jobId?: string;
    query?: string;
    initialStatus?: MockJobState["status"];
    error?: string;
    streamProgress?: boolean;
    failOnStream?: boolean;
    historyItems?: Array<{
      jobId: string;
      query: string;
      status: MockJobState["status"];
      createdAt?: string;
    }>;
    historyError?: { status: number; message: string };
    submitError?: { status: number; message: string };
    jobNotFound?: boolean;
    submitDelayMs?: number;
    freezeStream?: boolean;
  } = {},
) {
  const jobId = options.jobId ?? TEST_JOB_ID;
  const query = options.query ?? TEST_QUERY;
  let status = options.initialStatus ?? "running";
  const jobError = options.error ?? "Research pipeline failed.";
  const result = {
    markdown: "# Playwright E2E Result\n\nAutomated testing works.",
    sources: [
      {
        title: "Playwright docs",
        url: "https://playwright.dev/docs/intro",
      },
    ],
  };

  await page.route(apiPattern("/research"), async (route: Route) => {
    const method = route.request().method();

    if (method === "POST") {
      if (options.submitError) {
        await route.fulfill({
          status: options.submitError.status,
          contentType: "application/json",
          body: JSON.stringify({ detail: options.submitError.message }),
        });
        return;
      }
      if (options.submitDelayMs) {
        await new Promise((resolve) =>
          setTimeout(resolve, options.submitDelayMs),
        );
      }
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ jobId }),
      });
      return;
    }

    if (method === "GET") {
      if (options.historyError) {
        await route.fulfill({
          status: options.historyError.status,
          contentType: "application/json",
          body: JSON.stringify({ detail: options.historyError.message }),
        });
        return;
      }
      const items =
        options.historyItems ??
        [
          {
            jobId,
            query,
            status: "done" as const,
            createdAt: NOW,
          },
        ];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(items),
      });
      return;
    }

    await route.continue();
  });

  await page.route(apiPattern(`/research/${jobId}$`), async (route: Route) => {
    if (options.jobNotFound) {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Job not found." }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        jobDetail(jobId, query, {
          status,
          result: status === "done" ? result : undefined,
          error: status === "failed" ? jobError : undefined,
        }),
      ),
    });
  });

  await page.route(
    apiPattern(`/research/${jobId}/events`),
    async (route: Route) => {
      if (options.jobNotFound) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Job not found." }),
        });
        return;
      }
      const events =
        status === "done"
          ? defaultEvents
          : defaultEvents.filter((e) => e.event !== "completed");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(events),
      });
    },
  );

  if (options.jobNotFound) {
    await page.route(
      apiPattern(`/research/${jobId}/stream`),
      async (route: Route) => {
        await route.abort("failed");
      },
    );
  }

  if (options.streamProgress !== false && !options.jobNotFound) {
    await page.route(
      apiPattern(`/research/${jobId}/stream`),
      async (route: Route) => {
        if (status === "done") {
          await route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            body: [
              `event: completed\n`,
              `data: ${JSON.stringify(result)}\n\n`,
            ].join(""),
          });
          return;
        }

        if (status === "failed" || options.failOnStream) {
          const failedMessage = jobError;
          status = "failed";
          await route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            body: [
              `event: failed\n`,
              `data: ${JSON.stringify({
                error: failedMessage,
                timestamp: LATER,
              })}\n\n`,
            ].join(""),
          });
          return;
        }

        if (options.freezeStream) {
          await route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            body: [
              `event: progress\n`,
              `data: ${JSON.stringify({
                phase: "supervisor",
                pct: 30,
                message: "Planning research steps.",
                timestamp: LATER,
              })}\n\n`,
            ].join(""),
          });
          return;
        }

        const sse = [
          `event: progress\n`,
          `data: ${JSON.stringify({
            phase: "supervisor",
            pct: 30,
            message: "Planning research steps.",
            timestamp: LATER,
          })}\n\n`,
          `event: progress\n`,
          `data: ${JSON.stringify({
            phase: "researcher",
            pct: 70,
            message: "Searching the web.",
            timestamp: "2026-07-05T12:00:15.000Z",
          })}\n\n`,
          `event: completed\n`,
          `data: ${JSON.stringify(result)}\n\n`,
        ].join("");

        status = "done";

        await route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: sse,
        });
      },
    );
  }

  return { jobId, query };
}
