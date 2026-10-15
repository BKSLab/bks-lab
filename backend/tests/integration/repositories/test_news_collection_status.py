"""Durable collection and exact-version progress against real PostgreSQL."""

from datetime import datetime, timezone

from pydantic import SecretStr

from src.core.news_settings import NewsSettings
from src.db.models import NewsRunItem
from src.repositories.news_analyses import NewsAnalysisRepository
from src.repositories.news_catalog import NewsCatalogRepository
from src.repositories.news_decisions import NewsDecisionRepository
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_runs import NewsRunRepository
from src.repositories.news_settings import NewsSettingsRepository
from src.repositories.news_sources import NewsSourceRepository
from src.services.news_admin import NewsAdminService
from tests.news_helpers import add_source, analysis_data, collected


def status_service(session, *, configured=True):
    return NewsAdminService(
        sources=NewsSourceRepository(session), catalog=NewsCatalogRepository(session),
        items=NewsItemRepository(session), analyses=NewsAnalysisRepository(session),
        decisions=NewsDecisionRepository(session), jobs=NewsJobRepository(session),
        runs=NewsRunRepository(session), settings=NewsSettingsRepository(session),
        config=NewsSettings(
            _env_file=None, llm_api_key=SecretStr("fixture-key" if configured else ""),
            llm_model="fixture-model", llm_api_url="https://fixture.example/v1/chat/completions",
        ),
    )


async def terminal_collection(session, source, materials):
    jobs, runs = NewsJobRepository(session), NewsRunRepository(session)
    job = await jobs.enqueue("collect", source_id=source.id)
    await jobs.claim("status-test", 120, 3, kinds=["collect"])
    run = await runs.begin(source.id, job.id)
    counts = await NewsItemRepository(session).ingest(
        source.id, materials, {}, run_id=run.id, job_id=job.id, owner_token="status-test",
    )
    job.status, job.completed_at = "completed", datetime.now(timezone.utc)
    await session.commit()
    return job, run, counts["item_ids"]


async def test_empty_overview_and_scope_snapshot_survive_source_changes_and_concurrent_requests(db_session):
    service = status_service(db_session)
    empty = await service.collection_status()
    assert empty.job is None and empty.busy is False and empty.active_jobs == 0
    first = await add_source(db_session, name="First")
    second = await add_source(db_session, name="Second", url="https://second.example/feed")
    jobs = NewsJobRepository(db_session)
    all_job = await jobs.enqueue("collect")
    assert {target["source_slug"] for target in all_job.payload["collection_targets"]} == {first.slug, second.slug}
    await NewsSourceRepository(db_session).update_preferences(first.id, {"active": False})
    await add_source(db_session, name="Later", url="https://later.example/feed")
    another_job = await jobs.enqueue("collect", source_id=second.id)
    restored = await service.collection_status()
    assert restored.job.slug == all_job.slug and restored.active_jobs == 2
    assert restored.collection.sources_total == restored.collection.sources_queued == 2
    assert restored.collection.sources_done == restored.collection.sources_running == 0
    assert restored.busy is True
    assert {row.source_slug for row in restored.sources} == {first.slug, second.slug}
    scoped = await service.collection_status(another_job.slug)
    assert scoped.job.slug == another_job.slug and scoped.collection.sources_total == 1
    assert scoped.sources[0].source_slug == second.slug
    for source in await NewsSourceRepository(db_session).list_active():
        await NewsSourceRepository(db_session).update_preferences(source.id, {"active": False})
    no_targets = await jobs.enqueue("collect")
    assert no_targets.payload["collection_targets"] == []
    empty_scope = await service.collection_status(no_targets.slug)
    assert empty_scope.collection.sources_total == 0 and empty_scope.busy is False


async def test_totals_use_latest_source_attempt_and_exact_observed_versions_once(db_session):
    source = await add_source(db_session)
    other = await add_source(db_session, name="Other", url="https://other.example/feed")
    jobs, runs = NewsJobRepository(db_session), NewsRunRepository(db_session)
    items, analyses = NewsItemRepository(db_session), NewsAnalysisRepository(db_session)
    unchanged = collected(external_id="unchanged", url="https://example.org/unchanged", title="Already retained")
    await items.ingest(source.id, [unchanged], {})
    job = await jobs.enqueue("collect")
    await jobs.claim("status-test", 120, 3, kinds=["collect"])
    previous = await runs.begin(source.id, job.id)
    await runs.finish(previous.id, "failed", new_count=100, error="Old retry")
    run = await runs.begin(source.id, job.id)
    materials = [collected(
        external_id=str(index), url=f"https://example.org/{index}", title=f"Material {index}",
        content="tiny" if index == 5 else f"Sufficient version {index}. " * 25,
    ) for index in range(8)]
    counts = await items.ingest(
        source.id, [*materials, unchanged], {}, run_id=run.id,
        job_id=job.id, owner_token="status-test",
    )
    ids = counts["item_ids"]
    await analyses.save(ids[0], materials[0]["content_hash"], "fixture-model", "v1", analysis_data())
    # New current content and its queued analysis must not replace the observed completed version.
    newer = {**materials[0], **collected(external_id="0", url="https://example.org/0", content="Newer version " * 40)}
    await items.ingest(source.id, [newer], {})
    await jobs.enqueue("analyze", item_id=ids[0], payload={"content_hash": newer["content_hash"]})
    for index, state in ((1, "queued"), (2, "running"), (3, "failed"), (7, "completed")):
        analysis_job = await jobs.enqueue("analyze", item_id=ids[index], payload={"content_hash": materials[index]["content_hash"]})
        analysis_job.status = state
        if state == "completed":
            analysis_job.result = {"skipped": "content_changed"}
        await db_session.commit()
    obsolete = collected(external_id="6", url="https://example.org/6", content="Replacement text " * 40)
    await items.ingest(source.id, [obsolete], {})
    await analyses.save(ids[6], obsolete["content_hash"], "fixture-model", "v1", analysis_data())
    db_session.add(NewsRunItem(
        run_id=run.id, item_id=ids[1], title=materials[1]["title"], outcome="new",
        content_hash=materials[1]["content_hash"],
    ))
    await db_session.commit()
    await runs.begin(other.id, job.id)
    result = await status_service(db_session).collection_status()
    assert result.job.slug == job.slug and result.busy is True
    assert result.collection.sources_total == 2
    assert result.collection.sources_done == result.collection.sources_completed == 1
    assert result.collection.sources_running == 1 and result.collection.sources_failed == 0
    assert result.collection.new == 8 and result.collection.unchanged == 1
    assert result.analysis.model_dump() == {
        "scope": "new_updated", "total": 8, "queued": 1, "running": 1,
        "completed": 1, "failed": 1, "blocked": 3, "pending": 1,
        "blocked_reasons": {"missing_llm": 0, "paused": 0, "insufficient_text": 1, "unavailable": 2},
    }
    first_status = next(row for row in result.sources if row.source_slug == source.slug)
    assert first_status.analysis == result.analysis and first_status.new == 8


async def test_unschedulable_analysis_is_blocked_and_does_not_keep_progress_busy(db_session):
    source = await add_source(db_session)
    material = collected()
    job, _, item_ids = await terminal_collection(db_session, source, [material])
    missing = await status_service(db_session, configured=False).collection_status()
    assert missing.analysis.blocked == missing.analysis.blocked_reasons.missing_llm == 1
    assert missing.busy is False
    await NewsSettingsRepository(db_session).set({"enabled": False})
    paused = await status_service(db_session).collection_status()
    assert paused.analysis.blocked_reasons.paused == 1 and paused.busy is False
    await NewsSettingsRepository(db_session).set({"enabled": True})
    pending = await status_service(db_session).collection_status()
    assert pending.analysis.pending == 1 and pending.busy is True
    await NewsJobRepository(db_session).enqueue("analyze", item_id=item_ids[0], payload={"content_hash": material["content_hash"]})
    await NewsSettingsRepository(db_session).set({"enabled": False})
    queued = await status_service(db_session).collection_status(job.slug)
    assert queued.analysis.queued == 1 and queued.analysis.blocked == 0 and queued.busy is True
    missing_queued = await status_service(db_session, configured=False).collection_status(job.slug)
    assert missing_queued.analysis.blocked_reasons.missing_llm == 1 and missing_queued.busy is False


async def test_runnable_analysis_keeps_older_collection_relevant_but_blocked_work_does_not(db_session):
    source = await add_source(db_session)
    old, _, ids = await terminal_collection(db_session, source, [collected()])
    newer, _, _ = await terminal_collection(db_session, source, [collected()])
    service = status_service(db_session)
    assert (await service.collection_status()).job.slug == old.slug
    assert (await status_service(db_session, configured=False).collection_status()).job.slug == newer.slug
    analysis = await NewsJobRepository(db_session).enqueue(
        "analyze", item_id=ids[0], payload={"content_hash": collected()["content_hash"]},
    )
    assert (await service.collection_status()).job.slug == old.slug
    analysis.status = "failed"
    await db_session.commit()
    assert (await service.collection_status()).job.slug == newer.slug
