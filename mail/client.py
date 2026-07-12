"""Thin AgentMail wrapper used by the API worker.

Keeps the SDK import lazy so offline tests never need the package installed
against a live key. Inbox creation is idempotent via ``client_id``.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from settings import get_settings

logger = logging.getLogger(__name__)

# Stable idempotency key so retries / restarts reuse the same inbox.
INBOX_CLIENT_ID = "research-assistant-inbox-v1"
INBOX_DISPLAY_NAME = "Research Assistant"


def get_client():
    """Return a configured ``AgentMail`` client, or ``None`` if not configured."""
    settings = get_settings()
    if not settings.agentmail_api_key_configured:
        return None
    from agentmail import AgentMail

    return AgentMail(api_key=settings.agentmail_api_key)


def ensure_inbox(client=None) -> Optional[str]:
    """Return an inbox id, creating one if ``AGENTMAIL_INBOX_ID`` is unset.

    Prefers the configured ``AGENTMAIL_INBOX_ID``. Otherwise creates (or reuses
    via ``client_id``) the research-assistant inbox and returns its id.
    """
    settings = get_settings()
    configured = (settings.agentmail_inbox_id or "").strip()
    if configured:
        return configured

    client = client or get_client()
    if client is None:
        return None

    from agentmail.inboxes.types.create_inbox_request import CreateInboxRequest

    inbox = client.inboxes.create(
        request=CreateInboxRequest(
            client_id=INBOX_CLIENT_ID,
            display_name=INBOX_DISPLAY_NAME,
        )
    )
    inbox_id = getattr(inbox, "inbox_id", None) or getattr(inbox, "inboxId", None)
    if not inbox_id:
        raise RuntimeError(f"AgentMail inbox create returned no inbox_id: {inbox!r}")
    logger.info("AgentMail inbox ready: %s", inbox_id)
    return str(inbox_id)


def send_research_result(
    *,
    to: str,
    query: str,
    job_id: str,
    markdown: str,
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Email a finished research report. Raises on send failure."""
    client = get_client()
    if client is None:
        raise RuntimeError(
            "AgentMail is not configured. Set AGENTMAIL_API_KEY in .env."
        )

    inbox_id = ensure_inbox(client)
    if not inbox_id:
        raise RuntimeError("Could not resolve AgentMail inbox id.")

    sources = sources or []
    sources_block = "\n".join(
        f"- {s.get('title') or s.get('url')}: {s.get('url')}" for s in sources if s.get("url")
    )
    text = (
        f"Research Assistant finished job {job_id}.\n\n"
        f"Query: {query}\n\n"
        f"{markdown}\n"
    )
    if sources_block:
        text += f"\nSources:\n{sources_block}\n"

    html_sources = "".join(
        f"<li><a href=\"{s.get('url')}\">{s.get('title') or s.get('url')}</a></li>"
        for s in sources
        if s.get("url")
    )
    # Keep HTML simple: wrap markdown as preformatted text for reliable delivery.
    html_body = (
        f"<p><strong>Research Assistant</strong> finished job "
        f"<code>{job_id}</code>.</p>"
        f"<p><strong>Query:</strong> {_escape(query)}</p>"
        f"<pre style=\"white-space:pre-wrap;font-family:ui-monospace,monospace;"
        f"font-size:14px;line-height:1.45\">{_escape(markdown)}</pre>"
    )
    if html_sources:
        html_body += f"<h3>Sources</h3><ul>{html_sources}</ul>"

    subject = f"Research results: {_truncate(query, 80)}"
    sent = client.inboxes.messages.send(
        inbox_id,
        to=to,
        subject=subject,
        text=text,
        html=html_body,
    )
    message_id = getattr(sent, "message_id", None) or getattr(sent, "messageId", None)
    logger.info("Emailed research job %s to %s (message_id=%s)", job_id, to, message_id)
    return {
        "inbox_id": inbox_id,
        "message_id": message_id,
        "to": to,
    }


def _truncate(value: str, max_len: int) -> str:
    value = (value or "").strip().replace("\n", " ")
    if len(value) <= max_len:
        return value
    return value[: max_len - 1] + "…"


def _escape(value: str) -> str:
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
