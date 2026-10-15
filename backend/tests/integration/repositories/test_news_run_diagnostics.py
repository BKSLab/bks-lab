"""Real PostgreSQL stable addresses and historical observation reports."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import delete

from src.core.news_slugs import job_slug_base, readable_slug
from src.db.models import NewsJob, NewsRunItem
from src.repositories.news_analyses import NewsAnalysisRepository
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_runs import NewsRunRepository
from src.repositories.news_sources import NewsSourceRepository
from tests.news_helpers import add_source, analysis_data, collected


def test_readable_slugs_transliterate_and_use_samara_calendar():
    assert readable_slug("Исследования ИИ / BKS Lab") == "issledovaniya-ii-bks-lab"
    assert readable_slug("École 日本語") == "ecole"
    assert readable_slug("日本語") == "source"
    assert readable_slug("123") == "source-123"
    assert readable_slug("***") == "source"
    now = datetime(2026, 10, 14, 22, 4, 5, tzinfo=timezone.utc)
    assert job_slug_base("collect", "all-sources", created_at=now) == "all-sources-2026-10-15-020405"
    assert job_slug_base("discover", "example-org", created_at=now) == "discover-example-org-2026-10-15-020405"


async def test_source_slug_is_stable_after_rename_and_concurrent_duplicates_are_unique(session_factory):
    async def create():
        async with session_factory() as session:
            return await add_source(session, name="Исследования ИИ")

    first, second = await asyncio.gather(create(), create())
    assert {first.slug, second.slug} == {"issledovaniya-ii", "issledovaniya-ii-2"}
    async with session_factory() as session:
        sources = NewsSourceRepository(session)
        changed = await sources.update(first.id, {"name": "New display name"})
        assert changed.slug == first.slug
        assert (await sources.get_by_slug(first.slug)).name == "New display name"
        assert await sources.get_by_slug(str(first.id)) is None


async def test_concurrent_same_second_job_addresses_and_other_enqueue_paths(session_factory, monkeypatch):
    now = datetime(2026, 10, 14, 22, 4, 5, tzinfo=timezone.utc)
    monkeypatch.setattr("src.repositories.news_jobs.job_slug_base", lambda kind, scope, **kwargs: job_slug_base(kind, scope, created_at=now))
    async with session_factory() as session:
        source = await add_source(session, name="Источник ИИ")

    async def enqueue():
        async with session_factory() as session:
            return await NewsJobRepository(session).enqueue("collect", source_id=source.id)

    first, second = await asyncio.gather(enqueue(), enqueue())
    base = "istochnik-ii-2026-10-15-020405"
    assert {first.slug, second.slug} == {base, f"{base}-2"}
    async with session_factory() as session:
        jobs = NewsJobRepository(session)
        scheduled = await jobs.enqueue_scheduled("2026-10-15:08:00")
        assert scheduled.slug == "all-sources-2026-10-15-020405"
        assert await jobs.enqueue_scheduled("2026-10-15:08:00") is None
        repair = await jobs.enqueue_repair(source.id, [7, 8, 9], batch_size=2)
        assert len(repair) == len({job.slug for job in repair}) == 2
        assert [job.slug for job in await jobs.enqueue_repair(source.id, [7, 8, 9], batch_size=2)] == [job.slug for job in repair]
        preview = await jobs.enqueue("discover", payload={"url": "https://example.org/feed"})
        assert preview.slug == "discover-example-org-2026-10-15-020405"


async def test_long_analysis_slugs_keep_full_timestamp_after_collision(db_session, monkeypatch):
    now = datetime(2026, 10, 14, 22, 4, 5, tzinfo=timezone.utc)
    monkeypatch.setattr("src.repositories.news_jobs.job_slug_base", lambda kind, scope, **kwargs: job_slug_base(kind, scope, created_at=now))
    source = await add_source(db_session, name="Long source " * 16)
    material = collected(title="Long material title " * 60)
    item_id = (await NewsItemRepository(db_session).ingest(source.id, [material], {}))["item_ids"][0]
    jobs = NewsJobRepository(db_session)
    first = await jobs.enqueue("analyze", item_id=item_id)
    second = await jobs.enqueue("analyze", item_id=item_id)
    assert len(first.slug) <= 240 and len(second.slug) <= 240
    assert first.slug.endswith("2026-10-15-020405")
    assert second.slug.endswith("2026-10-15-020405-2")


async def test_report_snapshots_survive_edits_and_analysis_matches_exact_observed_version(db_session):
    source = await add_source(db_session)
    source_id, original_slug = source.id, source.slug
    jobs, runs = NewsJobRepository(db_session), NewsRunRepository(db_session)
    collect_job = await jobs.enqueue("collect", source_id=source_id)
    run = await runs.begin(source_id, collect_job.id, parameters={"initial_lookback_days": 7})
    items = NewsItemRepository(db_session)
    original = collected()
    item_id = (await items.ingest(source_id, [original], {}))["item_ids"][0]
    observation = NewsRunItem(run_id=run.id, item_id=item_id, title=original["title"], url=original["url"], content_hash=original["content_hash"], outcome="new", warning="Article fetch failed.", preserved_previous=True)
    skipped = NewsRunItem(run_id=run.id, title="Old post", url="https://example.org/old", outcome="skipped", reason="Outside the time window.", stage="listing")
    db_session.add_all([observation, skipped])
    await db_session.commit()
    await NewsAnalysisRepository(db_session).save(item_id, original["content_hash"], "model", "v1", analysis_data())
    await items.ingest(source_id, [collected(content="Updated source version with changed detail. " * 20)], {})
    current = await items.get(item_id)
    newer_job = await jobs.enqueue("analyze", item_id=item_id, payload={"content_hash": current.content_hash})
    await NewsSourceRepository(db_session).update(source_id, {"name": "Renamed", "url": "https://example.org/new-feed"})
    await runs.finish(run.id, "completed", new_count=1, skipped_count=1, warning_count=1, http_status=200, limit_reached=True)

    page, total = await runs.list_page(1, 20, job_id=collect_job.id)
    assert total == 1 and page[0].source_name == "Example"
    assert page[0].source_slug == original_slug and page[0].source_url == "https://example.org/feed.xml"
    assert page[0].parameters == {"initial_lookback_days": 7}
    assert page[0].skipped_count == page[0].warning_count == 1
    rows, total = await runs.list_items(collect_job.id, page=1, page_size=20)
    assert total == 2
    first, analysis_job, analyzed = rows[0]
    assert first.title == original["title"] and first.content_hash == original["content_hash"]
    assert analysis_job is None and analyzed is True
    exact_job = await jobs.enqueue("analyze", item_id=item_id, payload={"content_hash": original["content_hash"]})
    rows, _ = await runs.list_items(collect_job.id, page=1, page_size=20, warnings_only=True, source_slug=original_slug)
    assert len(rows) == 1 and rows[0][1].id == exact_job.id != newer_job.id
    assert (await runs.list_items(collect_job.id, page=1, page_size=20, outcome="skipped"))[1] == 1
    assert (await runs.list_items(collect_job.id, page=2, page_size=1))[0][0][0].outcome == "skipped"
    await db_session.execute(delete(NewsJob).where(NewsJob.id == exact_job.id))
    await db_session.commit()
    rows, _ = await runs.list_items(collect_job.id, page=1, page_size=20, warnings_only=True)
    assert rows[0][1] is None and rows[0][2] is True
