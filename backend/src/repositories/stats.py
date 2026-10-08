"""Repository for the page_views event log."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, cast, func, select, tuple_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PageView
from src.exceptions.repositories import StatsRepositoryError


class StatsRepository:
    """Database operations on the page_views table."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def save_page_view(
        self,
        *,
        path: str,
        note_slug: str | None,
        referrer_domain: str | None,
        visitor_hash: str,
    ) -> None:
        """Insert one page view row.

        Raises:
            StatsRepositoryError: On any database error (after rollback).
        """
        try:
            self.db_session.add(
                PageView(
                    path=path,
                    note_slug=note_slug,
                    referrer_domain=referrer_domain,
                    visitor_hash=visitor_hash,
                )
            )
            await self.db_session.commit()
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise StatsRepositoryError(str(error)) from error

    async def _read(self, statement: Any) -> Any:
        try:
            return await self.db_session.execute(statement)
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise StatsRepositoryError("Statistics read failed") from error

    @staticmethod
    def _utc_day() -> Any:
        return cast(func.timezone("UTC", PageView.viewed_at), Date)

    @staticmethod
    def _period(start: datetime, end: datetime) -> tuple[Any, Any]:
        return PageView.viewed_at >= start, PageView.viewed_at <= end

    async def get_overview_counts(
        self, *, today: datetime, week: datetime, month: datetime, end: datetime
    ) -> dict[str, int]:
        """Aggregate dashboard counters in one scan, excluding future events."""
        result = await self._read(
            select(
                func.count().filter(PageView.viewed_at >= today).label("views_today"),
                func.count().filter(PageView.viewed_at >= week).label("views_7d"),
                func.count().label("views_30d"),
                func.count(func.distinct(PageView.visitor_hash))
                .filter(PageView.viewed_at >= today).label("uniques_today"),
            ).where(*self._period(month, end))
        )
        return dict(result.mappings().one())

    async def get_top_pages(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """Return the ten most visited paths, including anchored note visits."""
        result = await self._read(
            select(PageView.path, func.count().label("views"))
            .where(*self._period(start, end)).group_by(PageView.path)
            .order_by(func.count().desc(), PageView.path.asc()).limit(10)
        )
        return [dict(row) for row in result.mappings()]

    async def get_timeseries(
        self, *, start: datetime, end: datetime, metric: str,
        path: str | None = None, note_slug: str | None = None,
    ) -> dict[date, int]:
        """Read day buckets in UTC, independent of the database session timezone."""
        count = func.count(func.distinct(PageView.visitor_hash)) if metric == "uniques" else func.count()
        day = self._utc_day()
        statement = select(day.label("date"), count.label("value")).where(*self._period(start, end))
        if path is not None:
            statement = statement.where(PageView.path == path)
        if note_slug is not None:
            statement = statement.where(PageView.note_slug == note_slug)
        result = await self._read(statement.group_by(day).order_by(day))
        return {row.date: row.value for row in result}

    async def get_pages(
        self, *, start: datetime, end: datetime, page: int, page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Group paths and note anchors; uniques are the sum of daily uniques."""
        grouped = (
            select(
                PageView.path, PageView.note_slug,
                func.count().label("views"),
                func.count(func.distinct(tuple_(self._utc_day(), PageView.visitor_hash)))
                .label("uniques"),
            )
            .where(*self._period(start, end))
            .group_by(PageView.path, PageView.note_slug)
        )
        total = (await self._read(select(func.count()).select_from(grouped.subquery()))).scalar_one()
        result = await self._read(
            grouped.order_by(func.count().desc(), PageView.path.asc(), PageView.note_slug.asc().nulls_first())
            .offset((page - 1) * page_size).limit(page_size)
        )
        return [dict(row) for row in result.mappings()], total

    async def get_referrers(
        self, start: datetime, end: datetime, limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return the most frequent non-empty referrer domains."""
        result = await self._read(
            select(PageView.referrer_domain.label("domain"), func.count().label("views"))
            .where(*self._period(start, end), PageView.referrer_domain.is_not(None))
            .group_by(PageView.referrer_domain)
            .order_by(func.count().desc(), PageView.referrer_domain.asc()).limit(limit)
        )
        return [dict(row) for row in result.mappings()]

    async def get_content_views(
        self, *, start: datetime, end: datetime, paths: list[str], note_slugs: list[str],
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Batch counts by path and by note slug, across every paginated note feed."""
        path_counts: dict[str, int] = {}
        note_counts: dict[str, int] = {}
        if paths:
            result = await self._read(
                select(PageView.path, func.count().label("views"))
                .where(*self._period(start, end), PageView.path.in_(paths))
                .group_by(PageView.path)
            )
            path_counts = {row.path: row.views for row in result}
        if note_slugs:
            result = await self._read(
                select(PageView.note_slug, func.count().label("views"))
                .where(*self._period(start, end), PageView.note_slug.in_(note_slugs))
                .group_by(PageView.note_slug)
            )
            note_counts = {row.note_slug: row.views for row in result}
        return path_counts, note_counts
