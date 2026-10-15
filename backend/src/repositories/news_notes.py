"""Short atomic queue transactions; no provider or frontend calls run here."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert

from src.db.models import ContentItem, NewsAnalysis, NewsItem, NewsNoteQueue, NewsNoteSetting, NewsSource
from src.repositories.news_base import NewsRepository


class NewsNoteRepository(NewsRepository):
    """Persistence and locks for the automatic-note aggregate."""

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        """Commit the complete service use-case or roll it back on any failure."""
        async with self.operation():
            try:
                yield
                await self.db_session.commit()
            except BaseException:
                await self.db_session.rollback()
                raise

    async def lock_settings(self) -> NewsNoteSetting:
        """Serialize queue mutation/publication before taking item or content locks."""
        await self.db_session.execute(insert(NewsNoteSetting).values(id=1).on_conflict_do_nothing())
        return await self.db_session.scalar(
            select(NewsNoteSetting).where(NewsNoteSetting.id == 1)
            .with_for_update().execution_options(populate_existing=True)
        )

    async def settings(self) -> NewsNoteSetting | None:
        """Read settings without creating state on a read-only request."""
        async with self.operation():
            return await self.db_session.get(NewsNoteSetting, 1)

    async def lock_for_content(self, content_id: int) -> None:
        """Lock a linked queue before the editor takes a content lock.

        ON DELETE SET NULL also locks the queue. Content-first deletion would
        invert the publisher's settings -> queue -> content lock order.
        """
        async with self.operation():
            queue_id = await self.db_session.scalar(select(NewsNoteQueue.id).where(NewsNoteQueue.content_id == content_id))
            if queue_id is not None:
                await self.lock_settings()
                await self.db_session.scalar(select(NewsNoteQueue.id).where(NewsNoteQueue.id == queue_id).with_for_update())

    async def counts(self) -> dict[str, int]:
        """Count queue dispositions for the administration screen."""
        async with self.operation():
            rows = await self.db_session.execute(
                select(NewsNoteQueue.status, func.count()).group_by(NewsNoteQueue.status)
            )
            return dict(rows.all())

    async def analysis_source(self, analysis_id: int):
        """Lock the live item while reading its saved analysis and trusted source."""
        return (await self.db_session.execute(
            select(NewsItem, NewsAnalysis, NewsSource)
            .join(NewsAnalysis, NewsAnalysis.item_id == NewsItem.id)
            .join(NewsSource, NewsSource.id == NewsItem.source_id)
            .where(NewsAnalysis.id == analysis_id)
            .with_for_update(of=NewsItem).execution_options(populate_existing=True)
        )).one_or_none()

    async def identity_exists(self, source_key: str, external_key: str | None, item_id: int) -> bool:
        """Check permanent identities as well as the retained raw item reference."""
        conditions = [NewsNoteQueue.source_key == source_key, NewsNoteQueue.source_item_id == item_id]
        if external_key is not None:
            conditions.append(NewsNoteQueue.external_key == external_key)
        return await self.db_session.scalar(select(NewsNoteQueue.id).where(or_(*conditions)).limit(1)) is not None

    async def add(self, values: dict[str, Any]) -> NewsNoteQueue:
        """Stage one permanent identity and draft reference without committing."""
        row = NewsNoteQueue(**values)
        self.db_session.add(row)
        await self.db_session.flush()
        return row

    async def queued(self) -> list[NewsNoteQueue]:
        """Lock a bounded oldest-first batch; the singleton already fences workers."""
        return list(await self.db_session.scalars(
            select(NewsNoteQueue).where(NewsNoteQueue.status == "queued")
            .order_by(NewsNoteQueue.created_at, NewsNoteQueue.id).limit(200)
            .with_for_update().execution_options(populate_existing=True)
        ))

    async def lock_content(self, content_id: int | None) -> ContentItem | None:
        """Serialize publishing and queue edits with saves in the content editor."""
        if content_id is None:
            return None
        return await self.db_session.scalar(
            select(ContentItem).where(ContentItem.id == content_id)
            .with_for_update().execution_options(populate_existing=True)
        )

    async def lock_item(self, item_id: int | None) -> NewsItem | None:
        """Fence publication against concurrent raw content updates."""
        if item_id is None:
            return None
        return await self.db_session.scalar(
            select(NewsItem).where(NewsItem.id == item_id)
            .with_for_update().execution_options(populate_existing=True)
        )

    async def analysis(self, analysis_id: int | None) -> NewsAnalysis | None:
        """Read an analysis referenced by the locked raw item."""
        return await self.db_session.get(NewsAnalysis, analysis_id) if analysis_id is not None else None

    async def lock_slug(self, slug: str) -> NewsNoteQueue | None:
        """Lock one queue row after locking the shared settings row."""
        return await self.db_session.scalar(
            select(NewsNoteQueue).where(NewsNoteQueue.note_slug == slug)
            .with_for_update().execution_options(populate_existing=True)
        )

    async def page(self, status: str, page: int, page_size: int):
        """Read bounded queue rows with live editor text, retaining deleted snapshots."""
        async with self.operation():
            total = await self.db_session.scalar(
                select(func.count()).select_from(NewsNoteQueue).where(NewsNoteQueue.status == status)
            )
            rows = (await self.db_session.execute(
                select(NewsNoteQueue, ContentItem).outerjoin(ContentItem, ContentItem.id == NewsNoteQueue.content_id)
                .where(NewsNoteQueue.status == status)
                .order_by(NewsNoteQueue.created_at.desc(), NewsNoteQueue.id.desc())
                .offset((page - 1) * page_size).limit(page_size)
            )).all()
            return rows, int(total or 0)
