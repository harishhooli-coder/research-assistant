/**
 * Typed fetch helpers for the FastAPI research backend.
 *
 * The browser talks ONLY to FastAPI (never a DB directly). The base URL is
 * configured via NEXT_PUBLIC_API_URL (see .env.local.example).
 *
 * REST request/response types are generated from docs/api/openapi.json.
 * Regenerate with: npm run docs:update (from web/) or scripts/update-docs.ps1
 */

import type { components } from "./api.generated";

type Schemas = components["schemas"];

export type ResearchStatus = Schemas["JobSummary"]["status"];

/** Final research payload when status is "done". */
export type ResearchResultPayload = Schemas["ResearchResultPayload"];

export type ResearchSource = Schemas["ResearchSource"];

/** Summary row used by the history list (GET /research). */
export type ResearchSummary = Schemas["JobSummary"];

/** Full job detail (GET /research/{jobId}). */
export type ResearchJob = Schemas["JobDetail"];

/** SSE event payloads. */
export interface ProgressEvent {
  phase: string;
  pct: number;
  message: string;
  timestamp?: string;
}

export interface FailedEvent {
  error: string;
  timestamp?: string;
}

/** Persisted timeline record (GET /research/{jobId}/events). */
export type JobEventRecord = Schemas["JobEvent"];

/**
 * Thrown by the fetch helpers when the backend is reachable but returns a
 * non-2xx status, or when the network request itself fails.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Resolve the configured API base URL, throwing a descriptive error when it is
 * missing so UI components can render a clear configuration message.
 */
export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  if (!raw) {
    throw new ApiError(
      "NEXT_PUBLIC_API_URL is not set. Copy .env.local.example to .env.local and point it at your FastAPI backend.",
    );
  }
  // Normalise away any trailing slash so path joins are predictable.
  return raw.replace(/\/+$/, "");
}

/** Build an absolute URL against the API base. */
export function apiUrl(path: string): string {
  const base = getApiBaseUrl();
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch (err) {
    // Network error / backend unreachable / CORS.
    const detail = err instanceof Error ? err.message : String(err);
    throw new ApiError(
      `Could not reach the backend at ${getApiBaseUrl()}. Is FastAPI running and is CORS configured? (${detail})`,
    );
  }

  if (!res.ok) {
    let message = `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      if (body && typeof body === "object") {
        message =
          (body as { detail?: string; error?: string; message?: string })
            .detail ??
          (body as { error?: string }).error ??
          (body as { message?: string }).message ??
          message;
      }
    } catch {
      // Response body was not JSON; keep the generic message.
    }
    throw new ApiError(message, res.status);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

/** POST /research -> 202 { jobId } */
export async function submitResearch(
  query: string,
  options?: { notifyEmail?: string },
): Promise<{ jobId: string }> {
  const body: { query: string; notifyEmail?: string } = { query };
  const notifyEmail = options?.notifyEmail?.trim();
  if (notifyEmail) {
    body.notifyEmail = notifyEmail;
  }
  return request<{ jobId: string }>("/research", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** GET /research -> recent runs (most recent first). */
export async function listResearch(
  init?: RequestInit,
): Promise<ResearchSummary[]> {
  return request<ResearchSummary[]>("/research", {
    cache: "no-store",
    ...init,
  });
}

/** GET /research/{jobId} -> full job detail. */
export async function getResearch(
  jobId: string,
  init?: RequestInit,
): Promise<ResearchJob> {
  return request<ResearchJob>(`/research/${encodeURIComponent(jobId)}`, {
    cache: "no-store",
    ...init,
  });
}

/** GET /research/{jobId}/events -> persisted timeline (oldest first). */
export async function getJobEvents(
  jobId: string,
  init?: RequestInit,
): Promise<JobEventRecord[]> {
  return request<JobEventRecord[]>(`/research/${encodeURIComponent(jobId)}/events`, {
    cache: "no-store",
    ...init,
  });
}

/** Build the SSE stream URL for a job (consumed by EventSource). */
export function streamUrl(jobId: string): string {
  return apiUrl(`/research/${encodeURIComponent(jobId)}/stream`);
}
