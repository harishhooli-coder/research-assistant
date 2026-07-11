"""SQLAlchemy 2.0 models.

The ``result`` column is JSONB on Postgres (Neon) and falls back to generic
JSON on SQLite so the same models work for offline tests. ``Uuid`` and
``DateTime(timezone=True)`` are dialect-portable.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Status lifecycle for a research job.
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

# JSONB on Postgres, JSON elsewhere (SQLite in tests).
JsonType = JSONB().with_variant(JSON(), "sqlite")


_clock_lock = threading.Lock()
_last_ts = 0.0


def _utcnow() -> datetime:
    """Strictly-monotonic UTC timestamp.

    Guarantees "recent first" ordering is deterministic even when the OS clock
    resolution is coarse (e.g. Windows) and two rows are created in the same
    tick - we bump by 1µs so no two creation timestamps collide in-process.
    """
    global _last_ts
    with _clock_lock:
        now = datetime.now(timezone.utc)
        ts = now.timestamp()
        if ts <= _last_ts:
            ts = _last_ts + 1e-6
            now = datetime.fromtimestamp(ts, timezone.utc)
        _last_ts = ts
        return now


class Base(DeclarativeBase):
    pass


class ResearchResult(Base):
    __tablename__ = "research_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    query: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=STATUS_QUEUED, index=True)
    result: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Python-side microsecond defaults give deterministic "recent first"
    # ordering on every backend (SQLite's func.now() is only second-precision).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    def to_summary(self) -> dict:
        """Shape for the ``GET /research`` list endpoint."""
        return {
            "jobId": self.job_id,
            "query": self.query,
            "status": self.status,
            "createdAt": _iso(self.created_at),
        }

    def to_detail(self) -> dict:
        """Shape for the ``GET /research/{jobId}`` detail endpoint."""
        return {
            "jobId": self.job_id,
            "query": self.query,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "createdAt": _iso(self.created_at),
            "updatedAt": _iso(self.updated_at),
        }


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None
