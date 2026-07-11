"""CRUD helpers for ``research_results``."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    ResearchResult,
)


async def create_job(session: AsyncSession, job_id: str, query: str) -> ResearchResult:
    row = ResearchResult(job_id=job_id, query=query, status=STATUS_QUEUED)
    session.add(row)
    await session.flush()
    return row


async def get_job(session: AsyncSession, job_id: str) -> ResearchResult | None:
    res = await session.execute(
        select(ResearchResult).where(ResearchResult.job_id == job_id)
    )
    return res.scalar_one_or_none()


async def list_jobs(session: AsyncSession, limit: int = 50) -> list[ResearchResult]:
    res = await session.execute(
        select(ResearchResult).order_by(ResearchResult.created_at.desc()).limit(limit)
    )
    return list(res.scalars().all())


async def set_status(session: AsyncSession, job_id: str, status: str) -> None:
    row = await get_job(session, job_id)
    if row:
        row.status = status


async def mark_running(session: AsyncSession, job_id: str) -> None:
    await set_status(session, job_id, STATUS_RUNNING)


async def mark_done(session: AsyncSession, job_id: str, result: dict) -> None:
    row = await get_job(session, job_id)
    if row:
        row.status = STATUS_DONE
        row.result = result
        row.error = None


async def mark_failed(session: AsyncSession, job_id: str, error: str) -> None:
    row = await get_job(session, job_id)
    if row:
        row.status = STATUS_FAILED
        row.error = error
