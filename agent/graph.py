"""The 2-agent research graph: supervisor + researcher + editor.

Uses the *manual* tool-based supervisor pattern (not langgraph-supervisor) for
precise control over the three required failure paths:

  1. Tool failure   -> tools return "source unavailable"; graph continues.
  2. Context overflow-> truncate_messages() before every LLM call.
  3. Loop > 5 steps -> supervisor force-routes to editor and exits cleanly
                       with a partial-results notice.
"""

from __future__ import annotations

from typing import Callable, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

from agent import llm
from agent.state import AgentState
from agent.tools import (
    SOURCE_UNAVAILABLE,
    TOOLS,
    parse_sources_from_tool_output,
)
from agent.truncate import truncate_messages
from settings import get_settings

ProgressCB = Optional[Callable[[str, int, str], None]]

SUPERVISOR_PROMPT = """You are the supervisor of a research team. Decide the next step.

Reply with EXACTLY ONE WORD:
- RESEARCH  - if more web research/sources are needed to answer the user.
- EDIT      - if enough information has been gathered to write the final answer.

Consider the conversation so far. Prefer EDIT once you have at least one useful
source or after research has been attempted. Do not output anything else."""

RESEARCHER_PROMPT = """You are a research agent. Use the web_search tool to find
relevant sources for the user's question, and fetch_url to read promising pages.
If a tool reports 'source unavailable', try a different query or source, or
proceed with what you have. Summarise the key findings with their sources."""

EDITOR_PROMPT = """You are an expert editor. Using the research in the conversation,
write a clear, well-structured **markdown** answer to the user's original
question. Include a short '## Sources' section listing the sources used. If some
sources were unavailable or the research was incomplete, say so briefly and
answer with what is available. Be concise and factual."""


def _supervisor_node_factory(progress_cb: ProgressCB):
    settings = get_settings()
    max_steps = settings.max_supervisor_steps

    def supervisor(state: AgentState) -> dict:
        step = state.get("step_count", 0) + 1

        # --- Failure path #3: loop limit -> force a clean finish. ----------
        if step > max_steps:
            if progress_cb:
                progress_cb("supervisor", 80, f"Step limit ({max_steps}) reached; finalizing.")
            return {
                "step_count": step,
                "next": "editor",
                "partial": True,
                "messages": [
                    AIMessage(
                        content=(
                            f"[supervisor] Step limit of {max_steps} reached. "
                            "Routing to editor to finalize with partial results."
                        )
                    )
                ],
            }

        if progress_cb:
            progress_cb("supervisor", min(20 + step * 10, 70), f"Planning step {step}.")

        messages = state.get("messages", [])
        model = llm.get_supervisor_model()
        prompt = [SystemMessage(content=SUPERVISOR_PROMPT), *messages]
        prompt = truncate_messages(
            prompt,
            settings.max_context_tokens,
            max_chars_per_message=settings.max_fetch_chars,
        )
        resp = model.invoke(prompt)
        decision = _parse_decision(resp.content)
        return {"step_count": step, "next": decision}

    return supervisor


def _parse_decision(content) -> str:
    text = content if isinstance(content, str) else str(content)
    upper = text.strip().upper()
    if "RESEARCH" in upper:
        return "researcher"
    return "editor"


def _researcher_node_factory(progress_cb: ProgressCB):
    settings = get_settings()

    def researcher(state: AgentState) -> dict:
        if progress_cb:
            progress_cb("researcher", 50, "Searching the web for sources.")

        model = llm.get_researcher_model()
        react_agent = create_react_agent(model, TOOLS, prompt=RESEARCHER_PROMPT)

        # Only pass the human/AI context (not prior tool noise) to keep it lean.
        messages = state.get("messages", [])
        trimmed = truncate_messages(
            list(messages),
            settings.max_context_tokens,
            max_chars_per_message=settings.max_fetch_chars,
        )

        result = react_agent.invoke({"messages": trimmed})
        new_messages = result.get("messages", [])

        # Collect sources from any web_search tool outputs produced this turn.
        sources = list(state.get("sources", []))
        seen = {s.get("url") for s in sources}
        for m in new_messages:
            if m.__class__.__name__ == "ToolMessage":
                for src in parse_sources_from_tool_output(str(m.content)):
                    if src["url"] not in seen:
                        sources.append(src)
                        seen.add(src["url"])

        # Surface only the researcher's final summary back into shared state.
        summary = _last_ai_text(new_messages) or "No findings produced."
        return {
            "messages": [AIMessage(content=f"[researcher] {summary}")],
            "sources": sources,
        }

    return researcher


def _editor_node_factory(progress_cb: ProgressCB):
    settings = get_settings()

    def editor(state: AgentState) -> dict:
        if progress_cb:
            progress_cb("editor", 90, "Writing the final answer.")

        model = llm.get_editor_model()
        messages = state.get("messages", [])
        sources = state.get("sources", [])
        partial = state.get("partial", False)

        notice = ""
        if partial:
            notice = (
                "\nNOTE: research was cut short (step limit / degraded sources); "
                "write the best possible answer with what is available and say so."
            )
        sources_hint = ""
        if sources:
            listed = "\n".join(f"- {s['title']}: {s['url']}" for s in sources)
            sources_hint = f"\nKnown sources:\n{listed}"

        prompt = [
            SystemMessage(content=EDITOR_PROMPT + notice + sources_hint),
            *messages,
        ]
        prompt = truncate_messages(
            prompt,
            settings.max_context_tokens,
            max_chars_per_message=settings.max_fetch_chars,
        )
        resp = model.invoke(prompt)
        markdown = resp.content if isinstance(resp.content, str) else str(resp.content)

        if not markdown.strip():
            markdown = f"Unable to produce a full answer ({SOURCE_UNAVAILABLE})."

        return {
            "messages": [AIMessage(content=markdown)],
            "final_markdown": markdown,
        }

    return editor


def _last_ai_text(messages) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            content = m.content
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                texts = [b.get("text", "") for b in content if isinstance(b, dict)]
                joined = " ".join(t for t in texts if t).strip()
                if joined:
                    return joined
    return ""


def _route(state: AgentState) -> Literal["researcher", "editor"]:
    nxt = state.get("next", "editor")
    return "researcher" if nxt == "researcher" else "editor"


def build_graph(progress_cb: ProgressCB = None):
    """Compile and return the research graph.

    ``progress_cb(phase, pct, message)`` is an optional callback the worker uses
    to publish live progress to Redis for SSE.
    """
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", _supervisor_node_factory(progress_cb))
    graph.add_node("researcher", _researcher_node_factory(progress_cb))
    graph.add_node("editor", _editor_node_factory(progress_cb))

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route,
        {"researcher": "researcher", "editor": "editor"},
    )
    graph.add_edge("researcher", "supervisor")
    graph.add_edge("editor", END)

    return graph.compile()


def run_research(
    query: str,
    *,
    session_id: str | None = None,
    recall: list[dict] | None = None,
    progress_cb: ProgressCB = None,
    recursion_limit: int = 50,
) -> dict:
    """Run the full research graph for ``query`` and return the final result.

    Returns ``{"markdown": str, "sources": [{"title","url"}], "partial": bool}``.
    """
    if progress_cb:
        progress_cb("queued", 5, "Starting research.")

    initial_messages: list = []
    if recall:
        lines = [f"- {r.get('query', '')}: {r.get('summary', '')}" for r in recall]
        initial_messages.append(
            SystemMessage(
                content="Recent prior searches in this session (for context):\n"
                + "\n".join(lines)
            )
        )
    initial_messages.append(HumanMessage(content=query))

    app = build_graph(progress_cb)
    final_state = app.invoke(
        {
            "messages": initial_messages,
            "step_count": 0,
            "sources": [],
            "partial": False,
        },
        config={"recursion_limit": recursion_limit},
    )

    markdown = final_state.get("final_markdown") or _last_ai_text(
        final_state.get("messages", [])
    )
    result = {
        "markdown": markdown or f"No answer produced ({SOURCE_UNAVAILABLE}).",
        "sources": final_state.get("sources", []),
        "partial": bool(final_state.get("partial", False)),
    }
    if progress_cb:
        progress_cb("done", 100, "Research complete.")
    return result
