"""Shared pytest fixtures + an offline fake chat model.

The fake model lets us drive the entire LangGraph graph (supervisor, the
researcher react-agent, and the editor) without any Anthropic key or network.
It supports ``bind_tools`` (returned unchanged) and can emit scripted tool
calls so ``create_react_agent`` behaves realistically.
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeChatModel(BaseChatModel):
    """A scripted chat model.

    ``responses`` is a list of either strings (-> AIMessage content) or
    AIMessage objects (use these to script tool calls). When the script is
    exhausted, the last response repeats so multi-cycle graphs never starve.
    """

    responses: List[Any] = []
    i: int = 0
    received: List[List[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "fake-chat-model"

    def _next(self) -> AIMessage:
        if not self.responses:
            return AIMessage(content="")
        idx = min(self.i, len(self.responses) - 1)
        self.i += 1
        item = self.responses[idx]
        if isinstance(item, AIMessage):
            return item
        if isinstance(item, BaseMessage):
            return AIMessage(content=str(item.content))
        return AIMessage(content=str(item))

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.received.append(list(messages))
        msg = self._next()
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any):  # noqa: D401
        # The react agent binds tools; we ignore them and keep the script.
        return self


def tool_call_message(name: str, args: dict, call_id: str = "call_1") -> AIMessage:
    """Build an AIMessage that requests a single tool call."""
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


@pytest.fixture(autouse=True)
def runtime_api_keys(monkeypatch):
    """Tests mock the LLM/tools; only need non-placeholder key-shaped env values."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-" + ("x" * 80))
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-" + ("x" * 40))
    from settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def sqlite_db(tmp_path):
    """Initialise the async DB layer against a temp SQLite file."""
    import db.session as dbsession

    await dbsession.dispose()
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    dbsession.get_engine(url)
    await dbsession.create_all()
    try:
        yield url
    finally:
        await dbsession.dispose()


@pytest.fixture
def fake_arq_pool():
    """An ArqRedis pool backed by an in-memory fakeredis server."""
    import fakeredis.aioredis as fakeredis
    from arq.connections import ArqRedis

    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server)
    pool = ArqRedis(connection_pool=client.connection_pool)
    return pool


@pytest.fixture
def patch_models(monkeypatch):
    """Helper to patch the three model factories with fake models.

    Usage::

        patch_models(supervisor=FakeChatModel(responses=["RESEARCH", "EDIT"]),
                     researcher=FakeChatModel(responses=[...]),
                     editor=FakeChatModel(responses=["# Answer"]))
    """

    def _apply(
        supervisor: BaseChatModel | None = None,
        researcher: BaseChatModel | None = None,
        editor: BaseChatModel | None = None,
    ):
        from agent import llm

        if supervisor is not None:
            monkeypatch.setattr(llm, "get_supervisor_model", lambda: supervisor)
        if researcher is not None:
            monkeypatch.setattr(llm, "get_researcher_model", lambda: researcher)
        if editor is not None:
            monkeypatch.setattr(llm, "get_editor_model", lambda: editor)

    return _apply
