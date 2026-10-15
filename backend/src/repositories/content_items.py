"""Repository for the content_items primary storage."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, cast, func, select, tuple_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ContentItem
from src.exceptions.repositories import (
    ContentItemConflictError,
    ContentItemRepositoryError,
)

logger = logging.getLogger(__name__)


class ContentItemRepository:
    """Database operations on the content_items table."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    @asynccontextmanager
    async def _operation(self) -> AsyncIterator[None]:
        """Translate storage errors; a duplicate (type, slug) is a conflict."""
        try:
            yield
        except IntegrityError as error:
            await self.db_session.rollback()
            raise ContentItemConflictError(str(error)) from error
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise ContentItemRepositoryError(str(error)) from error

    async def add(self, values: dict[str, Any]) -> ContentItem:
        """Stage an insert without committing (multi-step service writes).

        Args:
            values: Column values; must include type, slug, title, status,
                word_count and content_text.

        Returns:
            The flushed row with the generated id populated.

        Raises:
            ContentItemConflictError: On a duplicate (type, slug).
            ContentItemRepositoryError: On any other database error.
        """
        async with self._operation():
            item = ContentItem(**values)
            self.db_session.add(item)
            await self.db_session.flush()
            return item

    async def apply(self, item: ContentItem, values: dict[str, Any]) -> ContentItem:
        """Stage column values on an existing row without committing.

        Raises:
            ContentItemConflictError: On a duplicate (type, slug).
            ContentItemRepositoryError: On any other database error.
        """
        async with self._operation():
            for key, value in values.items():
                setattr(item, key, value)
            await self.db_session.flush()
            return item

    async def remove(self, item: ContentItem) -> None:
        """Stage a delete without committing; revisions cascade on commit.

        Raises:
            ContentItemRepositoryError: On any database error.
        """
        async with self._operation():
            await self.db_session.delete(item)
            await self.db_session.flush()

    async def commit(self) -> None:
        """Commit staged writes, translating constraint violations.

        Raises:
            ContentItemConflictError: On a duplicate (type, slug).
            ContentItemRepositoryError: On any other database error.
        """
        async with self._operation():
            await self.db_session.commit()

    async def create(self, values: dict[str, Any]) -> ContentItem:
        """Insert one content item and commit.

        Args:
            values: Column values; must include type, slug, title, status,
                word_count and content_text.

        Returns:
            The persisted row with server-generated fields populated.

        Raises:
            ContentItemConflictError: On a duplicate (type, slug).
            ContentItemRepositoryError: On any other database error.
        """
        item = await self.add(values)
        await self.commit()
        async with self._operation():
            await self.db_session.refresh(item)
            return item

    async def update(self, item: ContentItem, values: dict[str, Any]) -> ContentItem:
        """Apply column values to an existing row and commit.

        Args:
            item: A persistent ContentItem (e.g. from get_by_id).
            values: Column values to set.

        Returns:
            The refreshed row.

        Raises:
            ContentItemConflictError: On a duplicate (type, slug).
            ContentItemRepositoryError: On any other database error.
        """
        await self.apply(item, values)
        await self.commit()
        async with self._operation():
            await self.db_session.refresh(item)
            return item

    async def delete(self, item: ContentItem) -> None:
        """Delete a material and commit; revisions are removed by the FK cascade.

        Raises:
            ContentItemRepositoryError: On any database error.
        """
        await self.remove(item)
        await self.commit()

    async def get_by_id(self, item_id: int, *, for_update: bool = False) -> ContentItem | None:
        """Return one material by its stable database identifier.

        Raises:
            ContentItemRepositoryError: On any database error.
        """
        async with self._operation():
            if for_update:
                return await self.db_session.scalar(
                    select(ContentItem).where(ContentItem.id == item_id)
                    .with_for_update().execution_options(populate_existing=True)
                )
            return await self.db_session.get(ContentItem, item_id)

    async def note_feed(
        self, *, limit: int, before: tuple[datetime, int] | None,
        after: tuple[datetime, int] | None,
    ) -> list[ContentItem]:
        """Read a stable keyset using the publication instant and unique content ID.

        Historical notes without an actual instant use their recorded date at
        midnight UTC, preserving their existing dates without a data migration.
        """
        published = func.coalesce(
            ContentItem.published_at_time,
            cast(ContentItem.published_at, DateTime()).op("AT TIME ZONE")("UTC"),
        )
        statement = select(ContentItem).where(ContentItem.type == "note", ContentItem.status == "active")
        if before is not None:
            statement = statement.where(tuple_(published, ContentItem.id) < before)
        if after is not None:
            statement = statement.where(tuple_(published, ContentItem.id) > after)
        async with self._operation():
            return list(await self.db_session.scalars(
                statement.order_by(published.desc(), ContentItem.id.desc()).limit(limit + 1)
            ))

    async def get_by_slug(self, content_type: str, slug: str) -> ContentItem | None:
        """Return one material by type and slug, or None when missing.

        Raises:
            ContentItemRepositoryError: On any database error.
        """
        async with self._operation():
            result = await self.db_session.scalars(
                select(ContentItem).where(
                    ContentItem.type == content_type,
                    ContentItem.slug == slug,
                )
            )
            return result.one_or_none()

    async def list_by_type(
        self, content_type: str, *, statuses: tuple[str, ...] | None = None
    ) -> list[ContentItem]:
        """Return all materials of a type, optionally filtered by status.

        Sorting is left to the caller: articles, notes and projects each
        have their own public ordering rules.

        Args:
            content_type: Content type (article | note | project).
            statuses: When given, only rows with these statuses are returned.

        Raises:
            ContentItemRepositoryError: On any database error.
        """
        statement = select(ContentItem).where(ContentItem.type == content_type)
        if statuses is not None:
            statement = statement.where(ContentItem.status.in_(statuses))
        async with self._operation():
            result = await self.db_session.scalars(statement)
            return list(result)

    async def get_page(
        self, *, content_type: str | None, status: str | None, query: str | None,
        page: int, page_size: int,
    ) -> tuple[list[ContentItem], int]:
        """Read admin rows with literal case-insensitive title matching.

        Returns:
            Tuple of the page slice (published_at desc nulls last, id desc)
            and the total number of rows matching the filters.

        Raises:
            ContentItemRepositoryError: On any database error.
        """
        statement = select(ContentItem)
        if content_type:
            statement = statement.where(ContentItem.type == content_type)
        if status:
            statement = statement.where(ContentItem.status == status)
        if query:
            statement = statement.where(ContentItem.title.icontains(query, autoescape=True))
        async with self._operation():
            total = await self.db_session.scalar(select(func.count()).select_from(statement.subquery()))
            result = await self.db_session.scalars(
                statement.order_by(ContentItem.published_at.desc().nulls_last(), ContentItem.id.desc())
                .offset((page - 1) * page_size).limit(page_size)
            )
            return list(result), int(total or 0)
