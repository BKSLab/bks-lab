"""Worker acceptance against PostgreSQL, with all external calls isolated."""

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import SecretStr
from sqlalchemy import func, select, update

from src.background_tasks.news_health import is_healthy
from src.background_tasks.news_scheduler import NewsScheduler, latest_scheduled_slot
from src.clients.news_sources import NewsSourceClient
from src.core.news_settings import NewsSettings
from src.db.models.news_items import NewsItem
from src.db.models.news_jobs import NewsJob, NewsSourceRun
from src.exceptions.llm import LlmApiRequestError
from src.repositories.news_analyses import NewsAnalysisRepository
from src.repositories.news_catalog import NewsCatalogRepository
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_runs import NewsRunRepository
from src.repositories.news_settings import NewsSettingsRepository
from src.repositories.news_sources import NewsSourceRepository
from src.schemas.news_collection import CollectedItem, CollectionResult, DiscoveryResult
from src.services.news_analysis import NewsAnalysisService
from src.services.news_pipeline import NewsPipeline, NewsRepositories


@pytest.fixture
def worker_scope(session_factory):
    active = ContextVar("worker_repository_scope", default=False)

    @asynccontextmanager
    async def scope():
        token = active.set(True)
        try:
            async with session_factory() as session:
                yield NewsRepositories(
                    jobs=NewsJobRepository(session), sources=NewsSourceRepository(session),
                    items=NewsItemRepository(session), analyses=NewsAnalysisRepository(session),
                    catalog=NewsCatalogRepository(session), settings=NewsSettingsRepository(session),
                    runs=NewsRunRepository(session),
                )
        finally:
            active.reset(token)
    scope.is_active = active.get
    return scope


@pytest.fixture
def worker_config(tmp_path):
    return NewsSettings(
        _env_file=None, llm_api_key=SecretStr("fixture-key"),
        llm_model="fixture-model", llm_api_url="https://provider.example/v1/chat/completions",
        heartbeat_seconds=0.03, lease_seconds=15, job_retry_delay_seconds=0,
        queue_poll_seconds=0.02, shutdown_grace_seconds=0.02,
        health_file=tmp_path / "news-health",
    )


@pytest.fixture
def collector():
    client = AsyncMock(spec=NewsSourceClient)
    client.fetch.return_value = CollectionResult(
        [CollectedItem(
            external_id="post-1", url="https://source.example/article",
            canonical_url="https://source.example/article", title="A useful material",
            description="Plain source excerpt", content="Collected text survives failed AI calls.",
        )], etag='"version-one"',
    )
    client.discover.return_value = DiscoveryResult("rss", "https://source.example/feed", [])
    return client


@pytest.fixture
def analyzer():
    service = AsyncMock(spec=NewsAnalysisService)
    service.analyze.return_value = {
        "is_relevant": True, "category_id": None, "topic_ids": [], "suggested_topics": [],
        "scores": {"topical_fit": 90, "significance": 80, "freshness": 70, "article_potential": 60},
        "summary_ru": "Краткое описание материала.", "editorial_comment_ru": "Подходит для разбора.",
        "recommended_formats": ["longread_candidate"], "confidence": 0.8,
        "needs_verification": True, "news_score": 80, "article_score": 75,
    }
    return service


@pytest.fixture
def pipeline(worker_scope, worker_config, collector, analyzer):
    return NewsPipeline(
        repositories=worker_scope, collector=collector, analyzer=analyzer,
        config=worker_config, utc_now=lambda: datetime.now(timezone.utc),
    )


async def add_source(scope):
    async with scope() as repositories:
        return await repositories.sources.create({
            "name": "Fixture source", "url": "https://source.example/feed", "kind": "rss",
            "config": {}, "interval_hours": 1, "topic_ids": [], "category_ids": [],
        })


async def enqueue_collect(scope, source_id):
    async with scope() as repositories:
        return await repositories.jobs.enqueue("collect", source_id=source_id)


@pytest.mark.asyncio
async def test_collection_commits_before_failed_analysis_and_retry_limit(
    worker_scope, worker_config, pipeline, collector, analyzer, session_factory,
):
    source = await add_source(worker_scope)
    collect_job = await enqueue_collect(worker_scope, source.id)
    collected = collector.fetch.return_value

    async def fetch_without_database_session(**kwargs):
        assert not worker_scope.is_active()
        return collected

    collector.fetch.side_effect = fetch_without_database_session
    analyzer.analyze.side_effect = LlmApiRequestError("fixture failure")

    assert await pipeline.run_once(("collect",))
    async with worker_scope() as repositories:
        finished = await repositories.jobs.get(collect_job.id)
        assert finished.status == "completed"
        rows, total = await repositories.items.list_page(page=1, page_size=10)
        assert total == 1
        item_id = rows[0].id
        assert rows[0].status == "pending_analysis"
        assert rows[0].content == collected.items[0].content

    for _ in range(worker_config.job_max_attempts):
        assert await pipeline.run_once(("analyze",))
    assert not await pipeline.run_once(("analyze",))
    assert await pipeline.enqueue_pending(await pipeline.get_settings()) == 0

    async with session_factory() as session:
        job = await session.scalar(select(NewsJob).where(NewsJob.kind == "analyze"))
        assert job.status == "failed"
        assert job.attempts == worker_config.job_max_attempts
        assert "fixture failure" not in job.error
    async with worker_scope() as repositories:
        item = await repositories.items.get(item_id)
        assert item.status == "pending_analysis"
        assert item.content == collected.items[0].content


@pytest.mark.asyncio
async def test_collection_without_provider_credentials_keeps_pending_items(
    worker_scope, worker_config, collector, session_factory,
):
    config = worker_config.model_copy(update={"llm_api_key": SecretStr("")})
    pipeline = NewsPipeline(
        repositories=worker_scope, collector=collector, analyzer=None,
        config=config, utc_now=lambda: datetime.now(timezone.utc),
    )
    source = await add_source(worker_scope)
    await enqueue_collect(worker_scope, source.id)

    assert await pipeline.run_once(("collect",))
    assert not await pipeline.run_once(("analyze",))
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(NewsItem).where(NewsItem.status == "pending_analysis")) == 1
        assert await session.scalar(select(func.count()).select_from(NewsJob).where(NewsJob.kind == "analyze")) == 0


@pytest.mark.asyncio
async def test_unchanged_collection_does_not_schedule_another_analysis(
    worker_scope, pipeline, collector, analyzer, session_factory,
):
    source = await add_source(worker_scope)
    await enqueue_collect(worker_scope, source.id)
    assert await pipeline.run_once(("collect",))
    assert await pipeline.run_once(("analyze",))
    collector.fetch.return_value = CollectionResult(collector.fetch.return_value.items)
    await enqueue_collect(worker_scope, source.id)
    assert await pipeline.run_once(("collect",))
    assert not await pipeline.run_once(("analyze",))
    analyzer.analyze.assert_awaited_once()
    assert collector.fetch.await_args.kwargs["etag"] == '"version-one"'
    async with worker_scope() as repositories:
        stored_source = await repositories.sources.get(source.id)
        assert stored_source.etag is None
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(NewsItem)) == 1
        item = await session.scalar(select(NewsItem))
        assert item.status == "analyzed"


@pytest.mark.asyncio
async def test_manual_reanalysis_replaces_the_existing_identity_output(
    worker_scope, pipeline, analyzer,
):
    source = await add_source(worker_scope)
    await enqueue_collect(worker_scope, source.id)
    assert await pipeline.run_once(("collect",))
    assert await pipeline.run_once(("analyze",))
    async with worker_scope() as repositories:
        items, _ = await repositories.items.list_page(page=1, page_size=10)
        item = items[0]
        first_analysis_id = item.latest_analysis_id
        await repositories.jobs.enqueue(
            "analyze", item_id=item.id,
            payload={"content_hash": item.content_hash, "force": True},
        )
    analyzer.analyze.return_value = {
        **analyzer.analyze.return_value, "summary_ru": "Уточнённое описание после ручного запроса.",
    }

    assert await pipeline.run_once(("analyze",))
    async with worker_scope() as repositories:
        current = await repositories.items.get(item.id)
        assert current.latest_analysis_id == first_analysis_id
        assert current.analysis.summary_ru == "Уточнённое описание после ручного запроса."
    assert analyzer.analyze.await_count == 2


@pytest.mark.asyncio
async def test_two_schedulers_and_restart_deduplicate_the_same_daily_slot(
    pipeline, worker_config, session_factory,
):
    now = datetime(2026, 10, 8, 11, 0, tzinfo=timezone.utc)
    config_two = worker_config.model_copy(update={"health_file": worker_config.health_file.with_name("second-health")})
    runners = [
        NewsScheduler(pipeline=pipeline, scheduler=AsyncIOScheduler(), config=config, utc_now=lambda: now)
        for config in (worker_config, config_two)
    ]
    await asyncio.gather(*(runner.refresh() for runner in runners))
    for runner in runners:
        daily_jobs = runner._scheduler.get_jobs()
        assert len(daily_jobs) == 3
        assert all(job.max_instances == 1 and job.coalesce for job in daily_jobs)
    restarted = NewsScheduler(
        pipeline=pipeline, scheduler=AsyncIOScheduler(), config=worker_config, utc_now=lambda: now,
    )
    await restarted.refresh()

    async with session_factory() as session:
        jobs = list((await session.scalars(select(NewsJob))).all())
        assert len(jobs) == 1
        assert jobs[0].dedupe_key == "scheduled:Europe/Samara:2026-10-08:14:00"
    assert is_healthy(worker_config.health_file, worker_config.health_max_age_seconds)


@pytest.mark.asyncio
async def test_fetch_duration_does_not_skip_the_next_six_hour_slot(
    worker_scope, worker_config, collector, analyzer,
):
    source = await add_source(worker_scope)
    first_slot = datetime(2026, 10, 8, 4, 0, tzinfo=timezone.utc)
    current = [first_slot + timedelta(seconds=10)]
    pipeline = NewsPipeline(
        repositories=worker_scope, collector=collector, analyzer=analyzer,
        config=worker_config, utc_now=lambda: current[0],
    )
    async with worker_scope() as repositories:
        await repositories.sources.update(source.id, {"interval_hours": 6})
    await pipeline.enqueue_scheduled("Europe/Samara:2026-10-08:08:00")
    assert await pipeline.run_once(("collect",))
    async with worker_scope() as repositories:
        await repositories.sources.update(source.id, {"last_success_at": first_slot + timedelta(seconds=10)})

    current[0] = first_slot + timedelta(hours=6)
    await pipeline.enqueue_scheduled("Europe/Samara:2026-10-08:14:00")
    assert await pipeline.run_once(("collect",))
    assert collector.fetch.await_count == 2
    async with worker_scope() as repositories:
        stored = await repositories.sources.get(source.id)
        assert stored.cursor["collected_at"] == current[0].isoformat()


@pytest.mark.asyncio
async def test_restart_recovers_expired_job_and_rejects_former_owner(
    worker_scope, pipeline, session_factory,
):
    async with worker_scope() as repositories:
        queued = await repositories.jobs.enqueue("discover", payload={"url": "https://source.example/feed"})
        claimed = await repositories.jobs.claim("dead-process", lease_seconds=15, max_attempts=3)
        assert claimed.id == queued.id
    async with session_factory() as session:
        await session.execute(update(NewsJob).where(NewsJob.id == queued.id).values(
            lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ))
        await session.commit()

    assert await pipeline.recover() == 1
    assert await pipeline.run_once(("discover",))
    async with worker_scope() as repositories:
        assert not await repositories.jobs.complete(queued.id, "dead-process", result={"bad": True})
        finished = await repositories.jobs.get(queued.id)
        assert finished.status == "completed"
        assert finished.attempts == 2
        assert finished.result["kind"] == "rss"


@pytest.mark.asyncio
async def test_shutdown_during_http_releases_job_without_advancing_cursor(
    worker_scope, worker_config, pipeline, collector, session_factory,
):
    source = await add_source(worker_scope)
    queued = await enqueue_collect(worker_scope, source.id)
    entered = asyncio.Event()

    async def waiting_fetch(**kwargs):
        entered.set()
        await asyncio.Event().wait()

    collector.fetch.side_effect = waiting_fetch
    async with worker_scope() as repositories:
        await repositories.settings.set({"enabled": False})
    runner = NewsScheduler(
        pipeline=pipeline, scheduler=AsyncIOScheduler(), config=worker_config,
        utc_now=lambda: datetime.now(timezone.utc),
    )
    await runner.start()
    await asyncio.wait_for(entered.wait(), timeout=3)
    await asyncio.sleep(0.08)
    async with worker_scope() as repositories:
        running = await repositories.jobs.get(queued.id)
        assert running.heartbeat_at > running.started_at
    await runner.stop()
    assert not runner._scheduler.running
    assert not worker_config.health_file.exists()

    async with worker_scope() as repositories:
        job = await repositories.jobs.get(queued.id)
        source = await repositories.sources.get(source.id)
        assert job.status == "queued"
        assert job.attempts == 0
        assert source.etag is None
        assert source.last_success_at is None
    async with session_factory() as session:
        run = await session.scalar(select(NewsSourceRun))
        assert run.status == "cancelled"
        assert await session.scalar(select(func.count()).select_from(NewsItem)) == 0


@pytest.mark.asyncio
async def test_lost_lease_cancels_source_and_does_not_overwrite_new_owner(
    worker_scope, pipeline, collector, session_factory,
):
    source = await add_source(worker_scope)
    queued = await enqueue_collect(worker_scope, source.id)
    entered, cancelled = asyncio.Event(), asyncio.Event()

    async def waiting_fetch(**kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    collector.fetch.side_effect = waiting_fetch
    worker = asyncio.create_task(pipeline.run_once(("collect",)))
    await asyncio.wait_for(entered.wait(), timeout=3)
    async with session_factory() as session:
        await session.execute(update(NewsJob).where(NewsJob.id == queued.id).values(owner_token="new-owner"))
        await session.commit()
    assert await asyncio.wait_for(worker, timeout=3)
    assert cancelled.is_set()
    async with worker_scope() as repositories:
        job = await repositories.jobs.get(queued.id)
        source = await repositories.sources.get(source.id)
        assert job.owner_token == "new-owner"
        assert job.status == "running"
        assert source.last_success_at is None
        assert source.last_error is None


@pytest.mark.asyncio
async def test_source_edit_during_fetch_discards_the_old_configuration_result(
    worker_scope, pipeline, collector, session_factory,
):
    source = await add_source(worker_scope)
    await enqueue_collect(worker_scope, source.id)
    collected = collector.fetch.return_value

    async def edit_source_then_return(**kwargs):
        async with worker_scope() as repositories:
            await repositories.sources.update(source.id, {"url": "https://source.example/new-feed"})
        return collected

    collector.fetch.side_effect = edit_source_then_return
    assert await pipeline.run_once(("collect",))
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(NewsItem)) == 0
    async with worker_scope() as repositories:
        saved = await repositories.sources.get(source.id)
        assert saved.url.endswith("/new-feed")
        assert saved.etag is None
        assert saved.last_error is None


@pytest.mark.parametrize(
    ("now", "zone", "expected"),
    [
        (datetime(2026, 10, 8, 1, 0, tzinfo=timezone.utc), "Europe/Samara", "Europe/Samara:2026-10-07:20:00"),
        (datetime(2026, 10, 8, 4, 0, tzinfo=timezone.utc), "Europe/Samara", "Europe/Samara:2026-10-08:08:00"),
        (datetime(2026, 10, 8, 20, 0, tzinfo=timezone.utc), "UTC", "UTC:2026-10-08:20:00"),
    ],
)
def test_latest_scheduled_slot_preserves_local_day_and_start(now, zone, expected):
    assert latest_scheduled_slot(now, ("08:00", "14:00", "20:00"), zone) == expected
