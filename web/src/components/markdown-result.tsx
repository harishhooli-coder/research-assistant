import Link from "next/link";
import { ExternalLinkIcon, LinkIcon } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { ResearchResultPayload } from "@/lib/api";

export function MarkdownResult({ result }: { result: ResearchResultPayload }) {
  const sources = result.sources ?? [];

  return (
    <div className="flex flex-col gap-4">
      <Card className="border-border/60 shadow-sm">
        <CardContent className="pt-6">
          <article className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {result.markdown || "_No content returned._"}
            </ReactMarkdown>
          </article>
        </CardContent>
      </Card>

      {sources.length > 0 && (
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="font-heading flex items-center gap-2 text-base">
              <LinkIcon className="size-4 text-primary" />
              Sources
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-normal text-primary">
                {sources.length}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="flex flex-col gap-2.5">
              {sources.map((source, i) => (
                <li key={`${source.url}-${i}`} className="flex gap-2 text-sm">
                  <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded bg-muted text-xs font-medium text-muted-foreground">
                    {i + 1}
                  </span>
                  <Link
                    href={source.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="group inline-flex cursor-pointer items-start gap-1 text-primary transition-colors duration-200 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    <span className="break-words">
                      {source.title || source.url}
                    </span>
                    <ExternalLinkIcon className="mt-0.5 size-3 shrink-0 opacity-60 transition-opacity duration-200 group-hover:opacity-100" />
                  </Link>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
