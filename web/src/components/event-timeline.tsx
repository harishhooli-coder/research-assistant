"use client";

import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  CircleDotIcon,
  ClockIcon,
  FileTextIcon,
  Loader2Icon,
  RadioIcon,
  SearchIcon,
  SendIcon,
  SparklesIcon,
  XCircleIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { formatClock, formatDateTime, formatDelta, formatDuration, parseTime } from "@/lib/time";

export type TimelineEventKind =
  | "submitted"
  | "progress"
  | "completed"
  | "failed"
  | "connected";

export interface TimelineEvent {
  id: string;
  kind: TimelineEventKind;
  timestamp: string;
  phase?: string;
  pct?: number;
  message?: string;
  error?: string;
}

interface EventTimelineProps {
  events: TimelineEvent[];
  startedAt?: string | null;
  finishedAt?: string | null;
  isLive?: boolean;
  emptyMessage?: string;
  className?: string;
}

const PHASE_ICONS: Record<string, typeof ClockIcon> = {
  queued: ClockIcon,
  submitted: SendIcon,
  running: Loader2Icon,
  supervisor: SparklesIcon,
  researcher: SearchIcon,
  editor: FileTextIcon,
  done: CheckCircle2Icon,
  completed: CheckCircle2Icon,
  failed: XCircleIcon,
  connected: RadioIcon,
};

function eventIcon(event: TimelineEvent) {
  if (event.kind === "completed") return CheckCircle2Icon;
  if (event.kind === "failed") return XCircleIcon;
  if (event.kind === "connected") return RadioIcon;
  if (event.kind === "submitted") return SendIcon;
  const phase = (event.phase ?? "").toLowerCase();
  return PHASE_ICONS[phase] ?? CircleDotIcon;
}

function eventTone(event: TimelineEvent): string {
  if (event.kind === "failed") {
    return "border-destructive/30 bg-destructive/5 text-destructive";
  }
  if (event.kind === "completed") {
    return "border-primary/30 bg-primary/5 text-primary";
  }
  if (event.kind === "connected") {
    return "border-sky-500/30 bg-sky-500/5 text-sky-600 dark:text-sky-400";
  }
  const phase = (event.phase ?? "").toLowerCase();
  if (phase === "supervisor") {
    return "border-violet-500/30 bg-violet-500/5 text-violet-600 dark:text-violet-400";
  }
  if (phase === "researcher") {
    return "border-amber-500/30 bg-amber-500/5 text-amber-600 dark:text-amber-400";
  }
  if (phase === "editor") {
    return "border-blue-500/30 bg-blue-500/5 text-blue-600 dark:text-blue-400";
  }
  return "border-border/60 bg-muted/30 text-foreground";
}

function eventTitle(event: TimelineEvent): string {
  if (event.kind === "submitted") return "Query submitted";
  if (event.kind === "connected") return "Live stream connected";
  if (event.kind === "completed") return "Research complete";
  if (event.kind === "failed") return "Research failed";
  const phase = event.phase ?? "progress";
  return phase.charAt(0).toUpperCase() + phase.slice(1);
}

export function EventTimeline({
  events,
  startedAt,
  finishedAt,
  isLive = false,
  emptyMessage = "Waiting for events…",
  className,
}: EventTimelineProps) {
  const anchor = parseTime(startedAt ?? events[0]?.timestamp);
  const end = parseTime(finishedAt ?? events.at(-1)?.timestamp);
  const totalMs =
    anchor && end ? Math.max(0, end.getTime() - anchor.getTime()) : null;

  if (events.length === 0) {
    return (
      <p className={cn("text-sm text-muted-foreground", className)}>{emptyMessage}</p>
    );
  }

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {startedAt ? (
          <span>
            Started{" "}
            <time dateTime={startedAt} className="font-medium text-foreground">
              {formatDateTime(startedAt)}
            </time>
          </span>
        ) : null}
        {totalMs !== null ? (
          <span>
            Total duration{" "}
            <span className="font-medium text-foreground">{formatDuration(totalMs)}</span>
          </span>
        ) : null}
        {isLive ? (
          <span className="inline-flex items-center gap-1 font-medium text-primary">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary/60 opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-primary" />
            </span>
            Live
          </span>
        ) : null}
      </div>

      <ol className="relative space-y-0">
        {events.map((event, index) => {
          const Icon = eventIcon(event);
          const current = parseTime(event.timestamp);
          const previous = index > 0 ? parseTime(events[index - 1]?.timestamp) : null;
          const deltaMs =
            current && previous
              ? current.getTime() - previous.getTime()
              : null;
          const elapsedMs =
            anchor && current ? current.getTime() - anchor.getTime() : null;
          const isLast = index === events.length - 1;

          return (
            <li key={event.id} className="relative flex gap-3 pb-6 last:pb-0">
              {!isLast ? (
                <span
                  aria-hidden
                  className="absolute left-[15px] top-8 bottom-0 w-px bg-border/80"
                />
              ) : null}

              <div
                className={cn(
                  "relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full border-2 border-background shadow-sm",
                  eventTone(event),
                )}
              >
                <Icon className="size-3.5" />
              </div>

              <div className="min-w-0 flex-1 pt-0.5">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="font-heading text-sm font-semibold">
                    {eventTitle(event)}
                  </span>
                  <time
                    dateTime={event.timestamp}
                    className="font-mono text-xs text-muted-foreground"
                    title={formatDateTime(event.timestamp)}
                  >
                    {formatClock(event.timestamp)}
                  </time>
                  {elapsedMs !== null && elapsedMs >= 0 ? (
                    <span className="text-xs text-muted-foreground">
                      T+{formatDuration(elapsedMs)}
                    </span>
                  ) : null}
                  {deltaMs !== null && index > 0 ? (
                    <span className="text-xs text-primary/80">{formatDelta(deltaMs)}</span>
                  ) : null}
                </div>

                {event.message ? (
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                    {event.message}
                  </p>
                ) : null}

                {event.error ? (
                  <p className="mt-1 flex items-start gap-1.5 text-sm text-destructive">
                    <AlertTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
                    {event.error}
                  </p>
                ) : null}

                {typeof event.pct === "number" && event.pct > 0 ? (
                  <div className="mt-2 flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary transition-all duration-300"
                        style={{ width: `${Math.min(100, event.pct)}%` }}
                      />
                    </div>
                    <span className="font-mono text-xs text-muted-foreground">
                      {Math.round(event.pct)}%
                    </span>
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function recordToTimelineEvent(record: {
  event: string;
  timestamp: string;
  data?: Record<string, unknown>;
}): TimelineEvent {
  const data = record.data ?? {};
  const phase = typeof data.phase === "string" ? data.phase : undefined;
  const pct = typeof data.pct === "number" ? data.pct : undefined;
  const message = typeof data.message === "string" ? data.message : undefined;
  const error = typeof data.error === "string" ? data.error : undefined;
  const kind = (
    ["submitted", "progress", "completed", "failed"].includes(record.event)
      ? record.event
      : "progress"
  ) as TimelineEventKind;

  return {
    id: `${record.timestamp}-${record.event}-${phase ?? ""}-${message ?? ""}`,
    kind,
    timestamp: record.timestamp,
    phase,
    pct,
    message,
    error,
  };
}

export function mergeTimelineEvents(
  existing: TimelineEvent[],
  incoming: TimelineEvent[],
): TimelineEvent[] {
  const map = new Map<string, TimelineEvent>();
  for (const event of [...existing, ...incoming]) {
    map.set(event.id, event);
  }
  return [...map.values()].sort(
    (a, b) =>
      (parseTime(a.timestamp)?.getTime() ?? 0) -
      (parseTime(b.timestamp)?.getTime() ?? 0),
  );
}

export function buildFallbackTimeline(job: {
  status: string;
  createdAt?: string | null;
  updatedAt?: string | null;
  error?: string | null;
}): TimelineEvent[] {
  const events: TimelineEvent[] = [];
  if (job.createdAt) {
    events.push({
      id: `fallback-submitted-${job.createdAt}`,
      kind: "submitted",
      timestamp: job.createdAt,
      phase: "queued",
      pct: 0,
      message: "Research query submitted.",
    });
  }
  if (job.status === "done" && job.updatedAt) {
    events.push({
      id: `fallback-completed-${job.updatedAt}`,
      kind: "completed",
      timestamp: job.updatedAt,
      phase: "done",
      pct: 100,
      message: "Research finished successfully.",
    });
  } else if (job.status === "failed" && job.updatedAt) {
    events.push({
      id: `fallback-failed-${job.updatedAt}`,
      kind: "failed",
      timestamp: job.updatedAt,
      phase: "failed",
      message: "Research failed.",
      error: job.error ?? undefined,
    });
  }
  return events;
}
