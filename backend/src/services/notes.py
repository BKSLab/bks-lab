"""Note use-cases: feed with pagination and latest notes."""

import logging
from typing import cast

from src.repositories.markdown_content import MarkdownContentRepository, ParsedContent
from src.schemas.frontmatter import NoteFrontmatter
from src.schemas.notes import Note, RelatedArticle
from src.schemas.pagination import Paged

logger = logging.getLogger(__name__)


def _fm(item: ParsedContent) -> NoteFrontmatter:
    return cast(NoteFrontmatter, item.frontmatter)


class NoteService:
    """Use-cases for short notes (the /notes feed)."""

    def __init__(
        self,
        notes_repository: MarkdownContentRepository,
        articles_repository: MarkdownContentRepository,
    ):
        self.notes_repository = notes_repository
        self.articles_repository = articles_repository

    async def list_notes(self, *, page: int, page_size: int) -> Paged[Note]:
        """Return a paginated feed of published notes (newest first)."""
        items = await self._published_items()
        total = len(items)
        start = (page - 1) * page_size
        page_items = [await self._build_note(item) for item in items[start : start + page_size]]
        return Paged.build(items=page_items, total=total, page=page, page_size=page_size)

    async def get_latest(self, *, limit: int) -> list[Note]:
        """Return the latest published notes for the home page and sidebar."""
        items = await self._published_items()
        return [await self._build_note(item) for item in items[:limit]]

    async def _published_items(self) -> list[ParsedContent]:
        items = await self.notes_repository.get_all()
        published = [item for item in items if item.status != "draft"]
        return sorted(
            published,
            key=lambda item: (-_fm(item).published_at.toordinal(), item.slug),
        )

    async def _build_note(self, item: ParsedContent) -> Note:
        frontmatter = _fm(item)
        return Note(
            slug=item.slug,
            title=frontmatter.title,
            excerpt=item.excerpt,
            published_at=frontmatter.published_at,
            reading_time=item.reading_time or 1,
            tags=frontmatter.tags,
            related_article=await self._resolve_related(frontmatter),
            content_html=item.content_html,
        )

    async def _resolve_related(self, frontmatter: NoteFrontmatter) -> RelatedArticle | None:
        """Resolve the optional related article slug; broken links degrade to null."""
        if not frontmatter.related:
            return None
        related = await self.articles_repository.get_by_slug(frontmatter.related)
        if related is None or related.status == "draft":
            logger.warning(
                "Note references a missing or draft article: %s", frontmatter.related
            )
            return None
        return RelatedArticle(slug=related.slug, title=related.frontmatter.title)
