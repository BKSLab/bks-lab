"""Read the Markdown projection, including drafts, and attach visit statistics."""

from collections.abc import Callable
from datetime import datetime

from src.exceptions.admin import AdminContentNotFoundError
from src.repositories.content_items import ContentItemRepository
from src.repositories.markdown_content import MarkdownContentRepository
from src.repositories.stats import StatsRepository
from src.schemas.admin import ContentItemDetail, ContentItemRow, ContentStatus, ContentType
from src.schemas.pagination import Paged
from src.services.admin_stats import fill_timeseries, period_bounds


class AdminContentService:
    def __init__(
        self, *, repository: ContentItemRepository, stats: StatsRepository,
        sources: tuple[MarkdownContentRepository, ...], utc_now: Callable[[], datetime],
    ) -> None:
        self.repository = repository
        self.stats = stats
        self.sources = sources
        self.utc_now = utc_now

    async def _refresh(self) -> None:
        for source in self.sources:
            await source.ensure_fresh()

    @staticmethod
    def _path(content_type: str, slug: str) -> str:
        prefix = "/blog/post/" if content_type == "article" else "/projects/"
        return f"{prefix}{slug}"

    async def get_page(
        self, *, content_type: ContentType | None, status: ContentStatus | None,
        query: str | None, page: int, page_size: int,
    ) -> Paged[ContentItemRow]:
        """Synchronize Markdown before reading so first admin visits see all drafts."""
        await self._refresh()
        rows, total = await self.repository.get_page(
            content_type=content_type, status=status, query=query.strip() if query else None,
            page=page, page_size=page_size,
        )
        start, end = period_bounds(self.utc_now(), 30)
        path_counts, note_counts = await self.stats.get_content_views(
            start=start, end=end,
            paths=[self._path(row.type, row.slug) for row in rows if row.type != "note"],
            note_slugs=[row.slug for row in rows if row.type == "note"],
        )
        items = [
            ContentItemRow.model_validate(row).model_copy(update={
                "views_30d": note_counts.get(row.slug, 0) if row.type == "note"
                else path_counts.get(self._path(row.type, row.slug), 0)
            })
            for row in rows
        ]
        return Paged[ContentItemRow].build(items, total, page, page_size)

    async def get_detail(self, item_id: int) -> ContentItemDetail:
        """Read a material and count note views consistently across feed pages."""
        await self._refresh()
        row = await self.repository.get_by_id(item_id)
        if row is None:
            raise AdminContentNotFoundError
        start, end = period_bounds(self.utc_now(), 30)
        values = await self.stats.get_timeseries(
            start=start, end=end, metric="views",
            path=self._path(row.type, row.slug) if row.type != "note" else None,
            note_slug=row.slug if row.type == "note" else None,
        )
        return ContentItemDetail(
            **ContentItemRow.model_validate(row).model_dump(exclude={"views_30d"}),
            views_30d=sum(values.values()), synced_at=row.synced_at, content_hash=row.content_hash,
            views_timeseries_30d=fill_timeseries(values, start, end),
        )
