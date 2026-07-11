"""Chat-model factory.

These three functions are the single seam tests monkeypatch to run the whole
graph offline with a fake model (no API key, no network). Production code
returns a provider-specific chat model configured from env.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from settings import get_settings


def _build_anthropic(temperature: float) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    settings = get_settings()
    return ChatAnthropic(
        model=settings.anthropic_model,
        temperature=temperature,
        timeout=60,
        max_retries=2,
        api_key=settings.anthropic_api_key or None,
    )


def _build_nvidia(temperature: float) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    return ChatOpenAI(
        model=settings.nvidia_model,
        temperature=temperature,
        timeout=60,
        max_retries=2,
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
    )


def _build_chat_model(temperature: float) -> BaseChatModel:
    settings = get_settings()
    settings.require_llm_keys()
    if settings.llm_provider == "nvidia":
        return _build_nvidia(temperature)
    return _build_anthropic(temperature)


def get_supervisor_model() -> BaseChatModel:
    """Routing model - deterministic (temperature 0)."""
    return _build_chat_model(temperature=0)


def get_researcher_model() -> BaseChatModel:
    """Tool-calling model used by the researcher react agent."""
    return _build_chat_model(temperature=0)


def get_editor_model() -> BaseChatModel:
    """Summarising/formatting model for the final markdown answer."""
    return _build_chat_model(temperature=0.2)
