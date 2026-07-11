"""Shared graph state for the research assistant."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """State threaded through the supervisor/researcher/editor graph.

    - ``messages``: full conversation (reducer appends new messages).
    - ``step_count``: number of supervisor cycles (used for the loop limit).
    - ``sources``: collected ``{"title", "url"}`` dicts from web_search.
    - ``next``: routing decision set by the supervisor ("researcher"|"editor").
    - ``final_markdown``: editor's final formatted answer.
    - ``partial``: True when we exited early (loop limit / degraded results).
    """

    messages: Annotated[list[BaseMessage], add_messages]
    step_count: int
    sources: list[dict]
    next: str
    final_markdown: str
    partial: bool
