"""Manual Phase-2 demo against a REAL Redis (proves persistence + eviction).

Prereqs: a running Redis (e.g. `docker compose up -d redis`) and REDIS_URL set
(defaults to redis://localhost:6379).

Run:
    python -m scripts.memory_demo

It will:
  1. Record 3 searches and show all 3 are recalled.
  2. Drop the client and reconnect (simulating a process restart) - data
     survives because it lives in Redis (AOF persistence in docker-compose).
  3. Record a 4th search and show the oldest was evicted (length stays 3).
"""

from __future__ import annotations

import asyncio

from memory import EpisodicMemory

SESSION = "demo-session"


async def main() -> None:
    mem = EpisodicMemory.from_url()
    await mem.clear(SESSION)

    for q in ["python asyncio", "rust ownership", "go channels"]:
        await mem.remember(SESSION, q, f"summary of {q}")
    recalled = await mem.recall(SESSION)
    print("1) After 3 searches, recalled (newest first):")
    for r in recalled:
        print("   -", r["query"])
    assert len(recalled) == 3

    # Simulate a process restart: drop the client, reconnect fresh.
    await mem.aclose()
    mem2 = EpisodicMemory.from_url()
    recalled2 = await mem2.recall(SESSION)
    print("2) After simulated restart, still recalled:", [r["query"] for r in recalled2])
    assert len(recalled2) == 3

    await mem2.remember(SESSION, "elixir processes", "summary of elixir processes")
    recalled3 = await mem2.recall(SESSION)
    print("3) After 4th search (oldest evicted):", [r["query"] for r in recalled3])
    assert len(recalled3) == 3
    assert "python asyncio" not in [r["query"] for r in recalled3]

    await mem2.clear(SESSION)
    await mem2.aclose()
    print("\nOK: 3 recalled, survived restart, 4th evicted the oldest.")


if __name__ == "__main__":
    asyncio.run(main())
