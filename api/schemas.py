"""Pydantic request/response models matching the documented API contract."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["queued", "running", "done", "failed"]


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The research question")


class EnqueueResponse(BaseModel):
    jobId: str


class JobSummary(BaseModel):
    jobId: str
    query: str
    status: Status
    createdAt: Optional[str] = None


class JobDetail(BaseModel):
    jobId: str
    query: str
    status: Status
    result: Optional[Any] = None
    error: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class JobEvent(BaseModel):
    event: str
    timestamp: str
    data: dict[str, Any] = Field(default_factory=dict)
