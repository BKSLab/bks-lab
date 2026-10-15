"""Protected automatic-note administration contracts and validation."""

import pytest

from src.schemas.news_notes import NoteSettingsPatch
from tests.api.endpoints.test_admin import ORIGIN, admin_config as admin_config, login
from tests.integration.test_news_notes import NOW, candidate, service


@pytest.mark.parametrize("method,path", [
    ("GET", "/note-settings"), ("PATCH", "/note-settings"),
    ("GET", "/note-queue"), ("PATCH", "/note-queue/missing-note"),
])
async def test_note_admin_requires_authentication_and_origin_and_no_store(client, method, path):
    response = await client.request(method, "/api/admin/news" + path, headers=ORIGIN)
    assert response.status_code == 401 and response.headers["cache-control"] == "no-store"
    await login(client)
    if method == "PATCH":
        for headers in ({}, {"Origin": "https://untrusted.example"}):
            response = await client.request(method, "/api/admin/news" + path, json={}, headers=headers)
            assert response.status_code == 403 and response.headers["cache-control"] == "no-store"


async def test_settings_contract_defaults_and_first_activation_survives_resume(client):
    await login(client)
    defaults = (await client.get("/api/admin/news/note-settings")).json()
    assert defaults == {
        "enabled": False, "interval_minutes": 10, "max_age_hours": 72, "started_at": None,
        "last_published_at": None, "next_publish_at": None,
        "queued": 0, "published": 0, "excluded": 0, "expired": 0,
    }
    first = await client.patch("/api/admin/news/note-settings", headers=ORIGIN, json={"enabled": True, "interval_minutes": 10})
    assert first.status_code == 200 and first.headers["cache-control"] == "no-store"
    start = first.json()["started_at"]
    assert start is not None and first.json()["next_publish_at"] is not None
    paused = await client.patch("/api/admin/news/note-settings", headers=ORIGIN, json={"enabled": False})
    assert paused.json()["started_at"] == start and paused.json()["next_publish_at"] is None
    resumed = await client.patch("/api/admin/news/note-settings", headers=ORIGIN, json={"enabled": True})
    assert resumed.json()["started_at"] == start


@pytest.mark.parametrize("body", [
    {"interval_minutes": 9}, {"interval_minutes": 1441}, {"interval_minutes": 10.5},
    {"max_age_hours": 0}, {"max_age_hours": 721}, {"enabled": "yes"},
    {"enabled": None}, {"started_at": "2020-01-01T00:00:00Z"},
])
async def test_settings_reject_invalid_or_server_owned_fields(client, body):
    await login(client)
    assert (await client.patch("/api/admin/news/note-settings", headers=ORIGIN, json=body)).status_code == 422


async def test_queue_contract_bounded_editor_edits_exclude_requeue_and_published_lock(client, db_session):
    await login(client)
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    row, *_ = await candidate(db_session, clock, notes=notes)
    path = "/api/admin/news/note-queue/" + row.note_slug
    queued = await client.get("/api/admin/news/note-queue")
    assert queued.status_code == 200 and queued.json()["total"] == 1
    item = queued.json()["items"][0]
    assert set(item) == {"note_slug", "content_id", "title", "text", "source_name", "source_url", "status", "created_at", "published_at_time", "reason"}
    assert item["source_url"] == "https://example.org/material-1" and item["published_at_time"] is None
    for body in ({"title": "я" * 91}, {"text": "я" * 301}, {"status": "published"}, {"source_url": "https://fake.example"}, {"text": None}):
        assert (await client.patch(path, headers=ORIGIN, json=body)).status_code == 422
    edited = await client.patch(path, headers=ORIGIN, json={"title": "Заголовок редактора", "text": "Текст редактора.", "status": "excluded"})
    assert edited.status_code == 200 and edited.json()["status"] == "excluded"
    assert (await client.get("/api/admin/news/note-queue?status=excluded")).json()["total"] == 1
    restored = await client.patch(path, headers=ORIGIN, json={"status": "queued"})
    assert restored.status_code == 200 and restored.json()["title"] == "Заголовок редактора"
    assert await notes.publish_due() == row.note_slug
    assert (await client.patch(path, headers=ORIGIN, json={"title": "Новая правка"})).status_code == 409
    published = (await client.get("/api/admin/news/note-queue?status=published")).json()
    assert published["total"] == 1 and published["items"][0]["published_at_time"] is not None
