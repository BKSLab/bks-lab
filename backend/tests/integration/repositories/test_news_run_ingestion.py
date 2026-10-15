"""Collection reports commit with materials and retain the observed version."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update

from src.db.models import NewsJob, NewsRunItem
from src.exceptions.news import NewsConflictError, NewsLeaseLostError
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_runs import NewsRunRepository
from tests.news_helpers import add_source, collected


async def test_reports_preserve_each_ingestion_outcome_and_skipped_candidate(db_session):
    source = await add_source(db_session)
    items, runs = NewsItemRepository(db_session), NewsRunRepository(db_session)
    first = await runs.begin(source.id, None)
    original = collected()
    result = await items.ingest(source.id, [original], {}, run_id=first.id)
    item_id = result["item_ids"][0]
    second = await runs.begin(source.id, None)
    changed = collected(title="Updated title", content="Updated substantial content. " * 20)
    await items.ingest(source.id, [changed], {}, run_id=second.id)
    third = await runs.begin(source.id, None)
    await items.ingest(source.id, [changed], {}, run_id=third.id, skipped=[{
        "title": "An older post", "url": "https://example.org/old",
        "reason": "Материал опубликован раньше начала периода сбора.", "stage": "filter",
    }])

    rows = list(await db_session.scalars(select(NewsRunItem).order_by(NewsRunItem.id)))
    assert [row.outcome for row in rows] == ["new", "updated", "unchanged", "skipped"]
    assert rows[0].title == original["title"]
    assert rows[0].content_hash == original["content_hash"]
    assert rows[1].content_hash == changed["content_hash"]
    assert rows[0].item_id == rows[1].item_id == rows[2].item_id == item_id
    assert rows[3].item_id is None and rows[3].stage == "filter"
    assert rows[3].reason == "Материал опубликован раньше начала периода сбора."
    await db_session.refresh(first)
    await db_session.refresh(second)
    await db_session.refresh(third)
    assert first.status == second.status == third.status == "completed"
    assert first.new_count == second.updated_count == third.unchanged_count == third.skipped_count == 1


async def test_failed_refresh_records_warning_while_preserving_previous_version(db_session):
    source = await add_source(db_session)
    items, runs = NewsItemRepository(db_session), NewsRunRepository(db_session)
    original = collected()
    await items.ingest(source.id, [original], {})
    first = await runs.begin(source.id, None)
    failed = collected(content="")
    failed["metadata_json"] = {
        "collection_status": "fetch_failed", "collection_stage": "fetch",
        "collection_warning": "Источник вернул HTTP 403.",
    }
    await items.ingest(source.id, [failed], {}, run_id=first.id)
    second = await runs.begin(source.id, None)
    await items.ingest(source.id, [original], {}, run_id=second.id)

    rows = list(await db_session.scalars(select(NewsRunItem).order_by(NewsRunItem.id)))
    assert rows[0].outcome == "unchanged"
    assert rows[0].preserved_previous is True
    assert rows[0].warning == "Источник вернул HTTP 403."
    assert rows[0].stage == "fetch"
    assert rows[0].content_hash == original["content_hash"]
    assert rows[1].warning is None and rows[1].preserved_previous is False


async def test_report_rejects_a_run_belonging_to_another_source(db_session):
    source = await add_source(db_session)
    other = await add_source(db_session, name="Other", url="https://other.example/feed")
    run = await NewsRunRepository(db_session).begin(other.id, None)
    with pytest.raises(NewsConflictError):
        await NewsItemRepository(db_session).ingest(source.id, [collected()], {}, run_id=run.id)
    assert await db_session.scalar(select(func.count()).select_from(NewsRunItem)) == 0


async def test_expired_lease_cannot_write_observations_or_materials(db_session):
    source = await add_source(db_session)
    jobs = NewsJobRepository(db_session)
    job = await jobs.enqueue("collect", source_id=source.id)
    await jobs.claim(owner_token="worker", lease_seconds=60, max_attempts=3, kinds=["collect"])
    run = await NewsRunRepository(db_session).begin(source.id, job.id, owner_token="worker")
    await db_session.execute(update(NewsJob).where(NewsJob.id == job.id).values(
        lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    ))
    await db_session.commit()
    with pytest.raises(NewsLeaseLostError):
        await NewsItemRepository(db_session).ingest(
            source.id, [collected()], {}, run_id=run.id, job_id=job.id, owner_token="worker",
        )
    assert await db_session.scalar(select(func.count()).select_from(NewsRunItem)) == 0


async def test_recovery_after_ingest_keeps_completed_report_counters(db_session):
    source = await add_source(db_session)
    jobs = NewsJobRepository(db_session)
    job = await jobs.enqueue("collect", source_id=source.id)
    await jobs.claim(owner_token="worker", lease_seconds=60, max_attempts=3, kinds=["collect"])
    run = await NewsRunRepository(db_session).begin(source.id, job.id, owner_token="worker")
    run_id, job_id, source_id = run.id, job.id, source.id
    await NewsItemRepository(db_session).ingest(
        source_id, [collected()], {}, run_id=run_id, job_id=job_id, owner_token="worker",
        run_diagnostics={"http_status": 200, "warning_count": 0, "limit_reached": True},
    )
    await db_session.execute(update(NewsJob).where(NewsJob.id == job_id).values(
        lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    ))
    await db_session.commit()
    await jobs.recover(3)
    await db_session.refresh(run)
    assert run.status == "completed" and run.new_count == 1
    assert run.http_status == 200 and run.limit_reached is True
    assert await db_session.scalar(select(func.count()).select_from(NewsRunItem).where(NewsRunItem.run_id == run_id)) == 1
