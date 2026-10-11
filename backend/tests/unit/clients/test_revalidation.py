"""Unit tests for RevalidationClient: the webhook is best-effort."""

import logging

import httpx
from pydantic import SecretStr

from src.clients.revalidation import RevalidationClient
from src.core.settings import RevalidateSettings

URL = "http://frontend:3000"
SECRET = "x" * 32


def make_client(
    url: str | None, secret: str | None, transport: httpx.AsyncBaseTransport
) -> RevalidationClient:
    settings = RevalidateSettings(
        frontend_internal_url=url,
        secret=SecretStr(secret) if secret else None,
    )
    return RevalidationClient(settings, transport=transport)


async def test_configured_client_posts_bearer_token_to_the_webhook() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, json={"revalidated": True})

    client = make_client(URL, SECRET, httpx.MockTransport(handler))

    await client.revalidate_content()

    assert seen["url"] == f"{URL}/api/revalidate"
    assert seen["authorization"] == f"Bearer {SECRET}"


async def test_http_error_response_does_not_raise() -> None:
    client = make_client(URL, SECRET, httpx.MockTransport(lambda request: httpx.Response(500)))

    await client.revalidate_content()


async def test_connection_failure_does_not_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("frontend is down")

    client = make_client(URL, SECRET, httpx.MockTransport(handler))

    await client.revalidate_content()


async def test_unconfigured_client_is_a_no_op() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("webhook must not be called")

    client = make_client(None, None, httpx.MockTransport(handler))

    await client.revalidate_content()


async def test_half_configured_client_warns_and_skips(caplog) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("webhook must not be called")

    client = make_client(URL, None, httpx.MockTransport(handler))

    with caplog.at_level(logging.WARNING):
        await client.revalidate_content()

    assert "half-configured" in caplog.text
