"""Markdown-file content repository with in-memory cache and DB projection sync.

One repository instance serves one content type (articles/notes/projects).
Sync protocol (docs/architecture.md section 3):

- API reads trigger a directory mtime check at most once per TTL (5 s).
- The rescan runs under an asyncio.Lock (single-flight): concurrent requests
  share one rescan and otherwise read the current cache.
- A rescan re-parses all files of the type; `content_hash` lets the DB
  projection skip unchanged rows.
- Projection update is a single transaction (upsert changed + delete gone).
  On a database error the in-memory cache is NOT updated, so the cache and
  the projection never diverge; the retry happens on the next TTL trigger.
- Files that fail frontmatter validation are excluded from the cache and
  removed from the projection; the error is logged.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISREG

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.exceptions.repositories import (
    ContentItemRepositoryError,
    ContentRepositoryError,
    RepositoryError,
)
from src.repositories.content_items import ContentItemRepository
from src.schemas.frontmatter import ArticleFrontmatter, NoteFrontmatter, ProjectFrontmatter
from src.utils import markdown as md

logger = logging.getLogger(__name__)

ContentType = str


@dataclass(frozen=True)
class ParsedContent:
    """One fully parsed and validated Markdown content file."""

    content_type: ContentType
    slug: str
    frontmatter: ArticleFrontmatter | NoteFrontmatter | ProjectFrontmatter
    status: str
    content_html: str
    content_text: str
    excerpt: str
    word_count: int
    reading_time: int | None
    content_hash: str


def resolve_status(
    frontmatter: ArticleFrontmatter | NoteFrontmatter | ProjectFrontmatter,
) -> str:
    """Map frontmatter flags to the projection status (docs/content_format.md)."""
    if frontmatter.draft:
        return "draft"
    if getattr(frontmatter, "status", None) == "archived":
        return "archived"
    return "active"


def resolve_reading_time(
    frontmatter: ArticleFrontmatter | NoteFrontmatter | ProjectFrontmatter,
    word_count: int,
    words_per_minute: int,
) -> int | None:
    """Compute reading time: frontmatter override wins; projects have none."""
    override = getattr(frontmatter, "reading_time", None)
    if override is not None:
        return override
    if not hasattr(frontmatter, "published_at"):
        return None
    return md.reading_time_minutes(word_count, words_per_minute)


class MarkdownContentRepository:
    """Repository over a directory of Markdown files for one content type."""

    def __init__(
        self,
        *,
        content_dir: Path,
        content_type: ContentType,
        frontmatter_model: type[BaseModel],
        session_factory: async_sessionmaker[AsyncSession],
        ttl_seconds: float,
        words_per_minute: int,
    ):
        self._content_dir = content_dir
        self._content_type = content_type
        self._frontmatter_model = frontmatter_model
        self._session_factory = session_factory
        self._ttl_seconds = ttl_seconds
        self._words_per_minute = words_per_minute
        self._lock = asyncio.Lock()
        self._cache: dict[str, ParsedContent] = {}
        self._last_check: float | None = None
        self._last_signature: tuple[tuple[str, int, int, int], ...] | None = None
        self._last_error: RepositoryError | None = None

    # Public read API

    async def get_all(self) -> list[ParsedContent]:
        """Return all valid items of the type (including drafts/archived).

        Returns:
            Parsed items keyed by nothing (list); callers apply visibility
            rules (drafts are excluded from the public API by services).
        """
        await self.ensure_fresh()
        return list(self._cache.values())

    async def get_by_slug(self, slug: str) -> ParsedContent | None:
        """Return one item by slug or None when missing/invalid."""
        await self.ensure_fresh()
        return self._cache.get(slug)

    # Sync mechanics

    async def ensure_fresh(self) -> None:
        """Re-scan the content directory when it changed since the last check."""
        if self._reuse_recent_result():
            return
        async with self._lock:
            # Waiters on the first scan must see its completed cache or error,
            # never an empty cache presented as a successful response.
            if self._reuse_recent_result():
                return
            try:
                try:
                    signature = self._dir_signature()
                    items = self._scan() if signature != self._last_signature else None
                except OSError as error:
                    raise ContentRepositoryError(str(error)) from error
                if items is not None:
                    await self._sync_projection(items)
                    self._cache = items
                    self._last_signature = signature
            except (ContentRepositoryError, ContentItemRepositoryError) as error:
                self._last_error = error
                self._last_check = time.monotonic()
                logger.error(
                    "Content refresh failed for %s; keeping previous cache. Details: %s",
                    self._content_type,
                    error,
                )
                if self._last_signature is None:
                    raise
            else:
                self._last_error = None
                self._last_check = time.monotonic()

    def _reuse_recent_result(self) -> bool:
        """Reuse a completed scan, including a failed cold start, within TTL."""
        if self._last_check is None or time.monotonic() - self._last_check >= self._ttl_seconds:
            return False
        if self._last_signature is None and self._last_error is not None:
            raise self._last_error
        return True

    def _content_files(self) -> list[Path]:
        """Enumerate files without hiding a missing/unreadable directory."""
        return sorted(
            path for path in self._content_dir.iterdir()
            if path.suffix == ".md" and S_ISREG(path.stat().st_mode)
        )

    def _dir_signature(self) -> tuple[tuple[str, int, int, int], ...]:
        """Track every filename and timestamp, including non-newest edits."""
        signature = []
        for path in self._content_files():
            stat = path.stat()
            signature.append((path.name, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))
        return tuple(signature)

    def _scan(self) -> dict[str, ParsedContent]:
        """Parse and validate every Markdown file of the content type."""
        items: dict[str, ParsedContent] = {}
        for path in self._content_files():
            parsed = self._parse_file(path)
            if parsed is not None:
                items[parsed.slug] = parsed
        return items

    def _parse_file(self, path: Path) -> ParsedContent | None:
        """Parse one file; invalid files are logged and excluded."""
        slug = path.stem
        if not md.is_valid_slug(slug):
            logger.error("Invalid slug for %s file: %s", self._content_type, path.name)
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            data, body = md.parse_frontmatter(raw)
            frontmatter = self._frontmatter_model.model_validate(data)
        except (UnicodeDecodeError, md.MarkdownParseError, ValidationError) as error:
            logger.error(
                "Failed to parse %s file %s: %s", self._content_type, path.name, error
            )
            return None
        content_text = md.extract_plain_text(body)
        word_count = md.count_words(content_text)
        return ParsedContent(
            content_type=self._content_type,
            slug=slug,
            frontmatter=frontmatter,
            status=resolve_status(frontmatter),
            content_html=md.render_markdown(body),
            content_text=content_text,
            excerpt=md.extract_excerpt(body),
            word_count=word_count,
            reading_time=resolve_reading_time(
                frontmatter, word_count, self._words_per_minute
            ),
            content_hash=md.content_hash(raw),
        )

    async def _sync_projection(self, items: dict[str, ParsedContent]) -> None:
        """Sync the content_items projection in one transaction."""
        async with self._session_factory() as session:
            repository = ContentItemRepository(session)
            await repository.sync_type(self._content_type, list(items.values()))
