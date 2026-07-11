"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangleIcon,
  ChevronRightIcon,
  InboxIcon,
  RefreshCwIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/status-badge";
import { ApiError, listResearch, type ResearchSummary } from "@/lib/api";

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function HistoryPage() {
  const [items, setItems] = React.useState<ResearchSummary[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listResearch();
      setItems(data);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to load history.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    // Inline async fetch so all setState calls happen after `await` (not
    // synchronously in the effect body). The `load` callback above is reused
    // by the Refresh button.
    (async () => {
      try {
        const data = await listResearch();
        if (!cancelled) setItems(data);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "Failed to load history.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-semibold tracking-tight">
            History
          </h1>
          <p className="text-sm text-muted-foreground">
            Past research runs, most recent first.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={load}
          disabled={loading}
          aria-label="Refresh history"
        >
          <RefreshCwIcon className={loading ? "size-4 animate-spin" : "size-4"} />
          Refresh
        </Button>
      </div>

      {loading && !items && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="flex items-center justify-between gap-4">
                <div className="flex flex-1 flex-col gap-2">
                  <Skeleton className="h-4 w-2/3" />
                  <Skeleton className="h-3 w-1/4" />
                </div>
                <Skeleton className="h-5 w-16 rounded-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {error && (
        <Card className="ring-destructive/30">
          <CardContent className="flex flex-col items-start gap-3">
            <div className="flex items-start gap-2 text-sm text-muted-foreground">
              <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-destructive" />
              <span>{error}</span>
            </div>
            <Button variant="outline" size="sm" onClick={load}>
              <RefreshCwIcon className="size-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {!loading && !error && items && items.length === 0 && (
        <Card className="border-dashed border-border/80">
          <CardContent className="flex flex-col items-center gap-4 py-12 text-center">
            <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/10">
              <InboxIcon className="size-7 text-primary" />
            </div>
            <div className="flex flex-col gap-1">
              <p className="font-heading font-medium">No research runs yet</p>
              <p className="text-sm text-muted-foreground">
                Submit your first query to get started.
              </p>
            </div>
            <Button size="sm" className="cursor-pointer" render={<Link href="/" />}>
              Start your first research
            </Button>
          </CardContent>
        </Card>
      )}

      {items && items.length > 0 && (
        <div className="flex flex-col gap-3">
          {items.map((item) => (
            <Link
              key={item.jobId}
              href={`/research/${item.jobId}`}
              className="group block cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-xl"
            >
              <Card className="border-border/60 transition-all duration-200 hover:border-primary/25 hover:bg-muted/30 hover:shadow-md hover:shadow-primary/5 group-focus-visible:ring-2 group-focus-visible:ring-ring">
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="truncate font-medium transition-colors duration-200 group-hover:text-primary">
                      {item.query}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatTimestamp(item.createdAt)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={item.status} />
                    <ChevronRightIcon className="size-4 text-muted-foreground transition-all duration-200 group-hover:translate-x-0.5 group-hover:text-primary" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
