"""Candidate admission, queue editing and paced atomic publication of notes."""

import re
from collections.abc import Callable
from datetime import datetime, timedelta
from hashlib import sha256

from pydantic import ValidationError

from src.clients.revalidation import RevalidationClient
from src.core.news_slugs import SAMARA, readable_slug
from src.db.models import ContentItem, NewsAnalysis, NewsNoteQueue
from src.exceptions.news import NewsConflictError, NewsNotFoundError, NewsValidationError
from src.repositories.content_items import ContentItemRepository
from src.repositories.content_revisions import ContentRevisionRepository
from src.repositories.news_notes import NewsNoteRepository
from src.schemas.news_collection import NEWS_MIN_CONTENT_CHARS
from src.schemas.news_notes import NoteCandidate, NoteQueuePatch, NoteQueueRow, NoteSettingsPatch, NoteSettingsRow
from src.schemas.pagination import Paged
from src.services.content_fields import ContentFields, build_item_values, build_snapshot, snapshot_of_item
from src.utils import markdown as md


def _plain_markdown(value: str) -> str:
    """Escape generated prose so it cannot become Markdown links or directives."""
    return re.sub(r"([\\`*_{}\[\]()<>#+.!|~-])", r"\\\1", value)


def _eligible(analysis: NewsAnalysis) -> bool:
    return bool(analysis.is_relevant and not analysis.needs_verification)


class NewsNoteService:
    """Use one existing analysis and one existing scheduler; never call an LLM."""

    def __init__(
        self, *, repository: NewsNoteRepository, items: ContentItemRepository,
        revisions: ContentRevisionRepository, revalidator: RevalidationClient,
        words_per_minute: int, utc_now: Callable[[], datetime],
    ) -> None:
        self.repository = repository
        self.items = items
        self.revisions = revisions
        self.revalidator = revalidator
        self.words_per_minute = words_per_minute
        self.utc_now = utc_now

    async def get_settings(self) -> NoteSettingsRow:
        """Read durable settings and queue counts, disabled before first activation."""
        state = await self.repository.settings()
        counts = await self.repository.counts()
        enabled = state.enabled if state else False
        interval = state.interval_minutes if state else 10
        last = state.last_published_at if state else None
        return NoteSettingsRow(
            enabled=enabled, interval_minutes=interval, max_age_hours=state.max_age_hours if state else 72,
            started_at=state.started_at if state else None, last_published_at=last,
            next_publish_at=(max(self.utc_now(), last + timedelta(minutes=interval)) if last else self.utc_now()) if enabled else None,
            **{status: counts.get(status, 0) for status in ("queued", "published", "excluded", "expired")},
        )

    async def update_settings(self, data: NoteSettingsPatch) -> NoteSettingsRow:
        """First activation establishes a permanent ingestion boundary; pause preserves it."""
        async with self.repository.transaction():
            state = await self.repository.lock_settings()
            values = data.model_dump(exclude_unset=True)
            if values.get("enabled") and state.started_at is None:
                state.started_at = self.utc_now()
            for key, value in values.items():
                setattr(state, key, value)
        return await self.get_settings()

    async def enqueue_analysis(self, analysis_id: int, *, job_id: int, owner_token: str) -> bool:
        """Atomically create a draft and its durable identity for a current eligible analysis."""
        async with self.repository.transaction():
            state = await self.repository.lock_settings()
            await self.repository.fence(job_id, owner_token)
            if state.started_at is None:
                return False
            record = await self.repository.analysis_source(analysis_id)
            if record is None:
                return False
            item, analysis, source = record
            if (item.first_seen_at < state.started_at or item.duplicate_of_id is not None
                or item.latest_analysis_id != analysis.id or item.content_hash != analysis.content_hash
                or not _eligible(analysis) or (item.metadata_json or {}).get("collection_warning")
                or max(len(item.content), len(item.excerpt)) < NEWS_MIN_CONTENT_CHARS):
                return False
            try:
                candidate = NoteCandidate.model_validate(analysis.note_candidate)
            except (ValidationError, ValueError, TypeError):
                return False
            source_key = sha256(item.normalized_url.encode()).hexdigest()
            external_key = sha256(f"{source.profile_id or source.slug}:{item.external_id}".encode()).hexdigest() if item.external_id else None
            if await self.repository.identity_exists(source_key, external_key, item.id):
                return False
            now = self.utc_now()
            slug = readable_slug(f"{source.slug}-{candidate.title}", fallback="news", limit=175) + "-" + source_key[:12]
            values = build_item_values("note", slug, ContentFields(
                title=candidate.title, status="draft", content_markdown=_plain_markdown(candidate.text),
                published_at=now.astimezone(SAMARA).date(),
            ), self.words_per_minute)
            values.update(excerpt=candidate.text, source_name=source.name, source_url=item.url)
            content = await self.items.add(values)
            await self.revisions.add(item_id=content.id, snapshot=build_snapshot(values), word_count=values["word_count"])
            source_age = now - (item.published_at or item.first_seen_at)
            expired = source_age > timedelta(hours=state.max_age_hours)
            await self.repository.add({
                "note_slug": slug, "content_id": content.id, "source_item_id": item.id, "analysis_id": analysis.id,
                "source_key": source_key, "external_key": external_key, "content_hash": item.content_hash,
                "title": candidate.title, "text": candidate.text, "source_name": source.name, "source_url": item.url,
                "source_published_at": item.published_at, "source_first_seen_at": item.first_seen_at,
                "created_at": now, "status": "expired" if expired else "queued",
                "reason": "Материал устарел до постановки в очередь." if expired else None,
            })
        return True

    async def list_queue(self, *, status: str, page: int, page_size: int) -> Paged[NoteQueueRow]:
        """Read live note text while preserving provenance and deletion tombstones."""
        rows, total = await self.repository.page(status, page, page_size)
        return Paged.build(items=[self._row(row, item) for row, item in rows], total=total, page=page, page_size=page_size)

    async def update_queue(self, slug: str, data: NoteQueuePatch) -> NoteQueueRow:
        """Edit the live draft and its revision; published notes use the content editor."""
        async with self.repository.transaction():
            await self.repository.lock_settings()
            row = await self.repository.lock_slug(slug)
            if row is None:
                raise NewsNotFoundError
            item = await self.repository.lock_content(row.content_id)
            if row.status == "published" or (item is not None and item.published_at_time is not None):
                raise NewsConflictError("Published notes use the content editor")
            if item is None or item.status != "draft":
                raise NewsConflictError("Note draft is unavailable")
            updates = data.model_dump(exclude_unset=True)
            if row.status == "expired" and updates.get("status") == "queued":
                raise NewsValidationError
            if "title" in updates or "text" in updates:
                title = updates.get("title", item.title)
                text = updates.get("text", item.content_text)
                # Manual queue edits need the same length bounds; the full editor
                # intentionally retains its established, more general note workflow.
                if not 1 <= len(title) <= 90 or not 1 <= len(text) <= 300:
                    raise NewsValidationError
                values = {
                    "title": title, "content_markdown": _plain_markdown(text),
                    "content_text": text,
                }
                values.update(content_html=md.render_markdown(values["content_markdown"]), excerpt=text,
                              word_count=md.count_words(text), reading_time=md.reading_time_minutes(md.count_words(text), self.words_per_minute))
                await self.items.apply(item, values)
                row.title, row.text = title, text
                await self.revisions.add(item_id=item.id, snapshot=self._snapshot(item), word_count=item.word_count)
            if "status" in updates:
                row.status = updates["status"]
                row.reason = "Исключено редактором." if row.status == "excluded" else None
            result = self._row(row, item)
        return result

    async def publish_due(self) -> str | None:
        """Publish at most one note atomically with a shared persisted interval clock."""
        published = None
        async with self.repository.transaction():
            state = await self.repository.lock_settings()
            now = self.utc_now()
            for row in await self.repository.queued():
                # All publishers take settings -> queue -> raw item -> content.
                # Analysis saving commits before queue admission takes these locks.
                raw = await self.repository.lock_item(row.source_item_id)
                item = await self.repository.lock_content(row.content_id)
                if item is None:
                    row.status, row.reason = "excluded", "Заметка удалена в редакторе."
                    continue
                if item.status == "active":
                    row.status, row.published_at_time = "published", item.published_at_time or now
                    row.reason = None
                    state.last_published_at = max(state.last_published_at or row.published_at_time, row.published_at_time)
                    continue
                age = timedelta(hours=state.max_age_hours)
                if now - (row.source_published_at or row.source_first_seen_at) > age or now - row.created_at > age:
                    row.status, row.reason = "expired", "Истёк срок свежести материала или ожидания в очереди."
                    continue
                analysis = await self.repository.analysis(raw.latest_analysis_id) if raw else None
                if (raw is None or raw.duplicate_of_id is not None or raw.content_hash != row.content_hash
                    or analysis is None or analysis.content_hash != row.content_hash
                    or not _eligible(analysis)):
                    row.status, row.reason = "excluded", "Исходный материал или его анализ изменились."
                    continue
                if item.status != "draft":
                    row.status, row.reason = "excluded", "Статус заметки изменён в редакторе."
                    continue
                if not state.enabled or state.started_at is None:
                    continue
                if state.last_published_at is not None and now < state.last_published_at + timedelta(minutes=state.interval_minutes):
                    continue
                await self.items.apply(item, {
                    "status": "active", "published_at_time": item.published_at_time or now,
                    "published_at": now.astimezone(SAMARA).date(),
                })
                await self.revisions.add(item_id=item.id, snapshot=self._snapshot(item), word_count=item.word_count)
                row.status, row.published_at_time, row.reason = "published", item.published_at_time, None
                state.last_published_at = now
                published = item.slug
                break
        if published is not None:
            await self.revalidator.revalidate_content()
        return published

    @staticmethod
    def _snapshot(item: ContentItem) -> dict:
        return snapshot_of_item(item)

    @staticmethod
    def _row(row: NewsNoteQueue, item: ContentItem | None) -> NoteQueueRow:
        return NoteQueueRow(
            note_slug=row.note_slug, content_id=row.content_id, title=item.title if item else row.title,
            text=item.content_text if item else row.text, source_name=row.source_name, source_url=row.source_url,
            status=row.status, created_at=row.created_at,
            published_at_time=(item.published_at_time if item else None) or row.published_at_time, reason=row.reason,
        )
