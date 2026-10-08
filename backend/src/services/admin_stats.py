"""Read-only statistics with explicit UTC calendar-day period semantics."""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from src.repositories.stats import StatsRepository
from src.schemas.admin import Metric, Overview, PageStatsRow, Period, ReferrerRow, TimeseriesPoint
from src.schemas.pagination import Paged


def period_bounds(now: datetime, days: int) -> tuple[datetime, datetime]:
    """Include today and the preceding days; exclude future timestamps."""
    now = now.astimezone(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=days - 1), now


def fill_timeseries(values: dict, start: datetime, end: datetime) -> list[TimeseriesPoint]:
    """Keep missing dates visible as zeroes on charts and accessible tables."""
    return [
        TimeseriesPoint(date=day, value=values.get(day, 0))
        for offset in range((end.date() - start.date()).days + 1)
        for day in [start.date() + timedelta(days=offset)]
    ]


class AdminStatsService:
    def __init__(self, *, repository: StatsRepository, utc_now: Callable[[], datetime]) -> None:
        self.repository = repository
        self.utc_now = utc_now

    async def overview(self) -> Overview:
        """Read the dashboard counters and the ten leading paths/referrer domains."""
        now = self.utc_now()
        today, end = period_bounds(now, 1)
        week, _ = period_bounds(now, 7)
        month, _ = period_bounds(now, 30)
        counts = await self.repository.get_overview_counts(today=today, week=week, month=month, end=end)
        return Overview(
            **counts,
            top_pages_30d=await self.repository.get_top_pages(month, end),
            top_referrers_30d=await self.repository.get_referrers(month, end, limit=10),
        )

    async def timeseries(self, *, metric: Metric, period: Period) -> list[TimeseriesPoint]:
        """Return daily values with a complete date range, even in an empty database."""
        start, end = period_bounds(self.utc_now(), int(period[:-1]))
        values = await self.repository.get_timeseries(start=start, end=end, metric=metric)
        return fill_timeseries(values, start, end)

    async def pages(self, *, period: Period, page: int, page_size: int) -> Paged[PageStatsRow]:
        """Page visit aggregates using summed daily, privacy-preserving uniques."""
        start, end = period_bounds(self.utc_now(), int(period[:-1]))
        rows, total = await self.repository.get_pages(start=start, end=end, page=page, page_size=page_size)
        return Paged[PageStatsRow].build(
            [PageStatsRow.model_validate(row) for row in rows], total, page, page_size
        )

    async def referrers(self, period: Period) -> list[ReferrerRow]:
        """Return the top fifty domains for the requested period."""
        start, end = period_bounds(self.utc_now(), int(period[:-1]))
        return [ReferrerRow.model_validate(row) for row in await self.repository.get_referrers(start, end)]
