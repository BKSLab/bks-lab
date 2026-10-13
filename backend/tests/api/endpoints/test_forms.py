"""Public form validation, rate limits, durable feedback and idempotent subscriptions."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from main import app
from src.db.models import FeedbackMessage, Subscriber
from src.dependencies.repositories import get_feedback_repository
from src.exceptions.repositories import FeedbackRepositoryError
from src.repositories.feedback import FeedbackRepository
from src.repositories.subscribers import SubscriberRepository

FEEDBACK = {"name": "Иван", "email": "ivan@example.com", "message": "Сообщение владельцу сайта", "website": ""}


async def test_feedback_is_committed_with_normalized_fields(client, session_factory):
    response = await client.post("/api/v1/feedback", json={**FEEDBACK, "email": " Ivan@Example.COM "})
    assert response.status_code == 200 and response.json() == {"status": "sent"}
    async with session_factory() as session:
        rows = list(await session.scalars(select(FeedbackMessage)))
        assert len(rows) == 1
        assert rows[0].name == "Иван"
        assert rows[0].email == "ivan@example.com"
        assert rows[0].message == FEEDBACK["message"]
        assert rows[0].created_at.tzinfo is not None
        assert list(await session.scalars(select(Subscriber))) == []


@pytest.mark.parametrize("website", ["https://spam.example", " "])
async def test_feedback_honeypot_does_not_store_a_message(client, session_factory, website):
    response = await client.post("/api/v1/feedback", json={**FEEDBACK, "website": website})
    assert response.status_code == 200 and response.json() == {"status": "sent"}
    async with session_factory() as session:
        assert list(await session.scalars(select(FeedbackMessage))) == []


async def test_feedback_storage_failure_does_not_claim_success_or_leak_details(client):
    repository = AsyncMock(spec=FeedbackRepository)
    repository.create.side_effect = FeedbackRepositoryError("private database diagnostics")
    app.dependency_overrides[get_feedback_repository] = lambda: repository
    response = await client.post("/api/v1/feedback", json=FEEDBACK)
    assert response.status_code == 503
    assert response.json() == {"detail": "Feedback storage is temporarily unavailable"}
    assert "private" not in response.text


@pytest.mark.parametrize("field,value", [
    ("email", "invalid"), ("email", "bad\r\nBcc: other@example.com"),
    ("email", "one@example.com,two@example.com"), ("email", "a@bad_domain.example"),
    ("email", "a@localhost"), ("email", "a..b@example.com"),
    ("email", '"a,b"@example.com'),
    ("name", " "), ("name", "n" * 101), ("message", "short"), ("message", "m" * 5001),
])
async def test_invalid_feedback_identifies_the_field_without_storage(client, session_factory, field, value):
    response = await client.post("/api/v1/feedback", json={**FEEDBACK, field: value})
    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    async with session_factory() as session:
        assert list(await session.scalars(select(FeedbackMessage))) == []


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
async def test_each_public_form_limits_five_requests_per_hour(client, route):
    for number in range(6):
        payload = FEEDBACK if route == "feedback" else {"email": "a@example.com"}
        response = await client.post(f"/api/v1/{route}", json=payload, headers={"X-Forwarded-For": f"192.0.2.{number}"})
        assert response.status_code == (200 if number < 5 else 429)


async def test_subscribe_rejects_text_plain_and_extra_fields(client):
    response = await client.post("/api/v1/subscribe", content='{"email":"x@example.com"}', headers={"Content-Type": "text/plain"})
    assert response.status_code == 422
    response = await client.post("/api/v1/subscribe", json={"email": "x@example.com", "recipient": "someone@example.com"})
    assert response.status_code == 422
