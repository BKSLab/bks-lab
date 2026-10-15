"""Persistent per-source calendars, metadata synchronization and pause boundaries."""

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from src.db.models import NewsItem, NewsJob, NewsSource
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_settings import NewsSettingsRepository
from src.repositories.news_sources import NewsSourceRepository
from tests.news_helpers import collected

DAILY = {"mode": "daily", "times": ["08:00", "20:00"]}


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def profile(identity="verified-source", **changes) -> dict:
    return {
        "profile_id": identity, "slug": identity, "name": "Verified source",
        "description": "A checked source", "url": f"https://{identity}.example/feed",
        "kind": "rss", "config": {}, "priority": 50, "trust_score": 70,
        "vendor_affiliated": False, "schedule": DAILY,
        **changes,
    }


async def enabled_source(session, *, schedule=None):
    repository = NewsSourceRepository(session)
    row = (await repository.synchronize_profiles([profile()]))[0]
    return await repository.update_preferences(
        row.id, {"active": True, "schedule": schedule or DAILY}, now=utc("2026-10-10T00:00:00"),
    )


async def test_profile_sync_attaches_exact_url_and_preserves_preferences_and_history(db_session):
    repository = NewsSourceRepository(db_session)
    old = await repository.create({
        "name": "Old display name", "url": profile()["url"], "kind": "rss", "config": {},
        "active": True, "schedule": {"mode": "weekly", "times": ["11:00"], "weekdays": [0]},
    })
    source_id, slug = old.id, old.slug
    await NewsItemRepository(db_session).ingest(source_id, [collected()], {"page": 7}, etag="saved")
    first = (await repository.synchronize_profiles([profile()]))[0]
    next_check = first.next_check_at
    assert (first.id, first.slug, first.active) == (source_id, slug, True)
    assert first.schedule == {"mode": "weekly", "times": ["11:00"], "weekdays": [0]}
    assert first.cursor == {"page": 7} and first.etag == "saved"
    assert first.profile_id == profile()["profile_id"] and first.name == "Verified source"
    assert await db_session.scalar(select(func.count()).select_from(NewsItem)) == 1

    second = (await repository.synchronize_profiles([profile(description="Updated checked notes", schedule=DAILY)]))[0]
    assert second.next_check_at == next_check
    assert second.description == "Updated checked notes"
    assert second.schedule == first.schedule
    assert await db_session.scalar(select(func.count()).select_from(NewsSource)) == 1


async def test_profile_sync_new_sources_are_paused_and_retired_sources_keep_history(db_session):
    repository = NewsSourceRepository(db_session)
    sources = await repository.synchronize_profiles([profile(), profile("second-source")])
    assert all(not row.active and row.next_check_at is None for row in sources)
    await repository.update_preferences(sources[0].id, {"active": True})
    item_id = (await NewsItemRepository(db_session).ingest(sources[0].id, [collected()], {}))["item_ids"][0]

    await repository.synchronize_profiles([profile("second-source")])
    retired = await repository.get(sources[0].id)
    assert retired.profile_id is None and retired.active is True and retired.next_check_at is None
    assert [row.profile_id for row in await repository.list()] == ["second-source"]
    assert await db_session.get(NewsItem, item_id) is not None


async def test_profile_parser_changes_reset_conditional_state_without_moving_import_boundary(db_session):
    repository = NewsSourceRepository(db_session)
    source = (await repository.synchronize_profiles([profile()]))[0]
    last_success = utc("2026-10-12T04:00:00")
    await repository.update(source.id, {
        "cursor": {"initial_cutoff_at": "2026-09-12T04:00:00+00:00", "collection_version": "old", "profile_version": "old"},
        "etag": "old-etag", "last_modified": "old-date", "last_success_at": last_success,
    })

    updated = (await repository.synchronize_profiles([profile(url="https://verified-source.example/new-feed")]))[0]

    assert updated.etag is None and updated.last_modified is None
    assert updated.cursor == {"initial_cutoff_at": "2026-09-12T04:00:00+00:00"}
    assert updated.last_success_at == last_success


async def test_two_schedulers_and_restart_queue_one_latest_due_source_start(session_factory):
    async with session_factory() as session:
        source = await enabled_source(session)
    now = utc("2026-10-15T05:00:00")

    async def tick():
        async with session_factory() as session:
            return await NewsJobRepository(session).enqueue_due_sources(now=now)

    results = await asyncio.gather(tick(), tick())
    assert sum(len(rows) for rows in results) == 1
    assert await tick() == []
    async with session_factory() as session:
        jobs = list(await session.scalars(select(NewsJob)))
        assert len(jobs) == 1 and jobs[0].source_id == source.id
        assert jobs[0].dedupe_key == f"scheduled:{source.id}:2026-10-15T04:00:00+00:00"
        assert jobs[0].payload["source_schedule"] == DAILY
        assert (await NewsSourceRepository(session).get(source.id)).next_check_at == utc("2026-10-15T16:00:00")


@pytest.mark.parametrize(("schedule", "now", "slot", "next_start"), [
    ({"mode": "weekly", "times": ["08:00"], "weekdays": [0, 3]}, "2026-10-15T05:00:00", "2026-10-15T04:00:00+00:00", "2026-10-19T04:00:00"),
    ({"mode": "interval_days", "times": ["08:00"], "every_days": 3, "start_date": "2026-10-10"}, "2026-10-16T05:00:00", "2026-10-16T04:00:00+00:00", "2026-10-19T04:00:00"),
])
async def test_due_source_uses_its_own_weekly_or_interval_calendar(db_session, schedule, now, slot, next_start):
    source = await enabled_source(db_session, schedule=schedule)
    jobs = await NewsJobRepository(db_session).enqueue_due_sources(now=utc(now))
    assert len(jobs) == 1 and jobs[0].payload["scheduled_slot"] == slot
    assert source.next_check_at == utc(next_start)


async def test_source_pause_and_calendar_edits_cancel_queued_starts_without_replaying(db_session):
    source = await enabled_source(db_session)
    jobs = NewsJobRepository(db_session)
    automatic = (await jobs.enqueue_due_sources(now=utc("2026-10-15T05:00:00")))[0]
    manual = await jobs.enqueue("collect", source_id=source.id)
    repository = NewsSourceRepository(db_session)
    await repository.update_preferences(source.id, {"active": False}, now=utc("2026-10-15T05:01:00"))
    assert automatic.status == "cancelled" and manual.status == "queued"
    assert source.next_check_at is None
    await repository.update_preferences(source.id, {"active": True}, now=utc("2026-10-15T05:02:00"))
    assert await jobs.enqueue_due_sources(now=utc("2026-10-15T05:03:00")) == []
    await repository.update_preferences(
        source.id, {"schedule": {"mode": "daily", "times": ["09:00"]}}, now=utc("2026-10-15T06:00:00"),
    )
    assert source.next_check_at == utc("2026-10-16T05:00:00")
    assert await jobs.enqueue_due_sources(now=utc("2026-10-15T17:00:00")) == []


async def test_global_pause_cancels_queued_starts_and_resume_starts_in_the_future(db_session):
    source = await enabled_source(db_session)
    jobs = NewsJobRepository(db_session)
    automatic = (await jobs.enqueue_due_sources(now=utc("2026-10-15T05:00:00")))[0]
    settings = NewsSettingsRepository(db_session)
    await settings.set({"enabled": False}, now=utc("2026-10-15T05:01:00"))
    assert automatic.status == "cancelled"
    assert await jobs.enqueue_due_sources(now=utc("2026-10-17T17:00:00")) == []
    await settings.set({"enabled": True}, now=utc("2026-10-20T05:00:00"))
    assert source.next_check_at == utc("2026-10-20T16:00:00")
    assert await jobs.enqueue_due_sources(now=utc("2026-10-20T05:00:00")) == []


async def test_catchup_coalesces_old_queued_starts_and_does_not_change_manual_work(db_session):
    source = await enabled_source(db_session)
    jobs = NewsJobRepository(db_session)
    old = (await jobs.enqueue_due_sources(now=utc("2026-10-15T05:00:00")))[0]
    manual = await jobs.enqueue("collect", source_id=source.id)
    latest = await jobs.enqueue_due_sources(now=utc("2026-10-20T17:00:00"))
    assert len(latest) == 1 and latest[0].payload["scheduled_slot"] == "2026-10-20T16:00:00+00:00"
    assert old.status == "cancelled" and manual.status == "queued"


async def test_claim_discards_stale_source_schedule_snapshot(db_session):
    source = await enabled_source(db_session)
    jobs = NewsJobRepository(db_session)
    stale = await jobs.enqueue(
        "collect", source_id=source.id,
        payload={"scheduled_slot": utc("2026-10-15T04:00:00").isoformat(), "source_schedule": {"mode": "daily", "times": ["09:00"]}},
    )
    assert await jobs.claim("owner", 120, 3, kinds=["collect"]) is None
    assert stale.status == "cancelled"
