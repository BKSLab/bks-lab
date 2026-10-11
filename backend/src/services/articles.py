"""Article use-cases: lists with filters/search, latest, detail."""

import logging

from src.db.models import ContentItem
from src.exceptions.content import ArticleNotFoundError
from src.repositories.content_items import ContentItemRepository
from src.schemas.articles import DEFAULT_OG_IMAGE, ArticleDetail, ArticleSummary, SeoMeta
from src.schemas.pagination import Paged
from src.schemas.results import DetailResult
from src.utils import markdown as md

logger = logging.getLogger(__name__)

CONTENT_TYPE = "article"


def build_article_summary(item: ContentItem) -> ArticleSummary:
    """Map a stored article to its public summary schema."""
    return ArticleSummary(
        slug=item.slug,
        title=item.title,
        excerpt=item.excerpt or "",
        category=item.category,
        published_at=item.published_at,
        reading_time=item.reading_time or 1,
        cover_image=item.cover_image or "",
        tags=list(item.tags),
    )


def build_article_detail(item: ContentItem) -> ArticleDetail:
    """Map a stored article to its public detail schema."""
    summary = build_article_summary(item)
    return ArticleDetail(
        **summary.model_dump(),
        content_html=item.content_html or "",
        seo=SeoMeta(
            title=item.seo_title or item.title,
            description=item.seo_description or item.excerpt or "",
            og_image=item.og_image or DEFAULT_OG_IMAGE,
        ),
    )


class ArticleService:
    """Use-cases for blog articles."""

    def __init__(self, articles_repository: ContentItemRepository):
        self.articles_repository = articles_repository

    async def list_articles(
        self,
        *,
        page: int,
        page_size: int,
        category: str | None,
        query: str | None,
    ) -> Paged[ArticleSummary]:
        """Return a paginated list of published articles.

        Sorting: published_at desc, slug asc. Drafts are excluded from the
        listing and from search. An unknown category yields an empty page
        (not an error).

        Args:
            page: 1-based page number; out-of-range pages return empty items.
            page_size: Items per page.
            category: Optional category slug filter.
            query: Optional case-insensitive substring search over
                title/excerpt/plain-text body.

        Returns:
            Paged envelope with ArticleSummary items.
        """
        items = await self._published_items()
        if category is not None:
            items = [item for item in items if item.category == category]
        if query is not None:
            needle = query.lower()
            items = [
                item
                for item in items
                if needle in item.title.lower()
                or needle in (item.excerpt or "").lower()
                or needle in item.content_text.lower()
            ]
        total = len(items)
        start = (page - 1) * page_size
        page_items = [build_article_summary(item) for item in items[start : start + page_size]]
        return Paged.build(items=page_items, total=total, page=page, page_size=page_size)

    async def get_latest(self, *, limit: int) -> list[ArticleSummary]:
        """Return the latest published articles for the home page."""
        items = await self._published_items()
        return [build_article_summary(item) for item in items[:limit]]

    async def get_article(self, *, slug: str) -> DetailResult[ArticleDetail]:
        """Return one published article by slug with a content hash for the ETag.

        The hash is derived from the stored HTML, so it changes exactly when
        the rendered content changes.

        Raises:
            ArticleNotFoundError: When the article is missing or is a draft.
        """
        item = await self.articles_repository.get_by_slug(CONTENT_TYPE, slug)
        if item is None or item.status == "draft":
            raise ArticleNotFoundError(slug=slug)
        return DetailResult(
            payload=build_article_detail(item),
            content_hash=md.content_hash(item.content_html or ""),
        )

    async def _published_items(self) -> list[ContentItem]:
        items = await self.articles_repository.list_by_type(
            CONTENT_TYPE, statuses=("active", "archived")
        )
        return sorted(
            items,
            key=lambda item: (-item.published_at.toordinal(), item.slug),
        )
