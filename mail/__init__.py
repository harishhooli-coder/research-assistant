"""AgentMail integration: inboxes and outbound research-result delivery."""

from mail.client import ensure_inbox, get_client, send_research_result

__all__ = ["ensure_inbox", "get_client", "send_research_result"]
