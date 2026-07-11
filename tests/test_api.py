"""API contract tests (offline: SQLite + fakeredis, no network, no keys)."""

from __future__ import annotations

import httpx
import pytest

from db import crud
from db.session import session_scope


@pytest.fixture
async def client(sqlite_db, fake_arq_pool):
    from api.main import create_app

    app = create_app()
    app.state.redis = fake_arq_pool  # inject fakeredis; skip real-pool lifespan
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_post_research_returns_202_and_jobid(client):
    resp = await client.post("/research", json={"query": "what is langgraph?"})
    assert resp.status_code == 202
    body = resp.json()
    assert "jobId" in body and body["jobId"]

    # Row was created with status queued.
    async with session_scope() as session:
        row = await crud.get_job(session, body["jobId"])
        assert row is not None
        assert row.status == "queued"
        assert row.query == "what is langgraph?"


async def test_post_research_rejects_empty_query(client):
    resp = await client.post("/research", json={"query": ""})
    assert resp.status_code == 422


async def test_list_and_detail(client):
    r1 = (await client.post("/research", json={"query": "first"})).json()
    r2 = (await client.post("/research", json={"query": "second"})).json()

    listing = (await client.get("/research")).json()
    assert isinstance(listing, list)
    job_ids = [j["jobId"] for j in listing]
    assert r1["jobId"] in job_ids and r2["jobId"] in job_ids
    # recent first
    assert job_ids[0] == r2["jobId"]

    detail = (await client.get(f"/research/{r1['jobId']}")).json()
    assert detail["jobId"] == r1["jobId"]
    assert detail["status"] == "queued"
    assert detail["query"] == "first"


async def test_detail_404_for_unknown_job(client):
    resp = await client.get("/research/does-not-exist")
    assert resp.status_code == 404


async def test_events_endpoint_returns_persisted_timeline(client, fake_arq_pool):
    from api.redis_utils import append_event

    job = (await client.post("/research", json={"query": "timeline test"})).json()
    job_id = job["jobId"]
    await append_event(
        fake_arq_pool,
        job_id,
        "progress",
        {"phase": "supervisor", "pct": 20, "message": "Planning."},
    )

    resp = await client.get(f"/research/{job_id}/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 2  # submitted + progress
    assert events[0]["event"] == "submitted"
    assert "timestamp" in events[0]
    assert events[-1]["data"]["phase"] == "supervisor"


async def test_events_404_for_unknown_job(client):
    resp = await client.get("/research/does-not-exist/events")
    assert resp.status_code == 404


async def test_stream_emits_completed_for_finished_job(client):
    job = (await client.post("/research", json={"query": "done job"})).json()
    job_id = job["jobId"]
    # Simulate the worker finishing the job.
    async with session_scope() as session:
        await crud.mark_done(
            session, job_id, {"markdown": "# Final", "sources": [{"title": "T", "url": "u"}]}
        )

    resp = await client.get(f"/research/{job_id}/stream")
    assert resp.status_code == 200
    text = resp.text
    assert "event: completed" in text
    assert "# Final" in text


async def test_stream_emits_failed_for_failed_job(client):
    job = (await client.post("/research", json={"query": "bad job"})).json()
    job_id = job["jobId"]
    async with session_scope() as session:
        await crud.mark_failed(session, job_id, "boom")

    resp = await client.get(f"/research/{job_id}/stream")
    assert resp.status_code == 200
    assert "event: failed" in resp.text
    assert "boom" in resp.text
