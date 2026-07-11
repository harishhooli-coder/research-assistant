"""arq worker: runs the LangGraph agent, streams progress, persists results.

Reliability (kill-worker-retry-completes):
  - ``retry_jobs=True`` + ``max_tries=MAX_TRIES``: a job whose worker is killed
    mid-run is NOT acknowledged, so arq re-queues and another/the-restarted
    worker re-runs it until it completes (jobs are idempotent: keyed by job_id
    and upserted in Postgres).
  - ``job_timeout=JOB_TIMEOUT``: a job that hangs is aborted and retried.
  - On an in-process exception we re-raise to let arq retry, only recording
    ``failed`` once the final attempt is exhausted.
  - ``on_shutdown`` disposes the DB engine so SIGTERM is graceful.
"""

from __future__ import annotations

import asyncio
import json
import logging

from arq import Retry

from api.constants import JOB_TIMEOUT, MAX_TRIES, QUEUE_NAME, progress_channel
from api.redis_utils import publish_event, redis_settings
from db import crud
from db.session import dispose, get_engine, session_scope
from settings import get_settings

logger = logging.getLogger(__name__)


def _friendly_error(exc: Exception) -> str:
    msg = str(exc)
    lower = msg.lower()
    if "authentication_error" in msg or "invalid x-api-key" in lower:
        return (
            "Anthropic API key is missing or invalid. Set ANTHROPIC_API_KEY in .env "
            "(https://console.anthropic.com/settings/keys) and restart the worker."
        )
    if "401" in msg or "unauthorized" in lower or "invalid api key" in lower:
        return (
            "NVIDIA API key is missing or invalid. Set NVIDIA_API_KEY in .env "
            "(https://build.nvidia.com) and restart the worker."
        )
    return msg[:1000]


async def run_research_job(ctx: dict, job_id: str, query: str) -> dict:
    """Execute the research graph for a queued job."""
    from agent.graph import run_research  # imported lazily to keep worker boot light

    redis = ctx["redis"]
    job_try = ctx.get("job_try", 1)
    loop = asyncio.get_running_loop()

    async with session_scope() as session:
        await crud.mark_running(session, job_id)
    await publish_event(redis, job_id, "progress", {"phase": "running", "pct": 10,
                                                     "message": "Job picked up by worker."})

    # Bridge the synchronous graph's progress callback (runs in a thread) back
    # onto this event loop so we can publish to Redis.
    def progress_cb(phase: str, pct: int, message: str) -> None:
        fut = asyncio.run_coroutine_threadsafe(
            publish_event(redis, job_id, "progress",
                          {"phase": phase, "pct": pct, "message": message}),
            loop,
        )
        try:
            fut.result(timeout=5)
        except Exception:  # pragma: no cover - best-effort progress
            pass

    try:
        result = await asyncio.to_thread(
            run_research, query, session_id=job_id, progress_cb=progress_cb
        )
    except Exception as exc:
        logger.exception("research job %s failed on try %s", job_id, job_try)
        error = _friendly_error(exc)
        if job_try >= MAX_TRIES:
            async with session_scope() as session:
                await crud.mark_failed(session, job_id, error)
            await publish_event(redis, job_id, "failed", {"error": error})
            return {"status": "failed", "error": error}
        # Not the final attempt -> ask arq to retry with exponential backoff.
        raise Retry(defer=min(2 ** (job_try - 1), 30))

    async with session_scope() as session:
        await crud.mark_done(session, job_id, result)
    await publish_event(redis, job_id, "completed", result)
    return result


async def on_startup(ctx: dict) -> None:
    get_settings().require_postgres_database()
    get_engine()  # warm the async engine / sessionmaker
    missing = get_settings().missing_runtime_keys()
    if missing:
        logger.warning(
            "Worker started with placeholder API keys (%s). "
            "Research jobs will fail until .env is updated.",
            ", ".join(missing),
        )
    logger.info("arq worker started")


async def on_shutdown(ctx: dict) -> None:
    await dispose()
    logger.info("arq worker shut down")


def _settings():
    return redis_settings(get_settings().redis_url)


class WorkerSettings:
    """arq entrypoint: ``arq api.worker.WorkerSettings``."""

    functions = [run_research_job]
    queue_name = QUEUE_NAME
    redis_settings = _settings()
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_tries = MAX_TRIES
    job_timeout = JOB_TIMEOUT
    retry_jobs = True
    # Finish/abort in-flight jobs cleanly on SIGTERM before exiting.
    job_completion_wait = 5
