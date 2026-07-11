# Research Assistant — Web UI

A Next.js (App Router, TypeScript, Tailwind CSS, shadcn/ui) frontend for the
Research Assistant. It is a **pure frontend**: the browser talks only to the
FastAPI backend (never to the database directly). All research execution,
storage, and progress streaming happens server-side.

## Features

- **Submit** a research query (`POST /research`) and get redirected to a live
  progress page (non-blocking).
- **Live progress** via Server-Sent Events (`GET /research/{jobId}/stream`):
  progress bar + phase log, with an automatic **polling fallback**
  (`GET /research/{jobId}`) when SSE is unavailable.
- **Final result** rendered as Markdown with a clickable sources list.
- **History** page (`GET /research`) listing past runs with status + timestamp;
  click a row to reopen its stored result.
- Dark mode, responsive layout, loading skeletons, and toasts.

## Tech stack

- Next.js 16 (App Router) + React 19 + TypeScript
- Tailwind CSS v4 + shadcn/ui (base-ui based components)
- `react-markdown` + `remark-gfm` for result rendering
- `next-themes` for dark mode, `sonner` for toasts

## Project layout

```
web/
├── src/
│   ├── app/
│   │   ├── layout.tsx                 # Root layout: theme, header, toaster
│   │   ├── page.tsx                   # Research submission form
│   │   ├── history/page.tsx           # History list (GET /research)
│   │   └── research/[jobId]/page.tsx  # Live progress + result (SSE + polling)
│   ├── components/
│   │   ├── markdown-result.tsx        # Markdown + sources renderer
│   │   ├── progress-bar.tsx
│   │   ├── status-badge.tsx
│   │   ├── site-header.tsx
│   │   ├── theme-provider.tsx
│   │   ├── theme-toggle.tsx
│   │   └── ui/                        # shadcn/ui components
│   └── lib/
│       └── api.ts                     # Typed fetch helpers + API types
├── .env.local.example
└── vercel.json
```

## Backend API contract

The UI is built exactly against this FastAPI contract (`{API}` =
`NEXT_PUBLIC_API_URL`):

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/research` | Body `{ "query": string }` → `202 { "jobId": string }` |
| `GET` | `/research` | `[{ jobId, query, status, createdAt }]` (recent first) |
| `GET` | `/research/{jobId}` | `{ jobId, query, status, result, error, createdAt, updatedAt }` |
| `GET` | `/research/{jobId}/stream` | SSE: `progress`, `completed`, `failed` events + heartbeat comments |

- `status` ∈ `queued | running | done | failed`
- `result` = `{ "markdown": string, "sources": [{ title, url }] }`
- SSE `progress` data = `{ phase, pct, message }`; `completed` data = the final
  result object; `failed` data = `{ error }`.

## Local development

1. Install dependencies:

   ```bash
   npm install
   ```

2. Configure the backend URL. Copy the example env file and point it at your
   running FastAPI instance:

   ```bash
   cp .env.local.example .env.local
   # then edit .env.local:
   # NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

   > On Windows PowerShell use `Copy-Item .env.local.example .env.local`.

3. Run the dev server:

   ```bash
   npm run dev
   ```

   Open http://localhost:3000. With the FastAPI backend running at
   `NEXT_PUBLIC_API_URL`, submit a query → you'll be redirected to the live
   progress page. If the backend is not running, the UI degrades gracefully
   with clear error/loading states.

### Scripts

- `npm run dev` — start the dev server
- `npm run build` — production build
- `npm run start` — serve the production build
- `npm run lint` — run ESLint

## Deploying to Vercel

This app deploys to Vercel as a standard Next.js project. The backend
(FastAPI) is deployed separately on Fly.io.

1. Import the repository in Vercel and set the **Root Directory** to `web/`
   (this is a monorepo; the Python backend lives outside `web/`).
2. Vercel auto-detects Next.js (see `vercel.json`). No custom config needed.
3. **Set the environment variable** in Project → Settings → Environment
   Variables:

   | Name | Value | Environments |
   | --- | --- | --- |
   | `NEXT_PUBLIC_API_URL` | `https://<your-fastapi-app>.fly.dev` | Production / Preview / Development |

   Because it is a `NEXT_PUBLIC_*` variable it is inlined into the client
   bundle at build time — re-deploy after changing it.

### CORS + SSE notes (important)

- **CORS:** the FastAPI backend must allow the Vercel origin (e.g.
  `https://<your-app>.vercel.app` and any preview/custom domains). Configure
  FastAPI's `CORSMiddleware` `allow_origins` accordingly. `EventSource`
  requests are subject to CORS just like `fetch`.
- **SSE through the proxy:** the stream is consumed with the browser's native
  `EventSource`. The browser connects **directly** to the Fly.io FastAPI URL
  (no Vercel rewrite/proxy in between), so SSE works as long as the backend
  emits `text/event-stream` and CORS allows the origin. Fly's edge drops idle
  connections at ~60s, so the backend sends heartbeat comments (~every 25s) to
  keep the stream alive; the UI also falls back to polling
  `GET /research/{jobId}` if the stream errors.
- **No deploy is performed by this repo** — set the env var and deploy via the
  Vercel dashboard or `vercel` CLI when credentials are available.
