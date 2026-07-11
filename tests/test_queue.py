"""Kill-worker-retry-completes test (offline, via fakeredis + SQLite).

Simulates a worker dying mid-job: the first attempt raises (as if the process
was killed before it could ack), and arq re-queues the job (retry_jobs=True,
max_tries=MAX_TRIES). A subsequent attempt completes and the result lands in
the database with status ``done`` - exactly the Phase-3 acceptance criterion.

For the *real* kill-the-process demonstration against a live Redis, see the
README section "Phase 3 - kill-worker retry (manual)".
"""

from __future__ import annotations

import arq.worker as arq_worker
import pytest
from arq.connections import ArqRedis
from arq.worker import Worker

import agent.graph as agent_graph
from api.constants import JOB_TIMEOUT, MAX_TRIES, QUEUE_NAME, RESEARCH_TASK
from api.worker import run_research_job
from db import crud
from db.session import session_scope


@pytest.fixture
def no_redis_info(monkeypatch):
    # fakeredis doesn't implement INFO, which arq calls on worker startup.
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(arq_worker, "log_redis_info", _noop)


async def test_killed_worker_job_retries_and_completes(
    sqlite_db, fake_arq_pool, no_redis_info, monkeypatch
):
    pool: ArqRedis = fake_arq_pool

    # A job that "crashes" on its first attempt, then completes on the retry.
    calls = {"n": 0}

    def flaky_run_research(query, *, session_id=None, recall=None, progress_cb=None, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("worker killed mid-job")
        if progress_cb:
            progress_cb("done", 100, "complete")
        return {"markdown": f"# Answer for {query}", "sources": [], "partial": False}

    monkeypatch.setattr(agent_graph, "run_research", flaky_run_research)

    # The API would have created this row + enqueued the job.
    job_id = "job-retry-1"
    query = "resilient research"
    async with session_scope() as session:
        await crud.create_job(session, job_id, query)
    await pool.enqueue_job(
        RESEARCH_TASK, job_id, query, _job_id=job_id, _queue_name=QUEUE_NAME
    )

    worker = Worker(
        functions=[run_research_job],
        redis_pool=pool,
        queue_name=QUEUE_NAME,
        burst=True,
        max_tries=MAX_TRIES,
        retry_jobs=True,
        job_timeout=JOB_TIMEOUT,
        poll_delay=0.05,
        handle_signals=False,
    )
    await worker.main()

    # The job ran more than once (crash -> retry) and ultimately completed.
    assert calls["n"] >= 2
    assert worker.jobs_complete == 1
    assert worker.jobs_retried >= 1
    assert worker.jobs_failed == 0

    # Result persisted with status done.
    async with session_scope() as session:
        row = await crud.get_job(session, job_id)
        assert row is not None
        assert row.status == "done"
        assert row.result["markdown"] == f"# Answer for {query}"
