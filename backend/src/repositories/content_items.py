"""Repository for the content_items read-model projection."""

import logging
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ContentItem
from src.exceptions.repositories import ContentItemRepositoryError

if TYPE_CHECKING:
    from src.repositories.markdown_content import ParsedContent

logger = logging.getLogger(__name__)


class ContentItemRepository:
    """Database operations on the content_items table."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def sync_type(
        self, content_type: str, items: list["ParsedContent"]
    ) -> None:
        """Replace the projection of one content type in a single transaction.

        Rows whose content_hash is unchanged are left untouched (synced_at is
        not bumped); new and changed rows are upserted; rows whose files
        disappeared or became invalid are deleted.

        Args:
            content_type: Content type being synced (article | note | project).
            items: ParsedContent items currently valid on disk.

        Raises:
            ContentItemRepositoryError: On any database error (after rollback).
        """
        try:
            result = await self.db_session.execute(
                select(ContentItem).where(ContentItem.type == content_type)
            )
            existing = {row.slug: row for row in result.scalars()}
            inserted = updated = 0
            for item in items:
                row = existing.pop(item.slug, None)
                if row is None:
                    self.db_session.add(self._build_row(item))
                    inserted += 1
                elif row.content_hash != item.content_hash:
                    self._update_row(row, item)
                    updated += 1
            for stale_slug, stale_row in existing.items():
                await self.db_session.delete(stale_row)
                logger.info(
                    "Removing stale %s projection row: %s", content_type, stale_slug
                )
            await self.db_session.commit()
            logger.info(
                "Projection sync for %s: %d inserted, %d updated, %d deleted, %d unchanged",
                content_type,
                inserted,
                updated,
                len(existing),
                len(items) - inserted - updated,
            )
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise ContentItemRepositoryError(str(error)) from error

    def _build_row(self, item: "ParsedContent") -> ContentItem:
        frontmatter = item.frontmatter
        return ContentItem(
            type=item.content_type,
            slug=item.slug,
            title=frontmatter.title,
            category=getattr(frontmatter, "category", None),
            tags=list(getattr(frontmatter, "tags", []) or []),
            published_at=getattr(frontmatter, "published_at", None),
            reading_time=item.reading_time,
            status=item.status,
            word_count=item.word_count,
            content_text=item.content_text,
            content_hash=item.content_hash,
        )

    def _update_row(self, row: ContentItem, item: "ParsedContent") -> None:
        fresh = self._build_row(item)
        row.title = fresh.title
        row.category = fresh.category
        row.tags = fresh.tags
        row.published_at = fresh.published_at
        row.reading_time = fresh.reading_time
        row.status = fresh.status
        row.word_count = fresh.word_count
        row.content_text = fresh.content_text
        row.content_hash = fresh.content_hash

    async def delete_type(self, content_type: str) -> None:
        """Delete all projection rows of a type (used by tests and tooling).

        Raises:
            ContentItemRepositoryError: On any database error (after rollback).
        """
        try:
            await self.db_session.execute(
                delete(ContentItem).where(ContentItem.type == content_type)
            )
            await self.db_session.commit()
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise ContentItemRepositoryError(str(error)) from error

    async def get_by_type(self, content_type: str) -> list[ContentItem]:
        """Return all projection rows of a type (admin/testing helper).

        Raises:
            ContentItemRepositoryError: On any database error.
        """
        try:
            result = await self.db_session.execute(
                select(ContentItem).where(ContentItem.type == content_type)
            )
            return list(result.scalars())
        except (SQLAlchemyError, OSError) as error:
            raise ContentItemRepositoryError(str(error)) from error

    async def get_page(
        self, *, content_type: str | None, status: str | None, query: str | None,
        page: int, page_size: int,
    ) -> tuple[list[ContentItem], int]:
        """Read projection rows with literal case-insensitive title matching."""
        statement = select(ContentItem)
        if content_type:
            statement = statement.where(ContentItem.type == content_type)
        if status:
            statement = statement.where(ContentItem.status == status)
        if query:
            statement = statement.where(ContentItem.title.icontains(query, autoescape=True))
        try:
            total = await self.db_session.scalar(select(func.count()).select_from(statement.subquery()))
            result = await self.db_session.scalars(
                statement.order_by(ContentItem.published_at.desc().nulls_last(), ContentItem.id.desc())
                .offset((page - 1) * page_size).limit(page_size)
            )
            return list(result), int(total or 0)
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise ContentItemRepositoryError("Content page read failed") from error

    async def get_by_id(self, item_id: int) -> ContentItem | None:
        """Return one projected material by its stable database identifier."""
        try:
            return await self.db_session.get(ContentItem, item_id)
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise ContentItemRepositoryError("Content detail read failed") from error
