/** Shared date/time formatting for timeline UI. */

export function parseTime(iso: string | number | undefined): Date | null {
  if (iso === undefined) return null;
  const date = typeof iso === "number" ? new Date(iso) : new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Wall-clock time with milliseconds, e.g. "9:38:12.456 PM". */
export function formatClock(iso: string | number | undefined): string {
  const date = parseTime(iso);
  if (!date) return "—";
  return date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
  });
}

/** Full locale datetime for headers. */
export function formatDateTime(iso: string | number | undefined): string {
  const date = parseTime(iso);
  if (!date) return "—";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Human duration, e.g. "2.4s", "1m 05s". */
export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const totalSeconds = ms / 1000;
  if (totalSeconds < 60) return `${totalSeconds.toFixed(1)}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

/** Compact delta label, e.g. "+2.4s". */
export function formatDelta(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "";
  if (ms < 1000) return `+${Math.round(ms)}ms`;
  return `+${(ms / 1000).toFixed(1)}s`;
}
