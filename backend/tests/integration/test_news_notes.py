"""Real PostgreSQL acceptance for admission, source identity and paced publication."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, func, select

from src.clients.revalidation import RevalidationClient
from src.db.models import ContentItem, ContentRevision, NewsAnalysis, NewsItem, NewsNoteQueue
from src.exceptions.news import NewsConflictError, NewsLeaseLostError
from src.repositories.content_items import ContentItemRepository
from src.repositories.content_revisions import ContentRevisionRepository
from src.repositories.news_analyses import NewsAnalysisRepository
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_notes import NewsNoteRepository
from src.schemas.admin import ContentPatch, NoteCreate
from src.schemas.news_notes import NoteQueuePatch, NoteSettingsPatch
from src.services.content_admin import ContentAdminService
from src.services.news_notes import NewsNoteService
from tests.news_helpers import add_source, analysis_data, collected

NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
CANDIDATE = {"title": "Новая модель помогает разработчикам", "text": "Команда представила инструмент для анализа кода. Он помогает находить ошибки в небольших проектах."}


def service(session, clock, *, revalidator=None):
    return NewsNoteService(
        repository=NewsNoteRepository(session), items=ContentItemRepository(session),
        revisions=ContentRevisionRepository(session),
        revalidator=revalidator or AsyncMock(spec=RevalidationClient), words_per_minute=200,
        utc_now=lambda: clock[0],
    )


async def raw_item(session, clock, *, number=1, source=None, published_at=None, first_seen=None):
    source = source or await add_source(session)
    data = collected(external_id=f"material-{number}", url=f"https://example.org/material-{number}")
    data["published_at"] = published_at
    counts = await NewsItemRepository(session).ingest(source.id, [data], {})
    item = await NewsItemRepository(session).get(counts["item_ids"][0])
    item.first_seen_at = first_seen or clock[0]
    await session.commit()
    return item, source


async def save_analysis(session, item, **changes):
    data = analysis_data() | {"needs_verification": False, "note_candidate": CANDIDATE} | changes
    return await NewsAnalysisRepository(session).save(
        item.id, item.content_hash, "fixture-model", changes.pop("prompt_version", "notes-fixture"), data,
        replace_existing=True,
    )


async def admit(session, notes, analysis):
    jobs = NewsJobRepository(session)
    job = await jobs.enqueue("analyze", item_id=analysis.item_id)
    claimed = await jobs.claim(owner_token="note-owner", lease_seconds=60, max_attempts=3, kinds=["analyze"])
    assert claimed.id == job.id
    result = await notes.enqueue_analysis(analysis.id, job_id=job.id, owner_token="note-owner")
    await jobs.complete(job.id, "note-owner", result={})
    return result


async def candidate(session, clock, *, number=1, notes=None, **changes):
    notes = notes or service(session, clock)
    item, source = await raw_item(session, clock, number=number)
    analysis = await save_analysis(session, item, **changes)
    assert await admit(session, notes, analysis)
    row = await session.scalar(select(NewsNoteQueue).where(NewsNoteQueue.source_item_id == item.id))
    return row, item, source, analysis


async def test_first_activation_does_not_backfill_existing_material_even_reanalyzed(db_session):
    clock = [NOW]
    notes = service(db_session, clock)
    original, _ = await raw_item(db_session, clock, first_seen=NOW - timedelta(seconds=1))
    analysis = await save_analysis(db_session, original)
    assert not await admit(db_session, notes, analysis)
    assert (await notes.get_settings()).enabled is False
    assert (await notes.get_settings()).interval_minutes == 10
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    assert not await admit(db_session, notes, await save_analysis(db_session, original))
    assert await db_session.scalar(select(func.count()).select_from(ContentItem)) == 0
    assert await db_session.scalar(select(func.count()).select_from(NewsAnalysis)) == 1


async def test_pause_preserves_start_and_admits_new_longread_only_candidates(db_session):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    clock[0] += timedelta(minutes=1)
    await notes.update_settings(NoteSettingsPatch(enabled=False))
    row, _, _, _ = await candidate(db_session, clock, notes=notes, recommended_formats=["longread_candidate"])
    assert row.status == "queued"
    assert await notes.publish_due() is None
    assert (await notes.get_settings()).started_at == NOW
    clock[0] += timedelta(minutes=1)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    assert (await notes.get_settings()).started_at == NOW
    assert await notes.publish_due() == row.note_slug


@pytest.mark.parametrize("changes", [
    {"is_relevant": False}, {"needs_verification": True}, {"note_candidate": None},
    {"note_candidate": {"title": "а" * 91, "text": "Текст"}},
    {"note_candidate": {"title": "Заголовок", "text": "б" * 301}},
    {"note_candidate": {"title": "English", "text": "Текст"}},
    {"note_candidate": {"title": "Заголовок", "text": "Текст", "url": "https://untrusted.example"}},
])
async def test_ineligible_or_invalid_candidate_keeps_analysis_without_creating_content(db_session, changes):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    item, _ = await raw_item(db_session, clock)
    analysis = await save_analysis(db_session, item, **changes)
    assert not await admit(db_session, notes, analysis)
    assert await db_session.scalar(select(func.count()).select_from(ContentItem)) == 0
    assert await db_session.get(NewsAnalysis, analysis.id) is not None


@pytest.mark.parametrize("kind", ["duplicate", "insufficient", "warning", "stale"])
async def test_admission_checks_live_item_quality_and_version(db_session, kind):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    item, _ = await raw_item(db_session, clock)
    analysis = await save_analysis(db_session, item)
    if kind == "duplicate":
        other, _ = await raw_item(db_session, clock, number=2)
        item.duplicate_of_id = other.id
    elif kind == "insufficient":
        item.excerpt = item.content = "Short"
    elif kind == "warning":
        item.metadata_json = {"collection_warning": "Extraction warning"}
    else:
        item.content_hash = "f" * 64
    await db_session.commit()
    assert not await admit(db_session, notes, analysis)


async def test_lease_fence_prevents_stale_worker_from_creating_note(db_session):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    item, _ = await raw_item(db_session, clock)
    analysis = await save_analysis(db_session, item)
    job = await NewsJobRepository(db_session).enqueue("analyze", item_id=item.id)
    with pytest.raises(NewsLeaseLostError):
        await notes.enqueue_analysis(analysis.id, job_id=job.id, owner_token="stale-owner")
    assert await db_session.scalar(select(func.count()).select_from(ContentItem)) == 0


async def test_draft_and_identity_roll_back_together(db_session):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    item, _ = await raw_item(db_session, clock)
    analysis = await save_analysis(db_session, item)
    original_add = notes.repository.add
    analysis_id = analysis.id
    notes.repository.add = AsyncMock(side_effect=RuntimeError("simulated write failure"))
    with pytest.raises(RuntimeError):
        await admit(db_session, notes, analysis)
    assert await db_session.scalar(select(func.count()).select_from(ContentItem)) == 0
    assert await db_session.scalar(select(func.count()).select_from(ContentRevision)) == 0
    assert await db_session.get(NewsAnalysis, analysis_id) is not None
    notes.repository.add = original_add


async def test_auto_note_feed_keeps_entire_candidate_with_multiple_paragraphs(client, db_session):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    text = "Первая мысль.\n\nВторой факт."
    row, *_ = await candidate(
        db_session, clock, notes=notes,
        note_candidate={"title": "Новость из двух абзацев", "text": text},
    )
    assert await notes.publish_due() == row.note_slug
    response = await client.get("/api/v1/notes/feed")
    assert response.status_code == 200
    public_note = next(item for item in response.json()["items"] if item["slug"] == row.note_slug)
    assert public_note["excerpt"] == text


async def test_exact_source_snapshot_safe_markup_and_permanent_deduplication(db_session):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    row, item, source, analysis = await candidate(
        db_session, clock, notes=notes,
        note_candidate={"title": "Текст новости", "text": "Разработчики показали **инструмент** и `пример`. # Новость!"},
    )
    note = await db_session.get(ContentItem, row.content_id)
    assert note.source_name == source.name and note.source_url == item.url
    assert "<strong>" not in note.content_html and "<code>" not in note.content_html
    assert "<h1>" not in note.content_html and "<a " not in note.content_html
    assert "**инструмент**" in note.content_text
    assert not await admit(db_session, notes, analysis)
    # The permanent keys still work after raw/source history disappears.
    await db_session.execute(delete(NewsItem).where(NewsItem.id == item.id))
    await db_session.commit()
    item2, _ = await raw_item(db_session, clock, source=source)
    second_analysis = await save_analysis(db_session, item2)
    assert not await admit(db_session, notes, second_analysis)
    assert await db_session.scalar(select(func.count()).select_from(ContentItem)) == 1
    await db_session.refresh(row)
    assert row.source_item_id is None and row.analysis_id is None


async def test_external_identifier_prevents_second_note_after_source_url_changes(db_session):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    row, item, source, _ = await candidate(db_session, clock, notes=notes)
    await db_session.execute(delete(NewsItem).where(NewsItem.id == item.id))
    await db_session.commit()
    data = collected(external_id="material-1", url="https://example.org/renamed-material")
    result = await NewsItemRepository(db_session).ingest(source.id, [data], {})
    replacement = await NewsItemRepository(db_session).get(result["item_ids"][0])
    assert not await admit(db_session, notes, await save_analysis(db_session, replacement))
    assert await db_session.scalar(select(func.count()).select_from(NewsNoteQueue)) == 1


async def test_concurrent_publishers_restart_and_persisted_clock(session_factory):
    clock = [NOW]
    async with session_factory() as session:
        notes = service(session, clock)
        await notes.update_settings(NoteSettingsPatch(enabled=True))
        first, *_ = await candidate(session, clock, number=1, notes=notes)
        second, *_ = await candidate(session, clock, number=2, notes=notes)
        first_slug, second_slug = first.note_slug, second.note_slug

    async def tick():
        async with session_factory() as session:
            return await service(session, clock).publish_due()

    results = await asyncio.gather(tick(), tick())
    assert results.count(first_slug) == 1 and results.count(None) == 1
    assert await tick() is None
    clock[0] += timedelta(minutes=9, seconds=59)
    assert await tick() is None
    clock[0] += timedelta(seconds=1)
    assert await tick() == second_slug
    assert await tick() is None
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ContentItem).where(ContentItem.status == "active")) == 2
        assert await session.scalar(select(func.count()).select_from(ContentRevision)) == 4


async def test_long_pause_publishes_one_without_catchup_burst(db_session):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    first, *_ = await candidate(db_session, clock, notes=notes)
    second, *_ = await candidate(db_session, clock, notes=notes, number=2)
    await notes.update_settings(NoteSettingsPatch(enabled=False))
    clock[0] += timedelta(hours=12)
    assert await notes.publish_due() is None
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    assert await notes.publish_due() == first.note_slug
    assert await notes.publish_due() is None
    await db_session.refresh(second)
    assert second.status == "queued"


async def test_publisher_rolls_back_note_revision_queue_and_clock_and_retries(db_session):
    clock = [NOW]
    revalidator = AsyncMock(spec=RevalidationClient)
    notes = service(db_session, clock, revalidator=revalidator)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    row, _, _, _ = await candidate(db_session, clock, notes=notes)
    slug, content_id = row.note_slug, row.content_id
    original_add = notes.revisions.add
    notes.revisions.add = AsyncMock(side_effect=RuntimeError("simulated revision failure"))
    with pytest.raises(RuntimeError):
        await notes.publish_due()
    note = await db_session.get(ContentItem, content_id)
    assert note.status == "draft" and note.published_at_time is None
    assert (await notes.get_settings()).last_published_at is None
    assert (await notes.list_queue(status="queued", page=1, page_size=20)).total == 1
    revalidator.revalidate_content.assert_not_awaited()
    notes.revisions.add = original_add
    assert await notes.publish_due() == slug
    revalidator.revalidate_content.assert_awaited_once()


async def test_queue_edits_and_eligible_reanalysis_same_hash_preserve_one_note(db_session):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    row, item, _, original_analysis = await candidate(db_session, clock, notes=notes)
    await notes.update_queue(row.note_slug, NoteQueuePatch(title="Редакторский заголовок", text="Редакторская заметка."))
    reanalysis = await save_analysis(db_session, item, prompt_version="new-prompt", note_candidate={"title": "Другой заголовок", "text": "Другой текст."})
    assert reanalysis.id != original_analysis.id
    assert not await admit(db_session, notes, reanalysis)
    assert await notes.publish_due() == row.note_slug
    note = await db_session.get(ContentItem, row.content_id)
    assert note.title == "Редакторский заголовок" and note.content_text == "Редакторская заметка."
    assert row.analysis_id == original_analysis.id
    assert await db_session.scalar(select(func.count()).select_from(ContentItem)) == 1
    assert await db_session.scalar(select(func.count()).select_from(ContentRevision)) == 3


@pytest.mark.parametrize("change", ["version", "verification"])
async def test_changed_or_newly_unverified_material_is_excluded_without_overwrite(db_session, change):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    row, item, _, _ = await candidate(db_session, clock, notes=notes)
    if change == "version":
        item.content_hash = "a" * 64
        await db_session.commit()
    else:
        await save_analysis(db_session, item, prompt_version="new-prompt", needs_verification=True)
    assert await notes.publish_due() is None
    await db_session.refresh(row)
    assert row.status == "excluded" and row.reason
    assert (await db_session.get(ContentItem, row.content_id)).status == "draft"


@pytest.mark.parametrize("age_kind", ["source", "first_seen", "waiting"])
async def test_source_or_queue_age_expires_terminally_even_while_paused(db_session, age_kind):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True, max_age_hours=1))
    row, _, _, _ = await candidate(db_session, clock, notes=notes)
    if age_kind == "source":
        row.source_published_at = NOW - timedelta(hours=2)
    elif age_kind == "first_seen":
        row.source_first_seen_at = NOW - timedelta(hours=2)
    else:
        row.created_at = NOW - timedelta(hours=2)
    await db_session.commit()
    await notes.update_settings(NoteSettingsPatch(enabled=False))
    assert await notes.publish_due() is None
    await db_session.refresh(row)
    assert row.status == "expired" and row.reason


async def test_published_note_and_identity_survive_raw_retention_and_deletion(db_session):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    row, item, _, _ = await candidate(db_session, clock, notes=notes)
    assert await notes.publish_due() == row.note_slug
    content_id, slug = row.content_id, row.note_slug
    await NewsItemRepository(db_session).retain(text_before=NOW + timedelta(days=1), history_before=NOW + timedelta(days=1))
    await db_session.execute(delete(NewsItem).where(NewsItem.id == item.id))
    await db_session.commit()
    note = await db_session.get(ContentItem, content_id)
    assert note.status == "active" and note.source_url == "https://example.org/material-1"
    assert note.content_text == CANDIDATE["text"]
    assert (await notes.list_queue(status="published", page=1, page_size=20)).items[0].note_slug == slug


async def test_editor_deletion_preserves_identity_tombstone_and_published_queue_is_immutable(db_session):
    clock = [NOW]
    notes = service(db_session, clock)
    await notes.update_settings(NoteSettingsPatch(enabled=True))
    row, _, _, analysis = await candidate(db_session, clock, notes=notes)
    await notes.publish_due()
    slug, content_id, analysis_id = row.note_slug, row.content_id, analysis.id
    with pytest.raises(NewsConflictError):
        await notes.update_queue(slug, NoteQueuePatch(text="Попытка правки."))
    await db_session.execute(delete(ContentItem).where(ContentItem.id == content_id))
    await db_session.commit()
    analysis = await NewsAnalysisRepository(db_session).list_for_item((await db_session.get(NewsAnalysis, analysis_id)).item_id)
    assert not await admit(db_session, notes, analysis[0])
    queued = await notes.list_queue(status="published", page=1, page_size=20)
    assert queued.items[0].content_id is None


async def test_manual_editor_preserves_first_publication_instant_across_draft_and_restore(db_session):
    clock = [NOW]
    revalidator = AsyncMock(spec=RevalidationClient)
    editor = ContentAdminService(
        items=ContentItemRepository(db_session), revisions=ContentRevisionRepository(db_session),
        revalidator=revalidator, words_per_minute=200, utc_now=lambda: clock[0],
        note_queue=NewsNoteRepository(db_session),
    )
    created = await editor.create_item(NoteCreate(type="note", slug="manual", title="Ручная заметка", content_markdown="Текст.", published_at=NOW.date(), draft=True))
    item = await db_session.get(ContentItem, created.id)
    assert item.published_at_time is None
    await editor.set_status(created.id, "active")
    assert item.published_at_time == NOW
    clock[0] += timedelta(hours=1)
    await editor.update_item(created.id, ContentPatch(title="Правка", draft=True))
    await editor.restore_revision(created.id, 1)
    await editor.set_status(created.id, "active")
    assert item.published_at_time == NOW
    assert item.source_name is None and item.source_url is None
    published_direct = await editor.create_item(NoteCreate(type="note", slug="direct", title="Опубликована сразу", content_markdown="Текст.", published_at=NOW.date(), draft=False))
    assert (await db_session.get(ContentItem, published_direct.id)).published_at_time == clock[0]


async def test_concurrent_editor_delete_and_publisher_use_one_lock_order(session_factory):
    clock = [NOW]
    async with session_factory() as setup:
        notes = service(setup, clock)
        await notes.update_settings(NoteSettingsPatch(enabled=True))
        row, *_ = await candidate(setup, clock, notes=notes)
        content_id, slug = row.content_id, row.note_slug

    queue_locked = asyncio.Event()
    release_publisher = asyncio.Event()
    editor_entered = asyncio.Event()
    async with session_factory() as publish_session, session_factory() as editor_session:
        publisher = service(publish_session, clock)
        original_lock = publisher.repository.lock_content

        async def pause_after_queue_lock(item_id):
            queue_locked.set()
            await release_publisher.wait()
            return await original_lock(item_id)

        publisher.repository.lock_content = pause_after_queue_lock
        editor_queue = NewsNoteRepository(editor_session)
        original_editor_lock = editor_queue.lock_for_content

        async def mark_editor_started(item_id):
            editor_entered.set()
            await original_editor_lock(item_id)

        editor_queue.lock_for_content = mark_editor_started
        editor = ContentAdminService(
            items=ContentItemRepository(editor_session), revisions=ContentRevisionRepository(editor_session),
            revalidator=AsyncMock(spec=RevalidationClient), words_per_minute=200,
            utc_now=lambda: clock[0], note_queue=editor_queue,
        )
        publish_task = asyncio.create_task(publisher.publish_due())
        await asyncio.wait_for(queue_locked.wait(), timeout=5)
        delete_task = asyncio.create_task(editor.delete_item(content_id))
        await asyncio.wait_for(editor_entered.wait(), timeout=5)
        release_publisher.set()
        results = await asyncio.wait_for(asyncio.gather(publish_task, delete_task), timeout=5)
        assert results == [slug, None]
    async with session_factory() as session:
        assert await session.get(ContentItem, content_id) is None
        tombstone = await session.scalar(select(NewsNoteQueue).where(NewsNoteQueue.note_slug == slug))
        assert tombstone.content_id is None and tombstone.status == "published"
