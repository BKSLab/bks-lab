"""Repository for the content_revisions version history."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ContentRevision
from src.exceptions.repositories import (
    ContentRevisionConflictError,
    ContentRevisionRepositoryError,
)

logger = logging.getLogger(__name__)


class ContentRevisionRepository:
    """Database operations on the content_revisions table."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    @asynccontextmanager
    async def _operation(self) -> AsyncIterator[None]:
        """Translate storage errors; a duplicate (item_id, revision_no) is a conflict."""
        try:
            yield
        except IntegrityError as error:
            await self.db_session.rollback()
            raise ContentRevisionConflictError(str(error)) from error
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise ContentRevisionRepositoryError(str(error)) from error

    async def add(
        self, *, item_id: int, snapshot: dict[str, Any], word_count: int
    ) -> ContentRevision:
        """Stage the next revision of a material without committing.

        The revision number is max(existing) + 1 within the material; the
        unique (item_id, revision_no) index guards against concurrent saves.

        Args:
            item_id: Material the snapshot belongs to.
            snapshot: All editable fields, including content_markdown.
            word_count: Word count at save time.

        Returns:
            The flushed revision.

        Raises:
            ContentRevisionConflictError: On a revision number race.
            ContentRevisionRepositoryError: On any other database error.
        """
        async with self._operation():
            last = await self.db_session.scalar(
                select(func.max(ContentRevision.revision_no)).where(
                    ContentRevision.item_id == item_id
                )
            )
            revision = ContentRevision(
                item_id=item_id,
                revision_no=(last or 0) + 1,
                snapshot=snapshot,
                word_count=word_count,
            )
            self.db_session.add(revision)
            await self.db_session.flush()
            return revision

    async def commit(self) -> None:
        """Commit staged writes, translating constraint violations.

        Raises:
            ContentRevisionConflictError: On a revision number race.
            ContentRevisionRepositoryError: On any other database error.
        """
        async with self._operation():
            await self.db_session.commit()

    async def create(
        self, *, item_id: int, snapshot: dict[str, Any], word_count: int
    ) -> ContentRevision:
        """Append the next revision of a material and commit.

        Args:
            item_id: Material the snapshot belongs to.
            snapshot: All editable fields, including content_markdown.
            word_count: Word count at save time.

        Returns:
            The persisted revision.

        Raises:
            ContentRevisionConflictError: On a revision number race.
            ContentRevisionRepositoryError: On any other database error.
        """
        revision = await self.add(item_id=item_id, snapshot=snapshot, word_count=word_count)
        await self.commit()
        async with self._operation():
            await self.db_session.refresh(revision)
            return revision

    async def list_for_item(self, item_id: int) -> list[ContentRevision]:
        """Return all revisions of a material, newest first.

        Raises:
            ContentRevisionRepositoryError: On any database error.
        """
        async with self._operation():
            result = await self.db_session.scalars(
                select(ContentRevision)
                .where(ContentRevision.item_id == item_id)
                .order_by(ContentRevision.revision_no.desc())
            )
            return list(result)

    async def get(self, item_id: int, revision_no: int) -> ContentRevision | None:
        """Return one revision of a material, or None when missing.

        Raises:
            ContentRevisionRepositoryError: On any database error.
        """
        async with self._operation():
            result = await self.db_session.scalars(
                select(ContentRevision).where(
                    ContentRevision.item_id == item_id,
                    ContentRevision.revision_no == revision_no,
                )
            )
            return result.one_or_none()
