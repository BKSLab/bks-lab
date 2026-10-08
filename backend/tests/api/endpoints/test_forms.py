"""Public form validation, rate limits, delivery failures and idempotent storage."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from main import app
from src.clients.mail import MailClient
from src.db.models import Subscriber
from src.dependencies.services import get_mail_client
from src.exceptions.feedback import MailDeliveryError
from src.repositories.subscribers import SubscriberRepository

FEEDBACK = {"name": "Иван", "email": "ivan@example.com", "message": "Сообщение владельцу сайта", "website": ""}


@pytest.fixture
def mail_client(client):
    mail = AsyncMock(spec=MailClient)
    app.dependency_overrides[get_mail_client] = lambda: mail
    return mail


async def test_feedback_delivers_normalized_fields_without_storing_them(client, mail_client, session_factory):
    response = await client.post("/api/v1/feedback", json={**FEEDBACK, "email": " Ivan@Example.COM "})
    assert response.status_code == 200 and response.json() == {"status": "sent"}
    mail_client.send_feedback.assert_awaited_once_with(name="Иван", email="ivan@example.com", message=FEEDBACK["message"])
    async with session_factory() as session:
        assert list(await session.scalars(select(Subscriber))) == []


@pytest.mark.parametrize("website", ["https://spam.example", " "])
async def test_feedback_honeypot_does_not_send_mail(client, mail_client, website):
    response = await client.post("/api/v1/feedback", json={**FEEDBACK, "website": website})
    assert response.status_code == 200 and response.json() == {"status": "sent"}
    mail_client.send_feedback.assert_not_awaited()


async def test_missing_smtp_is_an_honest_service_unavailable(client):
    response = await client.post("/api/v1/feedback", json=FEEDBACK)
    assert response.status_code == 503
    assert response.json() == {"detail": "Feedback delivery is temporarily unavailable"}


async def test_smtp_failure_does_not_claim_success_or_leak_details(client, mail_client):
    mail_client.send_feedback.side_effect = MailDeliveryError("private SMTP diagnostics")
    response = await client.post("/api/v1/feedback", json=FEEDBACK)
    assert response.status_code == 503
    assert "private" not in response.text


@pytest.mark.parametrize("field,value", [
    ("email", "invalid"), ("email", "bad\r\nBcc: other@example.com"),
    ("email", "one@example.com,two@example.com"), ("email", "a@bad_domain.example"),
    ("email", "a@localhost"), ("email", "a..b@example.com"),
    ("email", '"a,b"@example.com'),
    ("name", " "), ("name", "n" * 101), ("message", "short"), ("message", "m" * 5001),
])
async def test_invalid_feedback_identifies_the_field_without_sending(client, mail_client, field, value):
    response = await client.post("/api/v1/feedback", json={**FEEDBACK, field: value})
    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    mail_client.send_feedback.assert_not_awaited()


async def test_subscription_is_normalized_idempotent_and_keeps_first_timestamp(client, session_factory):
    first = await client.post("/api/v1/subscribe", json={"email": "Reader@Example.COM"})
    assert first.status_code == 200 and first.json() == {"status": "subscribed"}
    async with session_factory() as session:
        saved_time = (await session.get(Subscriber, "reader@example.com")).subscribed_at
    second = await client.post("/api/v1/subscribe", json={"email": "reader@example.com"})
    assert second.status_code == 200 and second.json() == first.json()
    async with session_factory() as session:
        rows = list(await session.scalars(select(Subscriber)))
        assert len(rows) == 1 and rows[0].subscribed_at == saved_time


async def test_concurrent_duplicate_subscriptions_are_atomic(session_factory):
    async def subscribe_once():
        async with session_factory() as session:
            await SubscriberRepository(session).subscribe("same@example.com")
    await asyncio.gather(*(subscribe_once() for _ in range(4)))
    async with session_factory() as session:
        assert len(list(await session.scalars(select(Subscriber)))) == 1


async def test_subscription_honeypot_does_not_store_email(client, session_factory):
    response = await client.post("/api/v1/subscribe", json={"email": "bot@example.com", "website": "spam"})
    assert response.status_code == 200
    async with session_factory() as session:
        assert list(await session.scalars(select(Subscriber))) == []


@pytest.mark.parametrize("route", ["feedback", "subscribe"])
async def test_each_public_form_limits_five_requests_per_hour(client, mail_client, route):
    for number in range(6):
        payload = FEEDBACK if route == "feedback" else {"email": "a@example.com"}
        response = await client.post(f"/api/v1/{route}", json=payload, headers={"X-Forwarded-For": f"192.0.2.{number}"})
        assert response.status_code == (200 if number < 5 else 429)


async def test_subscribe_rejects_text_plain_and_extra_fields(client):
    response = await client.post("/api/v1/subscribe", content='{"email":"x@example.com"}', headers={"Content-Type": "text/plain"})
    assert response.status_code == 422
    response = await client.post("/api/v1/subscribe", json={"email": "x@example.com", "recipient": "someone@example.com"})
    assert response.status_code == 422
