"""Unit tests for StatsService: whitelist, normalization, hashing, bots."""

from datetime import datetime, timezone

import pytest

from src.services.stats import StatsService

FIXED_NOW = datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc)
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"


def make_service(utc_now=lambda: FIXED_NOW) -> StatsService:
    return StatsService(
        session_factory=None,  # not used by prepare_page_view
        stats_secret="test-secret",
        utc_now=utc_now,
        referrer_domain_max_length=255,
    )


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/blog",
        "/blog/development",
        "/blog/post/1c-async",
        "/blog/page/2",
        "/blog/development/page/2",
        "/blog/ai/page/3",
        "/notes",
        "/notes/page/3",
        "/projects",
        "/projects/work-for-everyone",
        "/about",
        "/contacts",
        "/privacy",
    ],
)
def test_prepare_page_view_accepts_whitelisted_paths(path: str) -> None:
    view = make_service().prepare_page_view(
        path=path, referrer=None, ip="1.2.3.4", user_agent=BROWSER_UA
    )

    assert view is not None
    assert view.path == path


@pytest.mark.parametrize(
    "path",
    [
        "/admin",
        "/api/v1/articles",
        "/bloggy",
        "/blog/../etc",
        "/blog/../page/2",
        "/blog/development/page/no",
        "/notes/topic/page/2",
        "/notes/anything",
        "/projects/",
        "blog",
        "",
    ],
)
def test_prepare_page_view_rejects_paths_outside_whitelist(path: str) -> None:
    view = make_service().prepare_page_view(
        path=path, referrer=None, ip="1.2.3.4", user_agent=BROWSER_UA
    )

    assert view is None


def test_prepare_page_view_strips_query_string() -> None:
    view = make_service().prepare_page_view(
        path="/blog?utm_source=x&page=2", referrer=None, ip="1.2.3.4", user_agent=BROWSER_UA
    )

    assert view is not None
    assert view.path == "/blog"
    assert view.note_slug is None


@pytest.mark.parametrize("path", ["/notes", "/notes/page/2"])
def test_prepare_page_view_extracts_note_anchor(path: str) -> None:
    view = make_service().prepare_page_view(
        path=f"{path}?utm_source=x#note-small-team-deploys",
        referrer=None,
        ip="1.2.3.4",
        user_agent=BROWSER_UA,
    )

    assert view is not None
    assert view.path == path
    assert view.note_slug == "small-team-deploys"


def test_prepare_page_view_ignores_anchor_outside_notes_feed() -> None:
    view = make_service().prepare_page_view(
        path="/blog#note-small-team-deploys", referrer=None, ip="1.2.3.4", user_agent=BROWSER_UA
    )

    assert view is not None
    assert view.note_slug is None


def test_prepare_page_view_keeps_only_referrer_domain() -> None:
    view = make_service().prepare_page_view(
        path="/",
        referrer="https://Google.com/search?q=test",
        ip="1.2.3.4",
        user_agent=BROWSER_UA,
    )

    assert view is not None
    assert view.referrer_domain == "google.com"


@pytest.mark.parametrize("referrer", ["not a url", "ftp://host/path", "just-text"])
def test_prepare_page_view_invalid_referrer_becomes_none(referrer: str) -> None:
    view = make_service().prepare_page_view(
        path="/", referrer=referrer, ip="1.2.3.4", user_agent=BROWSER_UA
    )

    assert view is not None
    assert view.referrer_domain is None


@pytest.mark.parametrize(
    "user_agent",
    [
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "YandexBot/3.0",
        "curl/8.0.1",
        "HeadlessChrome/120.0",
        "python-requests/2.31.0",
    ],
)
def test_prepare_page_view_skips_known_bots(user_agent: str) -> None:
    view = make_service().prepare_page_view(
        path="/", referrer=None, ip="1.2.3.4", user_agent=user_agent
    )

    assert view is None


def test_visitor_hash_is_deterministic_within_a_day() -> None:
    service = make_service()

    first = service.prepare_page_view(path="/", referrer=None, ip="1.2.3.4", user_agent=BROWSER_UA)
    second = service.prepare_page_view(path="/", referrer=None, ip="1.2.3.4", user_agent=BROWSER_UA)

    assert first is not None and second is not None
    assert first.visitor_hash == second.visitor_hash
    assert len(first.visitor_hash) == 64


def test_visitor_hash_differs_by_ip_and_rotates_daily() -> None:
    service = make_service()
    other_ip = service.prepare_page_view(
        path="/", referrer=None, ip="5.6.7.8", user_agent=BROWSER_UA
    )
    base = service.prepare_page_view(path="/", referrer=None, ip="1.2.3.4", user_agent=BROWSER_UA)

    next_day = make_service(
        utc_now=lambda: datetime(2026, 2, 21, 0, 0, 1, tzinfo=timezone.utc)
    )
    rotated = next_day.prepare_page_view(
        path="/", referrer=None, ip="1.2.3.4", user_agent=BROWSER_UA
    )

    assert base is not None and other_ip is not None and rotated is not None
    assert base.visitor_hash != other_ip.visitor_hash
    assert base.visitor_hash != rotated.visitor_hash
