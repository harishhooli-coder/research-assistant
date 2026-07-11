"""Manual helper: create a research job row + enqueue it (for the kill-worker
retry demo against a REAL Redis/Postgres). Prints the jobId.

Run (with REDIS_URL + DATABASE_URL set, DB migrated):
    python -m scripts.enqueue_job "What is LangGraph?"
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from api.constants import QUEUE_NAME, RESEARCH_TASK
from api.redis_utils import create_arq_pool
from db import crud
from db.session import dispose, session_scope


async def main(query: str) -> None:
    job_id = uuid.uuid4().hex
    async with session_scope() as session:
        await crud.create_job(session, job_id, query)

    pool = await create_arq_pool()
    await pool.enqueue_job(
        RESEARCH_TASK, job_id, query, _job_id=job_id, _queue_name=QUEUE_NAME
    )
    await pool.aclose()
    await dispose()
    print(job_id)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What is LangGraph?"
    asyncio.run(main(q))
