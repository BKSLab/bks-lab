"""Article use-cases: lists with filters/search, latest, detail."""

import logging
from typing import cast

from src.exceptions.content import ArticleNotFoundError
from src.repositories.markdown_content import MarkdownContentRepository, ParsedContent
from src.schemas.articles import DEFAULT_OG_IMAGE, ArticleDetail, ArticleSummary, SeoMeta
from src.schemas.frontmatter import ArticleFrontmatter
from src.schemas.pagination import Paged
from src.schemas.results import DetailResult

logger = logging.getLogger(__name__)


def _fm(item: ParsedContent) -> ArticleFrontmatter:
    return cast(ArticleFrontmatter, item.frontmatter)


def build_article_summary(item: ParsedContent) -> ArticleSummary:
    """Map a parsed article file to its public summary schema."""
    frontmatter = _fm(item)
    return ArticleSummary(
        slug=item.slug,
        title=frontmatter.title,
        excerpt=frontmatter.excerpt,
        category=frontmatter.category,
        published_at=frontmatter.published_at,
        reading_time=item.reading_time or 1,
        cover_image=frontmatter.cover_image,
        tags=frontmatter.tags,
    )


def build_article_detail(item: ParsedContent) -> ArticleDetail:
    """Map a parsed article file to its public detail schema."""
    summary = build_article_summary(item)
    frontmatter = _fm(item)
    return ArticleDetail(
        **summary.model_dump(),
        content_html=item.content_html,
        seo=SeoMeta(
            title=frontmatter.seo_title or frontmatter.title,
            description=frontmatter.seo_description or frontmatter.excerpt,
            og_image=frontmatter.og_image or DEFAULT_OG_IMAGE,
        ),
    )


class ArticleService:
    """Use-cases for blog articles."""

    def __init__(self, articles_repository: MarkdownContentRepository):
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
            items = [item for item in items if _fm(item).category == category]
        if query is not None:
            needle = query.lower()
            items = [
                item
                for item in items
                if needle in _fm(item).title.lower()
                or needle in _fm(item).excerpt.lower()
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
        """Return one published article by slug with its content hash.

        Raises:
            ArticleNotFoundError: When the article is missing or is a draft.
        """
        item = await self.articles_repository.get_by_slug(slug)
        if item is None or item.status == "draft":
            raise ArticleNotFoundError(slug=slug)
        return DetailResult(payload=build_article_detail(item), content_hash=item.content_hash)

    async def _published_items(self) -> list[ParsedContent]:
        items = await self.articles_repository.get_all()
        published = [item for item in items if item.status != "draft"]
        return sorted(
            published,
            key=lambda item: (-_fm(item).published_at.toordinal(), item.slug),
        )
