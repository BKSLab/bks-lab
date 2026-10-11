"""Note use-cases: feed with pagination and latest notes."""

import logging

from src.db.models import ContentItem
from src.repositories.content_items import ContentItemRepository
from src.schemas.notes import Note, RelatedArticle
from src.schemas.pagination import Paged

logger = logging.getLogger(__name__)


class NoteService:
    """Use-cases for short notes (the /notes feed)."""

    def __init__(
        self,
        notes_repository: ContentItemRepository,
        articles_repository: ContentItemRepository,
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

    async def _published_items(self) -> list[ContentItem]:
        items = await self.notes_repository.list_by_type("note", statuses=("active", "archived"))
        return sorted(
            items,
            key=lambda item: (-item.published_at.toordinal(), item.slug),
        )

    async def _build_note(self, item: ContentItem) -> Note:
        return Note(
            slug=item.slug,
            title=item.title,
            excerpt=item.excerpt or "",
            published_at=item.published_at,
            reading_time=item.reading_time or 1,
            tags=list(item.tags),
            related_article=await self._resolve_related(item),
            content_html=item.content_html or "",
        )

    async def _resolve_related(self, item: ContentItem) -> RelatedArticle | None:
        """Resolve the optional related article slug; broken links degrade to null."""
        if not item.related_slug:
            return None
        related = await self.articles_repository.get_by_slug("article", item.related_slug)
        if related is None or related.status == "draft":
            logger.warning(
                "Note references a missing or draft article: %s", item.related_slug
            )
            return None
        return RelatedArticle(slug=related.slug, title=related.title)
