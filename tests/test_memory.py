"""Phase 2 episodic-memory acceptance tests (offline via fakeredis).

Proves the three required properties:
  1. Three searches in a session are all recalled.
  2. Memory survives a simulated process restart (data persists in Redis,
     not in the bot's process memory) - we drop the client and reconnect to
     the same fakeredis server.
  3. A 4th search evicts the oldest (LTRIM keeps only the last 3).

To run against a REAL Redis instead of fakeredis, see tests/README in the
project README ("Phase 2 - run against real Redis").
"""

from __future__ import annotations

import fakeredis.aioredis as fakeredis
import pytest

from memory import EpisodicMemory

SESSION = "chat-123"


@pytest.fixture
def server():
    # A shared in-memory server so multiple clients see the same data
    # (this is what lets us simulate a process restart).
    return fakeredis.FakeServer()


def new_client(server):
    return fakeredis.FakeRedis(server=server, decode_responses=True)


async def test_three_searches_all_recalled(server):
    mem = EpisodicMemory(new_client(server))
    await mem.remember(SESSION, "python asyncio", "asyncio summary")
    await mem.remember(SESSION, "rust ownership", "ownership summary")
    await mem.remember(SESSION, "go channels", "channels summary")

    recalled = await mem.recall(SESSION)
    assert len(recalled) == 3
    queries = [r["query"] for r in recalled]
    # newest first
    assert queries == ["go channels", "rust ownership", "python asyncio"]


async def test_memory_survives_restart(server):
    # First "process": write 3 searches, then drop the client.
    mem1 = EpisodicMemory(new_client(server))
    await mem1.remember(SESSION, "q1", "s1")
    await mem1.remember(SESSION, "q2", "s2")
    await mem1.remember(SESSION, "q3", "s3")
    await mem1.aclose()
    del mem1

    # Second "process": brand-new client to the same Redis server.
    mem2 = EpisodicMemory(new_client(server))
    recalled = await mem2.recall(SESSION)
    assert len(recalled) == 3
    assert [r["query"] for r in recalled] == ["q3", "q2", "q1"]


async def test_fourth_search_evicts_oldest(server):
    mem = EpisodicMemory(new_client(server))
    for q in ["q1", "q2", "q3"]:
        await mem.remember(SESSION, q, f"summary {q}")

    assert await mem.count(SESSION) == 3

    # 4th search -> oldest (q1) evicted, length stays 3.
    await mem.remember(SESSION, "q4", "summary q4")

    assert await mem.count(SESSION) == 3
    recalled = [r["query"] for r in await mem.recall(SESSION)]
    assert recalled == ["q4", "q3", "q2"]
    assert "q1" not in recalled  # oldest evicted
