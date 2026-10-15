"""Note use-cases: feed with pagination and latest notes."""

import logging
import base64
import binascii
import json
from datetime import datetime, time, timezone

from src.db.models import ContentItem
from src.repositories.content_items import ContentItemRepository
from src.schemas.notes import Note, NoteFeed, RelatedArticle
from src.schemas.pagination import Paged
from src.exceptions.news import NewsValidationError

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

    async def get_feed(self, *, limit: int, before: str | None, after: str | None) -> NoteFeed:
        """Return one stable keyset page, or check notes newer than a known cursor."""
        if before is not None and after is not None:
            raise NewsValidationError
        rows = await self.notes_repository.note_feed(
            limit=limit, before=self._decode_cursor(before) if before is not None else None,
            after=self._decode_cursor(after) if after is not None else None,
        )
        has_more = len(rows) > limit
        items = rows[:limit]
        return NoteFeed(
            items=[await self._build_note(item) for item in items], has_more=has_more,
            next_cursor=self._cursor(items[-1]) if has_more and items else None,
            newest_cursor=self._cursor(items[0]) if items else None,
        )

    @staticmethod
    def _publication_time(item: ContentItem) -> datetime:
        return item.published_at_time or datetime.combine(item.published_at, time.min, timezone.utc)

    @classmethod
    def _cursor(cls, item: ContentItem) -> str:
        value = json.dumps([1, cls._publication_time(item).isoformat(), item.id], separators=(",", ":"))
        return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(value: str) -> tuple[datetime, int]:
        try:
            if not 1 <= len(value) <= 250:
                raise ValueError("Invalid cursor length")
            decoded = json.loads(base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True))
            if not isinstance(decoded, list) or len(decoded) != 3 or type(decoded[0]) is not int or decoded[0] != 1:
                raise ValueError("Invalid cursor version")
            instant = datetime.fromisoformat(decoded[1])
            if instant.tzinfo is None or type(decoded[2]) is not int or not 1 <= decoded[2] <= 2_147_483_647:
                raise ValueError("Invalid cursor identity")
            return instant.astimezone(timezone.utc), decoded[2]
        except (ValueError, TypeError, IndexError, OverflowError, binascii.Error, UnicodeError) as error:
            raise NewsValidationError from error

    async def _published_items(self) -> list[ContentItem]:
        items = await self.notes_repository.list_by_type("note", statuses=("active",))
        return sorted(
            items,
            key=lambda item: (self._publication_time(item), item.id or 0), reverse=True,
        )

    async def _build_note(self, item: ContentItem) -> Note:
        return Note(
            slug=item.slug,
            title=item.title,
            excerpt=item.excerpt or "",
            published_at=item.published_at,
            published_at_time=item.published_at_time,
            source_name=item.source_name,
            source_url=item.source_url,
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
