"""Shared transaction error boundary and lease fence for news repositories."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.news_jobs import NewsJob
from src.exceptions.news import (
    NewsConflictError,
    NewsLeaseLostError,
    NewsRepositoryError,
)


class NewsRepository:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    @asynccontextmanager
    async def operation(self) -> AsyncIterator[None]:
        """Translate storage exceptions without disclosing statements or parameters."""
        try:
            yield
        except IntegrityError as error:
            await self.db_session.rollback()
            raise NewsConflictError("News constraint conflict") from error
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise NewsRepositoryError("News storage operation failed") from error
        except NewsRepositoryError:
            await self.db_session.rollback()
            raise

    async def fence(self, job_id: int | None, owner_token: str | None) -> None:
        """Lock a valid lease until commit so recovery cannot overtake its writes."""
        if job_id is None and owner_token is None:
            return
        job = await self.db_session.scalar(
            select(NewsJob.id)
            .where(
                NewsJob.id == job_id,
                NewsJob.owner_token == owner_token,
                NewsJob.status == "running",
                NewsJob.lease_expires_at > func.now(),
            )
            .with_for_update()
        )
        if job is None:
            raise NewsLeaseLostError("Worker no longer owns the job")
