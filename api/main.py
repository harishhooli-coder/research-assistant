"""FastAPI application: POST /research, history, detail, and SSE stream.

API contract (also documented in the README):

  POST   /research                  body {query}        -> 202 {jobId}
  GET    /research                  -> [{jobId,query,status,createdAt}]  (recent first)
  GET    /research/{jobId}          -> {jobId,query,status,result,error,createdAt,updatedAt}
  GET    /research/{jobId}/stream   -> SSE: events `progress` | `completed` | `failed`
                                       + a comment heartbeat every ~25s
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from api.constants import QUEUE_NAME, RESEARCH_TASK, progress_channel
from api.redis_utils import append_event, create_arq_pool, list_events
from api.schemas import EnqueueResponse, JobDetail, JobEvent, JobSummary, ResearchRequest
from db import crud
from db.session import session_scope
from settings import get_settings

HEARTBEAT_SECONDS = 25


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings().require_postgres_database()
    # Allow tests / callers to pre-inject a redis pool (e.g. fakeredis).
    if not getattr(app.state, "redis", None):
        app.state.redis = await create_arq_pool()
        app.state._owns_redis = True
    yield
    if getattr(app.state, "_owns_redis", False):
        await app.state.redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Research Assistant API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_redis(request: Request):
        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            raise HTTPException(status_code=503, detail="queue unavailable")
        return redis

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/research", status_code=status.HTTP_202_ACCEPTED, response_model=EnqueueResponse)
    async def create_research(body: ResearchRequest, redis=Depends(get_redis)):
        try:
            settings.require_runtime_keys()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        job_id = uuid.uuid4().hex
        async with session_scope() as session:
            await crud.create_job(session, job_id, body.query)
        await append_event(
            redis,
            job_id,
            "submitted",
            {
                "phase": "queued",
                "pct": 0,
                "message": "Research query submitted and queued.",
            },
        )
        await redis.enqueue_job(
            RESEARCH_TASK, job_id, body.query, _job_id=job_id, _queue_name=QUEUE_NAME
        )
        return EnqueueResponse(jobId=job_id)

    @app.get("/research", response_model=list[JobSummary])
    async def list_research():
        async with session_scope() as session:
            rows = await crud.list_jobs(session)
            return [r.to_summary() for r in rows]

    @app.get("/research/{job_id}", response_model=JobDetail)
    async def get_research(job_id: str):
        async with session_scope() as session:
            row = await crud.get_job(session, job_id)
            if row is None:
                raise HTTPException(status_code=404, detail="job not found")
            return row.to_detail()

    @app.get("/research/{job_id}/events", response_model=list[JobEvent])
    async def get_research_events(job_id: str, redis=Depends(get_redis)):
        async with session_scope() as session:
            row = await crud.get_job(session, job_id)
            if row is None:
                raise HTTPException(status_code=404, detail="job not found")
        return await list_events(redis, job_id)

    @app.get("/research/{job_id}/stream")
    async def stream_research(job_id: str, request: Request, redis=Depends(get_redis)):
        channel = progress_channel(job_id)

        async def event_generator():
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel)
            try:
                # Emit the current state immediately so late subscribers aren't
                # stuck waiting (and terminal jobs close right away).
                async with session_scope() as session:
                    row = await crud.get_job(session, job_id)
                if row is None:
                    yield ServerSentEvent(
                        event="failed", data=json.dumps({"error": "job not found"})
                    )
                    return
                if row.status == "done":
                    yield ServerSentEvent(event="completed", data=json.dumps(row.result))
                    return
                if row.status == "failed":
                    yield ServerSentEvent(
                        event="failed", data=json.dumps({"error": row.error or "failed"})
                    )
                    return
                yield ServerSentEvent(
                    event="progress",
                    data=json.dumps(
                        {"phase": row.status, "pct": 5, "message": "Subscribed to job."}
                    ),
                )

                while True:
                    if await request.is_disconnected():
                        break
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                    if not message:
                        continue
                    raw = message.get("data")
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    try:
                        envelope = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    event = envelope.get("event", "progress")
                    yield ServerSentEvent(
                        event=event, data=json.dumps(envelope.get("data"))
                    )
                    if event in ("completed", "failed"):
                        break
            finally:
                try:
                    await pubsub.unsubscribe(channel)
                    await pubsub.aclose()
                except Exception:
                    pass

        # EventSourceResponse sends a `: ping` comment heartbeat every `ping`s,
        # keeping the connection alive through Fly's 60s idle proxy cutoff.
        return EventSourceResponse(event_generator(), ping=HEARTBEAT_SECONDS)

    return app


app = create_app()
