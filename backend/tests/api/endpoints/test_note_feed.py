"""Cursor feed remains stable when new notes arrive between older page reads."""

import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from src.db.models import ContentItem
from src.repositories.content_items import ContentItemRepository
from src.services.content_fields import ContentFields, build_item_values
from tests.api.endpoints.test_admin import ORIGIN, admin_config as admin_config, login

NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)


async def note(session, slug, instant, *, draft=False):
    values = build_item_values("note", slug, ContentFields(
        title=f"Заметка {slug}", status="draft" if draft else "active",
        content_markdown="Текст заметки.", published_at=instant.date(),
    ), 200)
    values.update(published_at_time=instant, source_name="Точный источник", source_url="https://example.org/original")
    return await ContentItemRepository(session).create(values)


async def test_keyset_before_and_after_handle_ties_concurrent_insert_and_drafts(client, db_session):
    first = await note(db_session, "feed-first", NOW)
    second = await note(db_session, "feed-second", NOW)
    third = await note(db_session, "feed-third", NOW)
    await note(db_session, "feed-draft", NOW + timedelta(days=1), draft=True)
    response = await client.get("/api/v1/notes/feed?limit=2")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    page = response.json()
    assert set(page) == {"items", "has_more", "next_cursor", "newest_cursor"}
    assert [entry["slug"] for entry in page["items"]] == [third.slug, second.slug]
    assert page["items"][0]["source_name"] == "Точный источник"
    assert page["items"][0]["source_url"] == "https://example.org/original"
    assert page["items"][0]["published_at_time"] == "2026-10-15T12:00:00Z"
    assert page["has_more"] is True and page["next_cursor"] and page["newest_cursor"]
    fourth = await note(db_session, "feed-fourth", NOW + timedelta(seconds=1))
    older = (await client.get("/api/v1/notes/feed", params={"limit": 2, "before": page["next_cursor"]})).json()
    assert older["items"][0]["slug"] == first.slug
    assert not {third.slug, second.slug, fourth.slug} & {entry["slug"] for entry in older["items"]}
    fresh = (await client.get("/api/v1/notes/feed", params={"after": page["newest_cursor"]})).json()
    assert [entry["slug"] for entry in fresh["items"]] == [fourth.slug]
    assert fresh["has_more"] is False and fresh["next_cursor"] is None
    no_change = (await client.get("/api/v1/notes/feed", params={"after": fresh["newest_cursor"]})).json()
    assert no_change == {"items": [], "has_more": False, "next_cursor": None, "newest_cursor": None}


async def test_feed_historical_fallback_and_archive_latest_have_same_stable_order(client):
    live = (await client.get("/api/v1/notes/feed")).json()
    archive = (await client.get("/api/v1/notes")).json()
    latest = (await client.get("/api/v1/notes/latest?limit=3")).json()
    assert [entry["slug"] for entry in live["items"]] == [entry["slug"] for entry in archive["items"]]
    assert [entry["slug"] for entry in latest] == [entry["slug"] for entry in live["items"]]
    assert live["items"][0]["published_at_time"] is None
    assert live["items"][0]["source_name"] is None and live["items"][0]["source_url"] is None
    last_cursor = live["newest_cursor"]
    assert (await client.get("/api/v1/notes/feed", params={"before": last_cursor})).status_code == 200


async def test_editing_legacy_published_note_preserves_cursor_and_does_not_look_new(client, db_session):
    await login(client)
    legacy = await db_session.scalar(select(ContentItem).where(ContentItem.type == "note", ContentItem.slug == "note-one"))
    assert legacy.published_at_time is None
    initial = (await client.get("/api/v1/notes/feed")).json()
    original_time = next(entry["published_at_time"] for entry in initial["items"] if entry["slug"] == legacy.slug)
    response = await client.patch(f"/api/admin/content/{legacy.id}", json={"title": "Уточнён старый заголовок"}, headers=ORIGIN)
    assert response.status_code == 200
    current = (await client.get("/api/v1/notes/feed")).json()
    assert [entry["slug"] for entry in current["items"]] == [entry["slug"] for entry in initial["items"]]
    assert current["newest_cursor"] == initial["newest_cursor"]
    assert next(entry["published_at_time"] for entry in current["items"] if entry["slug"] == legacy.slug) == original_time
    await db_session.refresh(legacy)
    assert legacy.published_at_time is None
    assert (await client.get("/api/v1/notes/feed", params={"after": initial["newest_cursor"]})).json()["items"] == []


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 51}, {"before": ""}, {"before": "broken"},
    {"before": "a", "after": "b"}, {"before": "WzEsIiIsMV0"},
    {"before": "WzEsIjIwMjYtMTAtMTVUMTI6MDA6MDAiLDFd"},
])
async def test_feed_invalid_parameters_are_422(client, params):
    assert (await client.get("/api/v1/notes/feed", params=params)).status_code == 422


@pytest.mark.parametrize("data", [
    [1, "0001-01-01T00:00:00+14:00", 1],
    [1, "2026-10-15T12:00:00+00:00", 10**50],
    [True, "2026-10-15T12:00:00+00:00", 1],
])
async def test_feed_rejects_cursor_overflows_and_non_integer_version(client, data):
    cursor = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    assert (await client.get("/api/v1/notes/feed", params={"before": cursor})).status_code == 422
