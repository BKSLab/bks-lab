"""Repository for the media_files table (uploaded images)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import MediaFile
from src.exceptions.repositories import MediaFileRepositoryError


class MediaFileRepository:
    """Database operations on the media_files table."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    @asynccontextmanager
    async def _operation(self) -> AsyncIterator[None]:
        """Translate storage errors into the repository error type."""
        try:
            yield
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise MediaFileRepositoryError(str(error)) from error

    async def add(self, values: dict[str, Any]) -> MediaFile:
        """Insert one media file row and commit.

        Raises:
            MediaFileRepositoryError: On any database error (including a
                duplicate path).
        """
        async with self._operation():
            media = MediaFile(**values)
            self.db_session.add(media)
            await self.db_session.commit()
            await self.db_session.refresh(media)
            return media

    async def list_all(self, *, limit: int = 200) -> list[MediaFile]:
        """Return uploaded files, newest first, bounded by limit.

        Raises:
            MediaFileRepositoryError: On any database error.
        """
        async with self._operation():
            result = await self.db_session.scalars(
                select(MediaFile).order_by(MediaFile.id.desc()).limit(limit)
            )
            return list(result)

    async def get_by_id(self, media_id: int) -> MediaFile | None:
        """Return one media file by id, or None when missing.

        Raises:
            MediaFileRepositoryError: On any database error.
        """
        async with self._operation():
            return await self.db_session.get(MediaFile, media_id)

    async def delete(self, media: MediaFile) -> None:
        """Delete one row and commit; removing the file itself is the caller's job.

        Raises:
            MediaFileRepositoryError: On any database error.
        """
        async with self._operation():
            await self.db_session.delete(media)
            await self.db_session.commit()
