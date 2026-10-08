"""Collection histories scoped to a source and durable job."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from src.db.models.news_jobs import NewsSourceRun
from src.repositories.news_base import NewsRepository


class NewsRunRepository(NewsRepository):
    async def begin(
        self, source_id: int, job_id: int | None, *, owner_token: str | None = None
    ) -> NewsSourceRun:
        """Record a collection attempt before any network operation."""
        async with self.operation():
            if owner_token is not None:
                await self.fence(job_id, owner_token)
            row = NewsSourceRun(source_id=source_id, job_id=job_id)
            self.db_session.add(row)
            await self.db_session.commit()
            return row

    async def finish(
        self,
        run_id: int,
        status: str,
        *,
        new_count: int = 0,
        updated_count: int = 0,
        unchanged_count: int = 0,
        error: str | None = None,
        job_id: int | None = None,
        owner_token: str | None = None,
    ) -> None:
        """Commit run counters for the current owner only when a fence is supplied."""
        async with self.operation():
            await self.fence(job_id, owner_token)
            row = await self.db_session.get(NewsSourceRun, run_id, with_for_update=True)
            if row is not None:
                row.status, row.completed_at = status, datetime.now(timezone.utc)
                row.new_count, row.updated_count, row.unchanged_count = (
                    new_count,
                    updated_count,
                    unchanged_count,
                )
                row.error = error[:500] if error else None
            await self.db_session.commit()

    async def list_page(
        self, page: int, page_size: int, source_id: int | None = None
    ) -> tuple[list[NewsSourceRun], int]:
        """Read a stable page of run history."""
        async with self.operation():
            statement = select(NewsSourceRun).options(joinedload(NewsSourceRun.source))
            if source_id is not None:
                statement = statement.where(NewsSourceRun.source_id == source_id)
            total = await self.db_session.scalar(
                select(func.count()).select_from(statement.subquery())
            )
            rows = list(
                (
                    await self.db_session.scalars(
                        statement.order_by(
                            NewsSourceRun.started_at.desc(), NewsSourceRun.id.desc()
                        )
                        .offset((page - 1) * page_size)
                        .limit(page_size)
                    )
                ).all()
            )
            return rows, total or 0
