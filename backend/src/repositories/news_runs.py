"""Collection histories scoped to a source and durable job."""

from datetime import datetime, timezone

from sqlalchemy import exists, func, select
from sqlalchemy.orm import joinedload

from src.db.models.news_analyses import NewsAnalysis
from src.db.models.news_jobs import NewsJob, NewsSourceRun
from src.db.models.news_run_items import NewsRunItem
from src.db.models.news_sources import NewsSource
from src.exceptions.news import NewsSourceChangedError
from src.repositories.news_base import NewsRepository


class NewsRunRepository(NewsRepository):
    async def first_completed_at(self, source_id: int) -> datetime | None:
        """Recover the initial collection boundary for sources created before cursors stored it."""
        async with self.operation():
            return await self.db_session.scalar(
                select(func.min(NewsSourceRun.started_at)).where(
                    NewsSourceRun.source_id == source_id,
                    NewsSourceRun.status == "completed",
                )
            )

    async def begin(
        self, source_id: int, job_id: int | None, *, owner_token: str | None = None,
        parameters: dict | None = None,
    ) -> NewsSourceRun:
        """Record a collection attempt before any network operation."""
        async with self.operation():
            if owner_token is not None:
                await self.fence(job_id, owner_token)
            source = await self.db_session.get(NewsSource, source_id)
            if source is None:
                raise NewsSourceChangedError("Source is unavailable at collection start")
            row = NewsSourceRun(
                source_id=source_id, job_id=job_id, source_name=source.name,
                source_slug=source.slug, source_url=source.url, source_kind=source.kind,
                parameters=parameters or {},
            )
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
        skipped_count: int = 0,
        warning_count: int = 0,
        not_modified: bool = False,
        http_status: int | None = None,
        limit_reached: bool = False,
        diagnostics_truncated: bool = False,
        parameters: dict | None = None,
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
                row.skipped_count, row.warning_count = skipped_count, warning_count
                row.not_modified, row.http_status = not_modified, http_status
                row.limit_reached, row.diagnostics_truncated = limit_reached, diagnostics_truncated
                if parameters is not None:
                    row.parameters = {**row.parameters, **parameters}
            await self.db_session.commit()

    async def list_page(
        self, page: int, page_size: int, source_id: int | None = None, *,
        source_slug: str | None = None, job_id: int | None = None,
    ) -> tuple[list[NewsSourceRun], int]:
        """Read a stable page of run history."""
        async with self.operation():
            statement = select(NewsSourceRun).options(joinedload(NewsSourceRun.job))
            if source_id is not None:
                statement = statement.where(NewsSourceRun.source_id == source_id)
            if source_slug is not None:
                statement = statement.where(NewsSourceRun.source_slug == source_slug)
            if job_id is not None:
                statement = statement.where(NewsSourceRun.job_id == job_id)
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

    async def list_items(
        self, job_id: int, *, page: int, page_size: int,
        outcome: str | None = None, warnings_only: bool = False,
        source_slug: str | None = None,
    ) -> tuple[list[tuple[NewsRunItem, NewsJob | None, bool]], int]:
        """Read bounded observations and analysis state for each observed content version."""
        async with self.operation():
            latest_job_id = (
                select(NewsJob.id).where(
                    NewsJob.kind == "analyze", NewsJob.item_id == NewsRunItem.item_id,
                    NewsJob.payload["content_hash"].astext == NewsRunItem.content_hash,
                ).order_by(NewsJob.id.desc()).limit(1).correlate(NewsRunItem).scalar_subquery()
            )
            analyzed = exists(select(NewsAnalysis.id).where(
                NewsAnalysis.item_id == NewsRunItem.item_id,
                NewsAnalysis.content_hash == NewsRunItem.content_hash,
            )).correlate(NewsRunItem)
            statement = (
                select(NewsRunItem, NewsJob, analyzed)
                .join(NewsSourceRun, NewsRunItem.run_id == NewsSourceRun.id)
                .outerjoin(NewsJob, NewsJob.id == latest_job_id)
                .where(NewsSourceRun.job_id == job_id)
                .options(joinedload(NewsRunItem.run))
            )
            if outcome is not None:
                statement = statement.where(NewsRunItem.outcome == outcome)
            if warnings_only:
                statement = statement.where(NewsRunItem.warning.is_not(None))
            if source_slug is not None:
                statement = statement.where(NewsSourceRun.source_slug == source_slug)
            total = await self.db_session.scalar(select(func.count()).select_from(statement.subquery()))
            rows = (await self.db_session.execute(
                statement.order_by(NewsRunItem.run_id, NewsRunItem.id)
                .offset((page - 1) * page_size).limit(page_size)
            )).all()
            return [(row[0], row[1], bool(row[2])) for row in rows], total or 0
