"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangleIcon,
  ArrowLeftIcon,
  CheckCircle2Icon,
  HistoryIcon,
  RadioIcon,
  RefreshCwIcon,
  WifiOffIcon,
} from "lucide-react";

import {
  EventTimeline,
  buildFallbackTimeline,
  mergeTimelineEvents,
  recordToTimelineEvent,
  type TimelineEvent,
} from "@/components/event-timeline";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { MarkdownResult } from "@/components/markdown-result";
import { ProgressBar } from "@/components/progress-bar";
import { StatusBadge } from "@/components/status-badge";
import { formatDateTime, formatDuration, parseTime } from "@/lib/time";
import {
  ApiError,
  getJobEvents,
  getResearch,
  streamUrl,
  type ProgressEvent as ResearchProgressEvent,
  type ResearchJob,
  type ResearchResultPayload,
  type ResearchStatus,
} from "@/lib/api";

type Connection = "connecting" | "streaming" | "polling" | "closed";

const TERMINAL: ResearchStatus[] = ["done", "failed"];
const POLL_INTERVAL_MS = 2500;

function progressToTimeline(data: ResearchProgressEvent, kind: TimelineEvent["kind"] = "progress"): TimelineEvent {
  const timestamp = data.timestamp ?? new Date().toISOString();
  return {
    id: `${timestamp}-${kind}-${data.phase ?? ""}-${data.message ?? ""}`,
    kind,
    timestamp,
    phase: data.phase,
    pct: data.pct,
    message: data.message,
  };
}

export default function ResearchPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;

  const [jobMeta, setJobMeta] = React.useState<ResearchJob | null>(null);
  const [query, setQuery] = React.useState<string | null>(null);
  const [status, setStatus] = React.useState<ResearchStatus>("queued");
  const [pct, setPct] = React.useState(0);
  const [events, setEvents] = React.useState<TimelineEvent[]>([]);
  const [result, setResult] = React.useState<ResearchResultPayload | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [connection, setConnection] = React.useState<Connection>("connecting");
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [initializing, setInitializing] = React.useState(true);

  const esRef = React.useRef<EventSource | null>(null);
  const pollRef = React.useRef<ReturnType<typeof setInterval> | null>(null);
  const settledRef = React.useRef(false);

  const pushEvents = React.useCallback((incoming: TimelineEvent[]) => {
    setEvents((prev) => mergeTimelineEvents(prev, incoming));
  }, []);

  const stopPolling = React.useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const closeStream = React.useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  }, []);

  const settle = React.useCallback(
    (job: ResearchJob) => {
      settledRef.current = true;
      setJobMeta(job);
      setStatus(job.status);
      if (job.status === "done") {
        setResult(job.result);
        setPct(100);
        if (job.updatedAt) {
          pushEvents([
            {
              id: `completed-${job.updatedAt}`,
              kind: "completed",
              timestamp: job.updatedAt,
              phase: "done",
              pct: 100,
              message: "Research finished successfully.",
            },
          ]);
        }
      } else if (job.status === "failed") {
        setError(job.error ?? "Research failed.");
        if (job.updatedAt) {
          pushEvents([
            {
              id: `failed-${job.updatedAt}`,
              kind: "failed",
              timestamp: job.updatedAt,
              phase: "failed",
              message: "Research failed.",
              error: job.error ?? "Research failed.",
            },
          ]);
        }
      }
      closeStream();
      stopPolling();
      setConnection("closed");
    },
    [closeStream, stopPolling, pushEvents],
  );

  const applyJob = React.useCallback(
    (job: ResearchJob) => {
      setJobMeta(job);
      if (job.query) setQuery(job.query);
      if (settledRef.current) return;
      setStatus(job.status);
      if (TERMINAL.includes(job.status)) {
        settle(job);
      }
    },
    [settle],
  );

  const loadPersistedEvents = React.useCallback(async (): Promise<TimelineEvent[]> => {
    try {
      const records = await getJobEvents(jobId);
      if (records.length > 0) {
        return records.map(recordToTimelineEvent);
      }
    } catch {
      // Fall back to job timestamps when the events endpoint is unavailable.
    }
    return [];
  }, [jobId]);

  const startPolling = React.useCallback(() => {
    if (pollRef.current || settledRef.current) return;
    setConnection("polling");

    const poll = async () => {
      try {
        const job = await getResearch(jobId);
        applyJob(job);
      } catch {
        // Keep trying; transient errors shouldn't kill the poller.
      }
    };

    void poll();
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS);
  }, [jobId, applyJob]);

  const startStream = React.useCallback(() => {
    if (typeof window === "undefined") return;
    if (settledRef.current) return;

    let es: EventSource;
    try {
      es = new EventSource(streamUrl(jobId));
    } catch {
      startPolling();
      return;
    }
    esRef.current = es;
    setConnection("connecting");

    es.onopen = () => {
      if (!settledRef.current) {
        setConnection("streaming");
        pushEvents([
          {
            id: `connected-${Date.now()}`,
            kind: "connected",
            timestamp: new Date().toISOString(),
            message: "Subscribed to live progress stream.",
          },
        ]);
      }
    };

    es.addEventListener("progress", (event) => {
      try {
        const data = JSON.parse(
          (event as MessageEvent).data,
        ) as ResearchProgressEvent;
        setStatus("running");
        if (typeof data.pct === "number") setPct(data.pct);
        pushEvents([progressToTimeline(data)]);
      } catch {
        // Ignore malformed progress frames.
      }
    });

    es.addEventListener("completed", (event) => {
      try {
        const data = JSON.parse(
          (event as MessageEvent).data,
        ) as ResearchResultPayload & { timestamp?: string };
        settledRef.current = true;
        setResult(data);
        setStatus("done");
        setPct(100);
        pushEvents([
          {
            id: `completed-live-${data.timestamp ?? Date.now()}`,
            kind: "completed",
            timestamp: data.timestamp ?? new Date().toISOString(),
            phase: "done",
            pct: 100,
            message: "Research finished successfully.",
          },
        ]);
      } catch {
        void getResearch(jobId).then(settle).catch(() => undefined);
      }
      closeStream();
      stopPolling();
      setConnection("closed");
    });

    es.addEventListener("failed", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data) as {
          error?: string;
          timestamp?: string;
        };
        const message = data.error ?? "Research failed.";
        setError(message);
        pushEvents([
          {
            id: `failed-live-${data.timestamp ?? Date.now()}`,
            kind: "failed",
            timestamp: data.timestamp ?? new Date().toISOString(),
            phase: "failed",
            message: "Research failed.",
            error: message,
          },
        ]);
      } catch {
        setError("Research failed.");
      }
      settledRef.current = true;
      setStatus("failed");
      closeStream();
      stopPolling();
      setConnection("closed");
    });

    es.onerror = () => {
      if (settledRef.current) {
        closeStream();
        return;
      }
      if (es.readyState === EventSource.CLOSED) {
        closeStream();
        startPolling();
      } else {
        setConnection("polling");
        startPolling();
      }
    };
  }, [jobId, startPolling, closeStream, stopPolling, settle, pushEvents]);

  React.useEffect(() => {
    let cancelled = false;
    settledRef.current = false;
    setEvents([]);

    (async () => {
      try {
        const job = await getResearch(jobId);
        if (cancelled) return;

        setJobMeta(job);
        setQuery(job.query);
        setStatus(job.status);

        const persisted = await loadPersistedEvents();
        if (cancelled) return;

        setEvents(
          persisted.length > 0 ? persisted : buildFallbackTimeline(job),
        );

        if (job.status === "done") {
          settledRef.current = true;
          setResult(job.result);
          setPct(100);
          setConnection("closed");
        } else if (job.status === "failed") {
          settledRef.current = true;
          setError(job.error ?? "Research failed.");
          setConnection("closed");
        } else {
          startStream();
        }
      } catch (err) {
        if (cancelled) return;
        setLoadError(
          err instanceof ApiError ? err.message : "Failed to load this job.",
        );
        startStream();
      } finally {
        if (!cancelled) setInitializing(false);
      }
    })();

    return () => {
      cancelled = true;
      closeStream();
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const isTerminal = status === "done" || status === "failed";
  const startedAt = jobMeta?.createdAt ?? events[0]?.timestamp ?? null;
  const finishedAt = isTerminal ? jobMeta?.updatedAt ?? events.at(-1)?.timestamp ?? null : null;
  const isLive = !isTerminal && (connection === "streaming" || connection === "polling");

  const headerDuration =
    startedAt && finishedAt
      ? formatDuration(
          (parseTime(finishedAt)?.getTime() ?? 0) - (parseTime(startedAt)?.getTime() ?? 0),
        )
      : null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <Button variant="ghost" size="sm" render={<Link href="/" />}>
          <ArrowLeftIcon className="size-4" />
          New research
        </Button>
        <ConnectionPill connection={connection} terminal={isTerminal} />
      </div>

      <Card className="border-border/60 shadow-sm">
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardDescription className="text-xs font-medium uppercase tracking-wider">
              Query
            </CardDescription>
            <StatusBadge status={status} />
          </div>
          <CardTitle className="font-heading text-lg leading-snug">
            {query ?? <Skeleton className="h-6 w-2/3" />}
          </CardTitle>
          {startedAt ? (
            <p className="text-xs text-muted-foreground">
              Submitted {formatDateTime(startedAt)}
              {headerDuration ? ` · ${headerDuration} total` : null}
            </p>
          ) : null}
        </CardHeader>
        {!isTerminal && (
          <CardContent className="flex flex-col gap-2">
            <ProgressBar value={pct} indeterminate={pct === 0} />
            <p className="text-xs text-muted-foreground">
              {pct > 0 ? `${Math.round(pct)}% complete` : "Starting agents…"}
            </p>
          </CardContent>
        )}
      </Card>

      {loadError && !isTerminal && (
        <Card className="ring-amber-500/30">
          <CardContent className="flex items-start gap-2 text-sm text-muted-foreground">
            <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-amber-500" />
            <span>{loadError} Retrying live updates…</span>
          </CardContent>
        </Card>
      )}

      <Card className="border-border/60">
        <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
          <div>
            <CardTitle className="font-heading flex items-center gap-2 text-base">
              <HistoryIcon className="size-4 text-primary" />
              Event timeline
            </CardTitle>
            <CardDescription>
              Timestamps, elapsed time, and deltas between each step.
            </CardDescription>
          </div>
          {!isTerminal && events.length > 0 ? (
            <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
              {events.length} events
            </span>
          ) : null}
        </CardHeader>
        <CardContent>
          {initializing ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : (
            <EventTimeline
              events={events}
              startedAt={startedAt}
              finishedAt={finishedAt}
              isLive={isLive}
              emptyMessage="Waiting for the worker to report progress…"
            />
          )}
        </CardContent>
      </Card>

      {status === "failed" && (
        <Card className="ring-destructive/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangleIcon className="size-5" />
              Research failed
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-start gap-3">
            <p className="text-sm text-muted-foreground">
              {error ?? "An unknown error occurred."}
            </p>
            <Button variant="outline" size="sm" render={<Link href="/" />}>
              <RefreshCwIcon className="size-4" />
              Try a new query
            </Button>
          </CardContent>
        </Card>
      )}

      {status === "done" && result && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm font-medium text-primary">
            <CheckCircle2Icon className="size-4 shrink-0" />
            Research complete — report ready below
          </div>
          <MarkdownResult result={result} />
        </div>
      )}

      {status === "done" && !result && (
        <Card>
          <CardContent className="text-sm text-muted-foreground">
            This job finished but returned no result content.
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ConnectionPill({
  connection,
  terminal,
}: {
  connection: Connection;
  terminal: boolean;
}) {
  if (terminal) return null;

  const map: Record<
    Connection,
    { label: string; icon: typeof RadioIcon; className: string; spin?: boolean }
  > = {
    connecting: {
      label: "Connecting…",
      icon: RefreshCwIcon,
      className: "text-muted-foreground",
      spin: true,
    },
    streaming: {
      label: "Live",
      icon: RadioIcon,
      className: "text-primary",
    },
    polling: {
      label: "Polling",
      icon: RefreshCwIcon,
      className: "text-amber-600 dark:text-amber-400",
      spin: true,
    },
    closed: {
      label: "Disconnected",
      icon: WifiOffIcon,
      className: "text-muted-foreground",
    },
  };

  const cfg = map[connection];
  const Icon = cfg.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium ${cfg.className}`}
    >
      <Icon className={`size-3.5 ${cfg.spin ? "animate-spin" : ""}`} />
      {cfg.label}
    </span>
  );
}
