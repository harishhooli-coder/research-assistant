"""Offline unit tests for the AgentMail wrapper."""

from __future__ import annotations

from types import SimpleNamespace

from mail import client as mail_client


class _FakeMessages:
    def __init__(self) -> None:
        self.sent = None

    def send(self, inbox_id, **kwargs):
        self.sent = {"inbox_id": inbox_id, **kwargs}
        return SimpleNamespace(message_id="msg_test_1")


class _FakeInboxes:
    def __init__(self) -> None:
        self.messages = _FakeMessages()
        self.created = None

    def create(self, **kwargs):
        self.created = kwargs
        return SimpleNamespace(inbox_id="inbox_test_1")


class _FakeClient:
    def __init__(self) -> None:
        self.inboxes = _FakeInboxes()


def test_send_research_result_uses_configured_inbox(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(mail_client, "get_client", lambda: fake)
    monkeypatch.setattr(
        mail_client,
        "get_settings",
        lambda: SimpleNamespace(
            agentmail_api_key_configured=True,
            agentmail_inbox_id="inbox_configured",
            agentmail_api_key="am_test",
        ),
    )

    meta = mail_client.send_research_result(
        to="you@example.com",
        query="What is LangGraph?",
        job_id="abc123",
        markdown="# Answer\nIt is a graph framework.",
        sources=[{"title": "Docs", "url": "https://example.com"}],
    )

    assert meta["inbox_id"] == "inbox_configured"
    assert meta["message_id"] == "msg_test_1"
    assert meta["to"] == "you@example.com"
    assert fake.inboxes.messages.sent["to"] == "you@example.com"
    assert "LangGraph" in fake.inboxes.messages.sent["subject"]
    assert "Docs" in fake.inboxes.messages.sent["text"]


def test_ensure_inbox_creates_when_unset(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(
        mail_client,
        "get_settings",
        lambda: SimpleNamespace(
            agentmail_api_key_configured=True,
            agentmail_inbox_id="",
            agentmail_api_key="am_test",
        ),
    )
    inbox_id = mail_client.ensure_inbox(fake)
    assert inbox_id == "inbox_test_1"
    req = fake.inboxes.created["request"]
    assert req.client_id == mail_client.INBOX_CLIENT_ID
    assert req.display_name == mail_client.INBOX_DISPLAY_NAME


def test_get_client_returns_none_without_key(monkeypatch):
    monkeypatch.setattr(
        mail_client,
        "get_settings",
        lambda: SimpleNamespace(
            agentmail_api_key_configured=False,
            agentmail_api_key="",
            agentmail_inbox_id="",
        ),
    )
    assert mail_client.get_client() is None
