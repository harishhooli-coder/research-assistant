"""Shared constants for the API/worker (queue, channels, retry policy)."""

from __future__ import annotations

QUEUE_NAME = "research:queue"
RESEARCH_TASK = "run_research_job"

# Reliability knobs (see api/worker.py WorkerSettings).
MAX_TRIES = 4          # a killed/crashed job is re-run up to this many times
JOB_TIMEOUT = 300      # seconds; a job exceeding this is considered failed/retried


def progress_channel(job_id: str) -> str:
    return f"progress:{job_id}"


def events_key(job_id: str) -> str:
    """Redis list key for persisted job timeline events."""
    return f"job_events:{job_id}"


# Keep persisted timelines for one week (seconds).
EVENTS_TTL_SECONDS = 7 * 86400
