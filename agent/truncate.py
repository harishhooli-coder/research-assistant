"""Context-overflow handling (failure path #2).

We count tokens with ``tiktoken`` and gracefully trim *oldest* non-system
messages plus cap any single oversized message, always keeping the system
prompt and the most recent messages. This guarantees we never exceed the
model context window even when a tool returns a huge blob of fetched text.
"""

from __future__ import annotations

from typing import Iterable

from langchain_core.messages import BaseMessage, SystemMessage

try:  # tiktoken is optional at runtime; fall back to a char heuristic.
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover - only hit if tiktoken missing/offline
    _ENC = None


def count_tokens(text: str) -> int:
    """Approximate token count for a string."""
    if not text:
        return 0
    if _ENC is not None:
        return len(_ENC.encode(text))
    # ~4 chars per token heuristic
    return max(1, len(text) // 4)


def _message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    # content can be a list of blocks (e.g. tool use); stringify defensively
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text", block)))
            else:
                parts.append(str(block))
    else:
        parts.append(str(content))
    return " ".join(parts)


def count_message_tokens(messages: Iterable[BaseMessage]) -> int:
    """Total token estimate for a list of messages (+per-message overhead)."""
    total = 0
    for m in messages:
        total += count_tokens(_message_text(m)) + 4  # role/formatting overhead
    return total


def truncate_content(text: str, max_chars: int) -> str:
    """Cap a single fetched/tool string, appending a clear truncation marker."""
    if text is None:
        return ""
    if len(text) <= max_chars:
        return text
    keep = max(0, max_chars - len("\n...[truncated]"))
    return text[:keep] + "\n...[truncated]"


def truncate_messages(
    messages: list[BaseMessage],
    max_tokens: int,
    *,
    max_chars_per_message: int | None = None,
) -> list[BaseMessage]:
    """Return a message list guaranteed to fit under ``max_tokens``.

    Strategy (graceful):
      1. Always keep every ``SystemMessage`` (instructions/persona).
      2. Optionally cap any single message body to ``max_chars_per_message``.
      3. Drop oldest non-system messages until we're under the token cap,
         always preserving the most recent message.
    """
    if not messages:
        return messages

    system = [m for m in messages if isinstance(m, SystemMessage)]
    rest = [m for m in messages if not isinstance(m, SystemMessage)]

    # Step 2: cap oversized individual messages in-place (new objects).
    if max_chars_per_message is not None:
        capped: list[BaseMessage] = []
        for m in rest:
            text = _message_text(m)
            if isinstance(m.content, str) and len(m.content) > max_chars_per_message:
                m = m.model_copy(
                    update={"content": truncate_content(m.content, max_chars_per_message)}
                )
            capped.append(m)
        rest = capped

    # Step 3: drop oldest non-system messages until under budget.
    system_tokens = count_message_tokens(system)
    while rest and (system_tokens + count_message_tokens(rest)) > max_tokens and len(rest) > 1:
        rest.pop(0)

    # If even the single most-recent message + system is too big, hard-cap it.
    if rest and (system_tokens + count_message_tokens(rest)) > max_tokens:
        last = rest[-1]
        budget_tokens = max(1, max_tokens - system_tokens)
        budget_chars = budget_tokens * 4
        if isinstance(last.content, str):
            rest[-1] = last.model_copy(
                update={"content": truncate_content(last.content, budget_chars)}
            )

    return system + rest
