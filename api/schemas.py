"""Pydantic request/response models matching the documented API contract."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["queued", "running", "done", "failed"]


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The research question")
    notifyEmail: Optional[str] = Field(
        default=None,
        description=(
            "Optional email address. When set and AgentMail is configured, "
            "the finished research report is emailed to this address."
        ),
    )


class EnqueueResponse(BaseModel):
    jobId: str


class ResearchSource(BaseModel):
    title: str
    url: str


class ResearchResultPayload(BaseModel):
    markdown: str
    sources: list[ResearchSource] = Field(default_factory=list)
    partial: bool = False


class JobSummary(BaseModel):
    jobId: str
    query: str
    status: Status
    createdAt: str


class JobDetail(BaseModel):
    jobId: str
    query: str
    status: Status
    result: Optional[ResearchResultPayload] = None
    error: Optional[str] = None
    createdAt: str
    updatedAt: str


class JobEvent(BaseModel):
    event: str
    timestamp: str
    data: dict[str, Any] = Field(default_factory=dict)
