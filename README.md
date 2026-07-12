# Research Assistant — Python Backend

A 2-agent **LangGraph** research assistant (Anthropic Claude + Tavily) exposed
three ways:

- a **Telegram bot** (Phase 1) with **Redis episodic memory** (Phase 2),
- a **FastAPI** backend with an **arq** job queue, **Redis pub/sub → SSE** live
  progress, and **Postgres (Neon)** persistence (Phase 3),
- ready for a Next.js web UI (Phase 4) that consumes the exact API contract below.

> This repository includes both the **Python backend** and the **`web/` Next.js
> frontend**. The HTTP contract is defined in FastAPI and kept in sync via the
> [documentation pipeline](#documentation-pipeline).

## Architecture

```
Telegram ─┐
          ├─▶ LangGraph (supervisor → researcher → editor) ─▶ Redis (memory)
Web UI  ──┘
Web UI ─POST /research─▶ FastAPI ─enqueue─▶ Redis(arq) ─▶ arq Worker ─▶ LangGraph
Worker ─store─▶ Postgres(Neon)          Worker ─publish progress─▶ Redis pub/sub
Web UI ─GET /research/:id/stream (SSE)─▶ FastAPI ─subscribe─▶ Redis pub/sub
```

## Repo layout

| Path | What |
|------|------|
| `agent/` | LangGraph graph, tools, truncation, failure handling, LLM factory |
| `bot/` | Telegram bot entrypoint (`python -m bot.main`) |
| `memory/` | Redis episodic memory (last-3 searches via `LPUSH`+`LTRIM`) |
| `api/` | FastAPI app (`api/main.py`), arq worker (`api/worker.py`), settings |
| `mail/` | AgentMail client: optional email delivery of research results |
| `db/` | SQLAlchemy 2.0 async models, session, CRUD, Alembic migrations |
| `tests/` | Offline pytest suite (failure paths, memory, API, queue retry) |
| `scripts/` | Manual demos, deploy helpers, and doc-generation scripts |
| `web/` | Next.js frontend (Clerk auth, SSE progress, history) |
| `docs/api/` | Generated OpenAPI schema (`openapi.json`) |
| `render.yaml` | Render Blueprint for API + arq worker |
| `settings.py` | Central env-driven config |
| `docker-compose.yml` | Local Redis (AOF) + Postgres |

## Quickstart

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then fill in keys for runtime (NOT needed for tests)
```

Start local services (Docker Desktop):

```bash
docker compose up -d          # Redis (6379) + Postgres (5432)
alembic upgrade head          # create the research_results table
```

### Run the Telegram bot (Phase 1 + 2)

```bash
# requires ANTHROPIC_API_KEY, TAVILY_API_KEY, TELEGRAM_BOT_TOKEN (+ Redis for memory)
python -m bot.main
# in Telegram: /research <your question>
```

### Run the API + worker locally (Phase 3)

```bash
# terminal 1 - API
uvicorn api.main:app --reload --port 8000
# terminal 2 - arq worker
arq api.worker.WorkerSettings
```

## API contract

The frontend is built against this exact contract.

### `POST /research`
Request body: `{ "query": string, "notifyEmail"?: string }`
Response: **202** `{ "jobId": string }` (returns immediately; work runs in the worker)

When `notifyEmail` is set and `AGENTMAIL_API_KEY` is configured, the worker emails
the finished markdown report via [AgentMail](https://docs.agentmail.to) after the
job completes. Email failures are reported as progress events and do not fail the job.

### `GET /research`
Response: `[{ "jobId", "query", "status", "createdAt" }]` — most recent first.

### `GET /research/{jobId}`
Response:
```json
{
  "jobId": "…",
  "query": "…",
  "status": "queued | running | done | failed",
  "result": { "markdown": "…", "sources": [{ "title": "…", "url": "…" }] },
  "error": null,
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601"
}
```
`result` is populated only when `status == "done"`; `error` only when `failed`.

### `GET /research/{jobId}/stream` (SSE)
`text/event-stream` via `sse-starlette`. Named events:

| event | data |
|-------|------|
| `progress` | `{ "phase", "pct", "message" }` |
| `completed` | the final result object `{ "markdown", "sources" }` |
| `failed` | `{ "error" }` |

A comment heartbeat (`: ping`) is sent every ~25s to keep proxies from closing
idle SSE connections. The stream closes after `completed`/`failed`. If the job
is already terminal when you connect, the terminal event is sent immediately.

### CORS
All origins are allowed in dev (`CORS_ALLOW_ORIGINS=*`). For prod set
`CORS_ALLOW_ORIGINS=https://your-app.vercel.app` (comma-separated for multiple).

## Documentation pipeline

The FastAPI app is the **source of truth** for the HTTP contract. When you change
`api/schemas.py` or route definitions in `api/main.py`, regenerate and commit
the derived artifacts:

```powershell
# Windows
.\scripts\update-docs.ps1

# macOS / Linux
python scripts/update_docs.py
```

This writes:

| Output | Purpose |
|--------|---------|
| `docs/api/openapi.json` | Committed OpenAPI schema |
| `web/src/lib/api.generated.ts` | TypeScript types for the web client |

CI (`.github/workflows/docs.yml`) runs `python scripts/check_docs.py` on PRs that
touch `api/`, `docs/`, or `web/src/lib/`. The job fails if generated files are
missing, untracked, or out of date — run the update script and commit the diff.
Backend unit tests run in CI via `.github/workflows/pytest.yml`.

See `docs/api/README.md` for details. Interactive Swagger UI is at `/docs` when
the API is running.

## Configuration (env)

See `.env.example`. Key vars: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`,
`TAVILY_API_KEY`, `TELEGRAM_BOT_TOKEN`, `AGENTMAIL_API_KEY` (optional email
delivery), `AGENTMAIL_INBOX_ID` (optional), `REDIS_URL`, `DATABASE_URL`,
`CORS_ALLOW_ORIGINS`, and agent limits (`MAX_SUPERVISOR_STEPS`,
`MAX_CONTEXT_TOKENS`, `MAX_FETCH_CHARS`).

`DATABASE_URL` is an **async** SQLAlchemy URL pointing at **Neon Postgres**
(`postgresql+asyncpg://...?ssl=require`). SQLite is not used at runtime; tests
alone use a temporary SQLite file via fixtures.

## Failure handling (the 3 required paths)

1. **Tool failure** — `agent/tools.py` wraps all network calls; tools never
   raise and instead return `"source unavailable"`. The graph continues and the
   editor degrades gracefully.
2. **Context overflow** — `agent/truncate.py` counts tokens (`tiktoken`) and
   trims oldest non-system messages + caps oversized fetched content before
   every LLM call, always keeping the system prompt + most recent message.
3. **Loop > 5 steps** — the supervisor increments `step_count` each cycle; once
   it exceeds `MAX_SUPERVISOR_STEPS` it force-routes to the editor and exits
   cleanly with a partial-results notice.

## Tests (offline — no API keys, no network, no Docker required)

The LLM is a scripted fake model and the tools' network helpers are
monkeypatched; Redis is `fakeredis`; the DB is SQLite (`aiosqlite`).

```bash
# everything
pytest

# the 3 required failure paths
pytest tests/test_failures.py -v

# Phase 2 memory: 3 recalled, survives restart, 4th evicts oldest
pytest tests/test_memory.py -v

# Phase 3 API contract (POST/GET/SSE)
pytest tests/test_api.py -v

# Phase 3 kill-worker-retry-completes (arq retry semantics)
pytest tests/test_queue.py -v
```

### Phase 2 — run against a REAL Redis (optional)

```bash
docker compose up -d redis
python -m scripts.memory_demo
```
Prints the 3 recalled searches, proves they survive a simulated restart (data
lives in Redis with AOF persistence), and that a 4th evicts the oldest.

### Phase 3 — kill-worker retry (manual, real Redis + Postgres)

The automated test (`tests/test_queue.py`) proves retry→complete by simulating
a crash on the first attempt. To demonstrate a literally killed process:

```bash
docker compose up -d            # Redis + Postgres
alembic upgrade head
uvicorn api.main:app --port 8000        # terminal 1 (API)
arq api.worker.WorkerSettings           # terminal 2 (worker)

# terminal 3: enqueue a job and watch progress
curl -X POST localhost:8000/research -H "Content-Type: application/json" \
  -d '{"query":"history of the transistor"}'
# -> {"jobId":"<id>"}; open the SSE stream:
curl -N localhost:8000/research/<id>/stream

# Now CTRL-C / kill the worker (terminal 2) WHILE the job is running,
# then restart it:
arq api.worker.WorkerSettings
# The unacked job is re-run (retry_jobs=True, max_tries=4, job_timeout=300)
# and eventually completes; GET /research/<id> shows status "done" with result.
```
Why it works: jobs are idempotent (keyed by `jobId`, upserted in Postgres). A
worker killed mid-job never acks the job, so arq re-queues it; in-process
exceptions retry with exponential backoff up to `max_tries`.

## Render + Vercel deploy (production)

**Architecture:** Vercel hosts the Next.js UI (`web/`); Render hosts the FastAPI
API and arq worker. Use Neon for Postgres and Upstash (or Render Redis) for
`REDIS_URL`.

### One-time setup

1. **Secrets in `.env`** — fill in real keys (never commit `.env`):
   - `NVIDIA_API_KEY` (or `ANTHROPIC_API_KEY`)
   - `TAVILY_API_KEY` (required for web search)
   - `LLM_PROVIDER=nvidia`
   - `DATABASE_URL` (Neon)
   - `REDIS_URL` (Upstash or Render Redis — not localhost)

2. **Render** — Dashboard → New → Blueprint → connect this repo (`render.yaml`).
   Set secret env vars on both `research-api` and `research-worker`:
   `DATABASE_URL`, `REDIS_URL`, `NVIDIA_API_KEY`, `TAVILY_API_KEY`, and
   `CORS_ALLOW_ORIGINS` (your Vercel origin) on the API service.

3. **Migrations** — once against Neon:
   ```bash
   DATABASE_URL='postgresql+asyncpg://...' alembic upgrade head
   ```

4. **Vercel** — Root Directory: `web`
   - Env var: `NEXT_PUBLIC_API_URL=https://<your-render-api>.onrender.com`

### Deploy frontend (Vercel)

After the API is live:

```powershell
.\scripts\deploy-vercel.ps1 -ApiUrl https://<your-render-api>.onrender.com
```

Then set `CORS_ALLOW_ORIGINS` on Render to your Vercel URL. Alternatively,
`.\scripts\deploy-vercel-app.ps1` can deploy API + web to Vercel (worker still
needs Render or a local process).
