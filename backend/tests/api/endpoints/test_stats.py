"""API contract tests for POST /api/v1/stats/pageview."""

import hashlib
import hmac

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.db.models import PageView

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"


async def stored_views(session_factory) -> list[PageView]:
    async with session_factory() as session:
        result = await session.execute(select(PageView))
        return list(result.scalars())


async def post_view(client: AsyncClient, path: str = "/", **kwargs):
    headers = {"User-Agent": BROWSER_UA}
    headers.update(kwargs.pop("headers", {}))
    payload = {"path": path}
    payload.update(kwargs)
    return await client.post("/api/v1/stats/pageview", json=payload, headers=headers)


async def test_pageview_is_stored_in_background(client: AsyncClient, session_factory) -> None:
    response = await post_view(
        client,
        path="/blog/post/article-one?utm_source=x",
        referrer="https://google.com/search?q=test",
    )

    assert response.status_code == 202
    assert response.content == b""
    views = await stored_views(session_factory)
    assert len(views) == 1
    view = views[0]
    assert view.path == "/blog/post/article-one"  # query string stripped
    assert view.note_slug is None
    assert view.referrer_domain == "google.com"
    assert len(view.visitor_hash) == 64


async def test_pageview_openapi_describes_empty_accepted_response(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    accepted = response.json()["paths"]["/api/v1/stats/pageview"]["post"]["responses"]["202"]
    assert "content" not in accepted


async def test_pageview_visitor_hash_matches_daily_salt_scheme(
    client: AsyncClient, session_factory, client_ip
) -> None:
    await post_view(client)

    views = await stored_views(session_factory)
    daily_salt = hmac.new(b"test-stats-secret", b"2026-02-20", hashlib.sha256).hexdigest()
    expected = hashlib.sha256(f"{daily_salt}{client_ip}{BROWSER_UA}".encode()).hexdigest()
    assert views[0].visitor_hash == expected


@pytest.mark.parametrize("path", ["/notes", "/notes/page/2"])
async def test_pageview_note_anchor_goes_to_note_slug(
    client: AsyncClient, session_factory, path
) -> None:
    response = await post_view(client, path=f"{path}?utm_source=x#note-note-one")

    assert response.status_code == 202
    views = await stored_views(session_factory)
    assert views[0].path == path
    assert views[0].note_slug == "note-one"


@pytest.mark.parametrize("path", ["/notes", "/notes/page/2"])
@pytest.mark.parametrize("slug_length", [200, 201])
async def test_note_slug_length_boundary_keeps_pageview(
    client: AsyncClient, session_factory, path, slug_length
) -> None:
    slug = "a" * slug_length
    response = await post_view(client, path=f"{path}#note-{slug}")

    assert response.status_code == 202
    views = await stored_views(session_factory)
    assert len(views) == 1
    assert views[0].path == path
    assert views[0].note_slug == (slug if slug_length == 200 else None)


async def test_pageview_outside_whitelist_accepted_but_not_stored(
    client: AsyncClient, session_factory
) -> None:
    response = await post_view(client, path="/admin/secret")

    assert response.status_code == 202
    assert await stored_views(session_factory) == []


async def test_pageview_from_bot_is_not_stored(
    client: AsyncClient, session_factory
) -> None:
    response = await client.post(
        "/api/v1/stats/pageview",
        json={"path": "/"},
        headers={"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"},
    )

    assert response.status_code == 202
    assert await stored_views(session_factory) == []


async def test_pageview_invalid_referrer_is_stored_as_null(
    client: AsyncClient, session_factory
) -> None:
    await post_view(client, referrer="not a url")

    views = await stored_views(session_factory)
    assert views[0].referrer_domain is None


async def test_pageview_requires_json_body(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/stats/pageview",
        content=b'{"path": "/"}',
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 422


async def test_pageview_missing_path_is_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/stats/pageview",
        json={"referrer": "https://google.com/"},
    )

    assert response.status_code == 422


async def test_pageview_rate_limit(client: AsyncClient) -> None:
    # The test environment configures STATS_PAGEVIEW_RATE_LIMIT=3/minute.
    codes = [await post_view(client) for _ in range(4)]

    assert [response.status_code for response in codes] == [202, 202, 202, 429]
    assert codes[-1].json() == {"detail": "Rate limit exceeded"}


async def test_invalid_real_ip_falls_back_to_peer_for_limit_and_hash(
    client: AsyncClient, session_factory
) -> None:
    responses = [
        await post_view(client, headers={
            "X-Forwarded-For": f"203.0.113.{number}",
            "X-Real-IP": f"invalid-{number}",
        })
        for number in range(1, 5)
    ]

    assert [response.status_code for response in responses] == [202, 202, 202, 429]
    views = await stored_views(session_factory)
    assert len(views) == 3
    assert len({view.visitor_hash for view in views}) == 1


@pytest.mark.parametrize("client_ip", ["10.0.0.2"], indirect=True)
async def test_nginx_real_ip_is_used_for_limit_and_hash(
    client: AsyncClient, session_factory
) -> None:
    real_client = "198.51.100.8"
    responses = [
        await post_view(client, headers={
            "X-Real-IP": real_client,
            "X-Forwarded-For": f"203.0.113.{number}",
        })
        for number in range(1, 5)
    ]

    assert [response.status_code for response in responses] == [202, 202, 202, 429]
    daily_salt = hmac.new(b"test-stats-secret", b"2026-02-20", hashlib.sha256).hexdigest()
    expected = hashlib.sha256(f"{daily_salt}{real_client}{BROWSER_UA}".encode()).hexdigest()
    views = await stored_views(session_factory)
    assert len(views) == 3
    assert {view.visitor_hash for view in views} == {expected}


@pytest.mark.parametrize("client_ip", ["10.0.0.2"], indirect=True)
async def test_visitors_behind_nginx_have_separate_limits_and_hashes(
    client: AsyncClient, session_factory
) -> None:
    real_clients = ("198.51.100.8", "198.51.100.9")
    for real_client in real_clients:
        responses = [
            await post_view(client, headers={"X-Real-IP": real_client})
            for _ in range(4)
        ]
        assert [response.status_code for response in responses] == [202, 202, 202, 429]

    daily_salt = hmac.new(b"test-stats-secret", b"2026-02-20", hashlib.sha256).hexdigest()
    expected = {
        hashlib.sha256(f"{daily_salt}{real_client}{BROWSER_UA}".encode()).hexdigest()
        for real_client in real_clients
    }
    views = await stored_views(session_factory)
    assert len(views) == 6
    assert {view.visitor_hash for view in views} == expected
