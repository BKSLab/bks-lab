"""SMTP is mocked; these tests never send an external email."""

from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from src.clients.mail import MailClient
from src.core.settings import SMTPSettings
from src.exceptions.feedback import MailDeliveryError


@pytest.fixture
def settings():
    return SMTPSettings(
        host="smtp.example.test", sender="sender@example.com", recipient="owner@example.com",
        username="test", password=SecretStr("test-only-password"), _env_file=None,
    )


async def test_smtp_uses_fixed_envelope_reply_to_and_verifies_tls(monkeypatch, settings):
    send = AsyncMock(return_value=({}, "OK"))
    monkeypatch.setattr("src.clients.mail.aiosmtplib.send", send)
    await MailClient(settings).send_feedback(name="Имя\nBcc: attacker@example.com", email="visitor@example.com", message="A message")
    message = send.await_args.args[0]
    kwargs = send.await_args.kwargs
    assert message["From"] == "sender@example.com"
    assert message["To"] == "owner@example.com"
    assert message["Reply-To"] == "visitor@example.com"
    assert "Bcc" not in message
    assert kwargs["recipients"] == ["owner@example.com"]
    assert kwargs["sender"] == "sender@example.com"
    assert kwargs["start_tls"] and kwargs["validate_certs"]
    assert kwargs["timeout"] == 10


@pytest.mark.parametrize("error", [OSError("network"), TimeoutError("timeout")])
async def test_transport_errors_become_safe_delivery_errors(monkeypatch, settings, error):
    monkeypatch.setattr("src.clients.mail.aiosmtplib.send", AsyncMock(side_effect=error))
    with pytest.raises(MailDeliveryError, match="SMTP delivery failed"):
        await MailClient(settings).send_feedback(name="Name", email="a@example.com", message="Text")


async def test_missing_smtp_fails_before_transport(monkeypatch):
    send = AsyncMock()
    monkeypatch.setattr("src.clients.mail.aiosmtplib.send", send)
    with pytest.raises(MailDeliveryError, match="not configured"):
        await MailClient(SMTPSettings(_env_file=None)).send_feedback(name="Name", email="a@example.com", message="Text")
    send.assert_not_awaited()


async def test_partial_recipient_refusal_is_not_success(monkeypatch, settings):
    monkeypatch.setattr("src.clients.mail.aiosmtplib.send", AsyncMock(return_value=({"owner@example.com": "refused"}, "FAIL")))
    with pytest.raises(MailDeliveryError, match="refused"):
        await MailClient(settings).send_feedback(name="Name", email="a@example.com", message="Text")
