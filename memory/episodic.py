"""Redis-backed episodic memory (Phase 2).

Keeps the **last 3 searches** per session using a Redis LIST:

    LPUSH session:{id}:searches  <json>      # newest at head
    LTRIM session:{id}:searches  0 2         # keep indices 0..2 (=3 newest)

Because data lives in Redis (not process memory), it survives a bot/process
restart as long as Redis persists (enable AOF/RDB in production; the bundled
docker-compose enables AOF). ``recall()`` returns the 3 most recent entries
(newest first) which the agent injects as prior-search context.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

MAX_ENTRIES = 3


def _key(session_id: str) -> str:
    return f"session:{session_id}:searches"


class EpisodicMemory:
    """Async wrapper around a Redis LIST keyed per session.

    Pass any ``redis.asyncio.Redis``-compatible client. For offline tests use
    ``fakeredis.aioredis.FakeRedis``; in production use a real connection built
    from ``REDIS_URL``.
    """

    def __init__(self, redis: Any, max_entries: int = MAX_ENTRIES):
        self.redis = redis
        self.max_entries = max_entries

    @classmethod
    def from_url(cls, url: Optional[str] = None, **kwargs: Any) -> "EpisodicMemory":
        import redis.asyncio as aioredis

        from settings import get_settings

        url = url or get_settings().redis_url
        client = aioredis.from_url(url, decode_responses=True)
        return cls(client, **kwargs)

    async def remember(self, session_id: str, query: str, summary: str = "") -> None:
        """Record a search; keep only the most recent ``max_entries``."""
        entry = json.dumps(
            {"query": query, "summary": summary, "ts": time.time()},
            ensure_ascii=False,
        )
        key = _key(session_id)
        await self.redis.lpush(key, entry)
        await self.redis.ltrim(key, 0, self.max_entries - 1)

    async def recall(self, session_id: str) -> list[dict]:
        """Return up to ``max_entries`` most-recent searches (newest first)."""
        key = _key(session_id)
        raw = await self.redis.lrange(key, 0, self.max_entries - 1)
        out: list[dict] = []
        for item in raw:
            if isinstance(item, bytes):
                item = item.decode("utf-8")
            try:
                out.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                continue
        return out

    async def count(self, session_id: str) -> int:
        return int(await self.redis.llen(_key(session_id)))

    async def clear(self, session_id: str) -> None:
        await self.redis.delete(_key(session_id))

    async def aclose(self) -> None:
        close = getattr(self.redis, "aclose", None) or getattr(self.redis, "close", None)
        if close:
            res = close()
            if hasattr(res, "__await__"):
                await res
