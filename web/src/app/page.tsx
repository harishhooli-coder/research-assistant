"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRightIcon,
  BookOpenIcon,
  Loader2Icon,
  SearchIcon,
  SparklesIcon,
  ZapIcon,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, submitResearch } from "@/lib/api";

const EXAMPLES = [
  "What are the latest breakthroughs in solid-state batteries?",
  "Compare the leading open-source vector databases.",
  "Summarize recent research on LLM agent reliability.",
];

const FEATURES = [
  {
    icon: SearchIcon,
    title: "Web search",
    description: "Agents scan the web for relevant, up-to-date sources.",
  },
  {
    icon: BookOpenIcon,
    title: "Deep reading",
    description: "Sources are read and synthesized into a coherent report.",
  },
  {
    icon: ZapIcon,
    title: "Live progress",
    description: "Watch each phase stream to you in real time.",
  },
] as const;

export default function HomePage() {
  const router = useRouter();
  const [query, setQuery] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || submitting) return;

    setSubmitting(true);
    try {
      const { jobId } = await submitResearch(trimmed);
      toast.success("Research enqueued", {
        description: "Streaming live progress…",
      });
      router.push(`/research/${jobId}`);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Something went wrong.";
      toast.error("Could not start research", { description: message });
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col items-center gap-4 pt-4 text-center sm:pt-8">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-medium text-primary transition-colors duration-200">
          <SparklesIcon className="size-3.5" />
          Multi-agent research assistant
        </span>
        <h1 className="font-heading glow-text max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl">
          Ask anything. Get a sourced answer.
        </h1>
        <p className="max-w-prose text-base text-muted-foreground sm:text-lg">
          Submit a query and a team of agents will search the web, read sources,
          and write up a cited report — streamed to you live.
        </p>
      </div>

      <Card className="border-border/60 shadow-lg shadow-primary/5 ring-1 ring-border/50 transition-shadow duration-200 hover:shadow-xl hover:shadow-primary/10">
        <CardHeader>
          <CardTitle className="font-heading text-xl">New research</CardTitle>
          <CardDescription>
            Your request runs asynchronously. You&apos;ll be redirected to a live
            progress page.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
            <Input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. What's new in WebGPU this year?"
              disabled={submitting}
              className="h-11 flex-1 border-border/80 text-base transition-colors duration-200 focus-visible:ring-primary/30"
              aria-label="Research query"
            />
            <Button
              type="submit"
              size="lg"
              disabled={submitting || query.trim().length === 0}
              className="h-11 cursor-pointer px-5 shadow-sm shadow-primary/20 transition-all duration-200 hover:shadow-md hover:shadow-primary/25"
            >
              {submitting ? (
                <>
                  <Loader2Icon className="size-4 animate-spin" />
                  Submitting…
                </>
              ) : (
                <>
                  Research
                  <ArrowRightIcon className="size-4 transition-transform duration-200 group-hover/button:translate-x-0.5" />
                </>
              )}
            </Button>
          </form>

          <div className="mt-4 flex flex-wrap gap-2">
            <span className="w-full text-xs font-medium text-muted-foreground sm:w-auto sm:py-1.5">
              Try:
            </span>
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                disabled={submitting}
                onClick={() => setQuery(example)}
                className="cursor-pointer rounded-full border border-border/80 bg-background px-3 py-1.5 text-left text-xs text-muted-foreground transition-all duration-200 hover:border-primary/30 hover:bg-primary/5 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
              >
                {example}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-3">
        {FEATURES.map((feature) => (
          <div
            key={feature.title}
            className="flex flex-col gap-2 rounded-xl border border-border/50 bg-card/50 p-4 backdrop-blur-sm transition-colors duration-200 hover:border-primary/20 hover:bg-card/80"
          >
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <feature.icon className="size-4" />
            </div>
            <h3 className="font-heading text-sm font-semibold">{feature.title}</h3>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {feature.description}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
