"""Failure-path tests (the 3 required correctness paths).

All run fully offline: the LLM is a scripted FakeChatModel and the tools'
network helpers are monkeypatched to raise. No API keys, no network.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from agent import tools as agent_tools
from agent.graph import run_research
from agent.truncate import (
    count_message_tokens,
    truncate_content,
    truncate_messages,
)
from tests.conftest import FakeChatModel, tool_call_message


# ---------------------------------------------------------------------------
# Failure path #1: tool failure -> "source unavailable", graph still finishes.
# ---------------------------------------------------------------------------
def test_tool_failure(monkeypatch, patch_models):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(agent_tools, "_tavily_search", boom)
    monkeypatch.setattr(agent_tools, "_http_get", boom)

    # The tool itself must degrade gracefully, never raise.
    out = agent_tools.web_search.invoke({"query": "anything"})
    assert "source unavailable" in out
    assert json.loads(out)["error"] == "source unavailable"
    assert agent_tools.fetch_url.invoke({"url": "http://x"}) == "source unavailable"

    # And the full graph must still complete cleanly.
    patch_models(
        supervisor=FakeChatModel(responses=["RESEARCH", "EDIT"]),
        researcher=FakeChatModel(
            responses=[
                tool_call_message("web_search", {"query": "anything"}),
                "I attempted to search but the source was unavailable.",
            ]
        ),
        editor=FakeChatModel(
            responses=["# Answer\n\nSome sources were unavailable, but here is what I found."]
        ),
    )

    result = run_research("tell me about X")
    assert result["markdown"].strip()  # produced a final answer, no crash
    assert "partial" in result


# ---------------------------------------------------------------------------
# Failure path #2: context overflow -> graceful truncation under the cap.
# ---------------------------------------------------------------------------
def test_truncate_content_caps_single_blob():
    big = "x" * 100_000
    capped = truncate_content(big, 5_000)
    assert len(capped) <= 5_000
    assert capped.endswith("[truncated]")


def test_truncate_messages_keeps_system_and_recent_under_cap():
    system = SystemMessage(content="SYSTEM RULES")
    old = HumanMessage(content="old " * 5000)
    recent = HumanMessage(content="the most recent and important question")
    msgs = [system, old, recent]

    trimmed = truncate_messages(msgs, max_tokens=200, max_chars_per_message=2000)

    assert any(isinstance(m, SystemMessage) for m in trimmed)  # system preserved
    assert trimmed[-1].content == recent.content  # most recent preserved
    assert count_message_tokens(trimmed) <= 200


def test_context_overflow_graph_completes(patch_models):
    # Supervisor may try EDIT immediately; the graph overrides to RESEARCH until
    # the researcher has produced output, so patch all three roles.
    supervisor = FakeChatModel(responses=["EDIT"])
    researcher = FakeChatModel(responses=["Findings under truncation."])
    editor = FakeChatModel(responses=["# Final answer"])
    patch_models(supervisor=supervisor, researcher=researcher, editor=editor)

    from settings import get_settings

    cap = get_settings().max_context_tokens

    huge_query = "word " * 40_000  # ~tens of thousands of tokens
    result = run_research(huge_query)

    assert result["markdown"] == "# Final answer"  # completed, no overflow crash
    # Every prompt the models actually received stayed under the token cap.
    for received in supervisor.received + researcher.received + editor.received:
        assert count_message_tokens(received) <= cap


# ---------------------------------------------------------------------------
# Failure path #3: loop > 5 steps -> clean exit with partial results.
# ---------------------------------------------------------------------------
def test_loop_limit_clean_exit(patch_models):
    # Supervisor always wants more research; the guard must force a finish.
    patch_models(
        supervisor=FakeChatModel(responses=["RESEARCH"]),
        researcher=FakeChatModel(responses=["partial findings, no tools used"]),
        editor=FakeChatModel(responses=["# Partial answer\n\nBased on limited research."]),
    )

    result = run_research("loop forever please")

    assert result["partial"] is True  # we exited via the step-limit guard
    assert result["markdown"].strip()  # still produced a final answer


def test_supervisor_forces_research_before_edit(patch_models):
    """EDIT before any researcher output must be overridden to RESEARCH."""
    patch_models(
        supervisor=FakeChatModel(responses=["EDIT", "EDIT"]),
        researcher=FakeChatModel(responses=["Found one useful source about X."]),
        editor=FakeChatModel(responses=["# Answer\n\nBased on research."]),
    )

    result = run_research("tell me about X")

    assert result["markdown"].startswith("# Answer")
    assert result["partial"] is False
