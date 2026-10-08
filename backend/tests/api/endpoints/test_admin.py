"""Real PostgreSQL security and contract checks for every admin entry point."""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.routing import APIRoute
from pydantic import SecretStr
from sqlalchemy import func, select

from main import app
from src.core.settings import get_settings
from src.db.models import AdminSession, PageView, Subscriber
from src.dependencies.admin import require_admin
from src.dependencies.services import get_utc_now

NOW = datetime(2026, 2, 20, 12, tzinfo=timezone.utc)
LOGIN = {"username": "test-admin", "password": "test-only-password"}
ORIGIN = {"Origin": "http://test"}
PROTECTED = [
    "/auth/me", "/overview", "/stats/timeseries", "/stats/pages",
    "/stats/referrers", "/content", "/content/1", "/subscribers",
]


@pytest.fixture(autouse=True)
def admin_config(monkeypatch):
    settings = get_settings().admin
    monkeypatch.setattr(settings, "username", LOGIN["username"])
    monkeypatch.setattr(settings, "password", SecretStr(LOGIN["password"]))
    monkeypatch.setattr(settings, "allowed_origins", ("http://test",))
    monkeypatch.setattr(settings, "cookie_secure", False)


async def login(client):
    response = await client.post("/api/admin/auth/login", json=LOGIN, headers=ORIGIN)
    assert response.status_code == 200
    return response


def test_every_admin_endpoint_depends_on_require_admin():
    def dependency_calls(dependant):
        return {dependant.call}.union(*(dependency_calls(child) for child in dependant.dependencies))

    routes = [route for route in app.routes if isinstance(route, APIRoute) and route.path.startswith("/api/admin/")]
    assert len([route for route in routes if not route.path.startswith("/api/admin/news/")]) == 10
    for route in routes:
        if route.path == "/api/admin/auth/login":
            continue
        assert require_admin in dependency_calls(route.dependant), route.path
        if route.path.startswith("/api/admin/news/"):
            continue
        assert route.methods <= {"GET", "POST"}
        if route.methods == {"POST"}:
            assert route.path == "/api/admin/auth/logout"


@pytest.mark.parametrize("path", PROTECTED)
async def test_every_admin_get_rejects_anonymous_and_disables_cache(client, path):
    response = await client.get(f"/api/admin{path}")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["cache-control"] == "no-store"


async def test_logout_also_requires_a_session(client):
    response = await client.post("/api/admin/auth/logout", headers=ORIGIN)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("data", [
    {"username": "unknown", "password": LOGIN["password"]},
    {"username": LOGIN["username"], "password": "incorrect"},
    {"username": "неверный", "password": "неверный"},
])
async def test_invalid_credentials_have_one_response(client, data):
    response = await client.post("/api/admin/auth/login", json=data, headers=ORIGIN)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
    assert "set-cookie" not in response.headers
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("field", ["username", "password"])
async def test_unconfigured_credentials_fail_closed(client, monkeypatch, field):
    monkeypatch.setattr(get_settings().admin, field, SecretStr("") if field == "password" else "")
    response = await client.post("/api/admin/auth/login", json=LOGIN, headers=ORIGIN)
    assert response.status_code == 401


@pytest.mark.parametrize("origin", [None, "null", "https://evil.example", "http://test/", "http://test.evil.example"])
async def test_login_rejects_untrusted_or_missing_origin_even_with_forged_host(client, origin):
    headers = {"Host": "evil.example"}
    if origin is not None:
        headers["Origin"] = origin
    response = await client.post("/api/admin/auth/login", json=LOGIN, headers=headers)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


async def test_duplicate_origin_and_unconfigured_allowlist_fail_closed(client, monkeypatch):
    response = await client.post("/api/admin/auth/login", json=LOGIN, headers=[("Origin", "http://test"), ("Origin", "http://test")])
    assert response.status_code == 403
    monkeypatch.setattr(get_settings().admin, "allowed_origins", ())
    assert (await client.post("/api/admin/auth/login", json=LOGIN, headers=ORIGIN)).status_code == 403


async def test_five_attempt_rate_limit_cannot_be_bypassed_with_forwarded_headers(client):
    for number in range(6):
        response = await client.post(
            "/api/admin/auth/login", json={**LOGIN, "password": "wrong"},
            headers={**ORIGIN, "X-Forwarded-For": f"198.51.100.{number}"},
        )
        assert response.status_code == (401 if number < 5 else 429)
        assert response.headers["cache-control"] == "no-store"


async def test_cookie_flags_hash_storage_sliding_expiry_and_logout(client, session_factory):
    response = await login(client)
    assert response.json() == {"status": "ok"}
    cookie = response.headers["set-cookie"]
    for attribute in ("HttpOnly", "SameSite=strict", "Path=/", "Max-Age=43200"):
        assert attribute in cookie
    token = response.cookies["admin_session"]
    digest = hashlib.sha256(token.encode()).hexdigest()
    async with session_factory() as session:
        row = await session.get(AdminSession, digest)
        assert row is not None
        assert row.token_hash != token
        assert row.expires_at == NOW + timedelta(hours=12)

    app.dependency_overrides[get_utc_now] = lambda: lambda: NOW + timedelta(hours=1)
    identity = await client.get("/api/admin/auth/me")
    assert identity.json() == {"username": LOGIN["username"]}
    assert "Max-Age=43200" in identity.headers["set-cookie"]
    assert identity.headers["cache-control"] == "no-store"
    async with session_factory() as session:
        assert (await session.get(AdminSession, digest)).expires_at == NOW + timedelta(hours=13)

    assert (await client.post("/api/admin/auth/logout", headers={"Origin": "http://evil.example"})).status_code == 403
    logout = await client.post("/api/admin/auth/logout", headers=ORIGIN)
    assert logout.status_code == 204 and not logout.content
    assert "Max-Age=0" in logout.headers["set-cookie"]
    replay = await client.get("/api/admin/auth/me", headers={"Cookie": f"admin_session={token}"})
    assert replay.status_code == 401


async def test_production_cookie_is_secure(client, monkeypatch):
    monkeypatch.setattr(get_settings().admin, "cookie_secure", True)
    response = await login(client)
    assert "; Secure" in response.headers["set-cookie"]


async def test_login_rotates_and_revokes_previous_browser_session(client, session_factory):
    first = (await login(client)).cookies["admin_session"]
    second = (await login(client)).cookies["admin_session"]
    assert first != second
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(AdminSession)) == 1
    assert (await client.get("/api/admin/auth/me", headers={"Cookie": f"admin_session={first}"})).status_code == 401


@pytest.mark.parametrize("delta", [timedelta(), timedelta(seconds=-1)])
async def test_expired_sessions_are_not_revived(client, session_factory, delta):
    token = "a" * 43
    async with session_factory() as session:
        session.add(AdminSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), username=LOGIN["username"], expires_at=NOW + delta))
        await session.commit()
    response = await client.get("/api/admin/auth/me", headers={"Cookie": f"admin_session={token}"})
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("token", ["short", "a" * 43, "!" * 43, "x" * 1000])
async def test_unknown_and_malformed_tokens_are_rejected(client, token):
    response = await client.get("/api/admin/auth/me", headers={"Cookie": f"admin_session={token}"})
    assert response.status_code == 401


async def test_admin_validation_and_missing_resource_responses_disable_cache(client):
    await login(client)
    for url, code in [("/content?page_size=51", 422), ("/stats/timeseries?period=2d", 422), ("/content/999999", 404), ("/missing", 404)]:
        response = await client.get(f"/api/admin{url}")
        assert response.status_code == code
        assert response.headers["cache-control"] == "no-store"


async def test_content_includes_drafts_filters_and_note_views_on_all_feed_pages(client, session_factory):
    await login(client)
    async with session_factory() as session:
        session.add_all([
            PageView(path="/notes", note_slug="note-one", visitor_hash="a" * 64, viewed_at=NOW),
            PageView(path="/notes/page/2", note_slug="note-one", visitor_hash="b" * 64, viewed_at=NOW),
            PageView(path="/notes", note_slug=None, visitor_hash="b" * 64, viewed_at=NOW),
        ])
        await session.commit()
    drafts = (await client.get("/api/admin/content?status=draft")).json()
    assert drafts["total"] == 3
    assert {item["type"] for item in drafts["items"]} == {"article", "note", "project"}
    notes = (await client.get("/api/admin/content?type=note&q=FIRST")).json()
    assert notes["total"] == 1
    note = notes["items"][0]
    assert note["views_30d"] == 2
    detail = (await client.get(f"/api/admin/content/{note['id']}")).json()
    assert detail["views_30d"] == 2
    assert len(detail["views_timeseries_30d"]) == 30
    assert sum(point["value"] for point in detail["views_timeseries_30d"]) == 2
    assert detail["content_hash"] and detail["synced_at"]
    assert (await client.get("/api/admin/content?q=%25")).json()["total"] == 0
    empty = (await client.get("/api/admin/content?page=999")).json()
    assert not empty["items"] and empty["total"] > 0


async def test_subscriber_pagination_is_stable_and_newest_first(client, session_factory):
    await login(client)
    async with session_factory() as session:
        session.add_all([
            Subscriber(email="old@example.com", subscribed_at=NOW - timedelta(days=1)),
            Subscriber(email="a@example.com", subscribed_at=NOW),
            Subscriber(email="b@example.com", subscribed_at=NOW),
        ])
        await session.commit()
    first = (await client.get("/api/admin/subscribers?page_size=2")).json()
    second = (await client.get("/api/admin/subscribers?page_size=2&page=2")).json()
    assert first["total"] == 3 and first["pages"] == 2
    assert [item["email"] for item in first["items"]] == ["a@example.com", "b@example.com"]
    assert [item["email"] for item in second["items"]] == ["old@example.com"]


async def test_empty_dashboard_returns_complete_zero_series(client):
    await login(client)
    overview = (await client.get("/api/admin/overview")).json()
    assert overview == {"views_today": 0, "views_7d": 0, "views_30d": 0, "uniques_today": 0, "top_pages_30d": [], "top_referrers_30d": []}
    values = (await client.get("/api/admin/stats/timeseries?period=7d&metric=uniques")).json()
    assert len(values) == 7
    assert values[0] == {"date": "2026-02-14", "value": 0}
    assert values[-1] == {"date": "2026-02-20", "value": 0}
    assert (await client.get("/api/admin/stats/pages")).json()["total"] == 0
    assert (await client.get("/api/admin/stats/referrers")).json() == []
