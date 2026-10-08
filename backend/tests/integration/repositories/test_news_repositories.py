"""Real PostgreSQL queue, ownership, deduplication and editorial data invariants."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update

from src.db.models import NewsAnalysis, NewsItem, NewsJob
from src.exceptions.news import (
    NewsConflictError,
    NewsLeaseLostError,
    NewsSourceChangedError,
)
from src.repositories.news_analyses import NewsAnalysisRepository
from src.repositories.news_catalog import NewsCatalogRepository
from src.repositories.news_decisions import NewsDecisionRepository
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_sources import NewsSourceRepository
from tests.news_helpers import add_source, analysis_data, collected


async def test_ingestion_deduplicates_either_key_and_commits_cursor(db_session):
    source = await add_source(db_session)
    repo = NewsItemRepository(db_session)
    first = await repo.ingest(source.id, [collected()], {"page": 1}, etag="v1")
    again = await repo.ingest(source.id, [collected()], {"page": 2}, etag="v2")
    same_url = await repo.ingest(
        source.id, [collected(external_id="new-guid")], {"page": 3}
    )
    same_guid = await repo.ingest(
        source.id, [collected(url="https://example.org/renamed")], {"page": 4}
    )

    assert first["new"] == 1
    assert again["unchanged"] == same_url["unchanged"] == same_guid["unchanged"] == 1
    assert await db_session.scalar(select(func.count()).select_from(NewsItem)) == 1
    assert (await NewsSourceRepository(db_session).get(source.id)).cursor == {"page": 4}
    assert (await repo.get(first["item_ids"][0])).url == "https://example.org/renamed"


async def test_concurrent_ingestion_preserves_one_item_and_cross_source_duplicate(
    session_factory,
):
    async with session_factory() as session:
        first = await add_source(session)
        second = await add_source(session, name="Other")

    async def ingest(source_id):
        async with session_factory() as session:
            return await NewsItemRepository(session).ingest(
                source_id, [collected()], {}
            )

    results = await asyncio.gather(
        ingest(first.id), ingest(first.id), ingest(second.id)
    )
    async with session_factory() as session:
        rows = list(
            (await session.scalars(select(NewsItem).order_by(NewsItem.id))).all()
        )
    assert len(rows) == 2
    assert sum(result["new"] for result in results) == 2
    assert rows[1].duplicate_of_id == rows[0].id


async def test_failed_ingestion_rolls_back_items_and_cursor(db_session):
    source = await add_source(db_session)
    source_id = source.id
    repo = NewsItemRepository(db_session)
    invalid = collected(external_id="two", url="https://example.org/two")
    invalid["title"] = None

    with pytest.raises(NewsConflictError):
        await repo.ingest(source_id, [collected(), invalid], {"bad": True}, etag="bad")

    assert await db_session.scalar(select(func.count()).select_from(NewsItem)) == 0
    source = await NewsSourceRepository(db_session).get(source_id)
    assert (
        source.cursor == {} and source.etag is None and source.last_success_at is None
    )


async def test_source_config_change_fences_inflight_collection(db_session):
    source = await add_source(db_session)
    source_id = source.id
    await NewsSourceRepository(db_session).update(
        source_id, {"url": "https://example.org/new-feed"}
    )
    with pytest.raises(NewsSourceChangedError):
        await NewsItemRepository(db_session).ingest(
            source_id,
            [collected()],
            {"bad": True},
            expected_url="https://example.org/feed.xml",
            expected_kind="rss",
            expected_config={},
        )
    source = await NewsSourceRepository(db_session).get(source_id)
    assert source.cursor == {} and source.last_success_at is None


async def test_conflicting_guid_and_url_roll_back_without_poisoning_canonical_identity(
    db_session,
):
    source_id = (await add_source(db_session)).id
    items = NewsItemRepository(db_session)
    first, second = (
        collected(),
        collected(external_id="two", url="https://example.org/two"),
    )
    result = await items.ingest(source_id, [first, second], {"version": 1})
    with pytest.raises(NewsConflictError):
        await items.ingest(
            source_id,
            [
                collected(
                    external_id="one",
                    url="https://example.org/two",
                    content="Conflicting",
                )
            ],
            {"version": 2},
        )
    preserved = await items.get(result["item_ids"][0])
    assert (
        preserved.url
        == preserved.canonical_url
        == preserved.normalized_url
        == first["url"]
    )
    assert preserved.content_hash == first["content_hash"]
    assert (await NewsSourceRepository(db_session).get(source_id)).cursor == {
        "version": 1
    }


async def test_analysis_identity_and_content_hash_prevent_stale_overwrite(db_session):
    source = await add_source(db_session)
    source_id = source.id
    items = NewsItemRepository(db_session)
    initial = collected()
    ingested = await items.ingest(source_id, [initial], {})
    item_id = ingested["item_ids"][0]
    analyses = NewsAnalysisRepository(db_session)
    first = await analyses.save(
        item_id, initial["content_hash"], "model", "v1", analysis_data()
    )
    again = await analyses.save(
        item_id, initial["content_hash"], "model", "v1", analysis_data()
    )
    assert first.id == again.id

    await items.ingest(source_id, [collected(content="Changed text")], {"v": 2})
    assert (
        await analyses.save(
            item_id, initial["content_hash"], "other-model", "v1", analysis_data()
        )
        is None
    )
    current = await items.get(item_id)
    assert current.status == "pending_analysis" and current.latest_analysis_id is None
    assert len(await analyses.list_for_item(item_id)) == 1


async def test_atomic_claim_applies_global_cap_across_workers(session_factory):
    async with session_factory() as session:
        repo = NewsJobRepository(session)
        for _ in range(3):
            await repo.enqueue("analyze")

    async def claim(owner):
        async with session_factory() as session:
            return await NewsJobRepository(session).claim(
                owner, 120, 3, kinds=["analyze"], concurrency_limits={"analyze": 2}
            )

    claimed = await asyncio.gather(*(claim(f"worker-{index}") for index in range(3)))
    assert len([row for row in claimed if row is not None]) == 2
    assert len({row.id for row in claimed if row is not None}) == 2


async def test_manual_analysis_refreshes_same_identity_without_creating_a_duplicate(
    db_session,
):
    source = await add_source(db_session)
    data = collected()
    item_id = (await NewsItemRepository(db_session).ingest(source.id, [data], {}))[
        "item_ids"
    ][0]
    analyses = NewsAnalysisRepository(db_session)
    original = await analyses.save(
        item_id, data["content_hash"], "model", "v1", analysis_data()
    )
    original_id = original.id
    changed = {**analysis_data(), "summary_ru": "Обновлённый разбор.", "news_score": 90}
    ignored = await analyses.save(item_id, data["content_hash"], "model", "v1", changed)
    assert ignored.summary_ru != changed["summary_ru"]
    refreshed = await analyses.save(
        item_id, data["content_hash"], "model", "v1", changed, replace_existing=True
    )
    assert refreshed.id == original_id and refreshed.summary_ru == changed["summary_ru"]
    assert refreshed.news_score == 90
    assert len(await analyses.list_for_item(item_id)) == 1


async def test_expired_lease_recovers_with_bounded_attempts_and_fences_old_owner(
    db_session,
):
    jobs = NewsJobRepository(db_session)
    job = await jobs.enqueue("collect")
    job_id = job.id
    await jobs.claim("old-owner", 120, 2)
    await db_session.execute(
        update(NewsJob)
        .where(NewsJob.id == job_id)
        .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    await db_session.commit()

    assert not await jobs.heartbeat(job_id, "old-owner", 120)
    assert await jobs.recover(2) == 1
    recovered = await jobs.claim("new-owner", 120, 2)
    assert recovered.id == job_id and recovered.attempts == 2
    assert not await jobs.complete(job_id, "old-owner", result={"wrong": True})
    await db_session.execute(
        update(NewsJob)
        .where(NewsJob.id == job_id)
        .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    await db_session.commit()
    assert await jobs.recover(2) == 1
    assert (await jobs.get(job_id)).status == "failed"
    assert await jobs.claim("third-owner", 120, 2) is None


async def test_stale_worker_cannot_commit_ingestion_or_analysis(db_session):
    source = await add_source(db_session)
    source_id = source.id
    items = NewsItemRepository(db_session)
    data = collected()
    item_id = (await items.ingest(source_id, [data], {}))["item_ids"][0]
    jobs = NewsJobRepository(db_session)
    job_id = (await jobs.enqueue("analyze", item_id=item_id)).id
    await jobs.claim("correct", 120, 3)

    with pytest.raises(NewsLeaseLostError):
        await items.ingest(
            source_id,
            [collected(content="Should not commit")],
            {"bad": True},
            job_id=job_id,
            owner_token="wrong",
        )
    with pytest.raises(NewsLeaseLostError):
        await NewsAnalysisRepository(db_session).save(
            item_id,
            data["content_hash"],
            "model",
            "v1",
            analysis_data(),
            job_id=job_id,
            owner_token="wrong",
        )
    assert (await items.get(item_id)).content == data["content"]
    assert (await NewsSourceRepository(db_session).get(source_id)).cursor == {}
    assert await db_session.scalar(select(func.count()).select_from(NewsAnalysis)) == 0


async def test_two_schedulers_enqueue_only_one_durable_slot(session_factory):
    async def enqueue():
        async with session_factory() as session:
            return await NewsJobRepository(session).enqueue_scheduled(
                "2026-10-08T08:00:00+04:00"
            )

    results = await asyncio.gather(enqueue(), enqueue())
    assert sum(row is not None for row in results) == 1
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(NewsJob)) == 1


async def test_failed_analysis_does_not_starve_pending_backlog(db_session):
    source = await add_source(db_session)
    items = NewsItemRepository(db_session)
    data = collected()
    first_id, second_id = (
        await items.ingest(
            source.id,
            [data, collected(external_id="two", url="https://example.org/two")],
            {},
        )
    )["item_ids"]
    jobs = NewsJobRepository(db_session)
    key = f"analysis:{first_id}:{data['content_hash']}:model:v1"
    job = await jobs.enqueue("analyze", item_id=first_id, dedupe_key=key)
    await jobs.claim("owner", 120, 1)
    await jobs.fail(job.id, "owner", "Provider unavailable", retry=True, max_attempts=1)
    again = await jobs.enqueue("analyze", item_id=first_id, dedupe_key=key)
    assert again.status == "failed"
    assert [row.id for row in await items.pending(1, "model", "v1")] == [second_id]
    explicit = await jobs.enqueue(
        "analyze", item_id=first_id, dedupe_key=key, retry_failed=True
    )
    assert explicit.status == "queued" and explicit.attempts == 0


async def test_current_analysis_and_decision_filters_do_not_match_history(db_session):
    source = await add_source(db_session)
    catalog = NewsCatalogRepository(db_session)
    topic = await catalog.create("topics", {"name": "AI"})
    category = await catalog.create("categories", {"name": "Engineering"})
    items = NewsItemRepository(db_session)
    data = collected()
    item_id = (await items.ingest(source.id, [data], {}))["item_ids"][0]
    await NewsAnalysisRepository(db_session).save(
        item_id,
        data["content_hash"],
        "model",
        "v1",
        analysis_data(category_id=category.id, topic_ids=[topic.id]),
    )
    decisions = NewsDecisionRepository(db_session)
    await decisions.create(
        item_id,
        {"decision": "in_work", "format": "longread_candidate", "editor": "admin"},
    )
    await decisions.create(
        item_id,
        {"decision": "deferred", "format": "longread_candidate", "editor": "admin"},
    )

    rows, total = await items.list_page(
        page=1,
        page_size=20,
        topic_id=topic.id,
        category_id=category.id,
        format="longread_candidate",
        min_score=75,
        decision="deferred",
    )
    assert total == 1 and rows[0].id == item_id
    assert (await items.list_page(page=1, page_size=20, decision="in_work"))[1] == 0
    assert (await items.list_page(page=2, page_size=1))[0] == []


async def test_retention_removes_superseded_history_but_keeps_current_editorial_data(
    db_session,
):
    source = await add_source(db_session)
    items = NewsItemRepository(db_session)
    data = collected()
    item_id = (await items.ingest(source.id, [data], {}))["item_ids"][0]
    analyses = NewsAnalysisRepository(db_session)
    await analyses.save(item_id, data["content_hash"], "model", "v1", analysis_data())
    latest = await analyses.save(
        item_id, data["content_hash"], "model", "v2", analysis_data()
    )
    latest_id = latest.id
    future = datetime.now(timezone.utc) + timedelta(days=1)
    counts = await items.retain(future, future)
    current = await items.get(item_id)
    assert counts["texts"] == 1 and counts["analyses"] == 1
    assert current.content == current.excerpt == ""
    assert current.latest_analysis_id == latest_id
    assert len(await analyses.list_for_item(item_id)) == 1


async def test_taxonomy_seed_is_idempotent_and_preserves_editor_changes(db_session):
    catalog = NewsCatalogRepository(db_session)
    defaults = [{"name": "AI", "description": "Initial", "active": True}]
    await catalog.seed("topics", defaults)
    topic = (await catalog.list("topics"))[0]
    await catalog.update("topics", topic.id, {"description": "Edited", "active": False})
    await catalog.seed("topics", defaults)
    topics = await catalog.list("topics")
    assert (
        len(topics) == 1 and topics[0].description == "Edited" and not topics[0].active
    )
