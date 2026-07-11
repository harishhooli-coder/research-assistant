"""Redis helpers for the API and worker (arq pool + pub/sub publish)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from arq.connections import RedisSettings, create_pool

from api.constants import EVENTS_TTL_SECONDS, QUEUE_NAME, events_key, progress_channel
from settings import get_settings


def redis_settings(url: str | None = None) -> RedisSettings:
    url = url or get_settings().redis_url
    return RedisSettings.from_dsn(url)


async def create_arq_pool(url: str | None = None):
    """Create an ArqRedis pool used to enqueue jobs and publish/subscribe."""
    return await create_pool(redis_settings(url), default_queue_name=QUEUE_NAME)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def append_event(redis: Any, job_id: str, event: str, data: dict) -> dict:
    """Persist a timeline event and return the stored record."""
    record = {"event": event, "timestamp": _utc_iso(), "data": data}
    key = events_key(job_id)
    await redis.rpush(key, json.dumps(record))
    await redis.expire(key, EVENTS_TTL_SECONDS)
    return record


async def list_events(redis: Any, job_id: str) -> list[dict]:
    """Return all persisted timeline events for a job, oldest first."""
    raw = await redis.lrange(events_key(job_id), 0, -1)
    events: list[dict] = []
    for item in raw or []:
        if isinstance(item, bytes):
            item = item.decode("utf-8")
        try:
            events.append(json.loads(item))
        except (json.JSONDecodeError, TypeError):
            continue
    return events


async def publish_event(redis: Any, job_id: str, event: str, data: dict) -> None:
    """Publish a single SSE-bound event onto ``progress:{job_id}`` and persist it.

    ``event`` is one of ``submitted`` | ``progress`` | ``completed`` | ``failed``.
    """
    record = await append_event(redis, job_id, event, data)
    payload = json.dumps(
        {
            "event": event,
            "data": {**data, "timestamp": record["timestamp"]},
        }
    )
    await redis.publish(progress_channel(job_id), payload)
